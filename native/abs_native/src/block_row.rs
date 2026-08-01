//! Typed Rocks block-row value codec (v1.3.149).
//!
//! Header scalars are packed binary; nested `transactions` stay length-prefixed JSON
//! so replay/open-schema fields survive. Reads accept ABLK **or** legacy JSON.
//! Soft industrial slice — not full Rocks rewrite / tip proof.

use pyo3::prelude::*;
use serde_json::{Map, Number, Value};

pub const BLOCK_ROW_MAGIC: &[u8; 4] = b"ABLK";
pub const BLOCK_ROW_VERSION: u8 = 1;

const TYPED_KEYS: &[&str] = &[
    "height",
    "number",
    "hash",
    "block_hash",
    "parent_hash",
    "miner",
    "proposer",
    "timestamp",
    "tx_count",
    "gas_used",
    "total_burned",
    "extra_data",
    "state_root",
    "tx_root",
    "transactions",
];

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
fn write_f64(out: &mut Vec<u8>, v: f64) {
    out.extend_from_slice(&v.to_le_bytes());
}

fn json_string(obj: &Map<String, Value>, keys: &[&str]) -> String {
    for k in keys {
        if let Some(v) = obj.get(*k) {
            match v {
                Value::Null => return String::new(),
                Value::String(s) => return s.clone(),
                other => return other.to_string(),
            }
        }
    }
    String::new()
}

fn json_u64(obj: &Map<String, Value>, keys: &[&str], default: u64) -> u64 {
    for k in keys {
        if let Some(v) = obj.get(*k) {
            match v {
                Value::Number(n) => {
                    if let Some(u) = n.as_u64() {
                        return u;
                    }
                    if let Some(i) = n.as_i64() {
                        return i.max(0) as u64;
                    }
                    if let Some(f) = n.as_f64() {
                        return if f.is_finite() && f > 0.0 {
                            f as u64
                        } else {
                            0
                        };
                    }
                }
                Value::String(s) => {
                    if let Ok(u) = s.trim().parse::<u64>() {
                        return u;
                    }
                }
                _ => {}
            }
        }
    }
    default
}

fn json_f64(obj: &Map<String, Value>, keys: &[&str], default: f64) -> Result<f64, String> {
    for k in keys {
        if let Some(v) = obj.get(*k) {
            match v {
                Value::Number(n) => {
                    if let Some(f) = n.as_f64() {
                        if !f.is_finite() {
                            return Err(format!("block field {k} is not finite"));
                        }
                        return Ok(f);
                    }
                }
                Value::String(s) => {
                    let f: f64 = s.trim().parse().unwrap_or(default);
                    if !f.is_finite() {
                        return Err(format!("block field {k} is not finite"));
                    }
                    return Ok(f);
                }
                Value::Null => return Ok(default),
                _ => {}
            }
        }
    }
    Ok(default)
}

fn write_len_str(out: &mut Vec<u8>, s: &str, max_u16: bool) -> Result<(), String> {
    if max_u16 {
        if s.len() > u16::MAX as usize {
            return Err("string too long for u16".to_string());
        }
        write_u16(out, s.len() as u16);
    } else {
        if s.len() > u32::MAX as usize {
            return Err("string too long for u32".to_string());
        }
        write_u32(out, s.len() as u32);
    }
    out.extend_from_slice(s.as_bytes());
    Ok(())
}

fn read_len_str(buf: &[u8], off: &mut usize, max_u16: bool) -> Result<String, String> {
    let len = if max_u16 {
        read_u16(buf, off).ok_or("block_row_truncated")? as usize
    } else {
        read_u32(buf, off).ok_or("block_row_truncated")? as usize
    };
    let bytes = read_bytes(buf, off, len).ok_or("block_row_truncated")?;
    std::str::from_utf8(bytes)
        .map(|s| s.to_string())
        .map_err(|_| "block_row_bad_utf8".to_string())
}

