//! Unified P2P ingress admit: wire parse + primary/exempt rate + bandwidth in one native path.
//! Connection governor: max_peers + per-IP inbound caps (Python remains control plane).
//! v1.3.78: cost-weighted per-peer byte budget (`bandwidth_exceeded`).
//! v1.3.87: outbound `p2p_egress_prepare` — encode + allowlist + size + egress admit.

use crate::p2p_rate_limit::P2PRateLimitTable;
use crate::p2p_wire::{
    clamp_max_bytes, encode_p2p_wire_message_inner, parse_p2p_wire_line_inner,
    DEFAULT_MAX_P2P_LINE_BYTES,
};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use std::collections::{HashMap, HashSet};

fn wire_reject_reason(err: &str) -> String {
    if err.starts_with("p2p_line_too_large") {
        "p2p_line_too_large".to_string()
    } else if err.starts_with("p2p_type_not_allowed") {
        err.to_string()
    } else if err.starts_with("p2p_") {
        // Keep specific wire reasons for shape_rejects; message_loop still strikes.
        err.split(':').next().unwrap_or(err).to_string()
    } else {
        "bad_wire_line".to_string()
    }
}

fn reject_dict(py: Python<'_>, reason: &str) -> PyResult<PyObject> {
    let dict = PyDict::new_bound(py);
    dict.set_item("ok", false)?;
    dict.set_item("reason", reason)?;
    Ok(dict.into_any().unbind())
}

/// One-shot ingress: decode line → type allowlist → rate/exempt → accept/reject.
///
/// Returns `{ok: true, type, data}` or `{ok: false, reason}`.
#[pyfunction]
#[pyo3(signature = (line, peer_id, now, max_bytes=DEFAULT_MAX_P2P_LINE_BYTES, allowed_types=None, rl=None))]
fn p2p_ingress_admit(
    py: Python<'_>,
    line: &[u8],
    peer_id: &str,
    now: f64,
    max_bytes: usize,
    allowed_types: Option<Vec<String>>,
    mut rl: Option<PyRefMut<'_, P2PRateLimitTable>>,
) -> PyResult<PyObject> {
    let allowed_set = allowed_types.map(|items| items.into_iter().collect::<HashSet<_>>());
    let (msg_type, data) = match parse_p2p_wire_line_inner(line, max_bytes, allowed_set.as_ref())
    {
        Ok(v) => v,
        Err(err) => return reject_dict(py, &wire_reject_reason(&err)),
    };

    if let Some(ref mut table) = rl {
        if let Some(reason) =
            table.admit_rate_inner(peer_id, &msg_type, now, line.len() as u64)
        {
            return reject_dict(py, &reason);
        }
    }

    let dict = PyDict::new_bound(py);
    dict.set_item("ok", true)?;
    dict.set_item("type", &msg_type)?;
    let data_json = serde_json::to_string(&data)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let data_obj = pyo3::types::PyModule::import_bound(py, "json")?
        .getattr("loads")?
        .call1((data_json,))?;
    dict.set_item("data", data_obj)?;
    Ok(dict.into_any().unbind())
}

/// Peer-count + per-IP inbound governor (v1.3.77).
#[pyclass]
pub struct P2PConnectionGovernor {
    max_peers: usize,
    max_inbound_per_ip: usize,
    inbound_by_ip: HashMap<String, usize>,
}

#[pymethods]
impl P2PConnectionGovernor {
    #[new]
    #[pyo3(signature = (max_peers=50, max_inbound_per_ip=8))]
    fn new(max_peers: usize, max_inbound_per_ip: usize) -> Self {
        Self {
            max_peers: max_peers.max(1),
            max_inbound_per_ip,
            inbound_by_ip: HashMap::new(),
        }
    }

    #[getter]
    fn max_peers(&self) -> usize {
        self.max_peers
    }

