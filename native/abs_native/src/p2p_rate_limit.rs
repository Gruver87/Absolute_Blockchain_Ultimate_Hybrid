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
    strikes: HashMap<String, u64>,
    bans: HashMap<String, f64>,
    limit: u64,
    max_strikes: u64,
    ban_seconds: u64,
    exempt: HashSet<String>,
}

#[pymethods]
impl P2PRateLimitTable {
    #[new]
    #[pyo3(signature = (limit=500, max_strikes=5, ban_seconds=300, exempt_types=None))]
    fn new(
        limit: u64,
        max_strikes: u64,
        ban_seconds: u64,
        exempt_types: Option<Vec<String>>,
    ) -> Self {
        let exempt = match exempt_types {
            Some(list) if !list.is_empty() => list.into_iter().collect(),
            _ => DEFAULT_EXEMPT.iter().map(|s| (*s).to_string()).collect(),
        };
        Self {
            windows: HashMap::new(),
            strikes: HashMap::new(),
            bans: HashMap::new(),
            limit,
            max_strikes: max_strikes.max(1),
            ban_seconds: ban_seconds.max(30),
            exempt,
        }
    }

    /// True if message type is rate-limit exempt.
    fn is_exempt(&self, msg_type: &str) -> bool {
        !msg_type.is_empty() && self.exempt.contains(msg_type)
    }

    /// Per-peer rate window tick. Returns True when the message is allowed.
    #[pyo3(signature = (peer_id, msg_type, now))]
    fn rate_ok(&mut self, peer_id: &str, msg_type: &str, now: f64) -> bool {
        if self.is_exempt(msg_type) {
            return true;
        }
        if self.limit == 0 || peer_id.is_empty() {
            return true;
        }
        let (mut count, mut start) = self
            .windows
            .get(peer_id)
            .copied()
            .unwrap_or((0, now));
        if now - start >= 1.0 {
            count = 0;
            start = now;
        }
        count = count.saturating_add(1);
        self.windows
            .insert(peer_id.to_string(), (count, start));
        count <= self.limit
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
    Ok(())
}
