//! Fail-closed P2P wire envelope parse/encode (newline-delimited JSON).

use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde_json::Value;
use std::collections::HashSet;

pub(crate) const DEFAULT_MAX_P2P_LINE_BYTES: usize = 2 * 1024 * 1024;
pub(crate) const MIN_P2P_LINE_BYTES: usize = 4096;
pub(crate) const MAX_P2P_LINE_BYTES: usize = 16 * 1024 * 1024;
pub(crate) const MAX_P2P_TYPE_LEN: usize = 64;

fn clamp_max_bytes(max_bytes: usize) -> usize {
    max_bytes.clamp(MIN_P2P_LINE_BYTES, MAX_P2P_LINE_BYTES)
}

fn parse_p2p_wire_line_inner(
    line: &[u8],
    max_bytes: usize,
    allowed_types: Option<&HashSet<String>>,
) -> Result<(String, Value), String> {
    let limit = clamp_max_bytes(max_bytes);
    if line.len() > limit {
        return Err(format!(
            "p2p_line_too_large: {} > {} bytes",
            line.len(),
            limit
        ));
    }
    let text = std::str::from_utf8(line)
        .map_err(|_| "p2p_line_not_utf8".to_string())?
        .trim()
        .trim_end_matches('\0');
    if text.is_empty() {
        return Err("p2p_line_empty".to_string());
    }
    let value: Value =
        serde_json::from_str(text).map_err(|e| format!("p2p_json_invalid: {e}"))?;
    let obj = value
        .as_object()
        .ok_or_else(|| "p2p_envelope_not_object".to_string())?;
    let msg_type = obj
        .get("type")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "p2p_type_missing_or_not_string".to_string())?;
    if msg_type.is_empty() || msg_type.len() > MAX_P2P_TYPE_LEN {
        return Err("p2p_type_invalid".to_string());
    }
    if let Some(allowed) = allowed_types {
        if !allowed.is_empty() && !allowed.contains(msg_type) {
            return Err(format!("p2p_type_not_allowed: {msg_type}"));
        }
    }
    let data = obj.get("data").cloned().unwrap_or(Value::Null);
    Ok((msg_type.to_string(), data))
}

fn encode_p2p_wire_message_inner(msg_type: &str, data_json: &str) -> Result<Vec<u8>, String> {
    if msg_type.is_empty() || msg_type.len() > MAX_P2P_TYPE_LEN {
        return Err("p2p_type_invalid".to_string());
    }
    let data: Value = if data_json.trim().is_empty() {
        Value::Null
    } else {
        serde_json::from_str(data_json).map_err(|e| format!("p2p_data_json_invalid: {e}"))?
    };
    let mut envelope = serde_json::Map::new();
    envelope.insert("type".to_string(), Value::String(msg_type.to_string()));
    envelope.insert("data".to_string(), data);
    let mut encoded = serde_json::to_string(&Value::Object(envelope))
        .map_err(|e| format!("p2p_encode_failed: {e}"))?;
    encoded.push('\n');
    let bytes = encoded.into_bytes();
    if bytes.len() > MAX_P2P_LINE_BYTES {
        return Err(format!(
            "p2p_line_too_large: {} > {} bytes",
            bytes.len(),
            MAX_P2P_LINE_BYTES
        ));
    }
    Ok(bytes)
}