    #[getter]
    fn max_inbound_per_ip(&self) -> usize {
        self.max_inbound_per_ip
    }

    /// None = allow, Some(reason) = reject.
    #[pyo3(signature = (peer_count, ip=""))]
    fn allow_inbound(&self, peer_count: usize, ip: &str) -> Option<String> {
        if peer_count >= self.max_peers {
            return Some("max_peers".to_string());
        }
        if self.max_inbound_per_ip > 0 && !ip.is_empty() {
            let n = self.inbound_by_ip.get(ip).copied().unwrap_or(0);
            if n >= self.max_inbound_per_ip {
                return Some("max_inbound_per_ip".to_string());
            }
        }
        None
    }

    #[pyo3(signature = (peer_count))]
    fn allow_outbound(&self, peer_count: usize) -> Option<String> {
        if peer_count >= self.max_peers {
            return Some("max_peers".to_string());
        }
        None
    }

    #[pyo3(signature = (ip))]
    fn on_connected(&mut self, ip: &str) {
        if ip.is_empty() || self.max_inbound_per_ip == 0 {
            return;
        }
        let entry = self.inbound_by_ip.entry(ip.to_string()).or_insert(0);
        *entry = entry.saturating_add(1);
    }

    #[pyo3(signature = (ip))]
    fn on_disconnected(&mut self, ip: &str) {
        if ip.is_empty() {
            return;
        }
        if let Some(n) = self.inbound_by_ip.get_mut(ip) {
            *n = n.saturating_sub(1);
            if *n == 0 {
                self.inbound_by_ip.remove(ip);
            }
        }
    }

    fn inbound_ip_count(&self, ip: &str) -> usize {
        self.inbound_by_ip.get(ip).copied().unwrap_or(0)
    }

    fn tracked_ips(&self) -> usize {
        self.inbound_by_ip.len()
    }
}

/// v1.3.87: outbound prepare — encode + allowlist + size + egress admit (mirror of ingress).
/// Returns `{ok:true, payload: bytes}` or `{ok:false, reason}`.
#[pyfunction]
#[pyo3(signature = (msg_type, data_json, peer_id, now, max_bytes=DEFAULT_MAX_P2P_LINE_BYTES, allowed_types=None, rl=None))]
fn p2p_egress_prepare(
    py: Python<'_>,
    msg_type: &str,
    data_json: &str,
    peer_id: &str,
    now: f64,
    max_bytes: usize,
    allowed_types: Option<Vec<String>>,
    mut rl: Option<PyRefMut<'_, P2PRateLimitTable>>,
) -> PyResult<PyObject> {
    let limit = clamp_max_bytes(max_bytes);
    if let Some(allowed) = allowed_types.as_ref() {
        let set: HashSet<&str> = allowed.iter().map(|s| s.as_str()).collect();
        if !set.is_empty() && !set.contains(msg_type) {
            return reject_dict(py, &format!("p2p_type_not_allowed:{msg_type}"));
        }
    }
    let payload = match encode_p2p_wire_message_inner(msg_type, data_json) {
        Ok(bytes) => bytes,
        Err(err) => return reject_dict(py, &wire_reject_reason(&err)),
    };
    if payload.len() > limit {
        return reject_dict(py, "p2p_line_too_large");
    }
    if let Some(ref mut table) = rl {
        if let Some(reason) =
            table.admit_egress_inner(peer_id, msg_type, now, payload.len() as u64)
        {
            return reject_dict(py, &reason);
        }
    }
    let dict = PyDict::new_bound(py);
    dict.set_item("ok", true)?;
    dict.set_item("payload", PyBytes::new_bound(py, &payload))?;
    dict.set_item("nbytes", payload.len())?;
    Ok(dict.into_any().unbind())
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<P2PConnectionGovernor>()?;
    m.add_function(wrap_pyfunction!(p2p_ingress_admit, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_egress_prepare, m)?)?;
    Ok(())
}
