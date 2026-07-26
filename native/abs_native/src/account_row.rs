//! Typed Rocks account-row value codec (v1.3.147).
//!
//! New writes use a compact binary blob; reads accept binary **or** legacy JSON.
//! Soft industrial slice — not a full store rewrite / block blob migration.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_json::{Map, Number, Value};

pub const ACCOUNT_ROW_MAGIC: &[u8; 4] = b"ABAR";
pub const ACCOUNT_ROW_VERSION: u8 = 1;

fn read_u16(buf: &[u8], off: &mut usize) -> Option<u16> {
    let end = off.checked_add(2)?;
    let v = u16::from_le_bytes(buf.get(*off..end)?.try_into().ok()?);
    *off = end;
    Some(v)
}

fn read_u32(buf: &[u8], off: &mut usize) -> Option<u32> {
    let end = off.checked_add(4)?;
    let v = u32::from_le_bytes(buf.get(*off..end)?.try_into().ok()?);
    *off = end;
    Some(v)
}

fn read_u64(buf: &[u8], off: &mut usize) -> Option<u64> {
    let end = off.checked_add(8)?;
    let v = u64::from_le_bytes(buf.get(*off..end)?.try_into().ok()?);
    *off = end;
    Some(v)
}

fn read_i64(buf: &[u8], off: &mut usize) -> Option<i64> {
    let end = off.checked_add(8)?;
    let v = i64::from_le_bytes(buf.get(*off..end)?.try_into().ok()?);
    *off = end;
    Some(v)
}

fn read_f64(buf: &[u8], off: &mut usize) -> Option<f64> {
    let end = off.checked_add(8)?;
    let v = f64::from_le_bytes(buf.get(*off..end)?.try_into().ok()?);
    *off = end;
    Some(v)
}

fn read_bytes<'a>(buf: &'a [u8], off: &mut usize, n: usize) -> Option<&'a [u8]> {
    let end = off.checked_add(n)?;
    let slice = buf.get(*off..end)?;
    *off = end;
    Some(slice)
}

fn write_u16(out: &mut Vec<u8>, v: u16) {
    out.extend_from_slice(&v.to_le_bytes());
}
fn write_u32(out: &mut Vec<u8>, v: u32) {
    out.extend_from_slice(&v.to_le_bytes());
}
fn write_u64(out: &mut Vec<u8>, v: u64) {
    out.extend_from_slice(&v.to_le_bytes());
}
fn write_i64(out: &mut Vec<u8>, v: i64) {
    out.extend_from_slice(&v.to_le_bytes());
}
fn write_f64(out: &mut Vec<u8>, v: f64) {
    out.extend_from_slice(&v.to_le_bytes());
}

fn storage_canonical_string(storage: &Value) -> String {
    match storage {
        Value::Null => "{}".to_string(),
        Value::String(s) => {
            let t = s.trim();
            if t.is_empty() {
                "{}".to_string()
            } else {
                t.to_string()
            }
        }
        Value::Object(_) => serde_json::to_string(storage).unwrap_or_else(|_| "{}".to_string()),
        _ => "{}".to_string(),
    }
}

fn storage_entries_from_canonical(storage_s: &str) -> Vec<(i128, i128)> {
    let trimmed = storage_s.trim();
    if trimmed.is_empty() || trimmed == "{}" {
        return Vec::new();
    }
    let parsed: Value = match serde_json::from_str(trimmed) {
        Ok(v) => v,
        Err(_) => return Vec::new(),
    };
    let obj = match parsed {
        Value::Object(m) => m,
        _ => return Vec::new(),
    };
    let mut out = Vec::with_capacity(obj.len());
    for (k, v) in obj {
        let key = {
            let k = k.trim();
            if let Some(hex) = k.strip_prefix("0x").or_else(|| k.strip_prefix("0X")) {
                i128::from_str_radix(hex, 16).unwrap_or(0)
            } else {
                k.parse::<i128>().unwrap_or(0)
            }
        };
        let val = match v {
            Value::Number(n) => n
                .as_i64()
                .map(i128::from)
                .or_else(|| n.as_u64().map(i128::from))
                .or_else(|| n.as_f64().map(|f| f as i128))
                .unwrap_or(0),
            Value::String(s) => {
                let s = s.trim();
                if let Some(hex) = s.strip_prefix("0x").or_else(|| s.strip_prefix("0X")) {
                    i128::from_str_radix(hex, 16).unwrap_or(0)
                } else {
                    s.parse::<i128>().unwrap_or(0)
                }
            }
            Value::Bool(b) => i128::from(if b { 1 } else { 0 }),
            _ => 0,
        };
        out.push((key, val));
    }
    out.sort_by_key(|(k, _)| *k);
    out
}

fn write_i128(out: &mut Vec<u8>, v: i128) {
    out.extend_from_slice(&v.to_le_bytes());
}

fn read_i128(buf: &[u8], off: &mut usize) -> Option<i128> {
    let end = off.checked_add(16)?;
    let mut raw = [0u8; 16];
    raw.copy_from_slice(buf.get(*off..end)?);
    *off = end;
    Some(i128::from_le_bytes(raw))
}

