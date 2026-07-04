use k256::ecdsa::signature::hazmat::PrehashVerifier;
use k256::ecdsa::{Signature, VerifyingKey};
use primitive_types::{U256, U512};
use pyo3::prelude::*;
use pyo3::types::{PyByteArray, PyList};
use serde_json::{Map, Number, Value};
use sha2::{Digest, Sha256};
use tiny_keccak::{Hasher, Keccak};

fn sha256_hex_bytes(data: &[u8]) -> String {
    hex::encode(Sha256::digest(data))
}

fn hash_string(data: &str) -> String {
    sha256_hex_bytes(data.as_bytes())
}

fn block_header_hash_payload(
    number: i64,
    parent_hash: &str,
    proposer: &str,
    state_root: &str,
    tx_root: &str,
    timestamp: i64,
    extra_data: &str,
) -> String {
    format!(
        "{number}{parent_hash}{proposer}{state_root}{tx_root}{timestamp}{extra_data}"
    )
}

fn block_header_hash_inner(
    number: i64,
    parent_hash: &str,
    proposer: &str,
    state_root: &str,
    tx_root: &str,
    timestamp: i64,
    extra_data: &str,
) -> String {
    hash_string(&block_header_hash_payload(
        number, parent_hash, proposer, state_root, tx_root, timestamp, extra_data,
    ))
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

fn format_py_float_component(value: f64) -> String {
    if !value.is_finite() {
        return value.to_string();
    }
    let mut rendered = format!("{value}");
    if value.fract() == 0.0
        && !rendered.contains('.')
        && !rendered.contains('e')
        && !rendered.contains('E')
    {
        rendered.push_str(".0");
    }
    rendered
}

fn transaction_hash_inner(
    from_addr: &str,
    to_addr: &str,
    value: f64,
    nonce: i64,
    gas: i64,
    data: &str,
    timestamp: i64,
) -> String {
    let raw = format!(
        "{from_addr}{to_addr}{}{nonce}{gas}{data}{timestamp}",
        format_py_float_component(value)
    );
    hash_string(&raw)
}

fn canonicalize_value(value: &Value) -> Value {
    match value {
        Value::Object(map) => {
            let mut sorted = Map::new();
            let mut keys: Vec<String> = map.keys().cloned().collect();
            keys.sort();
            for key in keys {
                if let Some(item) = map.get(&key) {
                    sorted.insert(key, canonicalize_value(item));
                }
            }
            Value::Object(sorted)
        }
        Value::Array(items) => Value::Array(items.iter().map(canonicalize_value).collect()),
        Value::Number(number) => {
            if number.is_f64() {
                let float_value = number.as_f64().unwrap_or(0.0);
                Value::Number(Number::from((float_value * 1_000_000.0) as i64))
            } else {
                value.clone()
            }
        }
        _ => value.clone(),
    }
}

fn canonical_serialize_json(value: &Value) -> PyResult<String> {
    let canonical = canonicalize_value(value);
    serde_json::to_string(&canonical)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

fn sort_block_transactions(block: &mut Value) {
    let Some(transactions) = block
        .as_object_mut()
        .and_then(|obj| obj.get_mut("transactions"))
        .and_then(|value| value.as_array_mut())
    else {
        return;
    };

    transactions.sort_by(|left, right| {
        let left_hash = left
            .as_object()
            .and_then(|obj| obj.get("hash"))
            .and_then(|value| value.as_str())
            .unwrap_or("");
        let right_hash = right
            .as_object()
            .and_then(|obj| obj.get("hash"))
            .and_then(|value| value.as_str())
            .unwrap_or("");
        left_hash.cmp(right_hash)
    });
}

fn block_canonical_hash_inner(block_json: &str) -> PyResult<String> {
    let mut block: Value = serde_json::from_str(block_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    sort_block_transactions(&mut block);
    let canonical = canonical_serialize_json(&block)?;
    Ok(hash_string(&canonical))
}

fn keccak256_hex_bytes(data: &[u8]) -> String {
    let mut hasher = Keccak::v256();
    hasher.update(data);
    let mut out = [0u8; 32];
    hasher.finalize(&mut out);
    hex::encode(out)
}

fn keccak256_digest_bytes(data: &[u8]) -> [u8; 32] {
    let mut hasher = Keccak::v256();
    hasher.update(data);
    let mut out = [0u8; 32];
    hasher.finalize(&mut out);
    out
}

fn u256_from_be32(bytes: [u8; 32]) -> U256 {
    U256::from_big_endian(&bytes)
}

fn u256_to_be32(value: U256) -> [u8; 32] {
    let mut out = [0u8; 32];
    value.to_big_endian(&mut out);
    out
}

fn evm_keccak256_memory_inner(memory: &[u8], offset: usize, size: usize) -> [u8; 32] {
    if size == 0 {
        return keccak256_digest_bytes(&[]);
    }
    let mut data = vec![0u8; size];
    if offset < memory.len() {
        let copied = usize::min(size, memory.len() - offset);
        data[..copied].copy_from_slice(&memory[offset..offset + copied]);
    }
    keccak256_digest_bytes(&data)
}

fn extract_canonical_transaction(tx: &Value) -> PyResult<Value> {
    let obj = tx.as_object().ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err("transaction row must be a JSON object")
    })?;

    let hash = value_to_string(obj.get("hash").or(obj.get("tx_hash")), "");
    let from_addr = value_to_string(obj.get("from").or(obj.get("from_addr")), "");
    let to_addr = value_to_string(obj.get("to").or(obj.get("to_addr")), "");
    let amount = value_to_f64(obj.get("amount").or(obj.get("value")));
    let fee = value_to_f64(obj.get("fee"));
    let nonce = value_to_i64(obj.get("nonce"));
    let timestamp = value_to_i64(obj.get("timestamp"));

    let mut row = Map::new();
    row.insert("amount".to_string(), Value::Number(Number::from_f64(amount).unwrap_or(Number::from(0))));
    row.insert("fee".to_string(), Value::Number(Number::from_f64(fee).unwrap_or(Number::from(0))));
    row.insert("from".to_string(), Value::String(from_addr));
    row.insert("hash".to_string(), Value::String(hash));
    row.insert("nonce".to_string(), Value::Number(Number::from(nonce)));
    row.insert("timestamp".to_string(), Value::Number(Number::from(timestamp)));
    row.insert("to".to_string(), Value::String(to_addr));
    Ok(Value::Object(row))
}

fn extract_canonical_block(block: &Value) -> PyResult<Value> {
    let obj = block.as_object().ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err("block must be a JSON object")
    })?;

    let height = value_to_i64(obj.get("height").or(obj.get("number")));
    let parent_hash = value_to_string(obj.get("parent_hash").or(obj.get("parent")), "");
    let miner = value_to_string(obj.get("miner").or(obj.get("proposer")), "");
    let timestamp = value_to_i64(obj.get("timestamp"));
    let extra_data = value_to_string(obj.get("extra_data"), "");
    let state_root = value_to_string(obj.get("state_root"), "");

    let mut tx_rows = Vec::new();
    if let Some(transactions) = obj.get("transactions").and_then(|value| value.as_array()) {
        for tx in transactions {
            tx_rows.push(extract_canonical_transaction(tx)?);
        }
    }
    tx_rows.sort_by(|left, right| {
        let left_hash = left
            .as_object()
            .and_then(|row| row.get("hash"))
            .and_then(|value| value.as_str())
            .unwrap_or("");
        let right_hash = right
            .as_object()
            .and_then(|row| row.get("hash"))
            .and_then(|value| value.as_str())
            .unwrap_or("");
        left_hash.cmp(right_hash)
    });

    let mut canonical = Map::new();
    canonical.insert("extra_data".to_string(), Value::String(extra_data));
    canonical.insert("height".to_string(), Value::Number(Number::from(height)));
    canonical.insert("miner".to_string(), Value::String(miner));
    canonical.insert("parent_hash".to_string(), Value::String(parent_hash));
    canonical.insert("state_root".to_string(), Value::String(state_root));
    canonical.insert("timestamp".to_string(), Value::Number(Number::from(timestamp)));
    canonical.insert("transactions".to_string(), Value::Array(tx_rows));
    Ok(Value::Object(canonical))
}

