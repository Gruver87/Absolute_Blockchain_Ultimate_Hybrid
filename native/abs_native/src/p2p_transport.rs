//! Native P2P TCP(+TLS) transport (v1.3.90–v1.3.113).
//!
//! Blocking TcpListener / TcpStream + optional rustls mTLS + NDJSON framer.
//! v1.3.92: `read_message` fuses framed read + wire parse.
//! v1.3.93: `write_message` fuses wire encode + write.
//! v1.3.94: `read_messages` batch drain (still not full message-loop).
//! v1.3.95: `write_messages` / `write_payloads` batch send.
//! v1.3.96: `handshake_roundtrip` I/O fuse (validate still Python).
//! v1.3.97: peer cert CN/SAN identities for native TLS bind.
//! v1.3.98: auto-pong on read path (keepalive only; not full dispatch).
//! v1.3.99: consume inbound pong + keepalive_touches (still not full dispatch).
//! v1.3.100: housekeeping payload gate on read (parity with Python).
//! v1.3.101: clamp helpers for configurable batch/chunk sizes.
//! v1.3.102: configurable socket I/O timeout (set_timeout_ms + clamp).
//! v1.3.103: mid-session handshake reject once session_established.
//! v1.3.104: status payload gate on read (parity with Python).
//! v1.3.105: attestation shape gate on read (parity with Python).
//! v1.3.106: new_block / get_block shape gates on read (parity with Python).
//! v1.3.107: get_blocks / get_block_by_hash / blocks shape gates on read.
//! v1.3.108: new_tx / mempool shape gates on read (parity with Python).
//! v1.3.109: singular `block` payload gate on read (null = not-found).
//! v1.3.110: peers / validator_register shape gates on read.
//! v1.3.111: state_root_request / state_root_response shape gates on read.
//! v1.3.112: cross_shard_tx / cross_shard_ack / shard_migration shape gates.
//! v1.3.113: handshake payload shape gate on handshake_roundtrip.
//! v1.3.115: handshake policy fuse (chain_id + TLS identity) on handshake_roundtrip.
//! v1.3.116: message-loop event shell (`read_message_loop_events`) — ordered dispatch/strike.
//! v1.3.117: attestation semantic gate on loop-shell (identity + secp256k1 before dispatch).
//! v1.3.118: new_tx signature semantic gate on loop-shell (chain_id-bound; mempool stays Python).
//! v1.3.119: mempool batch signature semantic gate on loop-shell (per-tx; nonce/balance stay Python).
//! v1.3.120: new_block canonical-hash semantic gate on loop-shell (parent/proposer stay Python).
//! v1.3.121: blocks batch canonical-hash semantic gate on loop-shell (per-block; import stays Python).
//! v1.3.122: singular `block` response canonical-hash semantic gate (null = not-found OK).
//! v1.3.123: state_root_response digest-semantic gate (32-byte hex; correlation stays Python).
//! Python remains the control plane (handshake policy, dispatch, gossip).
//! Honesty: not libp2p / multiplex; not full async message-loop ownership.

use crate::p2p_frame::P2PLineFramer;
use crate::p2p_wire::{
    clamp_max_bytes, encode_p2p_wire_message_inner, parse_p2p_wire_line_inner,
    validate_attestation_shape_inner, validate_block_announce_inner, validate_blocks_batch_inner,
    validate_cross_shard_ack_inner, validate_cross_shard_tx_inner, validate_get_block_by_hash_inner,
    validate_get_block_inner, validate_get_blocks_inner, validate_handshake_inner,
    validate_mempool_batch_inner, validate_peers_list_inner, validate_shard_migration_inner,
    validate_state_root_request_inner, validate_state_root_response_inner, validate_status_inner,
    validate_validator_register_inner, validate_wire_tx_inner, verify_attestation_semantics_inner,
    verify_block_announce_semantics_inner, verify_blocks_batch_semantics_inner,
    verify_mempool_batch_signatures_inner, verify_state_root_response_semantics_inner,
    verify_wire_tx_signature_inner, DEFAULT_MAX_P2P_LINE_BYTES,
};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use std::collections::HashSet;
use rustls::client::danger::{HandshakeSignatureValid, ServerCertVerified, ServerCertVerifier};
use rustls::pki_types::{CertificateDer, PrivateKeyDer, ServerName, UnixTime};
use rustls::server::WebPkiClientVerifier;
use rustls::{
    ClientConfig, ClientConnection, DigitallySignedStruct, Error as TlsError, RootCertStore,
    ServerConfig, ServerConnection, SignatureScheme, StreamOwned,
};
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{BufReader, Read, Write};
use std::net::{Shutdown, SocketAddr, TcpListener, TcpStream, ToSocketAddrs};
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;

/// v1.3.101: batch size bounds for `read_messages` / write batching.
pub const NATIVE_BATCH_MIN: usize = 1;
pub const NATIVE_BATCH_MAX: usize = 64;
pub const NATIVE_BATCH_DEFAULT: usize = 8;
/// Read chunk bounds (bytes).
pub const NATIVE_CHUNK_MIN: usize = 1024;
pub const NATIVE_CHUNK_MAX: usize = 1024 * 1024;
pub const NATIVE_CHUNK_DEFAULT: usize = 65536;
/// Socket I/O timeout bounds (milliseconds) — v1.3.102.
pub const NATIVE_IO_TIMEOUT_MIN_MS: u64 = 1_000;
pub const NATIVE_IO_TIMEOUT_MAX_MS: u64 = 600_000;
pub const NATIVE_IO_TIMEOUT_DEFAULT_MS: u64 = 30_000;

fn io_err(e: std::io::Error) -> String {
    format!("p2p_transport_io:{e}")
}

/// Short reject reason for `read_message` (transport + wire parse).
fn wire_fail_reason(err: &str) -> String {
    if err == "p2p_transport_timeout"
        || err == "p2p_transport_closed"
        || err == "p2p_handshake_eof"
        || err == "p2p_auto_pong_flood"
        || err == "mid_session_handshake"
        || err == "chain_id_mismatch"
        || err == "tls_missing"
        || err == "tls_identity_mismatch"
        || err == "handshake_rejected"
        || err == "missing_tx_signature"
        || err == "missing_tx_public_key"
        || err == "bad_tx_signature"
        || err.starts_with("p2p_transport_")
        || err.starts_with("p2p_handshake_")
    {
        return err.to_string();
    }
    // Preserve strike reasons: bad_*_payload, bad_attestation_shape, bad_block_announce, …
    if err.starts_with("bad_") {
        return err.to_string();
    }
    if err.starts_with("p2p_line_too_large") {
        return "p2p_line_too_large".to_string();
    }
    if err.starts_with("p2p_type_not_allowed") {
        return err.to_string();
    }
    if err.starts_with("p2p_") {
        return err.split(':').next().unwrap_or(err).to_string();
    }
    "bad_wire_line".to_string()
}

/// Parity with Python `_housekeeping_payload_ok` (v1.3.100).
fn housekeeping_payload_ok(msg_type: &str, data: &serde_json::Value) -> bool {
    match msg_type {
        "ping" | "pong" => {
            if data.is_null() {
                return true;
            }
            let Some(obj) = data.as_object() else {
                return false;
            };
            if obj.is_empty() {
                return true;
            }
            if obj.len() == 1 {
                if let Some(ts) = obj.get("ts") {
                    return ts.is_number();
                }
            }
            false
        }
        "get_mempool" | "get_peers" => data.as_object().map(|o| o.is_empty()).unwrap_or(false),
        _ => true,
    }
}

fn check_housekeeping(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if housekeeping_payload_ok(msg_type, data) {
        Ok(())
    } else {
        Err(format!("bad_{msg_type}_payload"))
    }
}

/// v1.3.103: reject handshake frames after the session is established.
fn check_mid_session_handshake(session_established: bool, msg_type: &str) -> Result<(), String> {
    if session_established && (msg_type == "handshake" || msg_type == "handshake_ack") {
        return Err("mid_session_handshake".to_string());
    }
    Ok(())
}

/// v1.3.104: parity with Python status shape gate (null ok; bad dict → reject).
fn check_status_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "status" {
        return Ok(());
    }
    if data.is_null() {
        return Ok(());
    }
    // Python only strikes when data is a dict that fails validate_p2p_status_payload.
    if !data.is_object() {
        return Ok(());
    }
    if validate_status_inner(data).is_none() {
        return Err("bad_status_payload".to_string());
    }
    Ok(())
}

/// v1.3.105: parity with Python attestation shape gate (fail-closed).
fn check_attestation_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "attestation" {
        return Ok(());
    }
    if !validate_attestation_shape_inner(data) {
        return Err("bad_attestation_shape".to_string());
    }
    Ok(())
}

/// v1.3.117: attestation identity + signature (loop-shell semantic ingress).
fn check_attestation_semantics(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "attestation" {
        return Ok(());
    }
    verify_attestation_semantics_inner(data)
}

/// v1.3.118: new_tx signature-only semantic gate (local chain_id).
fn check_wire_tx_semantics(
    msg_type: &str,
    data: &serde_json::Value,
    expected_chain_id: Option<i64>,
    require_signature: bool,
) -> Result<(), String> {
    if msg_type != "new_tx" {
        return Ok(());
    }
    let Some(chain_id) = expected_chain_id else {
        // No chain_id provided → skip semantic (compat with older callers).
        return Ok(());
    };
    verify_wire_tx_signature_inner(data, chain_id, require_signature)
}

/// v1.3.119: mempool batch per-tx signature semantic gate (local chain_id).
fn check_mempool_batch_semantics(
    msg_type: &str,
    data: &serde_json::Value,
    expected_chain_id: Option<i64>,
    require_signature: bool,
) -> Result<(), String> {
    if msg_type != "mempool" {
        return Ok(());
    }
    let Some(chain_id) = expected_chain_id else {
        return Ok(());
    };
    verify_mempool_batch_signatures_inner(data, chain_id, require_signature)
}

/// v1.3.120: new_block claimed hash vs canonical recompute.
fn check_block_announce_semantics(
    msg_type: &str,
    data: &serde_json::Value,
) -> Result<(), String> {
    if msg_type != "new_block" {
        return Ok(());
    }
    verify_block_announce_semantics_inner(data)
}

/// v1.3.121: sync `blocks` array — each entry must pass canonical-hash semantic.
fn check_blocks_batch_semantics(
    msg_type: &str,
    data: &serde_json::Value,
) -> Result<(), String> {
    if msg_type != "blocks" {
        return Ok(());
    }
    verify_blocks_batch_semantics_inner(data)
}

/// v1.3.122: singular `block` response — null OK; non-null must match canonical hash.
fn check_block_payload_semantics(
    msg_type: &str,
    data: &serde_json::Value,
) -> Result<(), String> {
    if msg_type != "block" {
        return Ok(());
    }
    if data.is_null() {
        return Ok(());
    }
    verify_block_announce_semantics_inner(data)
}

/// v1.3.123: state_root_response — state_root + head_hash must be 32-byte hex digests.
fn check_state_root_response_semantics(
    msg_type: &str,
    data: &serde_json::Value,
) -> Result<(), String> {
    if msg_type != "state_root_response" {
        return Ok(());
    }
    verify_state_root_response_semantics_inner(data)
}