fn write_len_bytes(out: &mut Vec<u8>, bytes: &[u8]) -> Result<(), String> {
    if bytes.len() > u32::MAX as usize {
        return Err("blob too long".to_string());
    }
    write_u32(out, bytes.len() as u32);
    out.extend_from_slice(bytes);
    Ok(())
}

fn read_len_bytes<'a>(buf: &'a [u8], off: &mut usize) -> Result<&'a [u8], String> {
    let len = read_u32(buf, off).ok_or("block_row_truncated")? as usize;
    read_bytes(buf, off, len).ok_or_else(|| "block_row_truncated".to_string())
}

fn transactions_json_bytes(obj: &Map<String, Value>) -> Result<Vec<u8>, String> {
    match obj.get("transactions") {
        None | Some(Value::Null) => Ok(b"[]".to_vec()),
        Some(Value::Array(_)) | Some(Value::Object(_)) | Some(Value::String(_)) => {
            let v = obj
                .get("transactions")
                .cloned()
                .unwrap_or(Value::Array(vec![]));
            // Normalize stringified JSON arrays.
            let normalized = match v {
                Value::String(s) => {
                    let t = s.trim();
                    if t.is_empty() {
                        Value::Array(vec![])
                    } else {
                        serde_json::from_str(t).unwrap_or(Value::Array(vec![]))
                    }
                }
                other => other,
            };
            serde_json::to_vec(&normalized).map_err(|e| format!("transactions encode: {e}"))
        }
        Some(_) => Ok(b"[]".to_vec()),
    }
}

fn extras_json_bytes(obj: &Map<String, Value>) -> Result<Vec<u8>, String> {
    let mut extras = Map::new();
    for (k, v) in obj {
        if TYPED_KEYS.iter().any(|t| *t == k.as_str()) {
            continue;
        }
        extras.insert(k.clone(), v.clone());
    }
    if extras.is_empty() {
        return Ok(b"{}".to_vec());
    }
    serde_json::to_vec(&Value::Object(extras)).map_err(|e| format!("extras encode: {e}"))
}

/// Pack a JSON-shaped block object into ABLK binary.
pub fn pack_block_row_value(block: &Value) -> Result<Vec<u8>, String> {
    let obj = block
        .as_object()
        .ok_or_else(|| "block row must be an object".to_string())?;
    let height = json_u64(obj, &["height", "number"], 0);
    let hash = json_string(obj, &["hash", "block_hash"]).trim().to_string();
    let parent_hash = json_string(obj, &["parent_hash"]).trim().to_string();
    let miner = json_string(obj, &["miner", "proposer"])
        .trim()
        .to_ascii_lowercase();
    let timestamp = json_u64(obj, &["timestamp"], 0);
    let tx_json = transactions_json_bytes(obj)?;
    let tx_count = {
        let explicit = json_u64(obj, &["tx_count"], u64::MAX);
        if explicit != u64::MAX {
            explicit
        } else {
            match serde_json::from_slice::<Value>(&tx_json) {
                Ok(Value::Array(a)) => a.len() as u64,
                _ => 0,
            }
        }
    };
    let gas_used = json_u64(obj, &["gas_used"], 0);
    let total_burned = json_f64(obj, &["total_burned"], 0.0)?;
    let extra_data = json_string(obj, &["extra_data"]);
    let state_root = json_string(obj, &["state_root"]).trim().to_string();
    let tx_root = json_string(obj, &["tx_root"]).trim().to_string();
    let extras = extras_json_bytes(obj)?;

    let mut out = Vec::with_capacity(
        64 + hash.len()
            + parent_hash.len()
            + miner.len()
            + extra_data.len()
            + state_root.len()
            + tx_root.len()
            + tx_json.len()
            + extras.len(),
    );
    out.extend_from_slice(BLOCK_ROW_MAGIC);
    out.push(BLOCK_ROW_VERSION);
    out.push(0); // flags reserved
    write_u64(&mut out, height);
    write_len_str(&mut out, &hash, true)?;
    write_len_str(&mut out, &parent_hash, true)?;
    write_len_str(&mut out, &miner, true)?;
    write_u64(&mut out, timestamp);
    write_u64(&mut out, tx_count);
    write_u64(&mut out, gas_used);
    write_f64(&mut out, total_burned);
    write_len_str(&mut out, &extra_data, false)?;
    write_len_str(&mut out, &state_root, true)?;
    write_len_str(&mut out, &tx_root, true)?;
    write_len_bytes(&mut out, &tx_json)?;
    write_len_bytes(&mut out, &extras)?;
    Ok(out)
}