fn validate_imported_block_chain_inner(
    blocks_json: &[String],
    expected_parent_hash: &str,
    start_height: i64,
) -> PyResult<bool> {
    let mut previous_hash = expected_parent_hash.to_string();
    let mut previous_height = start_height;

    for block_json in blocks_json {
        let block: Value = serde_json::from_str(block_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let obj = block.as_object().ok_or_else(|| {
            pyo3::exceptions::PyValueError::new_err("block must be a JSON object")
        })?;

        let height = value_to_i64(obj.get("height").or(obj.get("number")));
        let block_hash = value_to_string(obj.get("hash").or(obj.get("block_hash")), "");
        let parent_hash = value_to_string(obj.get("parent_hash").or(obj.get("parent")), "");

        if block_hash.is_empty() || height != previous_height + 1 {
            return Ok(false);
        }
        if !previous_hash.is_empty() && parent_hash != previous_hash {
            return Ok(false);
        }

        let canonical_block = extract_canonical_block(&block)?;
        let recomputed = hash_string(&canonical_serialize_json(&canonical_block)?);
        if recomputed != block_hash {
            return Ok(false);
        }

        previous_hash = block_hash;
        previous_height = height;
    }

    Ok(true)
}

fn validate_peer_header_chain_inner(
    headers: &[(i64, String, String, String, String, String, i64, String)],
    expected_parent_hash: &str,
    start_height: i64,
) -> bool {
    let mut previous_hash = expected_parent_hash.to_string();
    let mut previous_height = start_height;

    for (number, hash, parent_hash, proposer, state_root, tx_root, timestamp, extra_data) in headers {
        if hash.is_empty() || *number != previous_height + 1 {
            return false;
        }
        if !previous_hash.is_empty() && parent_hash != &previous_hash {
            return false;
        }
        let recomputed = block_header_hash_inner(
            *number,
            parent_hash,
            proposer,
            state_root,
            tx_root,
            *timestamp,
            extra_data,
        );
        if recomputed != *hash {
            return false;
        }
        previous_hash = hash.clone();
        previous_height = *number;
    }

    true
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

fn evm_deploy_address_create_inner(deployer: &str, block_number: u64, init_code_len: usize) -> String {
    let seed = format!("{deployer}{block_number}{init_code_len}");
    format!("0x{}", &hash_string(&seed)[..40])
}

fn evm_deploy_address_create2_legacy_inner(
    deployer: &str,
    salt: &str,
    init_code: &[u8],
) -> String {
    let seed = format!("create2:{deployer}:{salt}:{}", hex::encode(init_code));
    format!("0x{}", &hash_string(&seed)[..40])
}

fn parse_address_20(deployer: &str) -> PyResult<[u8; 20]> {
    let raw = deployer
        .trim()
        .trim_start_matches("0x")
        .trim_start_matches("0X");
    if raw.len() != 40 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "deployer must be a 20-byte hex address",
        ));
    }
    let bytes = hex::decode(raw)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let mut out = [0u8; 20];
    out.copy_from_slice(&bytes);
    Ok(out)
}

