//! Per-peer P2P rate-limit window + strike/ban table.
//! Behaviour matches `network/p2p_node.py` `_rate_limit_ok` / `_strike_peer_sync` / `_is_banned`.

use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};

const DEFAULT_EXEMPT: &[&str] = &[
    "ping",
    "pong",
    "__idle__",
    "status",
    "state_root_request",
    "state_root_response",
    "new_block",
    "get_block",
    "get_block_by_hash",
    "get_blocks",
    "block",
    "blocks",
    "new_tx",
    "get_mempool",
    "mempool",
];

#[pyclass]
pub struct P2PRateLimitTable {
    windows: HashMap<String, (u64, f64)>,
    exempt_windows: HashMap<String, (u64, f64)>,
    byte_windows: HashMap<String, (u64, f64)>,
    strikes: HashMap<String, u64>,
    bans: HashMap<String, f64>,
    limit: u64,
    exempt_limit: u64,
    byte_limit: u64,
    max_strikes: u64,
    ban_seconds: u64,
    exempt: HashSet<String>,
    bandwidth_rejects: u64,
}

/// Weighted ingress cost units (v1.3.78). Large sync payloads burn budget faster.
pub(crate) fn ingress_cost_units(msg_type: &str, nbytes: u64) -> u64 {
    let weight: u64 = match msg_type {
        "blocks" | "block" | "mempool" => 2,
        "get_blocks" | "new_block" | "new_tx" | "state_root_response" => 1,
        _ => 1,
    };
    nbytes.saturating_mul(weight).max(1)
}

impl P2PRateLimitTable {
    fn tick_window(
        map: &mut HashMap<String, (u64, f64)>,
        peer_id: &str,
        now: f64,
        limit: u64,
    ) -> bool {
        if limit == 0 || peer_id.is_empty() {
            return true;
        }
        let (mut count, mut start) = map.get(peer_id).copied().unwrap_or((0, now));
        if now - start >= 1.0 {
            count = 0;
            start = now;
        }
        count = count.saturating_add(1);
        map.insert(peer_id.to_string(), (count, start));
        count <= limit
    }

    fn tick_byte_window(&mut self, peer_id: &str, now: f64, cost: u64) -> bool {
        if self.byte_limit == 0 || peer_id.is_empty() {
            return true;
        }
        let (mut used, mut start) = self
            .byte_windows
            .get(peer_id)
            .copied()
            .unwrap_or((0, now));
        if now - start >= 1.0 {
            used = 0;
            start = now;
        }
        used = used.saturating_add(cost);
        self.byte_windows
            .insert(peer_id.to_string(), (used, start));
        used <= self.byte_limit
    }

    /// Primary + exempt + bandwidth. `None` = allowed, `Some(reason)` = reject.
    pub(crate) fn admit_rate_inner(
        &mut self,
        peer_id: &str,
        msg_type: &str,
        now: f64,
        nbytes: u64,
    ) -> Option<String> {
        if self.is_exempt_inner(msg_type) {
            if !Self::tick_window(&mut self.exempt_windows, peer_id, now, self.exempt_limit) {
                return Some("exempt_rate_exceeded".to_string());
            }
        } else if !Self::tick_window(&mut self.windows, peer_id, now, self.limit) {
            return Some("rate_limit_exceeded".to_string());
        }
        let cost = ingress_cost_units(msg_type, nbytes);
        if !self.tick_byte_window(peer_id, now, cost) {
            self.bandwidth_rejects = self.bandwidth_rejects.saturating_add(1);
            return Some("bandwidth_exceeded".to_string());
        }
        None
    }

    fn is_exempt_inner(&self, msg_type: &str) -> bool {
        !msg_type.is_empty() && self.exempt.contains(msg_type)
    }
}

#[pymethods]
impl P2PRateLimitTable {
    #[new]
    #[pyo3(signature = (limit=500, max_strikes=5, ban_seconds=300, exempt_types=None, exempt_limit=0, byte_limit=0))]
    fn new(
        limit: u64,
        max_strikes: u64,
        ban_seconds: u64,
        exempt_types: Option<Vec<String>>,
        exempt_limit: u64,
        byte_limit: u64,
    ) -> Self {
        let exempt = match exempt_types {
            Some(list) if !list.is_empty() => list.into_iter().collect(),
            _ => DEFAULT_EXEMPT.iter().map(|s| (*s).to_string()).collect(),
        };
        Self {
            windows: HashMap::new(),
            exempt_windows: HashMap::new(),
            byte_windows: HashMap::new(),
            strikes: HashMap::new(),
            bans: HashMap::new(),
            limit,
            exempt_limit,
            byte_limit,
            max_strikes: max_strikes.max(1),
            ban_seconds: ban_seconds.max(30),
            exempt,
            bandwidth_rejects: 0,
        }
    }

    /// True if message type is rate-limit exempt.
    fn is_exempt(&self, msg_type: &str) -> bool {
        self.is_exempt_inner(msg_type)
    }

    /// Per-peer rate window tick. Returns True when the message is allowed.
    #[pyo3(signature = (peer_id, msg_type, now))]
    fn rate_ok(&mut self, peer_id: &str, msg_type: &str, now: f64) -> bool {
        if self.is_exempt_inner(msg_type) {
            return true;
        }
        Self::tick_window(&mut self.windows, peer_id, now, self.limit)
    }

    /// Secondary budget for exempt types (v1.3.72 / v1.3.77). 0 = disabled.
    #[pyo3(signature = (peer_id, now))]
    fn exempt_rate_ok(&mut self, peer_id: &str, now: f64) -> bool {
        Self::tick_window(&mut self.exempt_windows, peer_id, now, self.exempt_limit)
    }