/// v1.3.106: parity with Python `new_block` announce gate (fail-closed).
fn check_block_announce_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "new_block" {
        return Ok(());
    }
    if validate_block_announce_inner(data).is_none() {
        return Err("bad_block_announce".to_string());
    }
    Ok(())
}

/// v1.3.106: parity with Python `get_block` height gate (fail-closed).
fn check_get_block_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "get_block" {
        return Ok(());
    }
    if validate_get_block_inner(data).is_none() {
        return Err("bad_get_block".to_string());
    }
    Ok(())
}

/// v1.3.107: parity with Python `get_blocks` range gate (fail-closed).
fn check_get_blocks_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "get_blocks" {
        return Ok(());
    }
    if validate_get_blocks_inner(data).is_none() {
        return Err("bad_get_blocks".to_string());
    }
    Ok(())
}

/// v1.3.107: parity with Python `get_block_by_hash` gate (fail-closed).
fn check_get_block_by_hash_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "get_block_by_hash" {
        return Ok(());
    }
    if validate_get_block_by_hash_inner(data).is_none() {
        return Err("bad_get_block_by_hash".to_string());
    }
    Ok(())
}

/// v1.3.107: parity with Python `blocks` batch gate (fail-closed).
fn check_blocks_batch_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "blocks" {
        return Ok(());
    }
    if validate_blocks_batch_inner(data).is_none() {
        return Err("bad_blocks_batch".to_string());
    }
    Ok(())
}

/// v1.3.108: parity with Python `new_tx` wire-tx gate (fail-closed).
fn check_wire_tx_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "new_tx" {
        return Ok(());
    }
    if !validate_wire_tx_inner(data) {
        return Err("bad_wire_tx".to_string());
    }
    Ok(())
}

/// v1.3.108: parity with Python `mempool` batch gate (fail-closed).
fn check_mempool_batch_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "mempool" {
        return Ok(());
    }
    if validate_mempool_batch_inner(data).is_none() {
        return Err("bad_mempool_batch".to_string());
    }
    Ok(())
}

/// v1.3.109: parity with Python singular `block` gate (null = not-found OK).
fn check_block_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "block" {
        return Ok(());
    }
    if data.is_null() {
        return Ok(());
    }
    if validate_block_announce_inner(data).is_none() {
        return Err("bad_block_payload".to_string());
    }
    Ok(())
}

/// v1.3.110: parity with Python `peers` list gate (fail-closed).
fn check_peers_list_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "peers" {
        return Ok(());
    }
    if validate_peers_list_inner(data).is_none() {
        return Err("bad_peers_list".to_string());
    }
    Ok(())
}

/// v1.3.110: parity with Python `validator_register` gate (fail-closed).
fn check_validator_register_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "validator_register" {
        return Ok(());
    }
    if validate_validator_register_inner(data).is_none() {
        return Err("bad_validator_register".to_string());
    }
    Ok(())
}

/// v1.3.111: parity with Python `state_root_request` gate (fail-closed).
fn check_state_root_request_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "state_root_request" {
        return Ok(());
    }
    if validate_state_root_request_inner(data).is_none() {
        return Err("bad_state_root_request".to_string());
    }
    Ok(())
}

/// v1.3.111: parity with Python `state_root_response` gate (fail-closed).
fn check_state_root_response_payload(
    msg_type: &str,
    data: &serde_json::Value,
) -> Result<(), String> {
    if msg_type != "state_root_response" {
        return Ok(());
    }
    if validate_state_root_response_inner(data).is_none() {
        return Err("bad_state_root_response".to_string());
    }
    Ok(())
}

/// v1.3.112: parity with Python `cross_shard_tx` gate (fail-closed).
fn check_cross_shard_tx_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "cross_shard_tx" {
        return Ok(());
    }
    if validate_cross_shard_tx_inner(data).is_none() {
        return Err("bad_cross_shard_tx".to_string());
    }
    Ok(())
}

/// v1.3.112: parity with Python `cross_shard_ack` gate (fail-closed).
fn check_cross_shard_ack_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "cross_shard_ack" {
        return Ok(());
    }
    if validate_cross_shard_ack_inner(data).is_none() {
        return Err("bad_cross_shard_ack".to_string());
    }
    Ok(())
}

/// v1.3.112: parity with Python `shard_migration` gate (fail-closed).
fn check_shard_migration_payload(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    if msg_type != "shard_migration" {
        return Ok(());
    }
    if validate_shard_migration_inner(data).is_none() {
        return Err("bad_shard_migration".to_string());
    }
    Ok(())
}

/// v1.3.113: parity with Python handshake shape gate (fail-closed).
fn check_handshake_payload(data: &serde_json::Value) -> Result<(), String> {
    if validate_handshake_inner(data).is_none() {
        return Err("bad_handshake_payload".to_string());
    }
    Ok(())
}

/// v1.3.115: chain_id + TLS identity policy after shape gate (fingerprint allowlist stays Python).
fn check_handshake_policy(
    data: &serde_json::Value,
    expected_chain_id: Option<i64>,
    tls_required: bool,
    bind_identity: bool,
    conn_tls: bool,
    peer_identities: &[String],
) -> Result<(), String> {
    let Some((chain_id, _height, _head, node_id, _port, accepted)) =
        validate_handshake_inner(data)
    else {
        return Err("bad_handshake_payload".to_string());
    };
    if !accepted {
        return Err("handshake_rejected".to_string());
    }
    if let Some(want) = expected_chain_id {
        if chain_id != want {
            return Err("chain_id_mismatch".to_string());
        }
    }
    if tls_required {
        if !conn_tls {
            return Err("tls_missing".to_string());
        }
        if bind_identity {
            let claimed = node_id.trim();
            if claimed.is_empty()
                || peer_identities.is_empty()
                || !peer_identities.iter().any(|id| id == claimed)
            {
                return Err("tls_identity_mismatch".to_string());
            }
        }
    }
    Ok(())
}

/// Run all fail-closed ingress shape gates (status…cross-shard). Still not full dispatch.
fn check_ingress_shape_gates(msg_type: &str, data: &serde_json::Value) -> Result<(), String> {
    check_status_payload(msg_type, data)?;
    check_attestation_payload(msg_type, data)?;
    check_block_announce_payload(msg_type, data)?;
    check_get_block_payload(msg_type, data)?;
    check_get_blocks_payload(msg_type, data)?;
    check_get_block_by_hash_payload(msg_type, data)?;
    check_blocks_batch_payload(msg_type, data)?;
    check_wire_tx_payload(msg_type, data)?;
    check_mempool_batch_payload(msg_type, data)?;
    check_block_payload(msg_type, data)?;
    check_peers_list_payload(msg_type, data)?;
    check_validator_register_payload(msg_type, data)?;
    check_state_root_request_payload(msg_type, data)?;
    check_state_root_response_payload(msg_type, data)?;
    check_cross_shard_tx_payload(msg_type, data)?;
    check_cross_shard_ack_payload(msg_type, data)?;
    check_shard_migration_payload(msg_type, data)?;
    Ok(())
}

fn decoded_ok_dict(
    py: Python<'_>,
    msg_type: &str,
    data: &serde_json::Value,
    nbytes: usize,
) -> PyResult<PyObject> {
    let dict = PyDict::new_bound(py);
    dict.set_item("ok", true)?;
    dict.set_item("eof", false)?;
    dict.set_item("type", msg_type)?;
    dict.set_item("nbytes", nbytes)?;
    let data_json = serde_json::to_string(data)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let data_obj = pyo3::types::PyModule::import_bound(py, "json")?
        .getattr("loads")?
        .call1((data_json,))?;
    dict.set_item("data", data_obj)?;
    Ok(dict.into_any().unbind())
}

fn messages_to_list(
    py: Python<'_>,
    batch: &[(String, serde_json::Value, usize)],
) -> PyResult<PyObject> {
    let list = PyList::empty_bound(py);
    for (msg_type, data, nbytes) in batch {
        let item = PyDict::new_bound(py);
        item.set_item("type", msg_type)?;
        item.set_item("nbytes", *nbytes)?;
        let data_json = serde_json::to_string(data)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let data_obj = pyo3::types::PyModule::import_bound(py, "json")?
            .getattr("loads")?
            .call1((data_json,))?;
        item.set_item("data", data_obj)?;
        list.append(item)?;
    }
    Ok(list.into_any().unbind())
}

/// v1.3.116: ordered shell events for Python `_message_loop` (not full dispatch).
enum LoopShellEvent {
    Dispatch {
        msg_type: String,
        data: serde_json::Value,
        nbytes: usize,
    },
    Strike {
        reason: String,
    },
    Keepalive {
        touches: u64,
    },
    Idle,
    Eof,
}

fn loop_events_to_list(py: Python<'_>, events: &[LoopShellEvent]) -> PyResult<PyObject> {
    let list = PyList::empty_bound(py);
    for ev in events {
        let item = PyDict::new_bound(py);
        match ev {
            LoopShellEvent::Dispatch {
                msg_type,
                data,
                nbytes,
            } => {
                item.set_item("action", "dispatch")?;
                item.set_item("type", msg_type)?;
                item.set_item("nbytes", *nbytes)?;
                let data_json = serde_json::to_string(data)
                    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
                let data_obj = pyo3::types::PyModule::import_bound(py, "json")?
                    .getattr("loads")?
                    .call1((data_json,))?;
                item.set_item("data", data_obj)?;
            }
            LoopShellEvent::Strike { reason } => {
                item.set_item("action", "strike")?;
                item.set_item("reason", reason)?;
            }
            LoopShellEvent::Keepalive { touches } => {
                item.set_item("action", "keepalive")?;
                item.set_item("touches", *touches)?;
            }
            LoopShellEvent::Idle => {
                item.set_item("action", "idle")?;
            }
            LoopShellEvent::Eof => {
                item.set_item("action", "eof")?;
            }
        }
        list.append(item)?;
    }
    Ok(list.into_any().unbind())
}

fn tls_err(e: impl std::fmt::Display) -> String {
    format!("p2p_transport_tls:{e}")
}

/// Extract CN + SAN DNS/URI identities from an X.509 DER certificate (v1.3.97).
fn extract_cert_identities(der: &[u8]) -> Vec<String> {
    use x509_parser::extensions::{GeneralName, ParsedExtension};
    use x509_parser::prelude::*;

    let mut out: HashSet<String> = HashSet::new();
    let Ok((_, cert)) = X509Certificate::from_der(der) else {
        return Vec::new();
    };
    for attr in cert.subject().iter_common_name() {
        if let Ok(v) = attr.as_str() {
            let s = v.trim();
            if !s.is_empty() {
                out.insert(s.to_string());
            }
        }
    }
    for ext in cert.extensions() {
        if let ParsedExtension::SubjectAlternativeName(san) = ext.parsed_extension() {
            for name in &san.general_names {
                match name {
                    GeneralName::DNSName(dns) => {
                        let s = dns.trim();
                        if !s.is_empty() {
                            out.insert(s.to_string());
                        }
                    }
                    GeneralName::URI(uri) => {
                        let v = uri.trim();
                        if v.is_empty() {
                            continue;
                        }
                        out.insert(v.to_string());
                        if v.contains('/') {
                            if let Some(last) = v.trim_end_matches('/').rsplit('/').next() {
                                if !last.is_empty() {
                                    out.insert(last.to_string());
                                }
                            }
                        }
                    }
                    _ => {}
                }
            }
        }
    }
    let mut list: Vec<String> = out.into_iter().collect();
    list.sort();
    list
}