/// Pack a JSON-shaped account object into ABAR binary.
pub fn pack_account_row_value(account: &Value) -> Result<Vec<u8>, String> {
    let obj = account
        .as_object()
        .ok_or_else(|| "account row must be an object".to_string())?;
    let address = obj
        .get("address")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .trim()
        .to_ascii_lowercase();
    if address.is_empty() {
        return Err("account row missing address".to_string());
    }
    if address.len() > u16::MAX as usize {
        return Err("address too long".to_string());
    }
    let balance_satoshi = obj
        .get("balance_satoshi")
        .and_then(|v| v.as_i64())
        .or_else(|| {
            obj.get("balance_satoshi")
                .and_then(|v| v.as_u64())
                .map(|u| u as i64)
        })
        .unwrap_or(0)
        .max(0);
    let nonce = obj
        .get("nonce")
        .and_then(|v| v.as_u64())
        .or_else(|| {
            obj.get("nonce")
                .and_then(|v| v.as_i64())
                .map(|i| i.max(0) as u64)
        })
        .unwrap_or(0);
    let balance = obj.get("balance").and_then(|v| v.as_f64()).unwrap_or(0.0);
    if !balance.is_finite() {
        return Err("account balance is not finite".to_string());
    }
    let code = obj
        .get("code")
        .and_then(|v| match v {
            Value::Null => Some(""),
            Value::String(s) => Some(s.as_str()),
            _ => None,
        })
        .unwrap_or("")
        .to_string();
    if code.len() > u32::MAX as usize {
        return Err("code too long".to_string());
    }
    let storage_s = storage_canonical_string(obj.get("storage").unwrap_or(&Value::Null));
    let entries = storage_entries_from_canonical(&storage_s);
    if entries.len() > u32::MAX as usize {
        return Err("storage too large".to_string());
    }

    let mut out = Vec::with_capacity(64 + address.len() + code.len() + entries.len() * 32);
    out.extend_from_slice(ACCOUNT_ROW_MAGIC);
    out.push(ACCOUNT_ROW_VERSION);
    out.push(0); // flags reserved
    write_i64(&mut out, balance_satoshi);
    write_u64(&mut out, nonce);
    write_f64(&mut out, balance);
    write_u16(&mut out, address.len() as u16);
    out.extend_from_slice(address.as_bytes());
    write_u32(&mut out, code.len() as u32);
    out.extend_from_slice(code.as_bytes());
    // Keep canonical storage string for tip-root hash parity (value_to_string path).
    if storage_s.len() > u32::MAX as usize {
        return Err("storage string too long".to_string());
    }
    write_u32(&mut out, storage_s.len() as u32);
    out.extend_from_slice(storage_s.as_bytes());
    // Typed slots (optional consumers); tip-root hashes storage string.
    write_u32(&mut out, entries.len() as u32);
    for (k, v) in entries {
        write_i128(&mut out, k);
        write_i128(&mut out, v);
    }
    Ok(out)
}

/// Unpack ABAR binary into a JSON object (same logical shape as legacy rows).
pub fn unpack_account_row_bytes(blob: &[u8]) -> Result<Value, String> {
    if blob.len() < 4 + 1 + 1 + 8 + 8 + 8 + 2 {
        return Err("account_row_too_short".to_string());
    }
    if &blob[0..4] != ACCOUNT_ROW_MAGIC {
        return Err("account_row_bad_magic".to_string());
    }
    let mut off = 4usize;
    let ver = *blob.get(off).ok_or("account_row_truncated")?;
    off += 1;
    if ver != ACCOUNT_ROW_VERSION {
        return Err(format!("account_row_bad_version:{ver}"));
    }
    let _flags = *blob.get(off).ok_or("account_row_truncated")?;
    off += 1;
    let balance_satoshi = read_i64(blob, &mut off).ok_or("account_row_truncated")?;
    let nonce = read_u64(blob, &mut off).ok_or("account_row_truncated")?;
    let balance = read_f64(blob, &mut off).ok_or("account_row_truncated")?;
    let addr_len = read_u16(blob, &mut off).ok_or("account_row_truncated")? as usize;
    let addr_bytes = read_bytes(blob, &mut off, addr_len).ok_or("account_row_truncated")?;
    let address = std::str::from_utf8(addr_bytes)
        .map_err(|_| "account_row_bad_address".to_string())?
        .to_ascii_lowercase();
    let code_len = read_u32(blob, &mut off).ok_or("account_row_truncated")? as usize;
    let code_bytes = read_bytes(blob, &mut off, code_len).ok_or("account_row_truncated")?;
    let code = std::str::from_utf8(code_bytes)
        .map_err(|_| "account_row_bad_code".to_string())?
        .to_string();
    let storage_len = read_u32(blob, &mut off).ok_or("account_row_truncated")? as usize;
    let storage_bytes = read_bytes(blob, &mut off, storage_len).ok_or("account_row_truncated")?;
    let storage_s = std::str::from_utf8(storage_bytes)
        .map_err(|_| "account_row_bad_storage".to_string())?
        .to_string();
    let entry_n = read_u32(blob, &mut off).ok_or("account_row_truncated")? as usize;
    for _ in 0..entry_n {
        let _k = read_i128(blob, &mut off).ok_or("account_row_truncated")?;
        let _v = read_i128(blob, &mut off).ok_or("account_row_truncated")?;
    }

    let mut map = Map::new();
    map.insert("address".into(), Value::String(address));
    map.insert(
        "balance_satoshi".into(),
        Value::Number(Number::from(balance_satoshi.max(0))),
    );
    map.insert("nonce".into(), Value::Number(Number::from(nonce)));
    map.insert(
        "balance".into(),
        Number::from_f64(balance)
            .map(Value::Number)
            .ok_or_else(|| "account balance is not finite".to_string())?,
    );
    if code.is_empty() {
        map.insert("code".into(), Value::Null);
    } else {
        map.insert("code".into(), Value::String(code));
    }
    map.insert("storage".into(), Value::String(storage_s));
    Ok(Value::Object(map))
}

