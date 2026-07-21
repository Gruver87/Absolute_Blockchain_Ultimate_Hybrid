//! RocksDB typed key codecs — byte-identical to `storage/keycodec.py`.

use pyo3::prelude::*;
use pyo3::types::PyBytes;

const P_BLOCK_HEIGHT: u8 = 0x01;
const P_BLOCK_HASH: u8 = 0x02;
const P_BLOCK_TX: u8 = 0x03;
const P_TX: u8 = 0x04;
const P_ACCOUNT: u8 = 0x10;
const P_VALIDATOR: u8 = 0x20;
const P_META: u8 = 0x40;
const P_BURN: u8 = 0x41;
const P_PROPOSER_AUDIT: u8 = 0x42;
const P_TX_PROP: u8 = 0x44;
const P_TX_FROM: u8 = 0x06;
const P_TX_TO: u8 = 0x07;
const P_TX_RECENT: u8 = 0x08;
const P_BRIDGE_LOCK: u8 = 0x50;
const P_BRIDGE_CREDIT: u8 = 0x51;
const P_EVM_LOG: u8 = 0x52;
const P_EVM_LOG_TX: u8 = 0x53;
const P_NFT_TOKEN: u8 = 0x54;
const P_NFT_OFFER: u8 = 0x55;
const P_NFT_AUCTION: u8 = 0x56;
const P_NFT_SALE: u8 = 0x57;

fn pack_u32_inner(value: u64) -> [u8; 4] {
    (value as u32).to_be_bytes()
}

fn pack_u64_inner(value: u64) -> [u8; 8] {
    value.to_be_bytes()
}

fn unpack_u32_inner(data: &[u8]) -> PyResult<u32> {
    if data.len() != 4 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "invalid u32 key segment",
        ));
    }
    Ok(u32::from_be_bytes([data[0], data[1], data[2], data[3]]))
}

fn unpack_u64_inner(data: &[u8]) -> PyResult<u64> {
    if data.len() != 8 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "invalid u64 key segment",
        ));
    }
    let mut buf = [0u8; 8];
    buf.copy_from_slice(data);
    Ok(u64::from_be_bytes(buf))
}

fn normalize_address_key_inner(address: &str) -> String {
    address.trim().to_ascii_lowercase()
}

fn normalize_hash_key_inner(block_hash: &str) -> PyResult<Vec<u8>> {
    let mut h = block_hash.trim().to_ascii_lowercase();
    if let Some(rest) = h.strip_prefix("0x") {
        h = rest.to_string();
    }
    if h.len() != 64 {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "invalid block hash key: {block_hash:?}"
        )));
    }
    hex::decode(&h).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("invalid block hash hex: {e}"))
    })
}

fn tx_hash_body_inner(tx_hash: &str) -> PyResult<Vec<u8>> {
    let mut h = tx_hash.trim().to_ascii_lowercase();
    if let Some(rest) = h.strip_prefix("0x") {
        h = rest.to_string();
    }
    if h.len() > 64 {
        h = h[h.len() - 64..].to_string();
    }
    while h.len() < 64 {
        h.insert(0, '0');
    }
    hex::decode(&h).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("invalid tx hash hex: {e}"))
    })
}

fn py_bytes(py: Python<'_>, data: &[u8]) -> PyObject {
    PyBytes::new_bound(py, data).into()
}

#[pyfunction]
fn rocks_pack_u32(py: Python<'_>, value: u64) -> PyObject {
    py_bytes(py, &pack_u32_inner(value))
}

#[pyfunction]
fn rocks_unpack_u32(data: Vec<u8>) -> PyResult<u32> {
    unpack_u32_inner(&data)
}

#[pyfunction]
fn rocks_pack_u64(py: Python<'_>, value: u64) -> PyObject {
    py_bytes(py, &pack_u64_inner(value))
}

#[pyfunction]
fn rocks_unpack_u64(data: Vec<u8>) -> PyResult<u64> {
    unpack_u64_inner(&data)
}

#[pyfunction]
fn rocks_normalize_address_key(address: String) -> String {
    normalize_address_key_inner(&address)
}