/// Unpack ABLK binary into a JSON object (same logical shape as legacy rows).
pub fn unpack_block_row_bytes(blob: &[u8]) -> Result<Value, String> {
    if blob.len() < 4 + 1 + 1 + 8 {
        return Err("block_row_too_short".to_string());
    }
    if &blob[0..4] != BLOCK_ROW_MAGIC {
        return Err("block_row_bad_magic".to_string());
    }
    let mut off = 4usize;
    let ver = *blob.get(off).ok_or("block_row_truncated")?;
    off += 1;
    if ver != BLOCK_ROW_VERSION {
        return Err(format!("block_row_bad_version:{ver}"));
    }
    let _flags = *blob.get(off).ok_or("block_row_truncated")?;
    off += 1;

    let height = read_u64(blob, &mut off).ok_or("block_row_truncated")?;
    let hash = read_len_str(blob, &mut off, true)?;
    let parent_hash = read_len_str(blob, &mut off, true)?;
    let miner = read_len_str(blob, &mut off, true)?;
    let timestamp = read_u64(blob, &mut off).ok_or("block_row_truncated")?;
    let tx_count = read_u64(blob, &mut off).ok_or("block_row_truncated")?;
    let gas_used = read_u64(blob, &mut off).ok_or("block_row_truncated")?;
    let total_burned = read_f64(blob, &mut off).ok_or("block_row_truncated")?;
    let extra_data = read_len_str(blob, &mut off, false)?;
    let state_root = read_len_str(blob, &mut off, true)?;
    let tx_root = read_len_str(blob, &mut off, true)?;
    let tx_bytes = read_len_bytes(blob, &mut off)?;
    let extras_bytes = read_len_bytes(blob, &mut off)?;

    if !total_burned.is_finite() {
        return Err("block_row_non_finite".to_string());
    }

    let transactions: Value =
        serde_json::from_slice(tx_bytes).map_err(|e| format!("block_row_bad_transactions:{e}"))?;
    let extras: Value = if extras_bytes.is_empty() {
        Value::Object(Map::new())
    } else {
        serde_json::from_slice(extras_bytes).map_err(|e| format!("block_row_bad_extras:{e}"))?
    };

    let mut map = Map::new();
    if let Value::Object(extra_map) = extras {
        for (k, v) in extra_map {
            map.insert(k, v);
        }
    }
    map.insert("height".into(), Value::Number(Number::from(height)));
    map.insert("hash".into(), Value::String(hash));
    map.insert("parent_hash".into(), Value::String(parent_hash));
    map.insert("miner".into(), Value::String(miner));
    map.insert("timestamp".into(), Value::Number(Number::from(timestamp)));
    map.insert("tx_count".into(), Value::Number(Number::from(tx_count)));
    map.insert("gas_used".into(), Value::Number(Number::from(gas_used)));
    map.insert(
        "total_burned".into(),
        Number::from_f64(total_burned)
            .map(Value::Number)
            .ok_or_else(|| "total_burned is not finite".to_string())?,
    );
    map.insert("extra_data".into(), Value::String(extra_data));
    map.insert("state_root".into(), Value::String(state_root));
    map.insert("tx_root".into(), Value::String(tx_root));
    map.insert("transactions".into(), transactions);
    Ok(Value::Object(map))
}

