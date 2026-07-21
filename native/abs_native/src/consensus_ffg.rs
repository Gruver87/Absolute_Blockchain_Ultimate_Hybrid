//! Casper FFG + FinalityEngine quorum kernels + slashing conflict checks.
//! Stateless pure functions — Python owns maps, callbacks, and honesty labels.

use pyo3::prelude::*;
use serde_json::{Map, Value};
use std::collections::HashSet;

fn parse_object(json: &str, label: &str) -> PyResult<Map<String, Value>> {
    let value: Value = serde_json::from_str(json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    value.as_object().cloned().ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err(format!("{label} must be a JSON object"))
    })
}

fn parse_int_set(json: &str) -> PyResult<HashSet<i64>> {
    let value: Value = serde_json::from_str(json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let arr = value
        .as_array()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("epochs must be a JSON array"))?;
    let mut out = HashSet::new();
    for item in arr {
        let n = item
            .as_i64()
            .or_else(|| item.as_u64().map(|u| u as i64))
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("epoch must be int"))?;
        out.insert(n);
    }
    Ok(out)
}

fn weight_of(v: &Value) -> i64 {
    v.as_i64()
        .or_else(|| v.as_u64().map(|u| u as i64))
        .or_else(|| v.as_f64().map(|f| f as i64))
        .unwrap_or(0)
}

/// Match Python ``int(total_stake * threshold_ratio)`` for ratio=2/3 by default.
#[pyfunction]
#[pyo3(signature = (total_stake, threshold_numer=2, threshold_denom=3))]
fn ffg_threshold(total_stake: i64, threshold_numer: i64, threshold_denom: i64) -> PyResult<i64> {
    if threshold_denom <= 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("threshold_denom must be > 0"));
    }
    if total_stake < 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("total_stake must be >= 0"));
    }
    // Python default uses float 2/3 then int(); match that truncation.
    let ratio = (threshold_numer as f64) / (threshold_denom as f64);
    Ok((total_stake as f64 * ratio) as i64)
}

#[pyfunction]
fn ffg_best_checkpoint(votes_json: String) -> PyResult<Option<(String, i64)>> {
    let votes = parse_object(&votes_json, "votes_json")?;
    if votes.is_empty() {
        return Ok(None);
    }
    let mut best_hash: Option<String> = None;
    let mut best_weight: i64 = i64::MIN;
    for (hash, w) in &votes {
        let weight = weight_of(w);
        if weight > best_weight
            || (weight == best_weight
                && best_hash
                    .as_ref()
                    .map(|b| hash < b)
                    .unwrap_or(true))
        {
            best_weight = weight;
            best_hash = Some(hash.clone());
        }
    }
    Ok(best_hash.map(|h| (h, best_weight)))
}

#[pyfunction]
fn ffg_accumulate_vote(votes_json: String, block_hash: String, weight: i64) -> PyResult<String> {
    let mut votes = parse_object(&votes_json, "votes_json")?;
    if block_hash.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err("block_hash required"));
    }
    if weight < 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("weight must be >= 0"));
    }
    let cur = votes.get(&block_hash).map(weight_of).unwrap_or(0);
    votes.insert(block_hash, Value::Number((cur + weight).into()));
    serde_json::to_string(&Value::Object(votes))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

/// Classic Casper/Beacon two-step: justify epoch when best >= threshold; finalize epoch-1.
#[pyfunction]
#[pyo3(signature = (
    epoch,
    votes_for_epoch_json,
    total_stake,
    justified_epochs_json,
    finalized_epochs_json,
    threshold_numer=2,
    threshold_denom=3
))]
fn ffg_evaluate_epoch(
    epoch: i64,
    votes_for_epoch_json: String,
    total_stake: i64,
    justified_epochs_json: String,
    finalized_epochs_json: String,
    threshold_numer: i64,
    threshold_denom: i64,
) -> PyResult<String> {
    let threshold = ffg_threshold(total_stake, threshold_numer, threshold_denom)?;
    let justified = parse_int_set(&justified_epochs_json)?;
    let finalized = parse_int_set(&finalized_epochs_json)?;
    let best = ffg_best_checkpoint(votes_for_epoch_json)?;

    let (best_hash, best_weight) = match best {
        Some((h, w)) => (Some(h), w),
        None => (None, 0),
    };

    let mut newly_justified = false;
    let mut finalize_prev = false;
    let mut justified_block: Option<String> = None;

    if let Some(ref hash) = best_hash {
        if best_weight >= threshold {
            justified_block = Some(hash.clone());
            newly_justified = !justified.contains(&epoch);
            let prev = epoch - 1;
            // After this evaluation current epoch is justified (new or already).
            if justified.contains(&prev) && !finalized.contains(&prev) {
                finalize_prev = true;
            }
        }
    }

    let mut out = Map::new();
    out.insert(
        "justified".to_string(),
        Value::Bool(justified_block.is_some() || justified.contains(&epoch)),
    );
    out.insert(
        "justified_block".to_string(),
        justified_block
            .clone()
            .map(Value::String)
            .unwrap_or(Value::Null),
    );
    out.insert("newly_justified".to_string(), Value::Bool(newly_justified));
    out.insert("finalize_prev".to_string(), Value::Bool(finalize_prev));
    out.insert("threshold".to_string(), Value::Number(threshold.into()));
    out.insert(
        "best_hash".to_string(),
        best_hash.map(Value::String).unwrap_or(Value::Null),
    );
    out.insert("best_weight".to_string(), Value::Number(best_weight.into()));
    serde_json::to_string(&Value::Object(out))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(signature = (block_number, epoch_length=32))]
