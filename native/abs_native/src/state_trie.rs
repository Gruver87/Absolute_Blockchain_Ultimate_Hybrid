//! Incremental in-memory account map for canonical state root (same hash as batch scan).

use pyo3::prelude::*;
use serde_json::Value;
use std::collections::BTreeMap;

use crate::{account_payload_row, hash_string, value_to_string};

/// Sorted payload rows keyed by account address (`a` field order == BTree key order).
#[pyclass]
pub struct StateRootAccumulator {
    rows: BTreeMap<String, Value>,
}

#[pymethods]
impl StateRootAccumulator {
    #[new]
    fn new() -> Self {
        Self {
            rows: BTreeMap::new(),
        }
    }

    fn clear(&mut self) -> PyResult<()> {
        self.rows.clear();
        Ok(())
    }

    fn len(&self) -> usize {
        self.rows.len()
    }

    fn upsert_account_json(&mut self, account_json: &str) -> PyResult<()> {
        let account: Value = serde_json::from_str(account_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        self.upsert_account_value(account)
    }

    fn upsert_account_blob(&mut self, blob: &[u8]) -> PyResult<()> {
        let account: Value = serde_json::from_slice(blob)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        self.upsert_account_value(account)
    }

    fn load_from_blobs(&mut self, blobs: Vec<Vec<u8>>) -> PyResult<()> {
        self.rows.clear();
        for blob in blobs {
            self.upsert_account_blob(&blob)?;
        }
        Ok(())
    }

    fn remove_account(&mut self, address: &str) -> PyResult<()> {
        self.rows.remove(&address.trim().to_lowercase());
        Ok(())
    }

    fn root(&self) -> PyResult<String> {
        let payload: Vec<&Value> = self.rows.values().collect();
        let encoded = serde_json::to_string(&payload)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(hash_string(&encoded))
    }
}

impl StateRootAccumulator {
    fn upsert_account_value(&mut self, account: Value) -> PyResult<()> {
        let row = account_payload_row(&account)?;
        let addr = value_to_string(row.get("a"), "");
        if addr.is_empty() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "account row missing address",
            ));
        }
        self.rows.insert(addr, row);
        Ok(())
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<StateRootAccumulator>()?;
    Ok(())
}
