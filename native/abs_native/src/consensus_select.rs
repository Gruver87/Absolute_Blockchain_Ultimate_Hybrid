//! Deterministic PoS proposer and committee selection (network-safe, byte-aligned with Python).

use num_bigint::BigUint;
use num_traits::{ToPrimitive, Zero};
use pyo3::prelude::*;
use serde_json::{Map, Value};

use crate::{hash_string, MAX_CONSENSUS_VALIDATORS};

fn canonical_validator_rows(validators: Vec<(String, f64, bool)>) -> PyResult<Vec<(String, f64)>> {
    if validators.len() > MAX_CONSENSUS_VALIDATORS {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "too_many_validators: {} > {}",
            validators.len(),
            MAX_CONSENSUS_VALIDATORS
        )));
    }
    let mut rows: Vec<(String, f64)> = validators
        .into_iter()
        .filter(|(_, stake, active)| *active && *stake > 0.0 && stake.is_finite())
        .map(|(addr, stake, _)| (addr, stake))
        .collect();
    rows.sort_by(|left, right| left.0.cmp(&right.0));
    Ok(rows)
}

fn canonical_stake_rows(validators: Vec<(String, u64)>) -> PyResult<Vec<(String, u64)>> {
    if validators.len() > MAX_CONSENSUS_VALIDATORS {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "too_many_validators: {} > {}",
            validators.len(),
            MAX_CONSENSUS_VALIDATORS
        )));
    }
    let mut rows = validators;
    rows.sort_by(|left, right| left.0.cmp(&right.0));
    Ok(rows)
}

fn consensus_proposer_pick(total_stake: f64, epoch: i64, slot: i64) -> f64 {
    let digest = hash_string(&format!("abs-proposer:{epoch}:{slot}"));
    let prefix = &digest[..16.min(digest.len())];
    let num = u64::from_str_radix(prefix, 16).unwrap_or(0);
    let ratio = num as f64 / 16_f64.powi(16);
    ratio * total_stake
}

fn fisher_yates_shuffle(mut addresses: Vec<String>, slot: i64) -> Vec<String> {
    let digest = hash_string(&format!("abs-committee:{slot}"));
    let len = addresses.len();
    for i in (1..len).rev() {
        let mix_digest = hash_string(&format!("{digest}:{i}"));
        let prefix = &mix_digest[..8.min(mix_digest.len())];
        let mix = u32::from_str_radix(prefix, 16).unwrap_or(0);
        let j = (mix as usize) % (i + 1);
        addresses.swap(i, j);
    }
    addresses
}

fn validator_hash_int(seed: &str, epoch: i64, parts: &[&str]) -> BigUint {
    let mut payload = seed.to_string();
    payload.push('|');
    payload.push_str(&epoch.to_string());
    for part in parts {
        payload.push('|');
        payload.push_str(part);
    }
    let digest = hash_string(&payload);
    BigUint::parse_bytes(digest.as_bytes(), 16).unwrap_or_else(BigUint::zero)
}

fn validator_hash_rank_key(seed: &str, epoch: i64, parts: &[&str]) -> String {
    let value = validator_hash_int(seed, epoch, parts);
    format!("{value:064x}")
}

#[pyfunction]
fn consensus_stake_weighted_proposer(
    validators: Vec<(String, f64, bool)>,
    epoch: i64,
    slot: i64,
) -> PyResult<Option<String>> {
    let rows = canonical_validator_rows(validators)?;
    let total_stake: f64 = rows.iter().map(|(_, stake)| stake).sum();
    if total_stake <= 0.0 {
        return Ok(None);
    }
    let pick = consensus_proposer_pick(total_stake, epoch, slot);
    let mut current = 0.0;
    for (address, stake) in &rows {
        current += stake;
        if current >= pick {
            return Ok(Some(address.clone()));
        }
    }
    Ok(rows.last().map(|(address, _)| address.clone()))
}

#[pyfunction]
fn consensus_fisher_yates_committee(
    validators: Vec<(String, f64, bool)>,
    slot: i64,
    committee_size: usize,
) -> PyResult<Vec<String>> {
    let rows = canonical_validator_rows(validators)?;
    if rows.is_empty() {
        return Ok(Vec::new());
    }
    let size = committee_size.max(1).min(rows.len());
    let addresses: Vec<String> = rows.into_iter().map(|(addr, _)| addr).collect();
    let shuffled = fisher_yates_shuffle(addresses, slot);
    Ok(shuffled.into_iter().take(size).collect())
}