fn parse_bytes32(value: &[u8]) -> PyResult<[u8; 32]> {
    if value.len() != 32 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "salt must be exactly 32 bytes",
        ));
    }
    let mut out = [0u8; 32];
    out.copy_from_slice(value);
    Ok(out)
}

fn evm_create2_address_eip1014_inner(
    deployer: &[u8; 20],
    salt: &[u8; 32],
    init_code_hash: &[u8; 32],
) -> [u8; 20] {
    let mut buf = [0u8; 85];
    buf[0] = 0xff;
    buf[1..21].copy_from_slice(deployer);
    buf[21..53].copy_from_slice(salt);
    buf[53..85].copy_from_slice(init_code_hash);
    let hash = keccak256_digest_bytes(&buf);
    let mut out = [0u8; 20];
    out.copy_from_slice(&hash[12..32]);
    out
}

#[pyfunction]
fn evm_deploy_address_create(
    deployer: String,
    block_number: u64,
    init_code_len: usize,
) -> PyResult<String> {
    Ok(evm_deploy_address_create_inner(&deployer, block_number, init_code_len))
}

#[pyfunction]
fn evm_deploy_address_create2_legacy(
    deployer: String,
    salt: String,
    init_code: Vec<u8>,
) -> PyResult<String> {
    Ok(evm_deploy_address_create2_legacy_inner(&deployer, &salt, &init_code))
}

#[pyfunction]
fn evm_create2_address_eip1014(
    deployer: String,
    salt: Vec<u8>,
    init_code: Vec<u8>,
) -> PyResult<Vec<u8>> {
    let deployer = parse_address_20(&deployer)?;
    let salt = parse_bytes32(&salt)?;
    let init_code_hash = keccak256_digest_bytes(&init_code);
    Ok(evm_create2_address_eip1014_inner(&deployer, &salt, &init_code_hash).to_vec())
}

#[pyfunction]
fn keccak256_digest(data: &[u8]) -> PyResult<[u8; 32]> {
    Ok(keccak256_digest_bytes(data))
}

#[pyfunction]
fn keccak256_digest_batch(items: Vec<Vec<u8>>) -> PyResult<Vec<[u8; 32]>> {
    Ok(items.iter().map(|item| keccak256_digest_bytes(item)).collect())
}

#[pyfunction]
fn evm_keccak256_memory(memory: &[u8], offset: usize, size: usize) -> PyResult<[u8; 32]> {
    Ok(evm_keccak256_memory_inner(memory, offset, size))
}

#[pyfunction]
fn evm_u256_add(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(
        u256_from_be32(a)
            .overflowing_add(u256_from_be32(b))
            .0,
    ))
}

#[pyfunction]
fn evm_u256_mul(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(
        u256_from_be32(a)
            .overflowing_mul(u256_from_be32(b))
            .0,
    ))
}

