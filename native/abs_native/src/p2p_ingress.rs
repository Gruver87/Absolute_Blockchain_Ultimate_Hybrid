//! Unified P2P ingress admit: wire parse + primary/exempt rate + bandwidth in one native path.
//! Connection governor: max_peers + per-IP inbound caps (Python remains control plane).
//! v1.3.78: cost-weighted per-peer byte budget (`bandwidth_exceeded`).
//! v1.3.87: outbound `p2p_egress_prepare` — encode + allowlist + size + egress admit.
//! v1.3.89: Sybil/Eclipse — public-only subnet diversity + reserved outbound slots.

use crate::p2p_rate_limit::P2PRateLimitTable;
use crate::p2p_wire::{
    clamp_max_bytes, encode_p2p_wire_by_codec, parse_p2p_wire_line_inner,
    DEFAULT_MAX_P2P_LINE_BYTES,
};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use std::collections::{HashMap, HashSet};
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};

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
    rl: Option<PyRef<'_, P2PRateLimitTable>>,
) -> PyResult<PyObject> {
    let allowed_set = allowed_types.map(|items| items.into_iter().collect::<HashSet<_>>());
    let (msg_type, data, wire_codec) =
        match parse_p2p_wire_line_inner(line, max_bytes, allowed_set.as_ref()) {
            Ok(v) => v,
            Err(err) => return reject_dict(py, &wire_reject_reason(&err)),
        };

    if let Some(ref table) = rl {
        if let Some(reason) = table.admit_rate_inner(peer_id, &msg_type, now, line.len() as u64) {
            return reject_dict(py, &reason);
        }
    }

    let dict = PyDict::new_bound(py);
    dict.set_item("ok", true)?;
    dict.set_item("type", &msg_type)?;
    dict.set_item("wire_codec", wire_codec)?;
    let data_json = serde_json::to_string(&data)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let data_obj = pyo3::types::PyModule::import_bound(py, "json")?
        .getattr("loads")?
        .call1((data_json,))?;
    dict.set_item("data", data_obj)?;
    Ok(dict.into_any().unbind())
}

/// IPv4 /24 or IPv6 /64 subnet key. Empty for unparseable input.
pub fn p2p_subnet_key_inner(ip: &str) -> String {
    let trimmed = ip.trim().trim_matches(|c| c == '[' || c == ']');
    // Strip optional :port on IPv4 (host:port). Leave bare IPv6 alone.
    let host = if trimmed.matches(':').count() == 1 {
        trimmed.split(':').next().unwrap_or(trimmed)
    } else {
        trimmed
    };
    match host.parse::<IpAddr>() {
        Ok(IpAddr::V4(v4)) => {
            let o = v4.octets();
            format!("{}.{}.{}.0/24", o[0], o[1], o[2])
        }
        Ok(IpAddr::V6(v6)) => {
            let seg = v6.segments();
            format!("{:x}:{:x}:{:x}:{:x}::/64", seg[0], seg[1], seg[2], seg[3])
        }
        Err(_) => String::new(),
    }
}

/// True for globally routable addresses (not loopback / RFC1918 / link-local / ULA).
pub fn p2p_ip_is_public_inner(ip: &str) -> bool {
    let trimmed = ip.trim().trim_matches(|c| c == '[' || c == ']');
    let host = if trimmed.matches(':').count() == 1 {
        trimmed.split(':').next().unwrap_or(trimmed)
    } else {
        trimmed
    };
    match host.parse::<IpAddr>() {
        Ok(IpAddr::V4(v4)) => is_public_v4(v4),
        Ok(IpAddr::V6(v6)) => is_public_v6(v6),
        Err(_) => false,
    }
}

fn is_public_v4(v4: Ipv4Addr) -> bool {
    if v4.is_loopback() || v4.is_unspecified() || v4.is_broadcast() || v4.is_link_local() {
        return false;
    }
    if v4.is_private() {
        return false;
    }
    // 100.64/10 CGNAT
    let o = v4.octets();
    if o[0] == 100 && (o[1] & 0xc0) == 64 {
        return false;
    }
    true
}

fn is_public_v6(v6: Ipv6Addr) -> bool {
    if v6.is_loopback() || v6.is_unspecified() {
        return false;
    }
    // link-local fe80::/10
    let seg = v6.segments();
    if (seg[0] & 0xffc0) == 0xfe80 {
        return false;
    }
    // ULA fc00::/7
    if (seg[0] & 0xfe00) == 0xfc00 {
        return false;
    }
    // IPv4-mapped: recurse on embedded v4
    if let Some(v4) = v6.to_ipv4_mapped() {
        return is_public_v4(v4);
    }
    true
}