fn set_timeouts(stream: &TcpStream, timeout_ms: u64) -> Result<(), String> {
    let dur = if timeout_ms == 0 {
        None
    } else {
        Some(Duration::from_millis(timeout_ms))
    };
    stream.set_read_timeout(dur).map_err(io_err)?;
    stream.set_write_timeout(dur).map_err(io_err)?;
    Ok(())
}

fn peer_addr_string(stream: &TcpStream) -> String {
    stream
        .peer_addr()
        .map(|a| a.to_string())
        .unwrap_or_default()
}

fn split_host_port(addr: &str) -> (String, u16) {
    if let Ok(sa) = addr.parse::<SocketAddr>() {
        return (sa.ip().to_string(), sa.port());
    }
    if let Some((h, p)) = addr.rsplit_once(':') {
        if let Ok(port) = p.parse::<u16>() {
            return (h.trim_matches(|c| c == '[' || c == ']').to_string(), port);
        }
    }
    (addr.to_string(), 0)
}

fn load_certs(path: &Path) -> Result<Vec<CertificateDer<'static>>, String> {
    let mut reader = BufReader::new(File::open(path).map_err(io_err)?);
    let certs: Vec<_> = rustls_pemfile::certs(&mut reader)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    if certs.is_empty() {
        return Err(format!("p2p_transport_tls:no_certs:{}", path.display()));
    }
    Ok(certs)
}

fn load_private_key(path: &Path) -> Result<PrivateKeyDer<'static>, String> {
    let mut reader = BufReader::new(File::open(path).map_err(io_err)?);
    let mut keys = rustls_pemfile::pkcs8_private_keys(&mut reader)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    if let Some(k) = keys.pop() {
        return Ok(PrivateKeyDer::Pkcs8(k));
    }
    let mut reader = BufReader::new(File::open(path).map_err(io_err)?);
    let mut keys = rustls_pemfile::rsa_private_keys(&mut reader)
        .collect::<Result<Vec<_>, _>>()
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    if let Some(k) = keys.pop() {
        return Ok(PrivateKeyDer::Pkcs1(k));
    }
    Err(format!("p2p_transport_tls:no_private_key:{}", path.display()))
}

fn load_root_store(ca_path: &Path) -> Result<RootCertStore, String> {
    let mut roots = RootCertStore::empty();
    for cert in load_certs(ca_path)? {
        roots
            .add(cert)
            .map_err(|e| tls_err(format!("ca_add:{e}")))?;
    }
    if roots.is_empty() {
        return Err(format!("p2p_transport_tls:empty_ca:{}", ca_path.display()));
    }
    Ok(roots)
}

/// Verify peer cert against CA roots; skip hostname (matches Python check_hostname=False).
#[derive(Debug)]
struct CaOnlyServerVerifier {
    roots: Arc<RootCertStore>,
}

impl ServerCertVerifier for CaOnlyServerVerifier {
    fn verify_server_cert(
        &self,
        end_entity: &CertificateDer<'_>,
        intermediates: &[CertificateDer<'_>],
        _server_name: &ServerName<'_>,
        _ocsp_response: &[u8],
        now: UnixTime,
    ) -> Result<ServerCertVerified, TlsError> {
        let cert = rustls::server::ParsedCertificate::try_from(end_entity)?;
        rustls::client::verify_server_cert_signed_by_trust_anchor(
            &cert,
            &self.roots,
            intermediates,
            now,
            rustls::crypto::ring::default_provider()
                .signature_verification_algorithms
                .all,
        )?;
        Ok(ServerCertVerified::assertion())
    }

    fn verify_tls12_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, TlsError> {
        rustls::crypto::verify_tls12_signature(
            message,
            cert,
            dss,
            &rustls::crypto::ring::default_provider().signature_verification_algorithms,
        )
    }

    fn verify_tls13_signature(
        &self,
        message: &[u8],
        cert: &CertificateDer<'_>,
        dss: &DigitallySignedStruct,
    ) -> Result<HandshakeSignatureValid, TlsError> {
        rustls::crypto::verify_tls13_signature(
            message,
            cert,
            dss,
            &rustls::crypto::ring::default_provider().signature_verification_algorithms,
        )
    }

    fn supported_verify_schemes(&self) -> Vec<SignatureScheme> {
        rustls::crypto::ring::default_provider()
            .signature_verification_algorithms
            .supported_schemes()
    }
}

fn build_server_config(
    cert_path: &Path,
    key_path: &Path,
    ca_path: &Path,
    require_client_cert: bool,
) -> Result<Arc<ServerConfig>, String> {
    let certs = load_certs(cert_path)?;
    let key = load_private_key(key_path)?;
    let roots = load_root_store(ca_path)?;
    // Industrial default: always require client certs when TLS material is configured
    // (matches Python fail-closed CERT_REQUIRED).
    let _ = require_client_cert;
    let verifier = WebPkiClientVerifier::builder(Arc::new(roots))
        .build()
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    let mut cfg = ServerConfig::builder()
        .with_client_cert_verifier(verifier)
        .with_single_cert(certs, key)
        .map_err(|e| format!("p2p_transport_tls:{e}"))?;
    cfg.alpn_protocols.clear();
    Ok(Arc::new(cfg))
}

fn build_client_config(
    cert_path: Option<&Path>,
    key_path: Option<&Path>,
    ca_path: &Path,
) -> Result<Arc<ClientConfig>, String> {
    let roots = Arc::new(load_root_store(ca_path)?);
    let verifier = Arc::new(CaOnlyServerVerifier {
        roots: roots.clone(),
    });
    let builder = ClientConfig::builder().dangerous().with_custom_certificate_verifier(verifier);
    let mut cfg = match (cert_path, key_path) {
        (Some(c), Some(k)) if c.exists() && k.exists() => {
            let certs = load_certs(c)?;
            let key = load_private_key(k)?;
            builder
                .with_client_auth_cert(certs, key)
                .map_err(|e| format!("p2p_transport_tls:{e}"))?
        }
        _ => builder.with_no_client_auth(),
    };
    cfg.alpn_protocols.clear();
    Ok(Arc::new(cfg))
}

enum ConnStream {
    Plain(TcpStream),
    TlsServer(StreamOwned<ServerConnection, TcpStream>),
    TlsClient(StreamOwned<ClientConnection, TcpStream>),
}

impl ConnStream {
    fn tcp_ref(&self) -> &TcpStream {
        match self {
            ConnStream::Plain(s) => s,
            ConnStream::TlsServer(s) => s.get_ref(),
            ConnStream::TlsClient(s) => s.get_ref(),
        }
    }

    fn peer_cert_fingerprint_sha256(&self) -> String {
        let Some(first) = self.peer_end_entity_der() else {
            return String::new();
        };
        hex::encode(Sha256::digest(&first))
    }

    fn peer_end_entity_der(&self) -> Option<Vec<u8>> {
        let certs = match self {
            ConnStream::Plain(_) => return None,
            ConnStream::TlsServer(s) => s.conn.peer_certificates(),
            ConnStream::TlsClient(s) => s.conn.peer_certificates(),
        };
        let chain = certs?;
        let first = chain.first()?;
        Some(first.as_ref().to_vec())
    }

    /// CN + SAN DNS/URI identities (parity with Python `peer_cert_identities`).
    fn peer_cert_identities(&self) -> Vec<String> {
        let Some(der) = self.peer_end_entity_der() else {
            return Vec::new();
        };
        extract_cert_identities(&der)
    }

    fn shutdown(&mut self) {
        match self {
            ConnStream::Plain(s) => {
                let _ = s.shutdown(Shutdown::Both);
            }
            ConnStream::TlsServer(s) => {
                let _ = s.flush();
                let _ = s.get_ref().shutdown(Shutdown::Both);
            }
            ConnStream::TlsClient(s) => {
                let _ = s.flush();
                let _ = s.get_ref().shutdown(Shutdown::Both);
            }
        }
    }
}

impl Read for ConnStream {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        match self {
            ConnStream::Plain(s) => s.read(buf),
            ConnStream::TlsServer(s) => s.read(buf),
            ConnStream::TlsClient(s) => s.read(buf),
        }
    }
}

impl Write for ConnStream {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        match self {
            ConnStream::Plain(s) => s.write(buf),
            ConnStream::TlsServer(s) => s.write(buf),
            ConnStream::TlsClient(s) => s.write(buf),
        }
    }

    fn flush(&mut self) -> std::io::Result<()> {
        match self {
            ConnStream::Plain(s) => s.flush(),
            ConnStream::TlsServer(s) => s.flush(),
            ConnStream::TlsClient(s) => s.flush(),
        }
    }
}

/// One TCP(+TLS) peer connection with fail-closed NDJSON framing.
#[pyclass]
pub struct P2PNativeConn {
    stream: ConnStream,
    framer: P2PLineFramer,
    pending: Vec<Vec<u8>>,
    max_bytes: usize,
    peer_host: String,
    peer_port: u16,
    bytes_read: u64,
    bytes_written: u64,
    lines_read: u64,
    auto_pongs: u64,
    /// v1.3.99: ping replies + inbound pongs consumed under `auto_pong`.
    auto_keeps: u64,
    io_timeout_ms: u64,
    /// v1.3.103: after successful Python handshake policy, reject mid-session HS.
    session_established: bool,
    closed: bool,
    tls: bool,
}

impl P2PNativeConn {
    fn from_stream(stream: ConnStream, max_bytes: usize, tls: bool) -> Self {
        let peer = peer_addr_string(stream.tcp_ref());
        let (host, port) = split_host_port(&peer);
        Self {
            stream,
            framer: P2PLineFramer::rust_new(max_bytes),
            pending: Vec::new(),
            max_bytes: clamp_max_bytes(max_bytes),
            peer_host: host,
            peer_port: port,
            bytes_read: 0,
            bytes_written: 0,
            lines_read: 0,
            auto_pongs: 0,
            auto_keeps: 0,
            io_timeout_ms: 0,
            session_established: false,
            closed: false,
            tls,
        }
    }

    fn from_plain(stream: TcpStream, max_bytes: usize, timeout_ms: u64) -> Result<Self, String> {
        let ms = timeout_ms.max(1);
        set_timeouts(&stream, ms)?;
        let mut conn = Self::from_stream(ConnStream::Plain(stream), max_bytes, false);
        conn.io_timeout_ms = ms;
        Ok(conn)
    }

    /// If `auto_pong`: reply to ping / silently consume pong; Ok(true) = consumed.
    /// Validates housekeeping payload before reply/consume (v1.3.100).
    fn maybe_auto_pong(
        &mut self,
        msg_type: &str,
        data: &serde_json::Value,
        auto_pong: bool,
    ) -> Result<bool, String> {
        if !auto_pong {
            return Ok(false);
        }
        if msg_type == "pong" {
            check_housekeeping(msg_type, data)?;
            // Inbound pong is keepalive only — drop before Python dispatch.
            self.auto_keeps = self.auto_keeps.saturating_add(1);
            return Ok(true);
        }
        if msg_type != "ping" {
            return Ok(false);
        }
        check_housekeeping(msg_type, data)?;
        let ts = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs_f64())
            .unwrap_or(0.0);
        let data_json = format!(r#"{{"ts":{ts}}}"#);
        let payload = encode_p2p_wire_message_inner("pong", &data_json)?;
        if payload.len() > self.max_bytes {
            return Err("p2p_line_too_large".to_string());
        }
        self.write_inner(&payload)?;
        self.auto_pongs = self.auto_pongs.saturating_add(1);
        self.auto_keeps = self.auto_keeps.saturating_add(1);
        Ok(true)
    }