    /// Bandwidth-only tick (cost-weighted bytes). None = allowed.
    #[pyo3(signature = (peer_id, nbytes, now, msg_type=""))]
    fn admit_bandwidth(
        &mut self,
        peer_id: &str,
        nbytes: u64,
        now: f64,
        msg_type: &str,
    ) -> Option<String> {
        let cost = ingress_cost_units(msg_type, nbytes);
        if self.tick_byte_window(peer_id, now, cost) {
            None
        } else {
            self.bandwidth_rejects = self.bandwidth_rejects.saturating_add(1);
            Some("bandwidth_exceeded".to_string())
        }
    }

    /// Combined primary + exempt + bandwidth. Returns None when allowed.
    #[pyo3(signature = (peer_id, msg_type, now, nbytes=0))]
    fn admit_rate(
        &mut self,
        peer_id: &str,
        msg_type: &str,
        now: f64,
        nbytes: u64,
    ) -> Option<String> {
        self.admit_rate_inner(peer_id, msg_type, now, nbytes)
    }

    /// Increment strike. Returns True when the peer must be banned/disconnected.
    fn strike(&mut self, key: &str, now: f64) -> bool {
        if key.is_empty() {
            return false;
        }
        let strikes = self.strikes.get(key).copied().unwrap_or(0).saturating_add(1);
        if strikes < self.max_strikes {
            self.strikes.insert(key.to_string(), strikes);
            return false;
        }
        self.bans
            .insert(key.to_string(), now + self.ban_seconds as f64);
        self.strikes.remove(key);
        true
    }

    fn strike_count(&self, key: &str) -> u64 {
        self.strikes.get(key).copied().unwrap_or(0)
    }

    fn is_banned(&mut self, key: &str, now: f64) -> bool {
        if key.is_empty() {
            return false;
        }
        let Some(until) = self.bans.get(key).copied() else {
            return false;
        };
        if now >= until {
            self.bans.remove(key);
            return false;
        }
        true
    }

    fn ban_until(&self, key: &str) -> Option<f64> {
        self.bans.get(key).copied()
    }

    /// True if host:port or any key with host: prefix is banned.
    fn is_addr_banned(&mut self, host: &str, port: u16, now: f64) -> bool {
        let exact = format!("{host}:{port}");
        if self.is_banned(&exact, now) {
            return true;
        }
        let prefix = format!("{host}:");
        let keys: Vec<String> = self.bans.keys().cloned().collect();
        for key in keys {
            if key.starts_with(&prefix) && self.is_banned(&key, now) {
                return true;
            }
        }
        false
    }

    fn tracked_strikes(&self) -> usize {
        self.strikes.len()
    }

    fn active_bans(&mut self, now: f64) -> usize {
        let keys: Vec<String> = self.bans.keys().cloned().collect();
        let mut n = 0usize;
        for key in keys {
            if self.is_banned(&key, now) {
                n += 1;
            }
        }
        n
    }

    fn ban_keys(&self) -> Vec<String> {
        self.bans.keys().cloned().collect()
    }

    fn clear_key(&mut self, key: &str) {
        self.windows.remove(key);
        self.exempt_windows.remove(key);
        self.byte_windows.remove(key);
        self.strikes.remove(key);
        self.bans.remove(key);
    }

    /// Drop strike counters for peers that are no longer connected.
    fn retain_strike_keys(&mut self, active_keys: Vec<String>) {
        let active: HashSet<String> = active_keys.into_iter().collect();
        self.strikes.retain(|k, _| active.contains(k));
    }

    #[getter]
    fn limit(&self) -> u64 {
        self.limit
    }

    #[getter]
    fn exempt_limit(&self) -> u64 {
        self.exempt_limit
    }

    #[getter]
    fn byte_limit(&self) -> u64 {
        self.byte_limit
    }

    #[getter]
    fn bandwidth_rejects(&self) -> u64 {
        self.bandwidth_rejects
    }

    #[getter]
    fn max_strikes(&self) -> u64 {
        self.max_strikes
    }

    #[getter]
    fn ban_seconds(&self) -> u64 {
        self.ban_seconds
    }

    fn exempt_count(&self) -> usize {
        self.exempt.len()
    }
}

/// Pure helper: whether msg_type is in the default exempt set.
#[pyfunction]
fn p2p_rate_limit_is_exempt(msg_type: String) -> bool {
    DEFAULT_EXEMPT.iter().any(|s| *s == msg_type.as_str())
}

/// Cost-weighted units for bandwidth budget (v1.3.78).
#[pyfunction]
fn p2p_ingress_cost_units(msg_type: String, nbytes: u64) -> u64 {
    ingress_cost_units(&msg_type, nbytes)
}

/// Pure window tick without table state (for tests / scripting).
/// Returns (allowed, new_count, new_start).
#[pyfunction]
fn p2p_rate_limit_tick(count: u64, start: f64, now: f64, limit: u64) -> (bool, u64, f64) {
    if limit == 0 {
        return (true, count, start);
    }
    let (mut c, mut s) = (count, start);
    if now - s >= 1.0 {
        c = 0;
        s = now;
    }
    c = c.saturating_add(1);
    (c <= limit, c, s)
}

/// After incrementing strikes to `strikes`, should we ban?
#[pyfunction]
fn p2p_strike_should_ban(strikes: u64, max_strikes: u64) -> bool {
    let max_s = max_strikes.max(1);
    strikes >= max_s
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<P2PRateLimitTable>()?;
    m.add_function(wrap_pyfunction!(p2p_rate_limit_is_exempt, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_rate_limit_tick, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_strike_should_ban, m)?)?;
    m.add_function(wrap_pyfunction!(p2p_ingress_cost_units, m)?)?;
    Ok(())
}
