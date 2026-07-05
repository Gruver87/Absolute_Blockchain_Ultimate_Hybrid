//! Incremental in-memory account map for canonical state root (same hash as batch scan).

use pyo3::prelude::*;
use serde_json::Value;
use std::collections::BTreeMap;

use crate::{account_payload_row, hash_string, value_to_string};

#[pyclass]
pub struct StateRootAccumulator {
    accounts: BTreeMap<String, Value>,
}

#[pymethods]
impl StateRootAccumulator {
    #[new]
    fn new() -> Self {
        Self {
            accounts: BTreeMap::new(),
        }
    }

    fn clear(&mut self) -> PyResult<()> {
        self.accounts.clear();
        Ok(())
    }

    fn len(&self) -> usize {
        self.accounts.len()
    }

    fn upsert_account_json(&mut self, account_json: &str) -> PyResult<()> {
        let account: Value = serde_json::from_str(account_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let obj = account.as_object().ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("account_json must be an object")
        })?;
        let addr = value_to_string(obj.get("address"), "");
        if addr.is_empty() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "account_json missing address",
            ));
        }
        self.accounts.insert(addr, account);
        Ok(())
    }

    fn remove_account(&mut self, address: &str) -> PyResult<()> {
        self.accounts.remove(&address.trim().to_lowercase());
        Ok(())
    }

    fn root(&self) -> PyResult<String> {
        let mut payload = Vec::with_capacity(self.accounts.len());
        for account in self.accounts.values() {
            payload.push(account_payload_row(account)?);
        }
        let encoded = serde_json::to_string(&payload)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(hash_string(&encoded))
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<StateRootAccumulator>()?;
    Ok(())
}
