//! RocksDB engine for Absolute chain storage (LSM, concurrent reads).

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use rocksdb::{
    BlockBasedOptions, Cache, Direction, IteratorMode, Options, WriteBatch, WriteOptions, DB,
};
use std::collections::HashMap;
use std::sync::Arc;

#[pyclass]
pub struct RocksWriteBatch {
    inner: WriteBatch,
}

#[pymethods]
impl RocksWriteBatch {
    #[new]
    fn new() -> Self {
        Self {
            inner: WriteBatch::default(),
        }
    }

    fn put(&mut self, key: &[u8], value: &[u8]) {
        self.inner.put(key, value);
    }

    fn delete(&mut self, key: &[u8]) {
        self.inner.delete(key);
    }

    fn clear(&mut self) {
        self.inner.clear();
    }

    fn len(&self) -> usize {
        self.inner.len()
    }
}

#[pyclass]
pub struct RocksEngine {
    db: Arc<DB>,
    sync_writes: bool,
    block_cache_mb: u32,
    write_buffer_mb: u32,
    _block_cache: Option<Arc<Cache>>,
}

const STORAGE_PROPERTY_KEYS: &[&str] = &[
    "rocksdb.estimate-num-keys",
    "rocksdb.cur-size-all-mem-tables",
    "rocksdb.estimate-table-readers-mem",
    "rocksdb.total-sst-files-size",
    "rocksdb.live-sst-files-size",
    "rocksdb.num-immutable-mem-table",
    "rocksdb.num-running-compactions",
    "rocksdb.num-running-flushes",
];

#[pymethods]
impl RocksEngine {
    #[new]
    #[pyo3(signature = (path, *, create_if_missing=true, sync_writes=false, block_cache_mb=0, write_buffer_mb=0, read_only=false))]
    fn new(
        path: &str,
        create_if_missing: bool,
        sync_writes: bool,
        block_cache_mb: u32,
        write_buffer_mb: u32,
        read_only: bool,
    ) -> PyResult<Self> {
        let mut opts = Options::default();
        opts.create_if_missing(create_if_missing);
        opts.create_missing_column_families(false);
        opts.set_max_open_files(512);
        opts.set_bytes_per_sync(1_048_576);
        opts.set_wal_bytes_per_sync(1_048_576);

        let mut block_cache = None;
        if block_cache_mb > 0 {
            let cache = Cache::new_lru_cache((block_cache_mb as usize) * 1024 * 1024);
            let mut block_opts = BlockBasedOptions::default();
            block_opts.set_block_cache(&cache);
            opts.set_block_based_table_factory(&block_opts);
            block_cache = Some(Arc::new(cache));
        }
        if write_buffer_mb > 0 {
            opts.set_write_buffer_size((write_buffer_mb as usize) * 1024 * 1024);
        }

        let db = if read_only {
            opts.create_if_missing(false);
            DB::open_for_read_only(&opts, path, false)
        } else {
            DB::open(&opts, path)
        }
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(e.to_string()))?;
        Ok(Self {
            db: Arc::new(db),
            sync_writes,
            block_cache_mb,
            write_buffer_mb,
            _block_cache: block_cache,
        })
    }

    fn get<'py>(&self, py: Python<'py>, key: &[u8]) -> PyResult<Option<Py<PyBytes>>> {
        match self.db.get(key).map_err(map_db_err)? {
            Some(value) => Ok(Some(PyBytes::new_bound(py, &value).unbind())),
            None => Ok(None),
        }
    }

    fn put(&self, key: &[u8], value: &[u8]) -> PyResult<()> {
        let mut write_opts = WriteOptions::default();
        write_opts.set_sync(self.sync_writes);
        self.db.put_opt(key, value, &write_opts).map_err(map_db_err)
    }

    fn delete(&self, key: &[u8]) -> PyResult<()> {
        let mut write_opts = WriteOptions::default();
        write_opts.set_sync(self.sync_writes);
        self.db.delete_opt(key, &write_opts).map_err(map_db_err)
    }

    fn write_batch(&self, batch: &mut RocksWriteBatch) -> PyResult<()> {
        let mut write_opts = WriteOptions::default();
        write_opts.set_sync(self.sync_writes);
        let data = std::mem::take(&mut batch.inner);
        self.db.write_opt(data, &write_opts).map_err(map_db_err)
    }

    #[pyo3(signature = (prefix, limit=10_000))]
    fn prefix_scan<'py>(
        &self,
        py: Python<'py>,
        prefix: &[u8],
        limit: usize,
    ) -> PyResult<Vec<(Py<PyBytes>, Py<PyBytes>)>> {
        let iter = self
            .db
            .iterator(IteratorMode::From(prefix, Direction::Forward));
        let mut out = Vec::new();
        for item in iter.take(limit) {
            let (key, value) = item.map_err(map_db_err)?;
            if !key.starts_with(prefix) {
                break;
            }
            out.push((
                PyBytes::new_bound(py, &key).unbind(),
                PyBytes::new_bound(py, &value).unbind(),
            ));
        }
        Ok(out)
    }

    fn checkpoint(&self, dest: &str) -> PyResult<()> {
        let checkpoint =
            rocksdb::checkpoint::Checkpoint::new(self.db.as_ref()).map_err(map_db_err)?;
        checkpoint.create_checkpoint(dest).map_err(map_db_err)
    }

    fn path(&self) -> PyResult<String> {
        Ok(self.db.path().to_str().unwrap_or("").to_string())
    }

    fn tuning_config(&self) -> PyResult<HashMap<String, u32>> {
        let mut out = HashMap::new();
        out.insert("block_cache_mb".to_string(), self.block_cache_mb);
        out.insert("write_buffer_mb".to_string(), self.write_buffer_mb);
        out.insert(
            "sync_writes".to_string(),
            if self.sync_writes { 1 } else { 0 },
        );
        Ok(out)
    }

    fn storage_properties<'py>(&self, py: Python<'py>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new_bound(py);
        for key in STORAGE_PROPERTY_KEYS {
            if let Ok(Some(value)) = self.db.property_value(*key) {
                dict.set_item(*key, value)?;
            }
        }
        Ok(dict.unbind())
    }

    #[pyo3(signature = (prefix, limit=100_000))]
    fn state_root_from_account_prefix(&self, prefix: &[u8], limit: usize) -> PyResult<String> {
        if limit > crate::MAX_STATE_ROOT_BLOBS {
            return Err(pyo3::exceptions::PyValueError::new_err(format!(
                "prefix_scan_limit_too_large: {} > {}",
                limit,
                crate::MAX_STATE_ROOT_BLOBS
            )));
        }
        let iter = self
            .db
            .iterator(IteratorMode::From(prefix, Direction::Forward));
        let mut values = Vec::new();
        for item in iter.take(limit) {
            let (key, value) = item.map_err(map_db_err)?;
            if !key.starts_with(prefix) {
                break;
            }
            if value.len() > crate::MAX_ACCOUNT_BLOB_BYTES {
                return Err(pyo3::exceptions::PyValueError::new_err(format!(
                    "account_blob_too_large: {} > {} bytes",
                    value.len(),
                    crate::MAX_ACCOUNT_BLOB_BYTES
                )));
            }
            values.push(value);
        }
        crate::state_trie::compute_state_root_from_account_blobs(values)
    }
}

fn map_db_err(err: rocksdb::Error) -> PyErr {
    PyErr::new::<pyo3::exceptions::PyOSError, _>(err.to_string())
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RocksEngine>()?;
    m.add_class::<RocksWriteBatch>()?;
    Ok(())
}