    fn read_line_inner(&mut self, chunk_sz: usize) -> Result<Option<Vec<u8>>, String> {
        if self.closed {
            return Ok(None);
        }
        if let Some(line) = self.pending.first().cloned() {
            self.pending.remove(0);
            return Ok(Some(line));
        }
        let mut buf = vec![0u8; chunk_sz.max(1024)];
        loop {
            match self.stream.read(&mut buf) {
                Ok(0) => {
                    if self.framer.pending_len_rust() > 0 {
                        self.framer.clear_rust();
                        return Err("p2p_line_incomplete".to_string());
                    }
                    self.closed = true;
                    return Ok(None);
                }
                Ok(n) => {
                    self.bytes_read = self.bytes_read.saturating_add(n as u64);
                    match self.framer.rust_feed(&buf[..n]) {
                        Ok(lines) => {
                            if lines.is_empty() {
                                continue;
                            }
                            let mut iter = lines.into_iter();
                            let first = iter.next().unwrap();
                            self.pending.extend(iter);
                            self.lines_read = self.lines_read.saturating_add(1);
                            return Ok(Some(first));
                        }
                        Err(reason) => return Err(reason),
                    }
                }
                Err(e)
                    if e.kind() == std::io::ErrorKind::WouldBlock
                        || e.kind() == std::io::ErrorKind::TimedOut =>
                {
                    return Err("p2p_transport_timeout".to_string());
                }
                Err(e) => {
                    self.closed = true;
                    return Err(io_err(e));
                }
            }
        }
    }

    fn write_inner(&mut self, data: &[u8]) -> Result<usize, String> {
        if self.closed {
            return Err("p2p_transport_closed".to_string());
        }
        match self.stream.write_all(data) {
            Ok(()) => {
                self.bytes_written = self.bytes_written.saturating_add(data.len() as u64);
                let _ = self.stream.flush();
                Ok(data.len())
            }
            Err(e)
                if e.kind() == std::io::ErrorKind::WouldBlock
                    || e.kind() == std::io::ErrorKind::TimedOut =>
            {
                Err("p2p_transport_timeout".to_string())
            }
            Err(e) => {
                self.closed = true;
                Err(io_err(e))
            }
        }
    }

    /// One framed line → decoded envelope (or EOF / error).
    fn read_one_decoded(
        &mut self,
        chunk_sz: usize,
        allowed: Option<&HashSet<String>>,
    ) -> Result<Option<(String, serde_json::Value, usize)>, String> {
        match self.read_line_inner(chunk_sz) {
            Ok(None) => Ok(None),
            Ok(Some(line)) => {
                let nbytes = line.len();
                let (msg_type, data) =
                    parse_p2p_wire_line_inner(&line, self.max_bytes, allowed)?;
                Ok(Some((msg_type, data, nbytes)))
            }
            Err(reason) => Err(reason),
        }
    }
}

