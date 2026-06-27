use k256::ecdsa::signature::hazmat::PrehashVerifier;
use k256::ecdsa::{Signature, VerifyingKey};
use pyo3::prelude::*;
use serde_json::{Map, Number, Value};
use sha2::{Digest, Sha256};

fn sha256_hex_bytes(data: &[u8]) -> String {
    hex::encode(Sha256::digest(data))
}

fn hash_string(data: &str) -> String {
    sha256_hex_bytes(data.as_bytes())
}

fn merkle_root_strings(items: &[String]) -> String {
    if items.is_empty() {
        return hash_string("empty");
    }

    let mut layer: Vec<String> = items.iter().map(|item| hash_string(item)).collect();

    while layer.len() > 1 {
        if layer.len() % 2 == 1 {
            let last = layer[layer.len() - 1].clone();
            layer.push(last);
        }

        let mut next = Vec::with_capacity(layer.len() / 2);
        let mut i = 0;
        while i < layer.len() {
            let combined = format!("{}{}", layer[i], layer[i + 1]);
            next.push(hash_string(&combined));
            i += 2;
        }
        layer = next;
    }

    layer[0].clone()
}

fn merkle_proof_strings(items: &[String], target_index: usize) -> Vec<String> {
    if items.is_empty() || target_index >= items.len() {
        return Vec::new();
    }

    let mut layer: Vec<String> = items.iter().map(|item| hash_string(item)).collect();
    let mut proof = Vec::new();
    let mut index = target_index;

    while layer.len() > 1 {
        if layer.len() % 2 == 1 {
            let last = layer[layer.len() - 1].clone();
            layer.push(last);
        }

        let sibling_index = if index % 2 == 0 { index + 1 } else { index - 1 };
        if sibling_index < layer.len() {
            proof.push(layer[sibling_index].clone());
        }

        let mut next = Vec::with_capacity(layer.len() / 2);
        let mut i = 0;
        while i < layer.len() {
            let combined = format!("{}{}", layer[i], layer[i + 1]);
            next.push(hash_string(&combined));
            i += 2;
        }

        layer = next;
        index /= 2;
    }

    proof
}

fn merkle_root_from_proof_string(item: &str, proof: &[String], target_index: usize) -> String {
    let mut current_hash = hash_string(item);
    let mut index = target_index;

    for sibling_hash in proof {
        let combined = if index % 2 == 0 {
            format!("{current_hash}{sibling_hash}")
        } else {
            format!("{sibling_hash}{current_hash}")
        };
        current_hash = hash_string(&combined);
        index /= 2;
    }

    current_hash
}

fn py_round_12(value: f64) -> f64 {
    const SCALE: f64 = 1_000_000_000_000.0;
    let scaled = value * SCALE;
    let floor = scaled.floor();
    let fraction = scaled - floor;

    let rounded = if (fraction - 0.5).abs() < f64::EPSILON {
        if (floor as i128) % 2 == 0 {
            floor
        } else {
            floor + 1.0
        }
    } else {
        scaled.round()
    };

    rounded / SCALE
}

fn value_to_string(value: Option<&Value>, default_value: &str) -> String {
    match value {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Null) | None => default_value.to_string(),
        Some(v) => v.to_string(),
    }
}

fn value_to_i64(value: Option<&Value>) -> i64 {
    match value {
        Some(Value::Number(n)) => n
            .as_i64()
            .or_else(|| n.as_u64().map(|v| v as i64))
            .unwrap_or(0),
        Some(Value::String(s)) => s.parse::<i64>().unwrap_or(0),
        _ => 0,
    }
}

fn value_to_f64(value: Option<&Value>) -> f64 {
    match value {
        Some(Value::Number(n)) => n.as_f64().unwrap_or(0.0),
        Some(Value::String(s)) => s.parse::<f64>().unwrap_or(0.0),
        _ => 0.0,
    }
}

fn account_payload_row(account: &Value) -> PyResult<Value> {
    let obj = account.as_object().ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err("account row must be a JSON object")
    })?;

    let address = value_to_string(obj.get("address"), "");
    let balance = py_round_12(value_to_f64(obj.get("balance")));
    let nonce = value_to_i64(obj.get("nonce"));
    let code = value_to_string(obj.get("code"), "");
    let storage = value_to_string(obj.get("storage"), "{}");
    let storage = if storage.is_empty() {
        "{}".to_string()
    } else {
        storage
    };

    let code_hash = if code.is_empty() {
        String::new()
    } else {
        hash_string(&code)
    };
    let storage_hash = if storage.is_empty() {
        String::new()
    } else {
        hash_string(&storage)
    };

    let mut row = Map::new();
    row.insert("a".to_string(), Value::String(address));
    row.insert(
        "b".to_string(),
        Value::Number(Number::from_f64(balance).ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("account balance is not finite")
        })?),
    );
    row.insert("c".to_string(), Value::String(code_hash));
    row.insert("n".to_string(), Value::Number(Number::from(nonce)));
    row.insert("s".to_string(), Value::String(storage_hash));
    Ok(Value::Object(row))
}