/// Dual-decode: ABAR binary or legacy JSON object bytes.
pub fn account_blob_to_value(blob: &[u8]) -> Result<Value, String> {
    if blob.is_empty() {
        return Err("empty_account_blob".to_string());
    }
    if blob.len() >= 4 && &blob[0..4] == ACCOUNT_ROW_MAGIC {
        return unpack_account_row_bytes(blob);
    }
    serde_json::from_slice(blob).map_err(|e| format!("account_blob_json_invalid:{e}"))
}

pub fn is_account_row_binary(blob: &[u8]) -> bool {
    blob.len() >= 4 && &blob[0..4] == ACCOUNT_ROW_MAGIC
}

#[pyfunction]
#[pyo3(name = "pack_account_row")]
fn pack_account_row_py(account_json: &str) -> PyResult<PyObject> {
    Python::with_gil(|py| {
        let parsed: Value = serde_json::from_str(account_json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("account_json invalid: {e}"))
        })?;
        let blob =
            pack_account_row_value(&parsed).map_err(pyo3::exceptions::PyValueError::new_err)?;
        Ok(pyo3::types::PyBytes::new_bound(py, &blob).into())
    })
}

#[pyfunction]
#[pyo3(name = "unpack_account_row")]
fn unpack_account_row_py(py: Python<'_>, blob: &[u8]) -> PyResult<String> {
    let _ = py;
    let value = unpack_account_row_bytes(blob).map_err(pyo3::exceptions::PyValueError::new_err)?;
    serde_json::to_string(&value).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("account_row encode failed: {e}"))
    })
}

#[pyfunction]
#[pyo3(name = "account_blob_to_json")]
fn account_blob_to_json_py(blob: &[u8]) -> PyResult<String> {
    let value = account_blob_to_value(blob).map_err(pyo3::exceptions::PyValueError::new_err)?;
    serde_json::to_string(&value).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("account_blob encode failed: {e}"))
    })
}

#[pyfunction]
#[pyo3(name = "is_account_row_binary")]
fn is_account_row_binary_py(blob: &[u8]) -> bool {
    is_account_row_binary(blob)
}

#[pyfunction]
#[pyo3(name = "pack_account_row_dict")]
fn pack_account_row_dict_py(py: Python<'_>, row: &Bound<'_, PyDict>) -> PyResult<PyObject> {
    let json_mod = py.import_bound("json")?;
    let s: String = json_mod.call_method1("dumps", (row,))?.extract()?;
    let parsed: Value = serde_json::from_str(&s).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("account dict invalid: {e}"))
    })?;
    let blob = pack_account_row_value(&parsed).map_err(pyo3::exceptions::PyValueError::new_err)?;
    Ok(pyo3::types::PyBytes::new_bound(py, &blob).into())
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(pack_account_row_py, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_account_row_py, m)?)?;
    m.add_function(wrap_pyfunction!(account_blob_to_json_py, m)?)?;
    m.add_function(wrap_pyfunction!(is_account_row_binary_py, m)?)?;
    m.add_function(wrap_pyfunction!(pack_account_row_dict_py, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn roundtrip_eoa() {
        let row = json!({
            "address": "0xABC",
            "balance": 1.5,
            "balance_satoshi": 150_000_000,
            "nonce": 3,
            "code": null,
            "storage": "{}"
        });
        let blob = pack_account_row_value(&row).unwrap();
        assert!(is_account_row_binary(&blob));
        let back = unpack_account_row_bytes(&blob).unwrap();
        assert_eq!(back["address"], "0xabc");
        assert_eq!(back["nonce"], 3);
        assert_eq!(back["balance_satoshi"], 150_000_000);
    }

    #[test]
    fn dual_read_json() {
        let row = json!({"address":"0x11","balance":0.0,"balance_satoshi":0,"nonce":0,"code":null,"storage":"{}"});
        let blob = serde_json::to_vec(&row).unwrap();
        let v = account_blob_to_value(&blob).unwrap();
        assert_eq!(v["address"], "0x11");
    }
}