#[pymethods]
impl P2PNativeConn {
    /// Outbound connect (plain TCP or rustls TLS when paths set).
    #[staticmethod]
    #[pyo3(signature = (
        host,
        port,
        max_bytes=DEFAULT_MAX_P2P_LINE_BYTES,
        timeout_ms=10_000,
        cert_path=None,
        key_path=None,
        ca_path=None
    ))]
    fn connect(
        py: Python<'_>,
        host: &str,
        port: u16,
        max_bytes: usize,
        timeout_ms: u64,
        cert_path: Option<String>,
        key_path: Option<String>,
        ca_path: Option<String>,
    ) -> PyResult<Self> {
        let addr = format!("{host}:{port}");
        let timeout = Duration::from_millis(timeout_ms.max(1));
        let use_tls = ca_path.as_ref().map(|p| !p.is_empty()).unwrap_or(false);
        let host_owned = host.to_string();
        let cert_path = cert_path.filter(|s| !s.is_empty());
        let key_path = key_path.filter(|s| !s.is_empty());
        let ca_path = ca_path.filter(|s| !s.is_empty());

        py.allow_threads(|| {
            let sock_addr = addr
                .to_socket_addrs()
                .map_err(|e| e.to_string())?
                .next()
                .ok_or_else(|| "p2p_transport_resolve_failed".to_string())?;
            let tcp = TcpStream::connect_timeout(&sock_addr, timeout).map_err(|e| e.to_string())?;
            set_timeouts(&tcp, timeout_ms)?;
            if !use_tls {
                return P2PNativeConn::from_plain(tcp, max_bytes, timeout_ms);
            }
            let ca = Path::new(ca_path.as_ref().unwrap());
            let cfg = build_client_config(
                cert_path.as_ref().map(Path::new),
                key_path.as_ref().map(Path::new),
                ca,
            )?;
            // SNI placeholder — hostname verification disabled (CaOnlyServerVerifier).
            let server_name = ServerName::try_from(host_owned.as_str())
                .or_else(|_| ServerName::try_from("localhost"))
                .map_err(|e| format!("p2p_transport_tls:{e}"))?
                .to_owned();
            let conn = ClientConnection::new(cfg, server_name).map_err(|e| format!("p2p_transport_tls:{e}"))?;
            let mut tls = StreamOwned::new(conn, tcp);
            // Complete handshake eagerly.
            while tls.conn.is_handshaking() {
                tls.conn
                    .complete_io(&mut tls.sock)
                    .map_err(|e| format!("p2p_transport_tls:{e}"))?;
            }
            let mut native = P2PNativeConn::from_stream(
                ConnStream::TlsClient(tls),
                max_bytes,
                true,
            );
            native.io_timeout_ms = timeout_ms.max(1);
            Ok(native)
        })
        .map_err(pyo3::exceptions::PyOSError::new_err)
    }

    #[getter]
    fn peer_host(&self) -> &str {
        &self.peer_host
    }

    #[getter]
    fn peer_port(&self) -> u16 {
        self.peer_port
    }

    #[getter]
    fn max_bytes(&self) -> usize {
        self.max_bytes
    }

    #[getter]
    fn bytes_read(&self) -> u64 {
        self.bytes_read
    }

    #[getter]
    fn bytes_written(&self) -> u64 {
        self.bytes_written
    }

    #[getter]
    fn lines_read(&self) -> u64 {
        self.lines_read
    }

    #[getter]
    fn auto_pongs(&self) -> u64 {
        self.auto_pongs
    }

    #[getter]
    fn auto_keeps(&self) -> u64 {
        self.auto_keeps
    }

    #[getter]
    fn closed(&self) -> bool {
        self.closed
    }

    #[getter]
    fn tls(&self) -> bool {
        self.tls
    }

    #[getter]
    fn peer_cert_sha256(&self) -> String {
        self.stream.peer_cert_fingerprint_sha256()
    }

    /// Sorted CN + SAN DNS/URI identities from the peer end-entity cert (v1.3.97).
    #[getter]
    fn peer_cert_identities(&self) -> Vec<String> {
        self.stream.peer_cert_identities()
    }

    /// `{ok:true, line:bytes|None}` or `{ok:false, reason}`. None line = EOF.
    #[pyo3(signature = (chunk_sz=65536))]
    fn read_line(&mut self, py: Python<'_>, chunk_sz: usize) -> PyResult<PyObject> {
        let result = py.allow_threads(|| self.read_line_inner(chunk_sz));
        match result {
            Ok(Some(line)) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("line", PyBytes::new_bound(py, &line))?;
                dict.set_item("eof", false)?;
                Ok(dict.into_any().unbind())
            }
            Ok(None) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("line", py.None())?;
                dict.set_item("eof", true)?;
                Ok(dict.into_any().unbind())
            }
            Err(reason) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", reason)?;
                dict.set_item("line", py.None())?;
                dict.set_item("eof", false)?;
                Ok(dict.into_any().unbind())
            }
        }
    }

    /// Framed read + wire parse in one native call (v1.3.92).
    ///
    /// `{ok:true, type, data, nbytes, eof:false}` | `{ok:true, eof:true}` |
    /// `{ok:true, keepalive:true, type:"pong", ...}` after only keepalive skips |
    /// `{ok:false, reason, eof:false}`.
    /// v1.3.98: `auto_pong` replies to ping in-band and skips returning it.
    /// v1.3.99: also consumes inbound pong; empty keepalive → synthetic pong.
    /// v1.3.100: housekeeping payload gate before auto-keepalive / return.
    /// v1.3.103: mid-session handshake reject when `session_established`.
    /// v1.3.104: status payload gate (bad dict → `bad_status_payload`).
    /// v1.3.105: attestation shape gate (`bad_attestation_shape`).
    /// v1.3.106: new_block / get_block shape gates.
    /// v1.3.107: get_blocks / get_block_by_hash / blocks shape gates.
    /// v1.3.108: new_tx / mempool shape gates.
    /// v1.3.109: singular `block` payload gate (null = not-found).
    /// v1.3.110: peers / validator_register shape gates.
    /// v1.3.111: state_root_request / state_root_response shape gates.
    /// v1.3.112: cross_shard_tx / cross_shard_ack / shard_migration shape gates.
    #[pyo3(signature = (chunk_sz=65536, allowed_types=None, auto_pong=false))]
    fn read_message(
        &mut self,
        py: Python<'_>,
        chunk_sz: usize,
        allowed_types: Option<Vec<String>>,
        auto_pong: bool,
    ) -> PyResult<PyObject> {
        let allowed_set = allowed_types.map(|items| items.into_iter().collect::<HashSet<_>>());
        let keeps_before = self.auto_keeps;
        let result = py.allow_threads(|| -> Result<Option<(String, serde_json::Value, usize)>, String> {
            // Bound auto-keepalive skips so a ping/pong flood cannot spin forever.
            for _ in 0..64 {
                match self.read_one_decoded(chunk_sz, allowed_set.as_ref())? {
                    None => return Ok(None),
                    Some((msg_type, data, nbytes)) => {
                        check_mid_session_handshake(self.session_established, &msg_type)?;
                        check_ingress_shape_gates(&msg_type, &data)?;
                        // Early reject get_* always; ping/pong gated inside auto_pong path.
                        if msg_type == "get_mempool" || msg_type == "get_peers" {
                            check_housekeeping(&msg_type, &data)?;
                        }
                        if self.maybe_auto_pong(&msg_type, &data, auto_pong)? {
                            continue;
                        }
                        return Ok(Some((msg_type, data, nbytes)));
                    }
                }
            }
            Err("p2p_auto_pong_flood".to_string())
        });
        let keepalive_touches = self.auto_keeps.saturating_sub(keeps_before);
        match result {
            Ok(None) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("eof", true)?;
                dict.set_item("keepalive_touches", keepalive_touches)?;
                Ok(dict.into_any().unbind())
            }
            Ok(Some((msg_type, data, nbytes))) => {
                let obj = decoded_ok_dict(py, &msg_type, &data, nbytes)?;
                obj.bind(py)
                    .downcast::<PyDict>()?
                    .set_item("keepalive_touches", keepalive_touches)?;
                Ok(obj)
            }
            Err(reason) => {
                // Timeout after only keepalive frames → synthetic pong for last_seen touch.
                if reason == "p2p_transport_timeout" && keepalive_touches > 0 {
                    let data = serde_json::json!({});
                    let obj = decoded_ok_dict(py, "pong", &data, 0)?;
                    let d = obj.bind(py).downcast::<PyDict>()?;
                    d.set_item("keepalive", true)?;
                    d.set_item("keepalive_touches", keepalive_touches)?;
                    return Ok(obj);
                }
                let short = wire_fail_reason(&reason);
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", short)?;
                dict.set_item("eof", false)?;
                dict.set_item("keepalive_touches", keepalive_touches)?;
                Ok(dict.into_any().unbind())
            }
        }
    }

    /// Batch framed read + wire parse (v1.3.94).
    ///
    /// Reads up to `max_n` envelopes in one `allow_threads` call.
    /// Timeout after ≥1 message → success with partial batch (no idle).
    /// Timeout with empty batch → `{ok:false, reason:p2p_transport_timeout}`.
    /// Timeout with only keepalive skips → `{ok:true, messages:[], keepalive_touches}`.
    /// v1.3.98: `auto_pong` replies to ping in-band and omits them from `messages`.
    /// v1.3.99: also consumes inbound pong; reports `keepalive_touches`.
    /// v1.3.100: housekeeping payload gate before auto-keepalive / return.
    /// v1.3.103: mid-session handshake reject when `session_established`.
    /// v1.3.104: status payload gate (bad dict → `bad_status_payload`).
    /// v1.3.105: attestation shape gate (`bad_attestation_shape`).
    /// v1.3.106: new_block / get_block shape gates.
    /// v1.3.107: get_blocks / get_block_by_hash / blocks shape gates.
    /// v1.3.108: new_tx / mempool shape gates.
    /// v1.3.109: singular `block` payload gate (null = not-found).
    /// v1.3.110: peers / validator_register shape gates.
    /// v1.3.111: state_root_request / state_root_response shape gates.
    /// v1.3.112: cross_shard_tx / cross_shard_ack / shard_migration shape gates.
    ///
    /// `{ok:true, messages:[{type,data,nbytes},...], eof:bool, auto_pongs, keepalive_touches}` |
    /// `{ok:false, reason, messages:[...], eof:false, ...}`.
    #[pyo3(signature = (max_n=8, chunk_sz=65536, allowed_types=None, auto_pong=false))]
    fn read_messages(
        &mut self,
        py: Python<'_>,
        max_n: usize,
        chunk_sz: usize,
        allowed_types: Option<Vec<String>>,
        auto_pong: bool,
    ) -> PyResult<PyObject> {
        let max_n = max_n.clamp(NATIVE_BATCH_MIN, NATIVE_BATCH_MAX);
        let allowed_set = allowed_types.map(|items| items.into_iter().collect::<HashSet<_>>());
        let pongs_before = self.auto_pongs;
        let keeps_before = self.auto_keeps;
        let result = py.allow_threads(|| {
            let mut batch: Vec<(String, serde_json::Value, usize)> = Vec::new();
            let mut eof = false;
            let mut err: Option<String> = None;
            let mut skips = 0u32;
            while batch.len() < max_n {
                match self.read_one_decoded(chunk_sz, allowed_set.as_ref()) {
                    Ok(None) => {
                        eof = true;
                        break;
                    }
                    Ok(Some((msg_type, data, nbytes))) => {
                        if let Err(reason) =
                            check_mid_session_handshake(self.session_established, &msg_type)
                        {
                            err = Some(reason);
                            break;
                        }
                        if let Err(reason) = check_ingress_shape_gates(&msg_type, &data) {
                            err = Some(reason);
                            break;
                        }
                        if msg_type == "get_mempool" || msg_type == "get_peers" {
                            if let Err(reason) = check_housekeeping(&msg_type, &data) {
                                err = Some(reason);
                                break;
                            }
                        }
                        match self.maybe_auto_pong(&msg_type, &data, auto_pong) {
                            Ok(true) => {
                                skips = skips.saturating_add(1);
                                if skips >= 64 {
                                    err = Some("p2p_auto_pong_flood".to_string());
                                    break;
                                }
                                continue;
                            }
                            Ok(false) => batch.push((msg_type, data, nbytes)),
                            Err(reason) => {
                                err = Some(reason);
                                break;
                            }
                        }
                    }
                    Err(reason) => {
                        if reason == "p2p_transport_timeout" && !batch.is_empty() {
                            break;
                        }
                        // Timeout with only keepalive consumed → success empty batch.
                        if reason == "p2p_transport_timeout" && batch.is_empty() && skips > 0 {
                            break;
                        }
                        err = Some(reason);
                        break;
                    }
                }
            }
            (batch, eof, err)
        });
        let (batch, eof, err) = result;
        let auto_pongs = self.auto_pongs.saturating_sub(pongs_before);
        let keepalive_touches = self.auto_keeps.saturating_sub(keeps_before);
        if let Some(reason) = err {
            let short = wire_fail_reason(&reason);
            let dict = PyDict::new_bound(py);
            dict.set_item("ok", false)?;
            dict.set_item("reason", short)?;
            dict.set_item("eof", false)?;
            dict.set_item("auto_pongs", auto_pongs)?;
            dict.set_item("keepalive_touches", keepalive_touches)?;
            dict.set_item("messages", messages_to_list(py, &batch)?)?;
            return Ok(dict.into_any().unbind());
        }
        let dict = PyDict::new_bound(py);
        dict.set_item("ok", true)?;
        dict.set_item("eof", eof)?;
        dict.set_item("auto_pongs", auto_pongs)?;
        dict.set_item("keepalive_touches", keepalive_touches)?;
        dict.set_item("messages", messages_to_list(py, &batch)?)?;
        Ok(dict.into_any().unbind())
    }

    /// Ordered message-loop events (v1.3.116) — shell only, not full dispatch ownership.
    ///
    /// v1.3.117: attestation semantic gate (identity + sig) before `dispatch`.
    /// v1.3.118: optional `new_tx` signature gate (`expected_chain_id` + `require_tx_signatures`).
    /// Returns `{ok:true, events:[{action,...},...], eof:bool}` where actions are:
    /// `dispatch` | `strike` | `keepalive` | `idle` | `eof`.
    /// Valid messages before a hard reject are preserved as `dispatch` then `strike`.
    /// Application handlers / rate strikes / peer lifecycle remain Python.
    #[pyo3(signature = (
        max_n=8,
        chunk_sz=65536,
        allowed_types=None,
        auto_pong=false,
        expected_chain_id=None,
        require_tx_signatures=false
    ))]
    fn read_message_loop_events(
        &mut self,
        py: Python<'_>,
        max_n: usize,
        chunk_sz: usize,
        allowed_types: Option<Vec<String>>,
        auto_pong: bool,
        expected_chain_id: Option<i64>,
        require_tx_signatures: bool,
    ) -> PyResult<PyObject> {
        let max_n = max_n.clamp(NATIVE_BATCH_MIN, NATIVE_BATCH_MAX);
        let allowed_set = allowed_types.map(|items| items.into_iter().collect::<HashSet<_>>());
        let keeps_before = self.auto_keeps;
        let result = py.allow_threads(|| {
            let mut events: Vec<LoopShellEvent> = Vec::new();
            let mut dispatch_n = 0usize;
            let mut eof = false;
            let mut skips = 0u32;
            let mut terminal_strike: Option<String> = None;
            while dispatch_n < max_n {
                match self.read_one_decoded(chunk_sz, allowed_set.as_ref()) {
                    Ok(None) => {
                        eof = true;
                        events.push(LoopShellEvent::Eof);
                        break;
                    }
                    Ok(Some((msg_type, data, nbytes))) => {
                        if let Err(reason) =
                            check_mid_session_handshake(self.session_established, &msg_type)
                        {
                            terminal_strike = Some(reason);
                            break;
                        }
                        if let Err(reason) = check_ingress_shape_gates(&msg_type, &data) {
                            terminal_strike = Some(reason);
                            break;
                        }
                        // v1.3.117: semantic attestation verify before dispatch.
                        if let Err(reason) = check_attestation_semantics(&msg_type, &data) {
                            terminal_strike = Some(reason);
                            break;
                        }
                        // v1.3.118: new_tx signature-only semantic.
                        if let Err(reason) = check_wire_tx_semantics(
                            &msg_type,
                            &data,
                            expected_chain_id,
                            require_tx_signatures,
                        ) {
                            terminal_strike = Some(reason);
                            break;
                        }
                        // v1.3.119: mempool batch per-tx signature semantic.
                        if let Err(reason) = check_mempool_batch_semantics(
                            &msg_type,
                            &data,
                            expected_chain_id,
                            require_tx_signatures,
                        ) {
                            terminal_strike = Some(reason);
                            break;
                        }
                        // v1.3.120: new_block canonical-hash semantic.
                        if let Err(reason) = check_block_announce_semantics(&msg_type, &data) {
                            terminal_strike = Some(reason);
                            break;
                        }
                        // v1.3.121: blocks batch per-block canonical-hash semantic.
                        if let Err(reason) = check_blocks_batch_semantics(&msg_type, &data) {
                            terminal_strike = Some(reason);
                            break;
                        }
                        // v1.3.122: singular block response canonical-hash semantic.
                        if let Err(reason) = check_block_payload_semantics(&msg_type, &data) {
                            terminal_strike = Some(reason);
                            break;
                        }
                        // v1.3.123: state_root_response digest semantic.
                        if let Err(reason) =
                            check_state_root_response_semantics(&msg_type, &data)
                        {
                            terminal_strike = Some(reason);
                            break;
                        }
                        if msg_type == "get_mempool" || msg_type == "get_peers" {
                            if let Err(reason) = check_housekeeping(&msg_type, &data) {
                                terminal_strike = Some(reason);
                                break;
                            }
                        }
                        match self.maybe_auto_pong(&msg_type, &data, auto_pong) {
                            Ok(true) => {
                                skips = skips.saturating_add(1);
                                if skips >= 64 {
                                    terminal_strike = Some("p2p_auto_pong_flood".to_string());
                                    break;
                                }
                                continue;
                            }
                            Ok(false) => {
                                events.push(LoopShellEvent::Dispatch {
                                    msg_type,
                                    data,
                                    nbytes,
                                });
                                dispatch_n = dispatch_n.saturating_add(1);
                            }
                            Err(reason) => {
                                terminal_strike = Some(reason);
                                break;
                            }
                        }
                    }
                    Err(reason) => {
                        if reason == "p2p_transport_timeout" {
                            if dispatch_n > 0 {
                                break;
                            }
                            let touches = self.auto_keeps.saturating_sub(keeps_before);
                            if touches > 0 || skips > 0 {
                                events.push(LoopShellEvent::Keepalive {
                                    touches: touches.max(u64::from(skips)),
                                });
                            } else {
                                events.push(LoopShellEvent::Idle);
                            }
                            break;
                        }
                        terminal_strike = Some(reason);
                        break;
                    }
                }
            }
            if let Some(reason) = terminal_strike {
                events.push(LoopShellEvent::Strike {
                    reason: wire_fail_reason(&reason),
                });
            }
            (events, eof)
        });
        let (events, eof) = result;
        let keepalive_touches = self.auto_keeps.saturating_sub(keeps_before);
        let dict = PyDict::new_bound(py);
        dict.set_item("ok", true)?;
        dict.set_item("eof", eof)?;
        dict.set_item("keepalive_touches", keepalive_touches)?;
        dict.set_item("events", loop_events_to_list(py, &events)?)?;
        Ok(dict.into_any().unbind())
    }

    fn write(&mut self, py: Python<'_>, data: &[u8]) -> PyResult<usize> {
        let data = data.to_vec();
        py.allow_threads(|| self.write_inner(&data))
            .map_err(pyo3::exceptions::PyOSError::new_err)
    }

    /// Wire encode + write in one native call (v1.3.93).
    ///
    /// `{ok:true, nbytes}` | `{ok:false, reason}`.
    /// Egress rate-limit remains Python (`p2p_egress_prepare` / `admit_egress`).
    #[pyo3(signature = (msg_type, data_json="null", allowed_types=None))]
    fn write_message(
        &mut self,
        py: Python<'_>,
        msg_type: &str,
        data_json: &str,
        allowed_types: Option<Vec<String>>,
    ) -> PyResult<PyObject> {
        if let Some(allowed) = allowed_types.as_ref() {
            if !allowed.is_empty() && !allowed.iter().any(|t| t == msg_type) {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", format!("p2p_type_not_allowed:{msg_type}"))?;
                return Ok(dict.into_any().unbind());
            }
        }
        let msg_type = msg_type.to_string();
        let data_json = data_json.to_string();
        let max_bytes = self.max_bytes;
        let result = py.allow_threads(|| -> Result<usize, String> {
            let payload = encode_p2p_wire_message_inner(&msg_type, &data_json)?;
            if payload.len() > max_bytes {
                return Err("p2p_line_too_large".to_string());
            }
            self.write_inner(&payload)?;
            Ok(payload.len())
        });
        match result {
            Ok(nbytes) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("nbytes", nbytes)?;
                Ok(dict.into_any().unbind())
            }
            Err(reason) => {
                let short = wire_fail_reason(&reason);
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", short)?;
                Ok(dict.into_any().unbind())
            }
        }
    }

    /// Batch wire encode + write (v1.3.95).
    ///
    /// `items` is a list of `(msg_type, data_json)` tuples.
    /// `{ok:true, nbytes, count}` | `{ok:false, reason, written, count}`.
    #[pyo3(signature = (items, allowed_types=None))]
    fn write_messages(
        &mut self,
        py: Python<'_>,
        items: Vec<(String, String)>,
        allowed_types: Option<Vec<String>>,
    ) -> PyResult<PyObject> {
        if items.is_empty() {
            let dict = PyDict::new_bound(py);
            dict.set_item("ok", true)?;
            dict.set_item("nbytes", 0usize)?;
            dict.set_item("count", 0usize)?;
            return Ok(dict.into_any().unbind());
        }
        if items.len() > 64 {
            let dict = PyDict::new_bound(py);
            dict.set_item("ok", false)?;
            dict.set_item("reason", "p2p_batch_too_large")?;
            dict.set_item("written", 0usize)?;
            dict.set_item("count", 0usize)?;
            return Ok(dict.into_any().unbind());
        }
        let allowed_set: Option<HashSet<String>> =
            allowed_types.map(|items| items.into_iter().collect());
        let max_bytes = self.max_bytes;
        let result = py.allow_threads(|| -> Result<(usize, usize), (String, usize, usize)> {
            let mut total = 0usize;
            let mut written = 0usize;
            for (msg_type, data_json) in &items {
                if let Some(ref allowed) = allowed_set {
                    if !allowed.is_empty() && !allowed.contains(msg_type) {
                        return Err((
                            format!("p2p_type_not_allowed:{msg_type}"),
                            total,
                            written,
                        ));
                    }
                }
                let payload = encode_p2p_wire_message_inner(msg_type, data_json)
                    .map_err(|e| (e, total, written))?;
                if payload.len() > max_bytes {
                    return Err(("p2p_line_too_large".to_string(), total, written));
                }
                self.write_inner(&payload)
                    .map_err(|e| (e, total, written))?;
                total = total.saturating_add(payload.len());
                written = written.saturating_add(1);
            }
            Ok((total, written))
        });
        match result {
            Ok((nbytes, count)) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("nbytes", nbytes)?;
                dict.set_item("count", count)?;
                Ok(dict.into_any().unbind())
            }
            Err((reason, nbytes, written)) => {
                let short = wire_fail_reason(&reason);
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", short)?;
                dict.set_item("nbytes", nbytes)?;
                dict.set_item("written", written)?;
                dict.set_item("count", written)?;
                Ok(dict.into_any().unbind())
            }
        }
    }

    /// Batch write of already-encoded payloads (v1.3.95).
    ///
    /// For egress-prepare path: Python admits/encodes, then one native write hop.
    /// `{ok:true, nbytes, count}` | `{ok:false, reason, written, count}`.
    fn write_payloads(&mut self, py: Python<'_>, payloads: Vec<Vec<u8>>) -> PyResult<PyObject> {
        if payloads.is_empty() {
            let dict = PyDict::new_bound(py);
            dict.set_item("ok", true)?;
            dict.set_item("nbytes", 0usize)?;
            dict.set_item("count", 0usize)?;
            return Ok(dict.into_any().unbind());
        }
        if payloads.len() > 64 {
            let dict = PyDict::new_bound(py);
            dict.set_item("ok", false)?;
            dict.set_item("reason", "p2p_batch_too_large")?;
            dict.set_item("written", 0usize)?;
            dict.set_item("count", 0usize)?;
            return Ok(dict.into_any().unbind());
        }
        let result = py.allow_threads(|| -> Result<(usize, usize), (String, usize, usize)> {
            let mut total = 0usize;
            let mut written = 0usize;
            for payload in &payloads {
                self.write_inner(payload)
                    .map_err(|e| (e, total, written))?;
                total = total.saturating_add(payload.len());
                written = written.saturating_add(1);
            }
            Ok((total, written))
        });
        match result {
            Ok((nbytes, count)) => {
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("nbytes", nbytes)?;
                dict.set_item("count", count)?;
                Ok(dict.into_any().unbind())
            }
            Err((reason, nbytes, written)) => {
                let short = wire_fail_reason(&reason);
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", short)?;
                dict.set_item("nbytes", nbytes)?;
                dict.set_item("written", written)?;
                dict.set_item("count", written)?;
                Ok(dict.into_any().unbind())
            }
        }
    }

    /// Handshake I/O round-trip (v1.3.96).
    ///
    /// Initiator: write `handshake` + read expecting `handshake_ack`.
    /// Responder: read expecting `handshake` + write `handshake_ack`.
    ///
    /// v1.3.113: inbound handshake/ack shape gate (`bad_handshake_payload`).
    /// v1.3.115: optional policy fuse — chain_id + TLS identity (fingerprint allowlist stays Python).
    ///
    /// `{ok:true, type, data, nbytes}` | `{ok:false, reason}`.
    #[pyo3(signature = (
        initiator,
        our_data_json,
        chunk_sz=65536,
        expected_chain_id=None,
        tls_required=false,
        bind_identity=true
    ))]
    fn handshake_roundtrip(
        &mut self,
        py: Python<'_>,
        initiator: bool,
        our_data_json: &str,
        chunk_sz: usize,
        expected_chain_id: Option<i64>,
        tls_required: bool,
        bind_identity: bool,
    ) -> PyResult<PyObject> {
        let our_data_json = our_data_json.to_string();
        let max_bytes = self.max_bytes;
        let conn_tls = self.tls;
        let peer_identities = if tls_required && bind_identity {
            self.stream.peer_cert_identities()
        } else {
            Vec::new()
        };
        let allowed: HashSet<String> = ["handshake".into(), "handshake_ack".into()]
            .into_iter()
            .collect();
        let result = py.allow_threads(|| -> Result<(String, serde_json::Value, usize), String> {
            if initiator {
                let payload = encode_p2p_wire_message_inner("handshake", &our_data_json)?;
                if payload.len() > max_bytes {
                    return Err("p2p_line_too_large".to_string());
                }
                self.write_inner(&payload)?;
                match self.read_one_decoded(chunk_sz, Some(&allowed))? {
                    None => Err("p2p_handshake_eof".to_string()),
                    Some((msg_type, data, nbytes)) => {
                        if msg_type != "handshake_ack" {
                            return Err(format!("p2p_handshake_unexpected:{msg_type}"));
                        }
                        check_handshake_payload(&data)?;
                        check_handshake_policy(
                            &data,
                            expected_chain_id,
                            tls_required,
                            bind_identity,
                            conn_tls,
                            &peer_identities,
                        )?;
                        Ok((msg_type, data, nbytes))
                    }
                }
            } else {
                match self.read_one_decoded(chunk_sz, Some(&allowed))? {
                    None => Err("p2p_handshake_eof".to_string()),
                    Some((msg_type, data, nbytes)) => {
                        if msg_type != "handshake" {
                            return Err(format!("p2p_handshake_unexpected:{msg_type}"));
                        }
                        check_handshake_payload(&data)?;
                        check_handshake_policy(
                            &data,
                            expected_chain_id,
                            tls_required,
                            bind_identity,
                            conn_tls,
                            &peer_identities,
                        )?;
                        let payload =
                            encode_p2p_wire_message_inner("handshake_ack", &our_data_json)?;
                        if payload.len() > max_bytes {
                            return Err("p2p_line_too_large".to_string());
                        }
                        self.write_inner(&payload)?;
                        Ok((msg_type, data, nbytes))
                    }
                }
            }
        });
        match result {
            Ok((msg_type, data, nbytes)) => decoded_ok_dict(py, &msg_type, &data, nbytes),
            Err(reason) => {
                let short = wire_fail_reason(&reason);
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", short)?;
                Ok(dict.into_any().unbind())
            }
        }
    }

    fn set_timeout_ms(&mut self, timeout_ms: u64) -> PyResult<()> {
        let ms = timeout_ms.max(1);
        set_timeouts(self.stream.tcp_ref(), ms).map_err(pyo3::exceptions::PyOSError::new_err)?;
        self.io_timeout_ms = ms;
        Ok(())
    }

    #[getter]
    fn io_timeout_ms(&self) -> u64 {
        self.io_timeout_ms
    }

    /// v1.3.103: mark post-handshake session so mid-session HS frames are rejected.
    fn set_session_established(&mut self, established: bool) {
        self.session_established = established;
    }

    #[getter]
    fn session_established(&self) -> bool {
        self.session_established
    }

    fn shutdown(&mut self) {
        self.stream.shutdown();
        self.closed = true;
    }

    fn close(&mut self) {
        self.shutdown();
    }
}