#[pyfunction]
fn rocks_normalize_hash_key(py: Python<'_>, block_hash: String) -> PyResult<PyObject> {
    Ok(py_bytes(py, &normalize_hash_key_inner(&block_hash)?))
}

#[pyfunction]
fn rocks_key_block_height(py: Python<'_>, height: u64) -> PyObject {
    let mut out = Vec::with_capacity(9);
    out.push(P_BLOCK_HEIGHT);
    out.extend_from_slice(&pack_u64_inner(height));
    py_bytes(py, &out)
}

#[pyfunction]
fn rocks_key_block_hash_to_height(py: Python<'_>, block_hash: String) -> PyResult<PyObject> {
    let mut out = Vec::with_capacity(33);
    out.push(P_BLOCK_HASH);
    out.extend_from_slice(&normalize_hash_key_inner(&block_hash)?);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_key_tx(py: Python<'_>, tx_hash: String) -> PyResult<PyObject> {
    let mut out = Vec::with_capacity(33);
    out.push(P_TX);
    out.extend_from_slice(&tx_hash_body_inner(&tx_hash)?);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_key_block_tx(py: Python<'_>, height: u64, tx_hash: String) -> PyResult<PyObject> {
    let body = tx_hash_body_inner(&tx_hash)?;
    let mut out = Vec::with_capacity(1 + 8 + body.len());
    out.push(P_BLOCK_TX);
    out.extend_from_slice(&pack_u64_inner(height));
    out.extend_from_slice(&body);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_key_tx_from_index(
    py: Python<'_>,
    address: String,
    block_height: u64,
    tx_hash: String,
) -> PyResult<PyObject> {
    let addr = normalize_address_key_inner(&address);
    let body = tx_hash_body_inner(&tx_hash)?;
    let mut out = Vec::with_capacity(1 + addr.len() + 8 + body.len());
    out.push(P_TX_FROM);
    out.extend_from_slice(addr.as_bytes());
    out.extend_from_slice(&pack_u64_inner(block_height));
    out.extend_from_slice(&body);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_key_tx_to_index(
    py: Python<'_>,
    address: String,
    block_height: u64,
    tx_hash: String,
) -> PyResult<PyObject> {
    let addr = normalize_address_key_inner(&address);
    let body = tx_hash_body_inner(&tx_hash)?;
    let mut out = Vec::with_capacity(1 + addr.len() + 8 + body.len());
    out.push(P_TX_TO);
    out.extend_from_slice(addr.as_bytes());
    out.extend_from_slice(&pack_u64_inner(block_height));
    out.extend_from_slice(&body);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_prefix_tx_from(py: Python<'_>, address: String) -> PyObject {
    let addr = normalize_address_key_inner(&address);
    let mut out = Vec::with_capacity(1 + addr.len());
    out.push(P_TX_FROM);
    out.extend_from_slice(addr.as_bytes());
    py_bytes(py, &out)
}

#[pyfunction]
fn rocks_prefix_tx_to(py: Python<'_>, address: String) -> PyObject {
    let addr = normalize_address_key_inner(&address);
    let mut out = Vec::with_capacity(1 + addr.len());
    out.push(P_TX_TO);
    out.extend_from_slice(addr.as_bytes());
    py_bytes(py, &out)
}

#[pyfunction]
fn rocks_key_tx_recent_index(
    py: Python<'_>,
    block_height: u64,
    timestamp: u64,
    tx_hash: String,
) -> PyResult<PyObject> {
    let inv_h = u64::MAX - block_height;
    let inv_ts = u64::MAX - timestamp;
    let body = tx_hash_body_inner(&tx_hash)?;
    let mut out = Vec::with_capacity(1 + 8 + 8 + body.len());
    out.push(P_TX_RECENT);
    out.extend_from_slice(&pack_u64_inner(inv_h));
    out.extend_from_slice(&pack_u64_inner(inv_ts));
    out.extend_from_slice(&body);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_prefix_tx_recent(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_TX_RECENT])
}

#[pyfunction]
fn rocks_key_tx_prop(py: Python<'_>, tx_hash: String, stage: String) -> PyResult<PyObject> {
    let body = tx_hash_body_inner(&tx_hash)?;
    let stage_bytes = stage.as_bytes();
    let stage_trim = if stage_bytes.len() > 16 {
        &stage_bytes[..16]
    } else {
        stage_bytes
    };
    let mut out = Vec::with_capacity(1 + body.len() + stage_trim.len());
    out.push(P_TX_PROP);
    out.extend_from_slice(&body);
    out.extend_from_slice(stage_trim);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_prefix_tx_prop(py: Python<'_>, tx_hash: String) -> PyResult<PyObject> {
    let body = tx_hash_body_inner(&tx_hash)?;
    let mut out = Vec::with_capacity(1 + body.len());
    out.push(P_TX_PROP);
    out.extend_from_slice(&body);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_prefix_tx_prop_all(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_TX_PROP])
}

#[pyfunction]
fn rocks_key_bridge_lock(py: Python<'_>, tx_hash: String) -> PyResult<PyObject> {
    let body = tx_hash_body_inner(&tx_hash)?;
    let mut out = Vec::with_capacity(1 + body.len());
    out.push(P_BRIDGE_LOCK);
    out.extend_from_slice(&body);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_key_bridge_credit(py: Python<'_>, credit_key: String) -> PyResult<PyObject> {
    let mut ck = credit_key.trim().to_ascii_lowercase();
    if let Some(rest) = ck.strip_prefix("0x") {
        ck = rest.to_string();
    }
    if ck.len() > 64 {
        ck = ck[ck.len() - 64..].to_string();
    }
    while ck.len() < 64 {
        ck.insert(0, '0');
    }
    let body = hex::decode(&ck).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("invalid credit key hex: {e}"))
    })?;
    let mut out = Vec::with_capacity(1 + body.len());
    out.push(P_BRIDGE_CREDIT);
    out.extend_from_slice(&body);
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_prefix_bridge_locks(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_BRIDGE_LOCK])
}

#[pyfunction]
fn rocks_prefix_bridge_credits(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_BRIDGE_CREDIT])
}