#[pyfunction]
fn evm_u256_sub(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(
        u256_from_be32(a)
            .overflowing_sub(u256_from_be32(b))
            .0,
    ))
}

#[pyfunction]
fn evm_u256_div(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    let denom = u256_from_be32(b);
    if denom.is_zero() {
        return Ok([0u8; 32]);
    }
    Ok(u256_to_be32(u256_from_be32(a) / denom))
}

#[pyfunction]
fn evm_u256_mod(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    let denom = u256_from_be32(b);
    if denom.is_zero() {
        return Ok([0u8; 32]);
    }
    Ok(u256_to_be32(u256_from_be32(a) % denom))
}

#[pyfunction]
fn evm_u256_and(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(u256_from_be32(a) & u256_from_be32(b)))
}

#[pyfunction]
fn evm_u256_or(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(u256_from_be32(a) | u256_from_be32(b)))
}

#[pyfunction]
fn evm_u256_xor(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(u256_from_be32(a) ^ u256_from_be32(b)))
}

#[pyfunction]
fn evm_u256_not(a: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(!u256_from_be32(a)))
}

#[pyfunction]
fn evm_u256_shl(a: [u8; 32], shift: u32) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(u256_from_be32(a) << shift))
}

#[pyfunction]
fn evm_u256_shr(a: [u8; 32], shift: u32) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(u256_from_be32(a) >> shift))
}

fn u256_is_negative(v: U256) -> bool {
    v.bit(255)
}

fn u256_abs(v: U256) -> U256 {
    if u256_is_negative(v) {
        (!v).overflowing_add(U256::one()).0
    } else {
        v
    }
}

fn u256_negate(v: U256) -> U256 {
    (!v).overflowing_add(U256::one()).0
}

fn evm_u256_sdiv_inner(a: U256, b: U256) -> U256 {
    if b.is_zero() {
        return U256::zero();
    }
    let min_i256 = U256::one() << 255;
    if a == min_i256 && b == U256::MAX {
        return min_i256;
    }
    let a_neg = u256_is_negative(a);
    let b_neg = u256_is_negative(b);
    let mut quot = u256_abs(a) / u256_abs(b);
    if a_neg ^ b_neg {
        quot = u256_negate(quot);
    }
    quot
}

fn evm_u256_smod_inner(a: U256, b: U256) -> U256 {
    if b.is_zero() {
        return U256::zero();
    }
    let a_neg = u256_is_negative(a);
    let mut rem = u256_abs(a) % u256_abs(b);
    if a_neg {
        rem = u256_negate(rem);
    }
    rem
}

fn evm_u256_addmod_inner(a: U256, b: U256, modulo: U256) -> U256 {
    if modulo.is_zero() {
        return U256::zero();
    }
    let sum = U512::from(a) + U512::from(b);
    U256::try_from(sum % U512::from(modulo)).unwrap_or(U256::zero())
}

fn evm_u256_mulmod_inner(a: U256, b: U256, modulo: U256) -> U256 {
    if modulo.is_zero() {
        return U256::zero();
    }
    let prod = U512::from(a) * U512::from(b);
    U256::try_from(prod % U512::from(modulo)).unwrap_or(U256::zero())
}

fn evm_u256_exp_inner(base: U256, exp: U256) -> U256 {
    if exp.is_zero() {
        return if base.is_zero() {
            U256::zero()
        } else {
            U256::one()
        };
    }
    let mut result = U256::one();
    let mut b = base;
    let mut e = exp;
    loop {
        if e.bit(0) {
            result = result.overflowing_mul(b).0;
        }
        e >>= 1;
        if e.is_zero() {
            break;
        }
        b = b.overflowing_mul(b).0;
    }
    result
}

fn evm_u256_signextend_inner(k: u32, x: U256) -> U256 {
    if k >= 32 {
        return x;
    }
    let bit = 8 * k + 7;
    let lower_mask = (U256::one() << (bit + 1)) - U256::one();
    if x.bit(bit as usize) {
        x | !lower_mask
    } else {
        x & lower_mask
    }
}

#[pyfunction]
fn evm_u256_sdiv(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(evm_u256_sdiv_inner(u256_from_be32(a), u256_from_be32(b))))
}

#[pyfunction]
fn evm_u256_smod(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(evm_u256_smod_inner(u256_from_be32(a), u256_from_be32(b))))
}

#[pyfunction]
fn evm_u256_addmod(a: [u8; 32], b: [u8; 32], modulo: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(evm_u256_addmod_inner(
        u256_from_be32(a),
        u256_from_be32(b),
        u256_from_be32(modulo),
    )))
}

#[pyfunction]
fn evm_u256_mulmod(a: [u8; 32], b: [u8; 32], modulo: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(evm_u256_mulmod_inner(
        u256_from_be32(a),
        u256_from_be32(b),
        u256_from_be32(modulo),
    )))
}