/// TCP listener with optional rustls server config (v1.3.91).
#[pyclass]
pub struct P2PNativeListener {
    listener: TcpListener,
    max_bytes: usize,
    timeout_ms: u64,
    accepts: u64,
    accept_timeouts: u64,
    accept_errors: u64,
    tls_config: Option<Arc<ServerConfig>>,
}

#[pymethods]
impl P2PNativeListener {
    #[new]
    #[pyo3(signature = (
        host="0.0.0.0",
        port=5000,
        max_bytes=DEFAULT_MAX_P2P_LINE_BYTES,
        timeout_ms=1000,
        cert_path=None,
        key_path=None,
        ca_path=None,
        require_client_cert=true
    ))]
    fn new(
        host: &str,
        port: u16,
        max_bytes: usize,
        timeout_ms: u64,
        cert_path: Option<String>,
        key_path: Option<String>,
        ca_path: Option<String>,
        require_client_cert: bool,
    ) -> PyResult<Self> {
        use socket2::{Domain, Protocol, Socket, Type};
        let addr: SocketAddr = format!("{host}:{port}")
            .parse()
            .or_else(|_| {
                format!("{host}:{port}")
                    .to_socket_addrs()
                    .ok()
                    .and_then(|mut i| i.next())
                    .ok_or(())
            })
            .map_err(|_| {
                pyo3::exceptions::PyOSError::new_err(format!("bad bind addr {host}:{port}"))
            })?;
        let domain = if addr.is_ipv4() {
            Domain::IPV4
        } else {
            Domain::IPV6
        };
        let socket = Socket::new(domain, Type::STREAM, Some(Protocol::TCP))
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        socket
            .set_reuse_address(true)
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        socket
            .bind(&addr.into())
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(format!("bind {addr}: {e}")))?;
        socket
            .listen(128)
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        let timeout = Duration::from_millis(timeout_ms.max(1));
        socket
            .set_read_timeout(Some(timeout))
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        let listener: TcpListener = socket.into();

        let tls_config = match (cert_path, key_path, ca_path) {
            (Some(c), Some(k), Some(ca))
                if !c.is_empty() && !k.is_empty() && !ca.is_empty() =>
            {
                Some(
                    build_server_config(
                        Path::new(&c),
                        Path::new(&k),
                        Path::new(&ca),
                        require_client_cert,
                    )
                    .map_err(pyo3::exceptions::PyOSError::new_err)?,
                )
            }
            _ => None,
        };

        Ok(Self {
            listener,
            max_bytes: clamp_max_bytes(max_bytes),
            timeout_ms: timeout_ms.max(1),
            accepts: 0,
            accept_timeouts: 0,
            accept_errors: 0,
            tls_config,
        })
    }

    #[getter]
    fn local_addr(&self) -> String {
        self.listener
            .local_addr()
            .map(|a| a.to_string())
            .unwrap_or_default()
    }

    #[getter]
    fn timeout_ms(&self) -> u64 {
        self.timeout_ms
    }

    #[getter]
    fn accepts(&self) -> u64 {
        self.accepts
    }

    #[getter]
    fn accept_timeouts(&self) -> u64 {
        self.accept_timeouts
    }

    #[getter]
    fn accept_errors(&self) -> u64 {
        self.accept_errors
    }

    #[getter]
    fn tls(&self) -> bool {
        self.tls_config.is_some()
    }

    /// `{ok:true, conn:P2PNativeConn|None}` — None means timed out with no connection.
    fn accept(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        let result = py.allow_threads(|| self.listener.accept());
        match result {
            Ok((tcp, _addr)) => {
                let built = py.allow_threads(|| -> Result<P2PNativeConn, String> {
                    let ms = NATIVE_IO_TIMEOUT_DEFAULT_MS;
                    set_timeouts(&tcp, ms)?;
                    if let Some(cfg) = &self.tls_config {
                        let conn =
                            ServerConnection::new(cfg.clone()).map_err(|e| format!("p2p_transport_tls:{e}"))?;
                        let mut tls = StreamOwned::new(conn, tcp);
                        while tls.conn.is_handshaking() {
                            tls.conn
                                .complete_io(&mut tls.sock)
                                .map_err(|e| format!("p2p_transport_tls:{e}"))?;
                        }
                        let mut native = P2PNativeConn::from_stream(
                            ConnStream::TlsServer(tls),
                            self.max_bytes,
                            true,
                        );
                        native.io_timeout_ms = ms;
                        Ok(native)
                    } else {
                        P2PNativeConn::from_plain(tcp, self.max_bytes, ms)
                    }
                });
                match built {
                    Ok(conn) => {
                        self.accepts = self.accepts.saturating_add(1);
                        let dict = PyDict::new_bound(py);
                        dict.set_item("ok", true)?;
                        dict.set_item("conn", Py::new(py, conn)?)?;
                        Ok(dict.into_any().unbind())
                    }
                    Err(reason) => {
                        self.accept_errors = self.accept_errors.saturating_add(1);
                        let dict = PyDict::new_bound(py);
                        dict.set_item("ok", false)?;
                        dict.set_item("reason", reason)?;
                        Ok(dict.into_any().unbind())
                    }
                }
            }
            Err(e)
                if e.kind() == std::io::ErrorKind::WouldBlock
                    || e.kind() == std::io::ErrorKind::TimedOut =>
            {
                self.accept_timeouts = self.accept_timeouts.saturating_add(1);
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", true)?;
                dict.set_item("conn", py.None())?;
                Ok(dict.into_any().unbind())
            }
            Err(e) => {
                self.accept_errors = self.accept_errors.saturating_add(1);
                let dict = PyDict::new_bound(py);
                dict.set_item("ok", false)?;
                dict.set_item("reason", io_err(e))?;
                Ok(dict.into_any().unbind())
            }
        }
    }

    fn close(&mut self) {}
}