#[pyfunction]
fn rocks_key_evm_log(
    py: Python<'_>,
    block_height: u64,
    tx_hash: String,
    log_index: u64,
) -> PyResult<PyObject> {
    let body = tx_hash_body_inner(&tx_hash)?;
    let mut out = Vec::with_capacity(1 + 8 + body.len() + 4);
    out.push(P_EVM_LOG);
    out.extend_from_slice(&pack_u64_inner(block_height));
    out.extend_from_slice(&body);
    out.extend_from_slice(&pack_u32_inner(log_index));
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_key_evm_log_tx(py: Python<'_>, tx_hash: String, log_index: u64) -> PyResult<PyObject> {
    let body = tx_hash_body_inner(&tx_hash)?;
    let mut out = Vec::with_capacity(1 + body.len() + 4);
    out.push(P_EVM_LOG_TX);
    out.extend_from_slice(&body);
    out.extend_from_slice(&pack_u32_inner(log_index));
    Ok(py_bytes(py, &out))
}

#[pyfunction]
fn rocks_prefix_evm_logs(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_EVM_LOG])
}

#[pyfunction]
fn rocks_prefix_evm_logs_tx(py: Python<'_>, tx_hash: String) -> PyResult<PyObject> {
    let body = tx_hash_body_inner(&tx_hash)?;
    let mut out = Vec::with_capacity(1 + body.len());
    out.push(P_EVM_LOG_TX);
    out.extend_from_slice(&body);
    Ok(py_bytes(py, &out))
}

fn length_prefixed_utf8(prefix: u8, text: &str) -> Vec<u8> {
    let raw = text.trim().as_bytes();
    let mut out = Vec::with_capacity(1 + 4 + raw.len());
    out.push(prefix);
    out.extend_from_slice(&pack_u32_inner(raw.len() as u64));
    out.extend_from_slice(raw);
    out
}

#[pyfunction]
fn rocks_key_nft_token(py: Python<'_>, token_id: String) -> PyObject {
    py_bytes(py, &length_prefixed_utf8(P_NFT_TOKEN, &token_id))
}

#[pyfunction]
fn rocks_prefix_nft_tokens(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_NFT_TOKEN])
}