#[pyfunction]
fn evm_u256_exp(base: [u8; 32], exp: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(evm_u256_exp_inner(u256_from_be32(base), u256_from_be32(exp))))
}

#[pyfunction]
fn evm_u256_signextend(k: u32, x: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(u256_to_be32(evm_u256_signextend_inner(k, u256_from_be32(x))))
}

fn evm_u256_bool_word(truthy: bool) -> [u8; 32] {
    if truthy {
        let mut out = [0u8; 32];
        out[31] = 1;
        out
    } else {
        [0u8; 32]
    }
}

#[pyfunction]
fn evm_u256_lt(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(evm_u256_bool_word(u256_from_be32(a) < u256_from_be32(b)))
}

#[pyfunction]
fn evm_u256_gt(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(evm_u256_bool_word(u256_from_be32(a) > u256_from_be32(b)))
}

#[pyfunction]
fn evm_u256_eq(a: [u8; 32], b: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(evm_u256_bool_word(u256_from_be32(a) == u256_from_be32(b)))
}

#[pyfunction]
fn evm_u256_iszero(a: [u8; 32]) -> PyResult<[u8; 32]> {
    Ok(evm_u256_bool_word(u256_from_be32(a).is_zero()))
}

#[pyfunction]
fn evm_u256_byte(index: u32, word: [u8; 32]) -> PyResult<[u8; 32]> {
    let value = u256_from_be32(word);
    if index >= 32 {
        return Ok([0u8; 32]);
    }
    let shift = 8 * (31 - index);
    let byte = if shift >= 256 {
        0
    } else {
        ((value >> shift).low_u32() & 0xff) as u64
    };
    Ok(u256_to_be32(U256::from(byte)))
}

fn evm_memory_read_word_inner(memory: &[u8], offset: usize) -> [u8; 32] {
    let mut out = [0u8; 32];
    if offset < memory.len() {
        let end = usize::min(offset + 32, memory.len());
        out[..end - offset].copy_from_slice(&memory[offset..end]);
    }
    out
}

#[pyfunction]
fn evm_memory_read_word(memory: &[u8], offset: usize) -> PyResult<[u8; 32]> {
    Ok(evm_memory_read_word_inner(memory, offset))
}

fn evm_calldataload_inner(calldata: &[u8], offset: usize) -> [u8; 32] {
    let mut out = [0u8; 32];
    if offset < calldata.len() {
        let end = usize::min(offset + 32, calldata.len());
        out[..end - offset].copy_from_slice(&calldata[offset..end]);
    }
    out
}

#[pyfunction]
fn evm_calldataload(calldata: &[u8], offset: usize) -> PyResult<[u8; 32]> {
    Ok(evm_calldataload_inner(calldata, offset))
}

#[pyfunction]
fn evm_memory_copy(
    py_memory: &Bound<'_, PyByteArray>,
    dest: usize,
    src: &[u8],
    src_offset: usize,
    size: usize,
) -> PyResult<()> {
    let memory = unsafe { py_memory.as_bytes_mut() };
    for i in 0..size {
        let byte = src.get(src_offset + i).copied().unwrap_or(0);
        let idx = dest + i;
        if idx < memory.len() {
            memory[idx] = byte;
        }
    }
    Ok(())
}

#[pyfunction]
fn evm_memory_write_word(
    py_memory: &Bound<'_, PyByteArray>,
    offset: usize,
    value: [u8; 32],
) -> PyResult<()> {
    let memory = unsafe { py_memory.as_bytes_mut() };
    for i in 0..32 {
        let idx = offset + i;
        if idx < memory.len() {
            memory[idx] = value[i];
        }
    }
    Ok(())
}

#[pyfunction]
fn evm_memory_write_byte(
    py_memory: &Bound<'_, PyByteArray>,
    offset: usize,
    value: u32,
) -> PyResult<()> {
    let memory = unsafe { py_memory.as_bytes_mut() };
    if offset < memory.len() {
        memory[offset] = (value & 0xff) as u8;
    }
    Ok(())
}

fn evm_read_push_inner(bytecode: &[u8], pc: usize, n: usize) -> [u8; 32] {
    let n = n.min(32);
    let mut out = [0u8; 32];
    if n == 0 {
        return out;
    }
    let start = pc.saturating_add(1);
    if start >= bytecode.len() {
        return out;
    }
    let available = usize::min(n, bytecode.len() - start);
    out[32 - n..32 - n + available].copy_from_slice(&bytecode[start..start + available]);
    out
}

#[pyfunction]
fn evm_read_push(bytecode: &[u8], pc: usize, n: usize) -> PyResult<[u8; 32]> {
    Ok(evm_read_push_inner(bytecode, pc, n))
}