#[pyfunction]
fn p2p_native_transport_available() -> bool {
    true
}

#[pyfunction]
fn p2p_native_tls_available() -> bool {
    true
}

/// Clamp native read/write batch size (v1.3.101).
#[pyfunction]
fn p2p_native_clamp_batch(n: usize) -> usize {
    n.clamp(NATIVE_BATCH_MIN, NATIVE_BATCH_MAX)
}

/// Clamp native read chunk size in bytes (v1.3.101).
#[pyfunction]
fn p2p_native_clamp_chunk(n: usize) -> usize {
    n.clamp(NATIVE_CHUNK_MIN, NATIVE_CHUNK_MAX)
}

/// Clamp native socket I/O timeout in milliseconds (v1.3.102).
#[pyfunction]
fn p2p_native_clamp_timeout_ms(n: u64) -> u64 {
    n.clamp(NATIVE_IO_TIMEOUT_MIN_MS, NATIVE_IO_TIMEOUT_MAX_MS)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<P2PNativeConn>()?;
    m.add_class::<P2PNativeListener>()?;
    m.add("NATIVE_BATCH_DEFAULT", NATIVE_BATCH_DEFAULT)?;
    m.add("NATIVE_BATCH_MAX", NATIVE_BATCH_MAX)?;
    m.add("NATIVE_CHUNK_DEFAULT", NATIVE_CHUNK_DEFAULT)?;
    m.add("NATIVE_CHUNK_MAX", NATIVE_CHUNK_MAX)?;
    m.add("NATIVE_IO_TIMEOUT_DEFAULT_MS", NATIVE_IO_TIMEOUT_DEFAULT_MS)?;
    m.add("NATIVE_IO_TIMEOUT_MAX_MS", NATIVE_IO_TIMEOUT_MAX_MS)?;
    m.add_function(wrap_pyfunction!(p2p_native_transport_available, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_native_tls_available, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_native_clamp_batch, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_native_clamp_chunk, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_native_clamp_timeout_ms, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread;

    #[test]
    fn framed_roundtrip_local_plain() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .write_all(b"{\"type\":\"ping\",\"data\":null}\n")
                .unwrap();
            let mut buf = [0u8; 64];
            let n = stream.read(&mut buf).unwrap();
            assert!(n > 0);
        });
        let client = TcpStream::connect(addr).unwrap();
        let mut conn = P2PNativeConn::from_plain(client, 1024 * 1024, 5_000).unwrap();
        let line = conn.read_line_inner(4096).unwrap().unwrap();
        assert!(line.starts_with(b"{\"type\":\"ping\""));
        conn.write_inner(b"{\"type\":\"pong\",\"data\":null}\n").unwrap();
        handle.join().unwrap();
    }

    #[test]
    fn read_message_parses_envelope() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        let handle = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .write_all(b"{\"type\":\"status\",\"data\":{\"height\":7}}\n")
                .unwrap();
        });
        let client = TcpStream::connect(addr).unwrap();
        let mut conn = P2PNativeConn::from_plain(client, 1024 * 1024, 5_000).unwrap();
        let allowed = Some(
            ["status".to_string()].into_iter().collect::<HashSet<_>>(),
        );
        let (msg_type, data, nbytes) = {
            let line = conn.read_line_inner(4096).unwrap().unwrap();
            let nbytes = line.len();
            let (t, d) = parse_p2p_wire_line_inner(&line, conn.max_bytes, allowed.as_ref()).unwrap();
            (t, d, nbytes)
        };
        assert_eq!(msg_type, "status");
        assert_eq!(data["height"], 7);
        assert!(nbytes > 10);
        handle.join().unwrap();
    }

    #[test]
    fn housekeeping_payload_ok_parity() {
        assert!(housekeeping_payload_ok("ping", &serde_json::json!(null)));
        assert!(housekeeping_payload_ok("ping", &serde_json::json!({})));
        assert!(housekeeping_payload_ok("ping", &serde_json::json!({"ts": 1.5})));
        assert!(!housekeeping_payload_ok(
            "ping",
            &serde_json::json!({"ts": "x"})
        ));
        assert!(!housekeeping_payload_ok(
            "ping",
            &serde_json::json!({"ts": 1, "extra": 1})
        ));
        assert!(housekeeping_payload_ok("get_peers", &serde_json::json!({})));
        assert!(!housekeeping_payload_ok(
            "get_peers",
            &serde_json::json!({"x": 1})
        ));
        assert!(housekeeping_payload_ok(
            "status",
            &serde_json::json!({"height": 1})
        ));
    }

    #[test]
    fn mid_session_handshake_gate() {
        assert!(check_mid_session_handshake(false, "handshake").is_ok());
        assert!(check_mid_session_handshake(true, "status").is_ok());
        assert_eq!(
            check_mid_session_handshake(true, "handshake").unwrap_err(),
            "mid_session_handshake"
        );
        assert_eq!(
            check_mid_session_handshake(true, "handshake_ack").unwrap_err(),
            "mid_session_handshake"
        );
    }

    #[test]
    fn status_payload_gate_parity() {
        assert!(check_status_payload("status", &serde_json::json!(null)).is_ok());
        assert!(check_status_payload("status", &serde_json::json!({})).is_ok());
        assert!(check_status_payload(
            "status",
            &serde_json::json!({"height": 1, "head_hash": "ab"})
        )
        .is_ok());
        // Non-dict non-null: Python does not strike
        assert!(check_status_payload("status", &serde_json::json!([1, 2])).is_ok());
        assert_eq!(
            check_status_payload(
                "status",
                &serde_json::json!({"height": -1, "head_hash": "x"})
            )
            .unwrap_err(),
            "bad_status_payload"
        );
        assert!(check_status_payload("ping", &serde_json::json!({"height": -1})).is_ok());
    }

    #[test]
    fn attestation_payload_gate_parity() {
        assert_eq!(
            check_attestation_payload("attestation", &serde_json::json!(null)).unwrap_err(),
            "bad_attestation_shape"
        );
        assert_eq!(
            check_attestation_payload("attestation", &serde_json::json!({})).unwrap_err(),
            "bad_attestation_shape"
        );
        let good = serde_json::json!({
            "validator": "abs-1",
            "target_hash": "aa",
            "signature": "ab",
            "public_key": "cd"
        });
        assert!(check_attestation_payload("attestation", &good).is_ok());
        assert!(check_attestation_payload("status", &serde_json::json!({})).is_ok());
    }

    #[test]
    fn block_sync_payload_gate_parity() {
        assert_eq!(
            check_block_announce_payload("new_block", &serde_json::json!(null)).unwrap_err(),
            "bad_block_announce"
        );
        assert_eq!(
            check_block_announce_payload("new_block", &serde_json::json!({})).unwrap_err(),
            "bad_block_announce"
        );
        let good_announce = serde_json::json!({"height": 1, "hash": "aa"});
        assert!(check_block_announce_payload("new_block", &good_announce).is_ok());
        assert!(check_block_announce_payload("status", &serde_json::json!({})).is_ok());

        assert_eq!(
            check_get_block_payload("get_block", &serde_json::json!(null)).unwrap_err(),
            "bad_get_block"
        );
        assert_eq!(
            check_get_block_payload("get_block", &serde_json::json!({"height": -1})).unwrap_err(),
            "bad_get_block"
        );
        assert!(check_get_block_payload("get_block", &serde_json::json!(7)).is_ok());
        assert!(check_get_block_payload("get_block", &serde_json::json!({"height": 3})).is_ok());
        assert!(check_get_block_payload("new_block", &serde_json::json!(null)).is_ok());
    }

    #[test]
    fn block_fetch_payload_gate_parity() {
        assert_eq!(
            check_get_blocks_payload("get_blocks", &serde_json::json!(null)).unwrap_err(),
            "bad_get_blocks"
        );
        assert_eq!(
            check_get_blocks_payload(
                "get_blocks",
                &serde_json::json!({"from_height": 5, "to_height": 1})
            )
            .unwrap_err(),
            "bad_get_blocks"
        );
        assert!(check_get_blocks_payload(
            "get_blocks",
            &serde_json::json!({"from_height": 0, "to_height": 2})
        )
        .is_ok());

        assert_eq!(
            check_get_block_by_hash_payload("get_block_by_hash", &serde_json::json!("")).unwrap_err(),
            "bad_get_block_by_hash"
        );
        assert!(check_get_block_by_hash_payload(
            "get_block_by_hash",
            &serde_json::json!({"hash": "aa"})
        )
        .is_ok());

        assert_eq!(
            check_blocks_batch_payload("blocks", &serde_json::json!({})).unwrap_err(),
            "bad_blocks_batch"
        );
        assert_eq!(
            check_blocks_batch_payload("blocks", &serde_json::json!([{}])).unwrap_err(),
            "bad_blocks_batch"
        );
        assert!(check_blocks_batch_payload("blocks", &serde_json::json!([])).is_ok());
        assert!(check_blocks_batch_payload(
            "blocks",
            &serde_json::json!([{"height": 1, "hash": "aa"}])
        )
        .is_ok());
        assert!(check_get_blocks_payload("new_block", &serde_json::json!(null)).is_ok());
    }

    #[test]
    fn tx_gossip_payload_gate_parity() {
        assert_eq!(
            check_wire_tx_payload("new_tx", &serde_json::json!(null)).unwrap_err(),
            "bad_wire_tx"
        );
        assert_eq!(
            check_wire_tx_payload("new_tx", &serde_json::json!({})).unwrap_err(),
            "bad_wire_tx"
        );
        let good_tx = serde_json::json!({"from": "alice", "to": "bob"});
        assert!(check_wire_tx_payload("new_tx", &good_tx).is_ok());
        assert!(check_wire_tx_payload("mempool", &good_tx).is_ok());

        assert_eq!(
            check_mempool_batch_payload("mempool", &serde_json::json!(null)).unwrap_err(),
            "bad_mempool_batch"
        );
        assert_eq!(
            check_mempool_batch_payload("mempool", &serde_json::json!({"transactions": [{}]}))
                .unwrap_err(),
            "bad_mempool_batch"
        );
        assert!(check_mempool_batch_payload(
            "mempool",
            &serde_json::json!({"transactions": []})
        )
        .is_ok());
        assert!(check_mempool_batch_payload(
            "mempool",
            &serde_json::json!({"transactions": [{"from": "a", "to": "b"}]})
        )
        .is_ok());
    }

    #[test]
    fn singular_block_payload_gate_parity() {
        assert!(check_block_payload("block", &serde_json::json!(null)).is_ok());
        assert_eq!(
            check_block_payload("block", &serde_json::json!({})).unwrap_err(),
            "bad_block_payload"
        );
        assert_eq!(
            check_block_payload("block", &serde_json::json!([1, 2])).unwrap_err(),
            "bad_block_payload"
        );
        assert!(check_block_payload(
            "block",
            &serde_json::json!({"height": 1, "hash": "aa"})
        )
        .is_ok());
        assert!(check_block_payload("new_block", &serde_json::json!({})).is_ok());
    }

    #[test]
    fn peer_discovery_payload_gate_parity() {
        assert_eq!(
            check_peers_list_payload("peers", &serde_json::json!(null)).unwrap_err(),
            "bad_peers_list"
        );
        assert_eq!(
            check_peers_list_payload("peers", &serde_json::json!(["bad"])).unwrap_err(),
            "bad_peers_list"
        );
        assert!(check_peers_list_payload("peers", &serde_json::json!([])).is_ok());
        assert!(check_peers_list_payload(
            "peers",
            &serde_json::json!(["127.0.0.1:5000"])
        )
        .is_ok());

        assert_eq!(
            check_validator_register_payload("validator_register", &serde_json::json!({}))
                .unwrap_err(),
            "bad_validator_register"
        );
        assert_eq!(
            check_validator_register_payload(
                "validator_register",
                &serde_json::json!({"address": "a", "stake": -1.0})
            )
            .unwrap_err(),
            "bad_validator_register"
        );
        assert!(check_validator_register_payload(
            "validator_register",
            &serde_json::json!({"address": "abs1", "stake": 1.0})
        )
        .is_ok());
        assert!(check_peers_list_payload("status", &serde_json::json!({})).is_ok());
    }

    #[test]
    fn state_root_payload_gate_parity() {
        assert_eq!(
            check_state_root_request_payload("state_root_request", &serde_json::json!(null))
                .unwrap_err(),
            "bad_state_root_request"
        );
        assert_eq!(
            check_state_root_request_payload(
                "state_root_request",
                &serde_json::json!({"height": -1})
            )
            .unwrap_err(),
            "bad_state_root_request"
        );
        assert!(check_state_root_request_payload(
            "state_root_request",
            &serde_json::json!({"height": 3})
        )
        .is_ok());

        assert_eq!(
            check_state_root_response_payload("state_root_response", &serde_json::json!(null))
                .unwrap_err(),
            "bad_state_root_response"
        );
        assert_eq!(
            check_state_root_response_payload(
                "state_root_response",
                &serde_json::json!({"height": -1})
            )
            .unwrap_err(),
            "bad_state_root_response"
        );
        assert!(check_state_root_response_payload(
            "state_root_response",
            &serde_json::json!({"height": 1, "state_root": "aa", "head_hash": "bb"})
        )
        .is_ok());
        assert!(check_state_root_request_payload("peers", &serde_json::json!(null)).is_ok());
    }

    #[test]
    fn cross_shard_payload_gate_parity() {
        assert_eq!(
            check_cross_shard_tx_payload("cross_shard_tx", &serde_json::json!({})).unwrap_err(),
            "bad_cross_shard_tx"
        );
        let good_tx = serde_json::json!({
            "tx_id": "t1",
            "from_shard": 0,
            "to_shard": 1,
            "from_addr": "a",
            "to_addr": "b",
            "amount": 1.0
        });
        assert!(check_cross_shard_tx_payload("cross_shard_tx", &good_tx).is_ok());

        assert_eq!(
            check_cross_shard_ack_payload("cross_shard_ack", &serde_json::json!({})).unwrap_err(),
            "bad_cross_shard_ack"
        );
        assert!(check_cross_shard_ack_payload(
            "cross_shard_ack",
            &serde_json::json!({"tx_id": "t1"})
        )
        .is_ok());

        assert_eq!(
            check_shard_migration_payload("shard_migration", &serde_json::json!({})).unwrap_err(),
            "bad_shard_migration"
        );
        assert!(check_shard_migration_payload(
            "shard_migration",
            &serde_json::json!({
                "type": "shard_migration",
                "address": "a",
                "from_shard": 0,
                "to_shard": 1,
                "balance": 1.0
            })
        )
        .is_ok());
        assert!(check_cross_shard_tx_payload("peers", &serde_json::json!({})).is_ok());
    }

    #[test]
    fn handshake_payload_gate_parity() {
        assert_eq!(
            check_handshake_payload(&serde_json::json!(null)).unwrap_err(),
            "bad_handshake_payload"
        );
        assert_eq!(
            check_handshake_payload(&serde_json::json!({})).unwrap_err(),
            "bad_handshake_payload"
        );
        assert_eq!(
            check_handshake_payload(&serde_json::json!({"chain_id": -1})).unwrap_err(),
            "bad_handshake_payload"
        );
        // Explicit rejection ack is shape-ok (accepted=false).
        assert!(check_handshake_payload(&serde_json::json!({"accepted": false})).is_ok());
        assert!(check_handshake_payload(&serde_json::json!({
            "chain_id": 1,
            "height": 0,
            "head_hash": "aa",
            "node_id": "n1",
            "p2p_port": 5000
        }))
        .is_ok());
    }

    #[test]
    fn handshake_policy_gate_parity() {
        let good = serde_json::json!({
            "chain_id": 778888,
            "height": 0,
            "head_hash": "aa",
            "node_id": "node-a",
            "p2p_port": 5000
        });
        assert!(check_handshake_policy(
            &good,
            Some(778888),
            false,
            false,
            false,
            &[]
        )
        .is_ok());
        assert_eq!(
            check_handshake_policy(&good, Some(1), false, false, false, &[])
                .unwrap_err(),
            "chain_id_mismatch"
        );
        assert_eq!(
            check_handshake_policy(
                &serde_json::json!({"accepted": false}),
                Some(1),
                false,
                false,
                false,
                &[]
            )
            .unwrap_err(),
            "handshake_rejected"
        );
        assert_eq!(
            check_handshake_policy(&good, Some(778888), true, false, false, &[])
                .unwrap_err(),
            "tls_missing"
        );
        assert_eq!(
            check_handshake_policy(
                &good,
                Some(778888),
                true,
                true,
                true,
                &["other".into()]
            )
            .unwrap_err(),
            "tls_identity_mismatch"
        );
        assert!(check_handshake_policy(
            &good,
            Some(778888),
            true,
            true,
            true,
            &["node-a".into()]
        )
        .is_ok());
    }
}