/// Peer-count + per-IP + public-subnet governor (v1.3.77 / v1.3.89).
#[pyclass]
pub struct P2PConnectionGovernor {
    max_peers: usize,
    max_inbound_per_ip: usize,
    max_peers_per_subnet: usize,
    reserved_outbound_slots: usize,
    inbound_by_ip: HashMap<String, usize>,
    inbound_by_subnet: HashMap<String, usize>,
    subnet_rejects: u64,
    reserved_slot_rejects: u64,
}

impl P2PConnectionGovernor {
    pub fn rust_new(
        max_peers: usize,
        max_inbound_per_ip: usize,
        max_peers_per_subnet: usize,
        reserved_outbound_slots: usize,
    ) -> Self {
        let max_peers = max_peers.max(1);
        let reserved = reserved_outbound_slots.min(max_peers.saturating_sub(1));
        Self {
            max_peers,
            max_inbound_per_ip,
            max_peers_per_subnet,
            reserved_outbound_slots: reserved,
            inbound_by_ip: HashMap::new(),
            inbound_by_subnet: HashMap::new(),
            subnet_rejects: 0,
            reserved_slot_rejects: 0,
        }
    }

    pub fn allow_inbound_inner(&mut self, peer_count: usize, ip: &str) -> Option<String> {
        let inbound_cap = self.max_peers.saturating_sub(self.reserved_outbound_slots);
        if peer_count >= self.max_peers {
            return Some("max_peers".to_string());
        }
        if peer_count >= inbound_cap {
            self.reserved_slot_rejects = self.reserved_slot_rejects.saturating_add(1);
            return Some("reserved_outbound_slots".to_string());
        }
        if self.max_inbound_per_ip > 0 && !ip.is_empty() {
            let n = self.inbound_by_ip.get(ip).copied().unwrap_or(0);
            if n >= self.max_inbound_per_ip {
                return Some("max_inbound_per_ip".to_string());
            }
        }
        if self.max_peers_per_subnet > 0 && p2p_ip_is_public_inner(ip) {
            let key = p2p_subnet_key_inner(ip);
            if !key.is_empty() {
                let n = self.inbound_by_subnet.get(&key).copied().unwrap_or(0);
                if n >= self.max_peers_per_subnet {
                    self.subnet_rejects = self.subnet_rejects.saturating_add(1);
                    return Some("max_peers_per_subnet".to_string());
                }
            }
        }
        None
    }

    pub fn allow_outbound_inner(&self, peer_count: usize) -> Option<String> {
        if peer_count >= self.max_peers {
            Some("max_peers".to_string())
        } else {
            None
        }
    }

    pub fn on_connected_inner(&mut self, ip: &str) {
        if ip.is_empty() {
            return;
        }
        if self.max_inbound_per_ip > 0 {
            let entry = self.inbound_by_ip.entry(ip.to_string()).or_insert(0);
            *entry = entry.saturating_add(1);
        }
        if self.max_peers_per_subnet > 0 && p2p_ip_is_public_inner(ip) {
            let key = p2p_subnet_key_inner(ip);
            if !key.is_empty() {
                let entry = self.inbound_by_subnet.entry(key).or_insert(0);
                *entry = entry.saturating_add(1);
            }
        }
    }

    pub fn on_disconnected_inner(&mut self, ip: &str) {
        if ip.is_empty() {
            return;
        }
        if let Some(n) = self.inbound_by_ip.get_mut(ip) {
            *n = n.saturating_sub(1);
            if *n == 0 {
                self.inbound_by_ip.remove(ip);
            }
        }
        let key = p2p_subnet_key_inner(ip);
        if !key.is_empty() {
            if let Some(n) = self.inbound_by_subnet.get_mut(&key) {
                *n = n.saturating_sub(1);
                if *n == 0 {
                    self.inbound_by_subnet.remove(&key);
                }
            }
        }
    }