fn evm_build_jumpdest_table_inner(bytecode: &[u8]) -> Vec<u8> {
    let mut table = vec![0u8; (bytecode.len() + 7) / 8];
    let mut pc = 0usize;
    while pc < bytecode.len() {
        let op = bytecode[pc];
        if op == 0x5B {
            table[pc / 8] |= 1u8 << (pc % 8);
        }
        if (0x60..=0x7F).contains(&op) {
            pc += 1 + (op - 0x5F) as usize;
        } else {
            pc += 1;
        }
    }
    table
}

fn evm_is_jumpdest_inner(table: &[u8], dest: usize, bytecode_len: usize) -> bool {
    if dest >= bytecode_len {
        return false;
    }
    (table[dest / 8] >> (dest % 8)) & 1 == 1
}

#[pyfunction]
fn evm_build_jumpdest_table(bytecode: &[u8]) -> PyResult<Vec<u8>> {
    Ok(evm_build_jumpdest_table_inner(bytecode))
}

#[pyfunction]
fn evm_is_jumpdest(table: &[u8], dest: usize, bytecode_len: usize) -> PyResult<bool> {
    Ok(evm_is_jumpdest_inner(table, dest, bytecode_len))
}

#[pyfunction]
fn evm_word_to_address(word: [u8; 32]) -> PyResult<String> {
    let value = u256_from_be32(word);
    let mask = (U256::one() << 160) - U256::one();
    Ok(format!("0x{:040x}", value & mask))
}

#[pyfunction]
fn evm_call_gas_cap(remaining: u64, requested: u64) -> PyResult<u64> {
    let cap = remaining.saturating_mul(63) / 64;
    if requested == 0 {
        Ok(cap)
    } else {
        Ok(cap.min(requested))
    }
}

fn evm_memory_slice_inner(memory: &[u8], offset: usize, size: usize) -> Vec<u8> {
    let mut out = vec![0u8; size];
    if offset < memory.len() {
        let copied = usize::min(size, memory.len() - offset);
        out[..copied].copy_from_slice(&memory[offset..offset + copied]);
    }
    out
}

#[pyfunction]
fn evm_memory_slice(memory: &[u8], offset: usize, size: usize) -> PyResult<Vec<u8>> {
    Ok(evm_memory_slice_inner(memory, offset, size))
}

#[pyfunction]
fn evm_stack_dup(stack: &Bound<'_, PyList>, depth: usize) -> PyResult<()> {
    let len = stack.len();
    if depth == 0 || depth > len {
        return Err(pyo3::exceptions::PyValueError::new_err("stack underflow"));
    }
    let item = stack.get_item(len - depth)?;
    stack.append(item)?;
    Ok(())
}

#[pyfunction]
fn evm_stack_swap(stack: &Bound<'_, PyList>, depth: usize) -> PyResult<()> {
    let len = stack.len();
    if depth == 0 || depth >= len {
        return Err(pyo3::exceptions::PyValueError::new_err("stack underflow"));
    }
    let top = len - 1;
    let other = len - 1 - depth;
    let top_item = stack.get_item(top)?;
    let other_item = stack.get_item(other)?;
    stack.set_item(top, other_item)?;
    stack.set_item(other, top_item)?;
    Ok(())
}

fn evm_opcode_supported(op: u8) -> bool {
    matches!(
        op,
        0x00 | 0x01
            | 0x02
            | 0x03
            | 0x04
            | 0x05
            | 0x06
            | 0x07
            | 0x08
            | 0x09
            | 0x0A
            | 0x0B
            | 0x10
            | 0x11
            | 0x12
            | 0x14
            | 0x15
            | 0x16
            | 0x17
            | 0x19
            | 0x1A
            | 0x1B
            | 0x1C
            | 0x20
            | 0x30
            | 0x31
            | 0x32
            | 0x33
            | 0x34
            | 0x35
            | 0x36
            | 0x37
            | 0x38
            | 0x39
            | 0x3B
            | 0x3C
            | 0x3D
            | 0x3E
            | 0x40
            | 0x42
            | 0x43
            | 0x45
            | 0x46
            | 0x50
            | 0x51
            | 0x52
            | 0x53
            | 0x54
            | 0x55
            | 0x56
            | 0x57
            | 0x5A
            | 0x5B
            | 0x5F
            | 0xF0
            | 0xF1
            | 0xF2
            | 0xF3
            | 0xF4
            | 0xF5
            | 0xFA
            | 0xFD
            | 0xFE
            | 0xFF
    ) || (0x60..=0x7F).contains(&op)
        || (0x80..=0x8F).contains(&op)
        || (0x90..=0x9F).contains(&op)
        || (0xA0..=0xA4).contains(&op)
}

