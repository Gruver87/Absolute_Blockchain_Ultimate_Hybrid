//! ADR 0008 — Borsh wire codec v2 + typed hot-path kernels (GIL-friendly).
//!
//! Wire envelope (version = 2):
//!   msg_type: UTF-8 string (≤64 bytes)
//!   payload:  opaque bytes (application Borsh / raw digests)
//!
//! Legacy NDJSON (`data_json`) remains in `p2p_wire` for v1 peers.

use borsh::{BorshDeserialize, BorshSerialize};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::Mutex;

pub const WIRE_CODEC_VERSION: u8 = 2;
pub const MAX_MSG_TYPE_LEN: usize = 64;
pub const MAX_PAYLOAD_BYTES: usize = 2 * 1024 * 1024;
pub const MAX_BATCH_MESSAGES: usize = 50_000;
pub const MAX_MERKLE_LEAVES: usize = 1_000_000;
pub const MAX_GHOST_NODES: usize = 100_000;
/// Nominal hot-path packet size for benches (1 KiB class).
pub const NOMINAL_PACKET_BYTES: usize = 1024;

#[derive(Clone, Debug, PartialEq, Eq, BorshSerialize, BorshDeserialize)]
pub struct WireEnvelopeV2 {
    pub version: u8,
    pub msg_type: String,
    pub payload: Vec<u8>,
}

fn validate_envelope(env: &WireEnvelopeV2) -> Result<(), String> {
    if env.version != WIRE_CODEC_VERSION {
        return Err(format!(
            "wire_codec_version_unsupported: {} (want {})",
            env.version, WIRE_CODEC_VERSION
        ));
    }
    if env.msg_type.is_empty() || env.msg_type.len() > MAX_MSG_TYPE_LEN {
        return Err("wire_codec_type_invalid".to_string());
    }
    if env.payload.len() > MAX_PAYLOAD_BYTES {
        return Err(format!(
            "wire_codec_payload_too_large: {} > {}",
            env.payload.len(),
            MAX_PAYLOAD_BYTES
        ));
    }
    Ok(())
}

pub fn encode_wire_v2_inner(msg_type: &str, payload: &[u8]) -> Result<Vec<u8>, String> {
    let env = WireEnvelopeV2 {
        version: WIRE_CODEC_VERSION,
        msg_type: msg_type.to_string(),
        payload: payload.to_vec(),
    };
    validate_envelope(&env)?;
    borsh::to_vec(&env).map_err(|e| format!("wire_codec_encode_failed: {e}"))
}

pub fn decode_wire_v2_inner(bytes: &[u8]) -> Result<WireEnvelopeV2, String> {
    if bytes.is_empty() {
        return Err("wire_codec_empty".to_string());
    }
    if bytes.len() > MAX_PAYLOAD_BYTES + 128 {
        return Err(format!("wire_codec_frame_too_large: {} bytes", bytes.len()));
    }
    let env = WireEnvelopeV2::try_from_slice(bytes)
        .map_err(|e| format!("wire_codec_decode_failed: {e}"))?;
    validate_envelope(&env)?;
    Ok(env)
}

/// Pack UTF-8 JSON into opaque payload bytes (migration helper).
pub fn payload_from_json_utf8(data_json: &str) -> Result<Vec<u8>, String> {
    if data_json.len() > MAX_PAYLOAD_BYTES {
        return Err("wire_codec_json_payload_too_large".to_string());
    }
    Ok(data_json.as_bytes().to_vec())
}

fn sha256_digest(data: &[u8]) -> [u8; 32] {
    let mut out = [0u8; 32];
    out.copy_from_slice(Sha256::digest(data).as_slice());
    out
}

fn merkle_root_from_digests_inner(leaves: &[[u8; 32]]) -> [u8; 32] {
    if leaves.is_empty() {
        return sha256_digest(b"empty");
    }
    let mut layer: Vec<[u8; 32]> = leaves.to_vec();
    while layer.len() > 1 {
        if layer.len() % 2 == 1 {
            let last = *layer.last().unwrap();
            layer.push(last);
        }
        let mut next = Vec::with_capacity(layer.len() / 2);
        let mut i = 0;
        while i < layer.len() {
            let mut buf = [0u8; 64];
            buf[..32].copy_from_slice(&layer[i]);
            buf[32..].copy_from_slice(&layer[i + 1]);
            next.push(sha256_digest(&buf));
            i += 2;
        }
        layer = next;
    }
    layer[0]
}

