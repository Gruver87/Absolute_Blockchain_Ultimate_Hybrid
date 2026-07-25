//! Account blob decode for nested CALL preload (v1.3.58).
//!
//! Fail-closed storage decode mirrors Python `_loads_contract_storage`.
//! Persist / CREATE remain on the Python DB path.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_json::Value;

fn json_int(v: &Value) -> Option<i128> {
    match v {
        Value::Number(n) => n
            .as_i64()
            .map(i128::from)
            .or_else(|| n.as_u64().map(i128::from))
            .or_else(|| n.as_f64().map(|f| f as i128)),
        Value::String(s) => {
            let s = s.trim();
            if let Some(hex) = s.strip_prefix("0x").or_else(|| s.strip_prefix("0X")) {
                i128::from_str_radix(hex, 16).ok()
            } else {
                s.parse::<i128>().ok()
            }
        }
        Value::Bool(b) => Some(if *b { 1 } else { 0 }),
        _ => None,
    }
}

fn storage_map_from_value(value: &Value) -> Option<Vec<(i128, i128)>> {
    let obj = match value {
        Value::Null => return Some(Vec::new()),
        Value::Object(map) => map,
        Value::String(s) => {
            let trimmed = s.trim();
            if trimmed.is_empty() {
                return Some(Vec::new());
            }
            let parsed: Value = serde_json::from_str(trimmed).ok()?;
            return storage_map_from_value(&parsed);
        }
        _ => return None,
    };
    let mut out = Vec::with_capacity(obj.len());
    for (k, v) in obj {
        let key = {
            let k = k.trim();
            if let Some(hex) = k.strip_prefix("0x").or_else(|| k.strip_prefix("0X")) {
                i128::from_str_radix(hex, 16).ok()?
            } else {
                k.parse::<i128>().ok()?
            }
        };
        let val = json_int(v)?;
        out.push((key, val));
    }
    Some(out)
}

fn code_bytes_from_hex(code: &str) -> Vec<u8> {
    let raw = code.trim().trim_start_matches("0x").trim_start_matches("0X");
    if raw.is_empty() {
        return Vec::new();
    }
    hex::decode(raw).unwrap_or_default()
}

fn empty_view(py: Python<'_>, address: &str) -> PyResult<PyObject> {
    let dict = PyDict::new_bound(py);
    dict.set_item("ok", true)?;
    dict.set_item("corrupt", false)?;
    dict.set_item("missing", true)?;
    dict.set_item("address", address)?;
    dict.set_item("balance_satoshi", 0i64)?;
    dict.set_item("nonce", 0u64)?;
    dict.set_item("code", "")?;
    dict.set_item("code_bytes", pyo3::types::PyBytes::new_bound(py, &[]))?;
    dict.set_item("storage", PyDict::new_bound(py))?;
    dict.set_item("native_account_view", true)?;
    Ok(dict.into())
}

fn view_from_json_value(py: Python<'_>, value: &Value, fallback_addr: &str) -> PyResult<PyObject> {
    let obj = match value {
        Value::Object(map) => map,
        _ => {
            let dict = PyDict::new_bound(py);
            dict.set_item("ok", false)?;
            dict.set_item("corrupt", true)?;
            dict.set_item("missing", false)?;
            dict.set_item("native_account_view", true)?;
            dict.set_item("error", "account_blob_not_object")?;
            return Ok(dict.into());
        }
    };

    let address = obj
        .get("address")
        .and_then(|v| v.as_str())
        .unwrap_or(fallback_addr)
        .to_string();

    let balance_satoshi = obj
        .get("balance_satoshi")
        .and_then(json_int)
        .or_else(|| obj.get("balance").and_then(json_int))
        .unwrap_or(0)
        .max(0) as i64;

    let nonce = obj
        .get("nonce")
        .and_then(json_int)
        .unwrap_or(0)
        .max(0) as u64;

    let code = obj
        .get("code")
        .and_then(|v| match v {
            Value::Null => Some(""),
            Value::String(s) => Some(s.as_str()),
            _ => None,
        })
        .unwrap_or("")
        .to_string();
    let code_bytes = code_bytes_from_hex(&code);

    let storage_val = obj.get("storage").cloned().unwrap_or(Value::Null);
    let Some(entries) = storage_map_from_value(&storage_val) else {
        let dict = PyDict::new_bound(py);
        dict.set_item("ok", false)?;
        dict.set_item("corrupt", true)?;
        dict.set_item("missing", false)?;
        dict.set_item("address", address)?;
        dict.set_item("native_account_view", true)?;
        dict.set_item("error", "corrupt_storage")?;
        return Ok(dict.into());
    };

    let storage = PyDict::new_bound(py);
    for (k, v) in entries {
        storage.set_item(k, v)?;
    }

    let dict = PyDict::new_bound(py);
    dict.set_item("ok", true)?;
    dict.set_item("corrupt", false)?;
    dict.set_item("missing", false)?;
    dict.set_item("address", address)?;
    dict.set_item("balance_satoshi", balance_satoshi)?;
    dict.set_item("nonce", nonce)?;
    dict.set_item("code", code)?;
    dict.set_item(
        "code_bytes",
        pyo3::types::PyBytes::new_bound(py, &code_bytes),
    )?;
    dict.set_item("storage", storage)?;
    dict.set_item("native_account_view", true)?;
    Ok(dict.into())
}

