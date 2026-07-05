//! RocksDB engine for Absolute chain storage (LSM, concurrent reads).

use pyo3::prelude::*;
use pyo3::types::PyBytes;
use rocksdb::{Direction, IteratorMode, Options, WriteBatch, WriteOptions, DB};
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
}

#[pymethods]
impl RocksEngine {
    #[new]
    #[pyo3(signature = (path, *, create_if_missing=true, sync_writes=false))]
    fn new(path: &str, create_if_missing: bool, sync_writes: bool) -> PyResult<Self> {
        let mut opts = Options::default();
        opts.create_if_missing(create_if_missing);
        opts.create_missing_column_families(false);
        opts.set_max_open_files(512);
        opts.set_bytes_per_sync(1_048_576);
        opts.set_wal_bytes_per_sync(1_048_576);
        let db = DB::open(&opts, path).map_err(|e| PyErr::new::<pyo3::exceptions::PyOSError, _>(e.to_string()))?;
        Ok(Self {
            db: Arc::new(db),
            sync_writes,
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
        self.db
            .put_opt(key, value, &write_opts)
            .map_err(map_db_err)
    }

    fn delete(&self, key: &[u8]) -> PyResult<()> {
        let mut write_opts = WriteOptions::default();
        write_opts.set_sync(self.sync_writes);
        self.db
            .delete_opt(key, &write_opts)
            .map_err(map_db_err)
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
        let iter = self.db.iterator(IteratorMode::From(prefix, Direction::Forward));
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
        let checkpoint = rocksdb::checkpoint::Checkpoint::new(self.db.as_ref()).map_err(map_db_err)?;
        checkpoint
            .create_checkpoint(dest)
            .map_err(map_db_err)
    }

    fn path(&self) -> PyResult<String> {
        Ok(self
            .db
            .path()
            .to_str()
            .unwrap_or("")
            .to_string())
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