fn parse_digest32(raw: &[u8]) -> Result<[u8; 32], String> {
    if raw.len() == 32 {
        let mut out = [0u8; 32];
        out.copy_from_slice(raw);
        return Ok(out);
    }
    if raw.len() == 64 {
        let s = std::str::from_utf8(raw).map_err(|_| "digest_not_utf8".to_string())?;
        let bytes = hex::decode(s).map_err(|e| format!("digest_hex_invalid: {e}"))?;
        if bytes.len() != 32 {
            return Err("digest_hex_len".to_string());
        }
        let mut out = [0u8; 32];
        out.copy_from_slice(&bytes);
        return Ok(out);
    }
    Err(format!("digest_len_invalid: {}", raw.len()))
}

// ── PyO3: wire codec ───────────────────────────────────────────────────────

#[pyfunction]
fn wire_codec_version() -> u8 {
    WIRE_CODEC_VERSION
}

#[pyfunction]
fn wire_codec_nominal_packet_bytes() -> usize {
    NOMINAL_PACKET_BYTES
}

#[pyfunction]
fn encode_wire_v2(msg_type: &str, payload: &[u8]) -> PyResult<Vec<u8>> {
    encode_wire_v2_inner(msg_type, payload).map_err(pyo3::exceptions::PyValueError::new_err)
}

#[pyfunction]
fn decode_wire_v2(py: Python<'_>, frame: &[u8]) -> PyResult<PyObject> {
    let env = decode_wire_v2_inner(frame).map_err(pyo3::exceptions::PyValueError::new_err)?;
    let dict = PyDict::new_bound(py);
    dict.set_item("version", env.version)?;
    dict.set_item("type", env.msg_type)?;
    dict.set_item("payload", PyBytes::new_bound(py, &env.payload))?;
    Ok(dict.into())
}

#[pyfunction]
fn encode_wire_v2_batch(py: Python<'_>, items: Vec<(String, Vec<u8>)>) -> PyResult<PyObject> {
    if items.len() > MAX_BATCH_MESSAGES {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "wire_codec_batch_too_large: {} > {}",
            items.len(),
            MAX_BATCH_MESSAGES
        )));
    }
    let encoded = py
        .allow_threads(|| {
            let mut out: Vec<Vec<u8>> = Vec::with_capacity(items.len());
            for (msg_type, payload) in &items {
                out.push(encode_wire_v2_inner(msg_type, payload)?);
            }
            Ok::<Vec<Vec<u8>>, String>(out)
        })
        .map_err(pyo3::exceptions::PyValueError::new_err)?;
    let list = PyList::empty_bound(py);
    for frame in encoded {
        list.append(PyBytes::new_bound(py, &frame))?;
    }
    Ok(list.into())
}

#[pyfunction]
fn decode_wire_v2_batch(py: Python<'_>, frames: Vec<Vec<u8>>) -> PyResult<PyObject> {
    if frames.len() > MAX_BATCH_MESSAGES {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "wire_codec_batch_too_large: {} > {}",
            frames.len(),
            MAX_BATCH_MESSAGES
        )));
    }
    let decoded = py
        .allow_threads(|| {
            let mut out = Vec::with_capacity(frames.len());
            for frame in &frames {
                out.push(decode_wire_v2_inner(frame)?);
            }
            Ok::<Vec<WireEnvelopeV2>, String>(out)
        })
        .map_err(pyo3::exceptions::PyValueError::new_err)?;
    let list = PyList::empty_bound(py);
    for env in decoded {
        let dict = PyDict::new_bound(py);
        dict.set_item("version", env.version)?;
        dict.set_item("type", env.msg_type)?;
        dict.set_item("payload", PyBytes::new_bound(py, &env.payload))?;
        list.append(dict)?;
    }
    Ok(list.into())
}

#[pyfunction]
fn encode_wire_v2_json_payload(msg_type: &str, data_json: &str) -> PyResult<Vec<u8>> {
    let payload =
        payload_from_json_utf8(data_json).map_err(pyo3::exceptions::PyValueError::new_err)?;
    encode_wire_v2(msg_type, &payload)
}

/// Legacy NDJSON encode for bench comparison (same shape as p2p_wire path).
#[pyfunction]
fn encode_legacy_data_json_line(msg_type: &str, data_json: &str) -> PyResult<Vec<u8>> {
    let mut envelope = serde_json::Map::new();
    envelope.insert(
        "type".to_string(),
        serde_json::Value::String(msg_type.to_string()),
    );
    let data: serde_json::Value = if data_json.trim().is_empty() {
        serde_json::Value::Null
    } else {
        serde_json::from_str(data_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
    };
    envelope.insert("data".to_string(), data);
    let mut encoded = serde_json::to_string(&serde_json::Value::Object(envelope))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    encoded.push('\n');
    Ok(encoded.into_bytes())
}

#[pyfunction]
fn decode_legacy_data_json_line(py: Python<'_>, line: &[u8]) -> PyResult<PyObject> {
    let text = std::str::from_utf8(line)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
        .trim()
        .trim_end_matches('\0');
    let value: serde_json::Value = serde_json::from_str(text)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let obj = value
        .as_object()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("envelope_not_object"))?;
    let msg_type = obj
        .get("type")
        .and_then(|v| v.as_str())
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("type_missing"))?;
    let data = obj.get("data").cloned().unwrap_or(serde_json::Value::Null);
    let data_json = serde_json::to_string(&data)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let dict = PyDict::new_bound(py);
    dict.set_item("type", msg_type)?;
    dict.set_item("data_json", data_json)?;
    Ok(dict.into())
}