fn verify_secp256k1_sha256_inner(
    message: &[u8],
    signature_der: &[u8],
    public_key_xy: &[u8],
) -> bool {
    if public_key_xy.len() != 64 {
        return false;
    }

    let signature = match Signature::from_der(signature_der) {
        Ok(sig) => sig,
        Err(_) => return false,
    };
    let signature = signature.normalize_s().unwrap_or(signature);

    let mut sec1_public_key = Vec::with_capacity(65);
    sec1_public_key.push(0x04);
    sec1_public_key.extend_from_slice(public_key_xy);

    let verifying_key = match VerifyingKey::from_sec1_bytes(&sec1_public_key) {
        Ok(key) => key,
        Err(_) => return false,
    };

    let digest = Sha256::digest(message);
    verifying_key.verify_prehash(&digest, &signature).is_ok()
}

#[pyfunction]
fn sha256_hex(data: &[u8]) -> PyResult<String> {
    Ok(sha256_hex_bytes(data))
}

#[pyfunction]
fn double_sha256_hex(data: &[u8]) -> PyResult<String> {
    let first = Sha256::digest(data);
    Ok(hex::encode(Sha256::digest(first)))
}

#[pyfunction]
fn merkle_root(items: Vec<String>) -> PyResult<String> {
    Ok(merkle_root_strings(&items))
}

#[pyfunction]
fn generate_proof(items: Vec<String>, target_index: usize) -> PyResult<Vec<String>> {
    Ok(merkle_proof_strings(&items, target_index))
}

#[pyfunction]
fn verify_proof(
    item: String,
    proof: Vec<String>,
    expected_root: String,
    target_index: usize,
) -> PyResult<bool> {
    Ok(merkle_root_from_proof_string(&item, &proof, target_index) == expected_root)
}

#[pyfunction]
fn merkle_root_from_proof(
    item: String,
    proof: Vec<String>,
    target_index: usize,
) -> PyResult<String> {
    Ok(merkle_root_from_proof_string(&item, &proof, target_index))
}

#[pyfunction]
fn state_root_from_accounts_json(accounts_json: String) -> PyResult<String> {
    let accounts: Value = serde_json::from_str(&accounts_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let accounts = accounts
        .as_array()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("accounts_json must be an array"))?;

    let mut payload = Vec::with_capacity(accounts.len());
    for account in accounts {
        payload.push(account_payload_row(account)?);
    }

    let encoded = serde_json::to_string(&payload)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(hash_string(&encoded))
}

#[pyfunction]
fn verify_secp256k1_sha256(
    message: &[u8],
    signature_der: &[u8],
    public_key_xy: &[u8],
) -> PyResult<bool> {
    Ok(verify_secp256k1_sha256_inner(
        message,
        signature_der,
        public_key_xy,
    ))
}

#[pyfunction]
fn verify_secp256k1_sha256_batch(items: Vec<(Vec<u8>, Vec<u8>, Vec<u8>)>) -> PyResult<Vec<bool>> {
    Ok(items
        .iter()
        .map(|(message, signature_der, public_key_xy)| {
            verify_secp256k1_sha256_inner(message, signature_der, public_key_xy)
        })
        .collect())
}

#[pymodule]
fn abs_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sha256_hex, m)?)?;
    m.add_function(wrap_pyfunction!(double_sha256_hex, m)?)?;
    m.add_function(wrap_pyfunction!(merkle_root, m)?)?;
    m.add_function(wrap_pyfunction!(generate_proof, m)?)?;
    m.add_function(wrap_pyfunction!(verify_proof, m)?)?;
    m.add_function(wrap_pyfunction!(merkle_root_from_proof, m)?)?;
    m.add_function(wrap_pyfunction!(state_root_from_accounts_json, m)?)?;
    m.add_function(wrap_pyfunction!(verify_secp256k1_sha256, m)?)?;
    m.add_function(wrap_pyfunction!(verify_secp256k1_sha256_batch, m)?)?;
    Ok(())
}