#[pyfunction]
fn rocks_key_nft_offer(py: Python<'_>, offer_id: String) -> PyObject {
    py_bytes(py, &length_prefixed_utf8(P_NFT_OFFER, &offer_id))
}

#[pyfunction]
fn rocks_prefix_nft_offers(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_NFT_OFFER])
}

#[pyfunction]
fn rocks_key_nft_auction(py: Python<'_>, auction_id: String) -> PyObject {
    py_bytes(py, &length_prefixed_utf8(P_NFT_AUCTION, &auction_id))
}

#[pyfunction]
fn rocks_prefix_nft_auctions(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_NFT_AUCTION])
}

#[pyfunction]
fn rocks_key_nft_sale(py: Python<'_>, created_at: u64, seq: u64) -> PyObject {
    let inv_ts = u64::MAX - created_at;
    let mut out = Vec::with_capacity(17);
    out.push(P_NFT_SALE);
    out.extend_from_slice(&pack_u64_inner(inv_ts));
    out.extend_from_slice(&pack_u64_inner(seq));
    py_bytes(py, &out)
}

#[pyfunction]
fn rocks_prefix_nft_sales(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_NFT_SALE])
}

#[pyfunction]
fn rocks_key_account(py: Python<'_>, address: String) -> PyObject {
    let addr = normalize_address_key_inner(&address);
    let mut out = Vec::with_capacity(1 + addr.len());
    out.push(P_ACCOUNT);
    out.extend_from_slice(addr.as_bytes());
    py_bytes(py, &out)
}

#[pyfunction]
fn rocks_key_validator(py: Python<'_>, address: String) -> PyObject {
    let addr = normalize_address_key_inner(&address);
    let mut out = Vec::with_capacity(1 + addr.len());
    out.push(P_VALIDATOR);
    out.extend_from_slice(addr.as_bytes());
    py_bytes(py, &out)
}

#[pyfunction]
fn rocks_key_meta(py: Python<'_>, name: String) -> PyObject {
    let mut out = Vec::with_capacity(1 + name.len());
    out.push(P_META);
    out.extend_from_slice(name.as_bytes());
    py_bytes(py, &out)
}

#[pyfunction]
fn rocks_key_burn(py: Python<'_>, height: u64) -> PyObject {
    let mut out = Vec::with_capacity(9);
    out.push(P_BURN);
    out.extend_from_slice(&pack_u64_inner(height));
    py_bytes(py, &out)
}

#[pyfunction]
fn rocks_key_proposer_audit(py: Python<'_>, height: u64) -> PyObject {
    let mut out = Vec::with_capacity(9);
    out.push(P_PROPOSER_AUDIT);
    out.extend_from_slice(&pack_u64_inner(height));
    py_bytes(py, &out)
}

#[pyfunction]
fn rocks_prefix_block_heights(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_BLOCK_HEIGHT])
}

#[pyfunction]
fn rocks_prefix_accounts(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_ACCOUNT])
}

#[pyfunction]
fn rocks_prefix_validators(py: Python<'_>) -> PyObject {
    py_bytes(py, &[P_VALIDATOR])
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rocks_pack_u32, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_unpack_u32, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_pack_u64, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_unpack_u64, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_normalize_address_key, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_normalize_hash_key, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_block_height, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_block_hash_to_height, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_tx, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_block_tx, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_tx_from_index, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_tx_to_index, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_tx_from, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_tx_to, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_tx_recent_index, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_tx_recent, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_tx_prop, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_tx_prop, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_tx_prop_all, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_bridge_lock, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_bridge_credit, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_bridge_locks, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_bridge_credits, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_evm_log, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_evm_log_tx, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_evm_logs, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_evm_logs_tx, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_nft_token, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_nft_tokens, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_nft_offer, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_nft_offers, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_nft_auction, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_nft_auctions, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_nft_sale, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_nft_sales, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_account, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_validator, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_meta, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_burn, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_key_proposer_audit, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_block_heights, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_accounts, m)?)?;
    m.add_function(wrap_pyfunction!(rocks_prefix_validators, m)?)?;
    Ok(())
}