// ── Merkle from digests (no hex-string layer) ──────────────────────────────

#[pyfunction]
fn merkle_root_from_digests(py: Python<'_>, leaves: Vec<Vec<u8>>) -> PyResult<PyObject> {
    if leaves.len() > MAX_MERKLE_LEAVES {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "too_many_merkle_leaves: {} > {}",
            leaves.len(),
            MAX_MERKLE_LEAVES
        )));
    }
    let root = py
        .allow_threads(|| {
            let mut digests = Vec::with_capacity(leaves.len());
            for leaf in &leaves {
                digests.push(parse_digest32(leaf)?);
            }
            Ok::<[u8; 32], String>(merkle_root_from_digests_inner(&digests))
        })
        .map_err(pyo3::exceptions::PyValueError::new_err)?;
    Ok(PyBytes::new_bound(py, &root).into())
}

#[pyfunction]
fn merkle_root_from_digests_hex(leaves_hex: Vec<String>) -> PyResult<String> {
    if leaves_hex.len() > MAX_MERKLE_LEAVES {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "too_many_merkle_leaves: {} > {}",
            leaves_hex.len(),
            MAX_MERKLE_LEAVES
        )));
    }
    let mut digests = Vec::with_capacity(leaves_hex.len());
    for h in &leaves_hex {
        let bytes = hex::decode(h.trim())
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        digests.push(parse_digest32(&bytes).map_err(pyo3::exceptions::PyValueError::new_err)?);
    }
    let root = merkle_root_from_digests_inner(&digests);
    Ok(hex::encode(root))
}

// ── Batch verify with GIL released (parity with verify_secp256k1_sha256_inner)

#[pyfunction]
fn verify_secp256k1_sha256_batch_nogil(
    py: Python<'_>,
    items: Vec<(Vec<u8>, Vec<u8>, Vec<u8>)>,
) -> PyResult<Vec<bool>> {
    if items.len() > MAX_BATCH_MESSAGES {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "batch_too_large: {} > {}",
            items.len(),
            MAX_BATCH_MESSAGES
        )));
    }
    Ok(py.allow_threads(|| {
        items
            .iter()
            .map(|(msg, sig, pk)| crate::verify_secp256k1_sha256_inner(msg, sig, pk))
            .collect()
    }))
}

// ── GhostForest opaque handle ──────────────────────────────────────────────

#[derive(Clone, Default)]
struct GhostNode {
    parent: Option<String>,
    number: i64,
    children: Vec<String>,
}

#[pyclass]
pub struct GhostForest {
    inner: Mutex<HashMap<String, GhostNode>>,
    weights: Mutex<HashMap<String, i64>>,
}

impl GhostForest {
    fn select_head_inner(
        tree: &HashMap<String, GhostNode>,
        weights: &HashMap<String, i64>,
    ) -> Option<String> {
        if tree.is_empty() {
            return None;
        }
        let mut genesis = None;
        for (h, n) in tree.iter() {
            if n.parent.is_none() {
                genesis = Some(h.clone());
                break;
            }
        }
        let mut current = genesis?;
        loop {
            let node = tree.get(&current)?;
            if node.children.is_empty() {
                return Some(current);
            }
            let mut best: Option<String> = None;
            let mut best_w = i64::MIN;
            for child in &node.children {
                let w = cumulative_weight_inner(child, tree, weights);
                let take = match &best {
                    None => true,
                    Some(b) => w > best_w || (w == best_w && child < b),
                };
                if take {
                    best_w = w;
                    best = Some(child.clone());
                }
            }
            current = best?;
        }
    }
}

fn cumulative_weight_inner(
    block_hash: &str,
    tree: &HashMap<String, GhostNode>,
    weights: &HashMap<String, i64>,
) -> i64 {
    let mut memo: HashMap<String, i64> = HashMap::new();
    let mut stack: Vec<(String, bool)> = vec![(block_hash.to_string(), false)];
    while let Some((node, expanded)) = stack.pop() {
        if expanded {
            let mut total = *weights.get(&node).unwrap_or(&0);
            if let Some(n) = tree.get(&node) {
                for child in &n.children {
                    total += *memo.get(child).unwrap_or(&0);
                }
            }
            memo.insert(node, total);
        } else {
            stack.push((node.clone(), true));
            if let Some(n) = tree.get(&node) {
                for child in n.children.iter().rev() {
                    if !memo.contains_key(child) {
                        stack.push((child.clone(), false));
                    }
                }
            }
        }
    }
    *memo.get(block_hash).unwrap_or(&0)
}