    /// Diversity over the live peer IP list (inbound + outbound).
    pub fn diversity_snapshot_inner(
        &self,
        peer_ips: &[String],
        warn_ratio: f64,
    ) -> (usize, usize, f64, bool, String) {
        let mut subnet_counts: HashMap<String, usize> = HashMap::new();
        let mut public_peers = 0usize;
        for ip in peer_ips {
            if !p2p_ip_is_public_inner(ip) {
                continue;
            }
            let key = p2p_subnet_key_inner(ip);
            if key.is_empty() {
                continue;
            }
            public_peers = public_peers.saturating_add(1);
            *subnet_counts.entry(key).or_insert(0) += 1;
        }
        let unique = subnet_counts.len();
        let densest = subnet_counts.values().copied().max().unwrap_or(0);
        let densest_key = subnet_counts
            .iter()
            .max_by_key(|(_, c)| *c)
            .map(|(k, _)| k.clone())
            .unwrap_or_default();
        let ratio = if public_peers == 0 {
            0.0
        } else {
            densest as f64 / public_peers as f64
        };
        let at_risk = warn_ratio > 0.0
            && public_peers >= 2
            && unique > 0
            && ratio + f64::EPSILON >= warn_ratio;
        (public_peers, unique, ratio, at_risk, densest_key)
    }
}

#[pymethods]
impl P2PConnectionGovernor {
    #[new]
    #[pyo3(signature = (
        max_peers=50,
        max_inbound_per_ip=8,
        max_peers_per_subnet=0,
        reserved_outbound_slots=0
    ))]
    fn new(
        max_peers: usize,
        max_inbound_per_ip: usize,
        max_peers_per_subnet: usize,
        reserved_outbound_slots: usize,
    ) -> Self {
        Self::rust_new(
            max_peers,
            max_inbound_per_ip,
            max_peers_per_subnet,
            reserved_outbound_slots,
        )
    }

    #[getter]
    fn max_peers(&self) -> usize {
        self.max_peers
    }

    #[getter]
    fn max_inbound_per_ip(&self) -> usize {
        self.max_inbound_per_ip
    }

    #[getter]
    fn max_peers_per_subnet(&self) -> usize {
        self.max_peers_per_subnet
    }

    #[getter]
    fn reserved_outbound_slots(&self) -> usize {
        self.reserved_outbound_slots
    }

    #[getter]
    fn subnet_rejects(&self) -> u64 {
        self.subnet_rejects
    }

    #[getter]
    fn reserved_slot_rejects(&self) -> u64 {
        self.reserved_slot_rejects
    }

    /// None = allow, Some(reason) = reject.
    #[pyo3(signature = (peer_count, ip=""))]
    fn allow_inbound(&mut self, peer_count: usize, ip: &str) -> Option<String> {
        self.allow_inbound_inner(peer_count, ip)
    }

    #[pyo3(signature = (peer_count))]
    fn allow_outbound(&self, peer_count: usize) -> Option<String> {
        self.allow_outbound_inner(peer_count)
    }

    #[pyo3(signature = (ip))]
    fn on_connected(&mut self, ip: &str) {
        self.on_connected_inner(ip)
    }

    #[pyo3(signature = (ip))]
    fn on_disconnected(&mut self, ip: &str) {
        self.on_disconnected_inner(ip)
    }

    fn inbound_ip_count(&self, ip: &str) -> usize {
        self.inbound_by_ip.get(ip).copied().unwrap_or(0)
    }

    fn inbound_subnet_count(&self, subnet: &str) -> usize {
        self.inbound_by_subnet.get(subnet).copied().unwrap_or(0)
    }

    fn tracked_ips(&self) -> usize {
        self.inbound_by_ip.len()
    }

    fn tracked_subnets(&self) -> usize {
        self.inbound_by_subnet.len()
    }

    /// `{public_peers, unique_public_subnets, eclipse_ratio, at_risk, densest_subnet}`.
    #[pyo3(signature = (peer_ips, warn_ratio=0.34))]
    fn diversity_snapshot(
        &self,
        py: Python<'_>,
        peer_ips: Vec<String>,
        warn_ratio: f64,
    ) -> PyResult<PyObject> {
        let (public_peers, unique, ratio, at_risk, densest) =
            self.diversity_snapshot_inner(&peer_ips, warn_ratio);
        let dict = PyDict::new_bound(py);
        dict.set_item("public_peers", public_peers)?;
        dict.set_item("unique_public_subnets", unique)?;
        dict.set_item("eclipse_ratio", ratio)?;
        dict.set_item("at_risk", at_risk)?;
        dict.set_item("densest_subnet", densest)?;
        Ok(dict.into_any().unbind())
    }
}