/// Decode contract storage JSON/dict → `{slot: value}` or `None` if corrupt.
#[pyfunction]
#[pyo3(name = "account_storage_map_from_raw")]
#[pyo3(signature = (raw=None))]
pub fn account_storage_map_from_raw_py(
    py: Python<'_>,
    raw: Option<&Bound<'_, PyAny>>,
) -> PyResult<Option<PyObject>> {
    let Some(raw) = raw else {
        return Ok(Some(PyDict::new_bound(py).into()));
    };
    if raw.is_none() {
        return Ok(Some(PyDict::new_bound(py).into()));
    }
    if let Ok(dict) = raw.downcast::<PyDict>() {
        let mut entries = Vec::new();
        for (k, v) in dict.iter() {
            let key = if let Ok(i) = k.extract::<i128>() {
                i
            } else if let Ok(s) = k.extract::<String>() {
                let s = s.trim();
                if let Some(hex) = s.strip_prefix("0x").or_else(|| s.strip_prefix("0X")) {
                    match i128::from_str_radix(hex, 16) {
                        Ok(v) => v,
                        Err(_) => return Ok(None),
                    }
                } else {
                    match s.parse::<i128>() {
                        Ok(v) => v,
                        Err(_) => return Ok(None),
                    }
                }
            } else {
                return Ok(None);
            };
            let val = if let Ok(i) = v.extract::<i128>() {
                i
            } else if let Ok(s) = v.extract::<String>() {
                match json_int(&Value::String(s)) {
                    Some(n) => n,
                    None => return Ok(None),
                }
            } else {
                return Ok(None);
            };
            entries.push((key, val));
        }
        let out = PyDict::new_bound(py);
        for (k, v) in entries {
            out.set_item(k, v)?;
        }
        return Ok(Some(out.into()));
    }
    if let Ok(s) = raw.extract::<String>() {
        let trimmed = s.trim();
        if trimmed.is_empty() {
            return Ok(Some(PyDict::new_bound(py).into()));
        }
        let parsed: Value = match serde_json::from_str(trimmed) {
            Ok(v) => v,
            Err(_) => return Ok(None),
        };
        return match storage_map_from_value(&parsed) {
            Some(entries) => {
                let out = PyDict::new_bound(py);
                for (k, v) in entries {
                    out.set_item(k, v)?;
                }
                Ok(Some(out.into()))
            }
            None => Ok(None),
        };
    }
    if let Ok(bytes) = raw.extract::<Vec<u8>>() {
        if bytes.is_empty() {
            return Ok(Some(PyDict::new_bound(py).into()));
        }
        let parsed: Value = match serde_json::from_slice(&bytes) {
            Ok(v) => v,
            Err(_) => return Ok(None),
        };
        return match storage_map_from_value(&parsed) {
            Some(entries) => {
                let out = PyDict::new_bound(py);
                for (k, v) in entries {
                    out.set_item(k, v)?;
                }
                Ok(Some(out.into()))
            }
            None => Ok(None),
        };
    }
    Ok(None)
}

/// Decode a full Rocks/SQLite account JSON blob into a structured view.
#[pyfunction]
#[pyo3(name = "account_view_from_blob")]
pub fn account_view_from_blob_py(py: Python<'_>, blob: &[u8]) -> PyResult<PyObject> {
    if blob.is_empty() {
        return empty_view(py, "");
    }
    let parsed: Value = match serde_json::from_slice(blob) {
        Ok(v) => v,
        Err(_) => {
            let dict = PyDict::new_bound(py);
            dict.set_item("ok", false)?;
            dict.set_item("corrupt", true)?;
            dict.set_item("missing", false)?;
            dict.set_item("native_account_view", true)?;
            dict.set_item("error", "account_blob_json_invalid")?;
            return Ok(dict.into());
        }
    };
    view_from_json_value(py, &parsed, "")
}

/// Decode from account-row JSON string (same shape as DB row dump).
#[pyfunction]
#[pyo3(name = "account_view_from_json")]
pub fn account_view_from_json_py(py: Python<'_>, account_json: &str) -> PyResult<PyObject> {
    let trimmed = account_json.trim();
    if trimmed.is_empty() {
        return empty_view(py, "");
    }
    let parsed: Value = match serde_json::from_str(trimmed) {
        Ok(v) => v,
        Err(_) => {
            let dict = PyDict::new_bound(py);
            dict.set_item("ok", false)?;
            dict.set_item("corrupt", true)?;
            dict.set_item("native_account_view", true)?;
            dict.set_item("error", "account_json_invalid")?;
            return Ok(dict.into());
        }
    };
    view_from_json_value(py, &parsed, "")
}

pub fn decode_account_view_bytes(py: Python<'_>, blob: &[u8], address: &str) -> PyResult<PyObject> {
    if blob.is_empty() {
        return empty_view(py, address);
    }
    let parsed: Value = match serde_json::from_slice(blob) {
        Ok(v) => v,
        Err(_) => {
            let dict = PyDict::new_bound(py);
            dict.set_item("ok", false)?;
            dict.set_item("corrupt", true)?;
            dict.set_item("missing", false)?;
            dict.set_item("address", address)?;
            dict.set_item("native_account_view", true)?;
            dict.set_item("error", "account_blob_json_invalid")?;
            return Ok(dict.into());
        }
    };
    view_from_json_value(py, &parsed, address)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(account_storage_map_from_raw_py, m)?)?;
    m.add_function(wrap_pyfunction!(account_view_from_blob_py, m)?)?;
    m.add_function(wrap_pyfunction!(account_view_from_json_py, m)?)?;
    Ok(())
}