#[pyfunction]
#[pyo3(signature = (line, max_bytes=DEFAULT_MAX_P2P_LINE_BYTES, allowed_types=None))]
fn parse_p2p_wire_line(
    py: Python<'_>,
    line: &[u8],
    max_bytes: usize,
    allowed_types: Option<Vec<String>>,
) -> PyResult<Option<PyObject>> {
    let allowed_set = allowed_types.map(|items| items.into_iter().collect::<HashSet<_>>());
    match parse_p2p_wire_line_inner(line, max_bytes, allowed_set.as_ref()) {
        Ok((msg_type, data)) => {
            let dict = PyDict::new_bound(py);
            dict.set_item("type", msg_type)?;
            let data_json = serde_json::to_string(&data)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
            let data_obj = pyo3::types::PyModule::import_bound(py, "json")?
                .getattr("loads")?
                .call1((data_json,))?;
            dict.set_item("data", data_obj)?;
            Ok(Some(dict.into_any().unbind()))
        }
        Err(err) if err.starts_with("p2p_line_too_large") => {
            Err(pyo3::exceptions::PyValueError::new_err(err))
        }
        Err(_) => Ok(None),
    }
}

#[pyfunction]
fn encode_p2p_wire_message(msg_type: String, data_json: String) -> PyResult<Vec<u8>> {
    encode_p2p_wire_message_inner(&msg_type, &data_json)
        .map_err(pyo3::exceptions::PyValueError::new_err)
}

#[pyfunction]
fn hash_sorted_json(obj_json: String) -> PyResult<String> {
    let value: Value = serde_json::from_str(&obj_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let encoded = sorted_compact_json(&value)?;
    Ok(crate::hash_string(&encoded))
}

fn sorted_compact_json(value: &Value) -> PyResult<String> {
    let sorted = sort_keys_value(value);
    serde_json::to_string(&sorted)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

fn sort_keys_value(value: &Value) -> Value {
    match value {
        Value::Object(map) => {
            let mut sorted = serde_json::Map::new();
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            for key in keys {
                if let Some(item) = map.get(key) {
                    sorted.insert(key.clone(), sort_keys_value(item));
                }
            }
            Value::Object(sorted)
        }
        Value::Array(items) => Value::Array(items.iter().map(sort_keys_value).collect()),
        other => other.clone(),
    }
}

#[pyfunction]
fn verify_attestation_secp256k1(
    attestation_json: String,
    signature_der: Vec<u8>,
    public_key_xy: Vec<u8>,
) -> PyResult<bool> {
    let value: Value = serde_json::from_str(&attestation_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let obj = value
        .as_object()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("attestation must be object"))?;
    let mut payload = serde_json::Map::new();
    for key in ["validator", "target_hash", "target_height", "slot"] {
        if let Some(item) = obj.get(key) {
            payload.insert(key.to_string(), item.clone());
        } else {
            payload.insert(key.to_string(), Value::Null);
        }
    }
    let encoded = sorted_compact_json(&Value::Object(payload))?;
    let digest = crate::hash_string(&encoded);
    Ok(crate::verify_secp256k1_sha256_inner(
        digest.as_bytes(),
        &signature_der,
        &public_key_xy,
    ))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_p2p_wire_line, m)?)?;
    m.add_function(wrap_pyfunction!(encode_p2p_wire_message, m)?)?;
    m.add_function(wrap_pyfunction!(hash_sorted_json, m)?)?;
    m.add_function(wrap_pyfunction!(verify_attestation_secp256k1, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_envelope() {
        let line = br#"{"type":"ping","data":null}"#;
        let (msg_type, data) = parse_p2p_wire_line_inner(line, 1024 * 1024, None).unwrap();
        assert_eq!(msg_type, "ping");
        assert!(data.is_null());
    }

    #[test]
    fn rejects_oversized() {
        let line = vec![b'a'; 5000];
        let err = parse_p2p_wire_line_inner(&line, 4096, None).unwrap_err();
        assert!(err.contains("p2p_line_too_large"));
    }

    #[test]
    fn encode_roundtrip_type() {
        let bytes = encode_p2p_wire_message_inner("status", r#"{"height":1}"#).unwrap();
        assert!(bytes.ends_with(b"\n"));
        let (msg_type, data) = parse_p2p_wire_line_inner(&bytes, 1024 * 1024, None).unwrap();
        assert_eq!(msg_type, "status");
        assert_eq!(data["height"], 1);
    }
}