#[pyfunction]
fn p2p_subnet_key(ip: &str) -> String {
    p2p_subnet_key_inner(ip)
}

#[pyfunction]
fn p2p_ip_is_public(ip: &str) -> bool {
    p2p_ip_is_public_inner(ip)
}

/// Split `host:port` / `[v6]:port` for discovery dialability checks.
fn split_peer_host_port(addr: &str) -> Option<(String, u16)> {
    let s = addr.trim();
    if s.is_empty() || s.len() > 253 {
        return None;
    }
    if s.starts_with('[') {
        let end = s.find(']')?;
        let host = s[1..end].trim().to_string();
        let rest = s[end + 1..].trim();
        let port_s = rest.strip_prefix(':')?;
        let port: u16 = port_s.parse().ok()?;
        if host.is_empty() || port == 0 {
            return None;
        }
        return Some((host, port));
    }
    let (host, port_s) = s.rsplit_once(':')?;
    let host = host.trim().to_string();
    let port: u16 = port_s.parse().ok()?;
    if host.is_empty() || port == 0 {
        return None;
    }
    Some((host, port))
}

fn is_hostname_label_ok(host: &str) -> bool {
    if host.is_empty() || host.len() > 253 {
        return false;
    }
    if host.contains('/') || host.contains(' ') || host.contains('\\') {
        return false;
    }
    if host.starts_with('.') || host.ends_with('.') {
        return false;
    }
    true
}

/// v1.3.128: discovery dial target policy.
/// - Literal public IP: always OK
/// - Literal private/loopback/link-local: OK only if `allow_private`
/// - Non-IP hostname (docker DNS): OK (not an RFC1918 spray vector)
///
/// Does not prove peer honesty / anti-Sybil / DHT.
pub fn p2p_peer_addr_is_dialable_inner(addr: &str, allow_private: bool) -> bool {
    let Some((host, _port)) = split_peer_host_port(addr) else {
        return false;
    };
    let host = host.trim().trim_matches(|c| c == '[' || c == ']');
    match host.parse::<IpAddr>() {
        Ok(IpAddr::V4(v4)) => {
            if allow_private {
                !(v4.is_unspecified() || v4.is_broadcast())
            } else {
                p2p_ip_is_public_inner(host)
            }
        }
        Ok(IpAddr::V6(v6)) => {
            if allow_private {
                !v6.is_unspecified()
            } else {
                p2p_ip_is_public_inner(host)
            }
        }
        Err(_) => is_hostname_label_ok(host),
    }
}

#[pyfunction]
fn p2p_peer_addr_is_dialable(addr: &str, allow_private: bool) -> bool {
    p2p_peer_addr_is_dialable_inner(addr, allow_private)
}

/// v1.3.87: outbound prepare — encode + allowlist + size + egress admit (mirror of ingress).
/// Returns `{ok:true, payload: bytes}` or `{ok:false, reason}`.
#[pyfunction]
#[pyo3(signature = (msg_type, data_json, peer_id, now, max_bytes=DEFAULT_MAX_P2P_LINE_BYTES, allowed_types=None, rl=None, codec="auto"))]
fn p2p_egress_prepare(
    py: Python<'_>,
    msg_type: &str,
    data_json: &str,
    peer_id: &str,
    now: f64,
    max_bytes: usize,
    allowed_types: Option<Vec<String>>,
    rl: Option<PyRef<'_, P2PRateLimitTable>>,
    codec: &str,
) -> PyResult<PyObject> {
    let limit = clamp_max_bytes(max_bytes);
    if let Some(allowed) = allowed_types.as_ref() {
        let set: HashSet<&str> = allowed.iter().map(|s| s.as_str()).collect();
        if !set.is_empty() && !set.contains(msg_type) {
            return reject_dict(py, &format!("p2p_type_not_allowed:{msg_type}"));
        }
    }
    let payload = match encode_p2p_wire_by_codec(msg_type, data_json, codec) {
        Ok(bytes) => bytes,
        Err(err) => return reject_dict(py, &wire_reject_reason(&err)),
    };
    if payload.len() > limit {
        return reject_dict(py, "p2p_line_too_large");
    }
    if let Some(ref table) = rl {
        if let Some(reason) = table.admit_egress_inner(peer_id, msg_type, now, payload.len() as u64)
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
    m.add_function(wrap_pyfunction!(p2p_subnet_key, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_ip_is_public, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_peer_addr_is_dialable, m)?)?;
    Ok(())
}