#[pymethods]
impl GhostForest {
    #[new]
    fn new() -> Self {
        Self {
            inner: Mutex::new(HashMap::new()),
            weights: Mutex::new(HashMap::new()),
        }
    }

    #[pyo3(signature = (block_hash, parent_hash, number, weight))]
    fn insert_block(
        &self,
        block_hash: &str,
        parent_hash: Option<&str>,
        number: i64,
        weight: i64,
    ) -> PyResult<()> {
        let mut tree = self
            .inner
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("ghost_lock"))?;
        if tree.len() >= MAX_GHOST_NODES && !tree.contains_key(block_hash) {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "too_many_ghost_nodes",
            ));
        }
        let parent = parent_hash.map(|s| s.to_string()).filter(|s| !s.is_empty());
        tree.entry(block_hash.to_string())
            .and_modify(|n| {
                n.parent = parent.clone();
                n.number = number;
            })
            .or_insert_with(|| GhostNode {
                parent: parent.clone(),
                number,
                children: Vec::new(),
            });
        if let Some(ref p) = parent {
            let child = block_hash.to_string();
            let entry = tree.entry(p.clone()).or_insert_with(|| GhostNode {
                parent: None,
                number: number.saturating_sub(1),
                children: Vec::new(),
            });
            if !entry.children.contains(&child) {
                entry.children.push(child);
            }
        }
        drop(tree);
        let mut weights = self
            .weights
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("ghost_lock"))?;
        weights.insert(block_hash.to_string(), weight);
        Ok(())
    }

    fn set_weight(&self, block_hash: &str, weight: i64) -> PyResult<()> {
        let mut weights = self
            .weights
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("ghost_lock"))?;
        weights.insert(block_hash.to_string(), weight);
        Ok(())
    }

    fn select_head(&self, py: Python<'_>) -> PyResult<Option<String>> {
        let tree = self
            .inner
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("ghost_lock"))?
            .clone();
        let weights = self
            .weights
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("ghost_lock"))?
            .clone();
        Ok(py.allow_threads(|| Self::select_head_inner(&tree, &weights)))
    }

    fn cumulative_weight(&self, py: Python<'_>, block_hash: &str) -> PyResult<i64> {
        let tree = self
            .inner
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("ghost_lock"))?
            .clone();
        let weights = self
            .weights
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("ghost_lock"))?
            .clone();
        let key = block_hash.to_string();
        Ok(py.allow_threads(|| cumulative_weight_inner(&key, &tree, &weights)))
    }

    fn len(&self) -> PyResult<usize> {
        let tree = self
            .inner
            .lock()
            .map_err(|_| pyo3::exceptions::PyRuntimeError::new_err("ghost_lock"))?;
        Ok(tree.len())
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(wire_codec_version, m)?)?;
    m.add_function(wrap_pyfunction!(wire_codec_nominal_packet_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(encode_wire_v2, m)?)?;
    m.add_function(wrap_pyfunction!(decode_wire_v2, m)?)?;
    m.add_function(wrap_pyfunction!(encode_wire_v2_batch, m)?)?;
    m.add_function(wrap_pyfunction!(decode_wire_v2_batch, m)?)?;
    m.add_function(wrap_pyfunction!(encode_wire_v2_json_payload, m)?)?;
    m.add_function(wrap_pyfunction!(encode_legacy_data_json_line, m)?)?;
    m.add_function(wrap_pyfunction!(decode_legacy_data_json_line, m)?)?;
    m.add_function(wrap_pyfunction!(merkle_root_from_digests, m)?)?;
    m.add_function(wrap_pyfunction!(merkle_root_from_digests_hex, m)?)?;
    m.add_function(wrap_pyfunction!(verify_secp256k1_sha256_batch_nogil, m)?)?;
    m.add_class::<GhostForest>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_1kib_payload() {
        let payload = vec![0xABu8; 900];
        let frame = encode_wire_v2_inner("new_tx", &payload).unwrap();
        let env = decode_wire_v2_inner(&frame).unwrap();
        assert_eq!(env.version, 2);
        assert_eq!(env.msg_type, "new_tx");
        assert_eq!(env.payload, payload);
        assert!(frame.len() < 1100);
    }

    #[test]
    fn merkle_two_leaves() {
        let a = sha256_digest(b"a");
        let b = sha256_digest(b"b");
        let root = merkle_root_from_digests_inner(&[a, b]);
        assert_ne!(root, a);
    }
}