fn evm_scan_bytecode_inner(bytecode: &[u8]) -> Vec<(usize, u8)> {
    let mut issues = Vec::new();
    let mut pc = 0usize;
    while pc < bytecode.len() {
        let op = bytecode[pc];
        if !evm_opcode_supported(op) {
            issues.push((pc, op));
        }
        if (0x60..=0x7F).contains(&op) {
            pc += 1 + (op - 0x5F) as usize;
        } else {
            pc += 1;
        }
    }
    issues
}

#[pyfunction]
fn evm_scan_bytecode(bytecode: &[u8]) -> PyResult<Vec<(usize, u8)>> {
    Ok(evm_scan_bytecode_inner(bytecode))
}

#[pyfunction]
fn evm_gas_remaining(gas_limit: u64, gas_used: u64) -> PyResult<u64> {
    Ok(gas_limit.saturating_sub(gas_used))
}

#[pyfunction]
fn keccak256_hex(data: &[u8]) -> PyResult<String> {
    Ok(keccak256_hex_bytes(data))
}

#[pyfunction]
fn validate_imported_block_chain(
    blocks_json: Vec<String>,
    expected_parent_hash: String,
    start_height: i64,
) -> PyResult<bool> {
    validate_imported_block_chain_inner(&blocks_json, &expected_parent_hash, start_height)
}

#[pyfunction]
fn validate_peer_header_chain(
    headers: Vec<(i64, String, String, String, String, String, i64, String)>,
    expected_parent_hash: String,
    start_height: i64,
) -> PyResult<bool> {
    Ok(validate_peer_header_chain_inner(
        &headers,
        &expected_parent_hash,
        start_height,
    ))
}

#[pyfunction]
fn transaction_hash(
    from_addr: String,
    to_addr: String,
    value: f64,
    nonce: i64,
    gas: i64,
    data: String,
    timestamp: i64,
) -> PyResult<String> {
    Ok(transaction_hash_inner(
        &from_addr,
        &to_addr,
        value,
        nonce,
        gas,
        &data,
        timestamp,
    ))
}

#[pyfunction]
fn transaction_hash_batch(
    transactions: Vec<(String, String, f64, i64, i64, String, i64)>,
) -> PyResult<Vec<String>> {
    Ok(transactions
        .iter()
        .map(|(from_addr, to_addr, value, nonce, gas, data, timestamp)| {
            transaction_hash_inner(from_addr, to_addr, *value, *nonce, *gas, data, *timestamp)
        })
        .collect())
}