/// Dual-decode: ABLK binary or legacy JSON object bytes.
pub fn block_blob_to_value(blob: &[u8]) -> Result<Value, String> {
    if blob.is_empty() {
        return Err("empty_block_blob".to_string());
    }
    if blob.len() >= 4 && &blob[0..4] == BLOCK_ROW_MAGIC {
        return unpack_block_row_bytes(blob);
    }
    serde_json::from_slice(blob).map_err(|e| format!("block_blob_json_invalid:{e}"))
}

pub fn is_block_row_binary(blob: &[u8]) -> bool {
    blob.len() >= 4 && &blob[0..4] == BLOCK_ROW_MAGIC
}

#[pyfunction]
#[pyo3(name = "pack_block_row")]
fn pack_block_row_py(block_json: &str) -> PyResult<PyObject> {
    Python::with_gil(|py| {
        let parsed: Value = serde_json::from_str(block_json).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!("block_json invalid: {e}"))
        })?;
        let blob =
            pack_block_row_value(&parsed).map_err(pyo3::exceptions::PyValueError::new_err)?;
        Ok(pyo3::types::PyBytes::new_bound(py, &blob).into())
    })
}

#[pyfunction]
#[pyo3(name = "unpack_block_row")]
fn unpack_block_row_py(py: Python<'_>, blob: &[u8]) -> PyResult<String> {
    let _ = py;
    let value = unpack_block_row_bytes(blob).map_err(pyo3::exceptions::PyValueError::new_err)?;
    serde_json::to_string(&value).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("block_row encode failed: {e}"))
    })
}

#[pyfunction]
#[pyo3(name = "block_blob_to_json")]
fn block_blob_to_json_py(blob: &[u8]) -> PyResult<String> {
    let value = block_blob_to_value(blob).map_err(pyo3::exceptions::PyValueError::new_err)?;
    serde_json::to_string(&value).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("block_blob encode failed: {e}"))
    })
}

#[pyfunction]
#[pyo3(name = "is_block_row_binary")]
fn is_block_row_binary_py(blob: &[u8]) -> bool {
    is_block_row_binary(blob)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(pack_block_row_py, m)?)?;
    m.add_function(wrap_pyfunction!(unpack_block_row_py, m)?)?;
    m.add_function(wrap_pyfunction!(block_blob_to_json_py, m)?)?;
    m.add_function(wrap_pyfunction!(is_block_row_binary_py, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn roundtrip_block() {
        let state_root = "aa".repeat(32);
        let tx_root = "bb".repeat(32);
        let row = json!({
            "height": 7,
            "hash": "0xabc",
            "parent_hash": "0xparent",
            "miner": "0xMiner",
            "timestamp": 100,
            "tx_count": 1,
            "gas_used": 21000,
            "total_burned": 0.5,
            "extra_data": "",
            "state_root": state_root,
            "tx_root": tx_root,
            "transactions": [{"hash":"0x1","from":"0xa","to":"0xb","amount":1.0}],
            "custom_flag": true
        });
        let blob = pack_block_row_value(&row).unwrap();
        assert!(is_block_row_binary(&blob));
        let back = unpack_block_row_bytes(&blob).unwrap();
        assert_eq!(back["height"], 7);
        assert_eq!(back["miner"], "0xminer");
        assert_eq!(back["custom_flag"], true);
        assert!(back["transactions"].as_array().unwrap().len() == 1);
    }

    #[test]
    fn dual_read_json() {
        let row = json!({"height":1,"hash":"0x1","parent_hash":"0x0","miner":"genesis","timestamp":1,"transactions":[]});
        let blob = serde_json::to_vec(&row).unwrap();
        let v = block_blob_to_value(&blob).unwrap();
        assert_eq!(v["height"], 1);
    }
}