#[pyfunction]
fn validator_selection_proposer(
    seed: String,
    epoch: i64,
    slot: i64,
    validators: Vec<(String, u64)>,
) -> PyResult<Option<String>> {
    let rows = canonical_stake_rows(validators)?;
    if rows.is_empty() {
        return Ok(None);
    }
    let mut ranked = rows;
    ranked.sort_by(|left, right| {
        let left_key =
            validator_hash_rank_key(&seed, epoch, &["proposer", &slot.to_string(), &left.0]);
        let right_key =
            validator_hash_rank_key(&seed, epoch, &["proposer", &slot.to_string(), &right.0]);
        left_key.cmp(&right_key)
    });
    Ok(Some(ranked[0].0.clone()))
}

#[pyfunction]
fn validator_selection_proposer_weighted(
    seed: String,
    epoch: i64,
    slot: i64,
    validators: Vec<(String, u64)>,
) -> PyResult<Option<String>> {
    let rows = canonical_stake_rows(validators)?;
    if rows.is_empty() {
        return Ok(None);
    }
    let total_stake: u64 = rows.iter().map(|(_, stake)| stake).sum();
    if total_stake == 0 {
        return validator_selection_proposer(seed, epoch, slot, rows);
    }
    let hash_value = validator_hash_int(&seed, epoch, &["weighted-proposer", &slot.to_string()]);
    let target = (&hash_value % BigUint::from(total_stake))
        .to_u64()
        .unwrap_or(0);
    let mut cumulative = 0_u64;
    for (address, stake) in &rows {
        cumulative += stake;
        if cumulative > target {
            return Ok(Some(address.clone()));
        }
    }
    Ok(Some(rows[0].0.clone()))
}

#[pyfunction]
fn validator_selection_committee(
    seed: String,
    epoch: i64,
    validators: Vec<(String, u64)>,
    committee_size: usize,
) -> PyResult<Vec<String>> {
    let rows = canonical_stake_rows(validators)?;
    if rows.is_empty() {
        return Ok(Vec::new());
    }
    let mut ranked = rows;
    ranked.sort_by(|left, right| {
        let left_key = validator_hash_rank_key(&seed, epoch, &["committee", &left.0]);
        let right_key = validator_hash_rank_key(&seed, epoch, &["committee", &right.0]);
        left_key.cmp(&right_key)
    });
    let take = committee_size.min(ranked.len());
    Ok(ranked
        .into_iter()
        .take(take)
        .map(|(addr, _)| addr)
        .collect())
}

#[pyfunction]
fn validator_selection_shuffle(
    seed: String,
    epoch: i64,
    validators: Vec<(String, u64)>,
) -> PyResult<Vec<(String, u64)>> {
    let rows = canonical_stake_rows(validators)?;
    let mut ranked = rows;
    ranked.sort_by(|left, right| {
        let left_key = validator_hash_rank_key(&seed, epoch, &["shuffle", &left.0]);
        let right_key = validator_hash_rank_key(&seed, epoch, &["shuffle", &right.0]);
        left_key.cmp(&right_key)
    });
    Ok(ranked)
}

#[pyfunction]
fn state_engine_root_from_accounts_json(accounts_json: String) -> PyResult<String> {
    let value: Value = serde_json::from_str(&accounts_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let obj = value.as_object().ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err("state_engine accounts must be a JSON object")
    })?;
    let mut sorted = Map::new();
    let mut keys: Vec<String> = obj.keys().cloned().collect();
    keys.sort();
    for key in keys {
        if let Some(item) = obj.get(&key) {
            sorted.insert(key, item.clone());
        }
    }
    let encoded = serde_json::to_string(&Value::Object(sorted))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(hash_string(&encoded)[..32].to_string())
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(consensus_stake_weighted_proposer, m)?)?;
    m.add_function(wrap_pyfunction!(consensus_fisher_yates_committee, m)?)?;
    m.add_function(wrap_pyfunction!(validator_selection_proposer, m)?)?;
    m.add_function(wrap_pyfunction!(validator_selection_proposer_weighted, m)?)?;
    m.add_function(wrap_pyfunction!(validator_selection_committee, m)?)?;
    m.add_function(wrap_pyfunction!(validator_selection_shuffle, m)?)?;
    m.add_function(wrap_pyfunction!(state_engine_root_from_accounts_json, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stake_weighted_proposer_is_stable() {
        let validators = vec![
            ("0x01".to_string(), 100.0, true),
            ("0x02".to_string(), 200.0, true),
        ];
        let first = consensus_stake_weighted_proposer(validators.clone(), 0, 5).unwrap();
        let second = consensus_stake_weighted_proposer(validators, 0, 5).unwrap();
        assert_eq!(first, second);
    }
}