fn fe_epoch(block_number: i64, epoch_length: i64) -> PyResult<i64> {
    if epoch_length <= 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("epoch_length must be > 0"));
    }
    Ok(block_number.div_euclid(epoch_length))
}

/// Match FinalityEngine: ``votes >= active_validator_count * 2 / 3`` (float).
#[pyfunction]
fn fe_quorum_reached(vote_count: i64, active_validator_count: i64) -> PyResult<bool> {
    let total = active_validator_count.max(1) as f64;
    Ok((vote_count as f64) >= total * 2.0 / 3.0)
}

#[pyfunction]
fn fe_can_finalize(epoch: i64, justified_epochs_json: String) -> PyResult<bool> {
    let justified = parse_int_set(&justified_epochs_json)?;
    Ok(justified.contains(&epoch) && justified.contains(&(epoch - 1)))
}

/// prior_hash=None → first vote; same hash → duplicate OK; different → double_vote.
#[pyfunction]
#[pyo3(signature = (new_hash, prior_hash=None))]
fn slash_check_double_vote(new_hash: String, prior_hash: Option<String>) -> PyResult<String> {
    let mut out = Map::new();
    if new_hash.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err("new_hash required"));
    }
    match prior_hash {
        None => {
            out.insert("accept".to_string(), Value::Bool(true));
            out.insert("duplicate".to_string(), Value::Bool(false));
            out.insert("slash".to_string(), Value::Null);
        }
        Some(prior) if prior == new_hash => {
            out.insert("accept".to_string(), Value::Bool(true));
            out.insert("duplicate".to_string(), Value::Bool(true));
            out.insert("slash".to_string(), Value::Null);
        }
        Some(_) => {
            out.insert("accept".to_string(), Value::Bool(false));
            out.insert("duplicate".to_string(), Value::Bool(false));
            out.insert("slash".to_string(), Value::String("double_vote".into()));
        }
    }
    serde_json::to_string(&Value::Object(out))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[pyfunction]
fn slash_check_double_proposal(already_proposed: bool) -> PyResult<String> {
    let mut out = Map::new();
    if already_proposed {
        out.insert("accept".to_string(), Value::Bool(false));
        out.insert(
            "slash".to_string(),
            Value::String("double_proposal".into()),
        );
    } else {
        out.insert("accept".to_string(), Value::Bool(true));
        out.insert("slash".to_string(), Value::Null);
    }
    serde_json::to_string(&Value::Object(out))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(ffg_threshold, m)?)?;
    m.add_function(wrap_pyfunction!(ffg_best_checkpoint, m)?)?;
    m.add_function(wrap_pyfunction!(ffg_accumulate_vote, m)?)?;
    m.add_function(wrap_pyfunction!(ffg_evaluate_epoch, m)?)?;
    m.add_function(wrap_pyfunction!(fe_epoch, m)?)?;
    m.add_function(wrap_pyfunction!(fe_quorum_reached, m)?)?;
    m.add_function(wrap_pyfunction!(fe_can_finalize, m)?)?;
    m.add_function(wrap_pyfunction!(slash_check_double_vote, m)?)?;
    m.add_function(wrap_pyfunction!(slash_check_double_proposal, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn threshold_matches_python_int_float() {
        assert_eq!(ffg_threshold(100, 2, 3).unwrap(), 66);
        assert_eq!(ffg_threshold(3, 2, 3).unwrap(), 2);
    }

    #[test]
    fn double_vote_conflict() {
        let raw = slash_check_double_vote("b".into(), Some("a".into())).unwrap();
        assert!(raw.contains("double_vote"));
        let ok = slash_check_double_vote("a".into(), None).unwrap();
        assert!(ok.contains("\"accept\":true") || ok.contains("\"accept\": true"));
    }
}