#[pyfunction]
fn canonical_hash_json(obj_json: String) -> PyResult<String> {
    let value: Value = serde_json::from_str(&obj_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let canonical = canonical_serialize_json(&value)?;
    Ok(hash_string(&canonical))
}

#[pyfunction]
fn block_canonical_hash_json(block_json: String) -> PyResult<String> {
    block_canonical_hash_inner(&block_json)
}

#[pyfunction]
fn block_canonical_hash_batch(block_json_items: Vec<String>) -> PyResult<Vec<String>> {
    block_json_items
        .iter()
        .map(|item| block_canonical_hash_inner(item))
        .collect()
}

#[pyfunction]
fn hash_text(text: String) -> PyResult<String> {
    Ok(hash_string(&text))
}

#[pyfunction]
fn hash_text_batch(items: Vec<String>) -> PyResult<Vec<String>> {
    Ok(items.iter().map(|item| hash_string(item)).collect())
}

#[pyfunction]
fn block_header_hash(
    number: i64,
    parent_hash: String,
    proposer: String,
    state_root: String,
    tx_root: String,
    timestamp: i64,
    extra_data: String,
) -> PyResult<String> {
    Ok(block_header_hash_inner(
        number,
        &parent_hash,
        &proposer,
        &state_root,
        &tx_root,
        timestamp,
        &extra_data,
    ))
}

#[pyfunction]
fn block_header_hash_batch(
    headers: Vec<(i64, String, String, String, String, i64, String)>,
) -> PyResult<Vec<String>> {
    Ok(headers
        .iter()
        .map(
            |(number, parent_hash, proposer, state_root, tx_root, timestamp, extra_data)| {
                block_header_hash_inner(
                    *number,
                    parent_hash,
                    proposer,
                    state_root,
                    tx_root,
                    *timestamp,
                    extra_data,
                )
            },
        )
        .collect())
}

#[pyfunction]
fn sha256_hex(data: &[u8]) -> PyResult<String> {
    Ok(sha256_hex_bytes(data))
}

#[pyfunction]
fn sha256_hex_batch(items: Vec<Vec<u8>>) -> PyResult<Vec<String>> {
    Ok(items.iter().map(|item| sha256_hex_bytes(item)).collect())
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

#[pyfunction]
fn validate_hash_chain(
    headers: Vec<(i64, String, String)>,
    expected_parent_hash: String,
    start_height: i64,
) -> PyResult<bool> {
    let mut previous_hash = expected_parent_hash;
    let mut previous_height = start_height;

    for (height, block_hash, parent_hash) in headers {
        if block_hash.is_empty() || height != previous_height + 1 {
            return Ok(false);
        }
        if !previous_hash.is_empty() && parent_hash != previous_hash {
            return Ok(false);
        }
        previous_hash = block_hash;
        previous_height = height;
    }

    Ok(true)
}

#[pymodule]
fn abs_native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(evm_deploy_address_create, m)?)?;
    m.add_function(wrap_pyfunction!(evm_deploy_address_create2_legacy, m)?)?;
    m.add_function(wrap_pyfunction!(evm_create2_address_eip1014, m)?)?;
    m.add_function(wrap_pyfunction!(keccak256_digest, m)?)?;
    m.add_function(wrap_pyfunction!(keccak256_digest_batch, m)?)?;
    m.add_function(wrap_pyfunction!(evm_keccak256_memory, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_add, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_mul, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_sub, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_div, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_mod, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_sdiv, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_smod, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_addmod, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_mulmod, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_exp, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_signextend, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_and, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_or, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_xor, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_not, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_shl, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_shr, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_lt, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_gt, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_eq, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_iszero, m)?)?;
    m.add_function(wrap_pyfunction!(evm_u256_byte, m)?)?;
    m.add_function(wrap_pyfunction!(evm_memory_read_word, m)?)?;
    m.add_function(wrap_pyfunction!(evm_memory_write_word, m)?)?;
    m.add_function(wrap_pyfunction!(evm_memory_write_byte, m)?)?;
    m.add_function(wrap_pyfunction!(evm_calldataload, m)?)?;
    m.add_function(wrap_pyfunction!(evm_memory_copy, m)?)?;
    m.add_function(wrap_pyfunction!(evm_read_push, m)?)?;
    m.add_function(wrap_pyfunction!(evm_build_jumpdest_table, m)?)?;
    m.add_function(wrap_pyfunction!(evm_is_jumpdest, m)?)?;
    m.add_function(wrap_pyfunction!(evm_word_to_address, m)?)?;
    m.add_function(wrap_pyfunction!(evm_call_gas_cap, m)?)?;
    m.add_function(wrap_pyfunction!(evm_memory_slice, m)?)?;
    m.add_function(wrap_pyfunction!(evm_stack_dup, m)?)?;
    m.add_function(wrap_pyfunction!(evm_stack_swap, m)?)?;
    m.add_function(wrap_pyfunction!(evm_scan_bytecode, m)?)?;
    m.add_function(wrap_pyfunction!(evm_gas_remaining, m)?)?;
    m.add_function(wrap_pyfunction!(keccak256_hex, m)?)?;
    m.add_function(wrap_pyfunction!(validate_imported_block_chain, m)?)?;
    m.add_function(wrap_pyfunction!(validate_peer_header_chain, m)?)?;
    m.add_function(wrap_pyfunction!(transaction_hash, m)?)?;
    m.add_function(wrap_pyfunction!(transaction_hash_batch, m)?)?;
    m.add_function(wrap_pyfunction!(canonical_hash_json, m)?)?;
    m.add_function(wrap_pyfunction!(block_canonical_hash_json, m)?)?;
    m.add_function(wrap_pyfunction!(block_canonical_hash_batch, m)?)?;
    m.add_function(wrap_pyfunction!(hash_text, m)?)?;
    m.add_function(wrap_pyfunction!(hash_text_batch, m)?)?;
    m.add_function(wrap_pyfunction!(block_header_hash, m)?)?;
    m.add_function(wrap_pyfunction!(block_header_hash_batch, m)?)?;
    m.add_function(wrap_pyfunction!(sha256_hex, m)?)?;
    m.add_function(wrap_pyfunction!(sha256_hex_batch, m)?)?;
    m.add_function(wrap_pyfunction!(double_sha256_hex, m)?)?;
    m.add_function(wrap_pyfunction!(merkle_root, m)?)?;
    m.add_function(wrap_pyfunction!(generate_proof, m)?)?;
    m.add_function(wrap_pyfunction!(verify_proof, m)?)?;
    m.add_function(wrap_pyfunction!(merkle_root_from_proof, m)?)?;
    m.add_function(wrap_pyfunction!(state_root_from_accounts_json, m)?)?;
    m.add_function(wrap_pyfunction!(verify_secp256k1_sha256, m)?)?;
    m.add_function(wrap_pyfunction!(verify_secp256k1_sha256_batch, m)?)?;
    m.add_function(wrap_pyfunction!(validate_hash_chain, m)?)?;
    Ok(())
}
