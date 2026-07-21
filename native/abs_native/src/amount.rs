//! Canonical ABS amount math (satoshi) + StateEngine batch apply.

use pyo3::prelude::*;
use rust_decimal::prelude::*;
use rust_decimal::{Decimal, RoundingStrategy};
use serde_json::{Map, Value};
use std::collections::BTreeMap;
use std::str::FromStr;

pub(crate) const SATOSHI_MULTIPLIER: i64 = 1_000_000;
pub(crate) const MAX_STATE_ENGINE_ACCOUNTS: usize = 1_000_000;
pub(crate) const MAX_STATE_ENGINE_TXS: usize = 100_000;

fn decimal_from_amount(amount: &str) -> PyResult<Decimal> {
    let trimmed = amount.trim();
    if trimmed.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err("invalid amount: empty"));
    }
    Decimal::from_str(trimmed).map_err(|e| {
        pyo3::exceptions::PyValueError::new_err(format!("invalid amount: {e}"))
    })
}

pub(crate) fn to_satoshi_inner(amount: &str) -> PyResult<i64> {
    let d = decimal_from_amount(amount)?;
    let scaled = d * Decimal::from(SATOSHI_MULTIPLIER);
    let truncated = scaled.round_dp_with_strategy(0, RoundingStrategy::ToZero);
    truncated.to_i64().ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err("amount out of i64 satoshi range")
    })
}

pub(crate) fn apply_delta_satoshi_inner(current_sat: i64, delta_abs: &str) -> PyResult<i64> {
    let delta = to_satoshi_inner(delta_abs)?;
    Ok((current_sat.saturating_add(delta)).max(0))
}

fn from_satoshi_float_inner(satoshi: i64) -> f64 {
    let d = Decimal::from(satoshi) / Decimal::from(SATOSHI_MULTIPLIER);
    d.to_f64().unwrap_or(0.0)
}

fn account_balance(acc: &Value) -> i64 {
    acc.get("balance")
        .and_then(|v| v.as_i64())
        .or_else(|| {
            acc.get("balance")
                .and_then(|v| v.as_u64())
                .map(|u| u as i64)
        })
        .unwrap_or(0)
        .max(0)
}

fn account_nonce(acc: &Value) -> i64 {
    acc.get("nonce")
        .and_then(|v| v.as_i64())
        .or_else(|| {
            acc.get("nonce")
                .and_then(|v| v.as_u64())
                .map(|u| u as i64)
        })
        .unwrap_or(0)
}

fn empty_account() -> Value {
    let mut row = Map::new();
    row.insert("balance".to_string(), Value::Number(0.into()));
    row.insert("nonce".to_string(), Value::Number(0.into()));
    Value::Object(row)
}

fn set_account_balance(acc: &mut Value, balance: i64, nonce: i64) {
    let obj = acc.as_object_mut().expect("account object");
    obj.insert("balance".to_string(), Value::Number(balance.into()));
    obj.insert("nonce".to_string(), Value::Number(nonce.into()));
}

fn tx_amount_sat(tx: &Value) -> PyResult<i64> {
    let obj = tx
        .as_object()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("tx must be object"))?;
    if let Some(v) = obj.get("amount_satoshi") {
        let sat = v
            .as_i64()
            .or_else(|| v.as_u64().map(|u| u as i64))
            .or_else(|| v.as_f64().map(|f| f as i64))
            .unwrap_or(0);
        return Ok(sat.max(0));
    }
    let amount = obj
        .get("amount")
        .or_else(|| obj.get("value"))
        .cloned()
        .unwrap_or(Value::Number(0.into()));
    match amount {
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                to_satoshi_inner(&i.to_string())
            } else if let Some(u) = n.as_u64() {
                to_satoshi_inner(&u.to_string())
            } else if let Some(f) = n.as_f64() {
                to_satoshi_inner(&f.to_string())
            } else {
                Ok(0)
            }
        }
        Value::String(s) => to_satoshi_inner(&s),
        _ => Ok(0),
    }
}

fn tx_fee_sat(tx: &Value) -> PyResult<i64> {
    let obj = tx
        .as_object()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("tx must be object"))?;
    if let Some(v) = obj.get("fee_satoshi") {
        let sat = v
            .as_i64()
            .or_else(|| v.as_u64().map(|u| u as i64))
            .or_else(|| v.as_f64().map(|f| f as i64))
            .unwrap_or(0);
        return Ok(sat.max(0));
    }
    let fee = obj.get("fee").cloned().unwrap_or(Value::Number(0.into()));
    match fee {
        Value::Null => Ok(0),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                to_satoshi_inner(&i.to_string())
            } else if let Some(u) = n.as_u64() {
                to_satoshi_inner(&u.to_string())
            } else if let Some(f) = n.as_f64() {
                to_satoshi_inner(&f.to_string())
            } else {
                Ok(0)
            }
        }
        Value::String(s) => to_satoshi_inner(&s),
        _ => Ok(0),
    }
}

fn apply_one_tx(accounts: &mut BTreeMap<String, Value>, tx: &Value) -> PyResult<()> {
    let obj = tx
        .as_object()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("tx must be object"))?;
    let from_addr = obj
        .get("from")
        .or_else(|| obj.get("from_addr"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let to_addr = obj
        .get("to")
        .or_else(|| obj.get("to_addr"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let amount_sat = tx_amount_sat(tx)?;
    let fee_sat = tx_fee_sat(tx)?;

    if !accounts.contains_key(&from_addr) {
        accounts.insert(from_addr.clone(), empty_account());
    }
    let from_bal = account_balance(accounts.get(&from_addr).unwrap());
    let from_nonce = account_nonce(accounts.get(&from_addr).unwrap());
    let total = amount_sat.saturating_add(fee_sat);
    if from_bal < total {
        return Err(pyo3::exceptions::PyRuntimeError::new_err(format!(
            "Insufficient balance: {from_addr}"
        )));
    }
    let tx_nonce = obj
        .get("nonce")
        .and_then(|v| v.as_i64().or_else(|| v.as_u64().map(|u| u as i64)))
        .unwrap_or(from_nonce);
    if tx_nonce != from_nonce {
        return Err(pyo3::exceptions::PyRuntimeError::new_err(format!(
            "Invalid nonce: expected {from_nonce}, got {tx_nonce}"
        )));
    }

    {
        let from = accounts.get_mut(&from_addr).unwrap();
        set_account_balance(from, from_bal - total, from_nonce + 1);
    }
    if !accounts.contains_key(&to_addr) {
        accounts.insert(to_addr.clone(), empty_account());
    }
    {
        let to = accounts.get_mut(&to_addr).unwrap();
        let to_bal = account_balance(to);
        let to_nonce = account_nonce(to);
        set_account_balance(to, to_bal + amount_sat, to_nonce);
    }
    Ok(())
}

fn parse_accounts_map(accounts_json: &str) -> PyResult<BTreeMap<String, Value>> {
    let value: Value = serde_json::from_str(accounts_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let obj = value.as_object().ok_or_else(|| {
        pyo3::exceptions::PyValueError::new_err("accounts_json must be an object")
    })?;
    if obj.len() > MAX_STATE_ENGINE_ACCOUNTS {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "too_many_accounts: {} > {}",
            obj.len(),
            MAX_STATE_ENGINE_ACCOUNTS
        )));
    }
    let mut map = BTreeMap::new();
    for (addr, row) in obj {
        if !row.is_object() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "account row must be object",
            ));
        }
        map.insert(addr.clone(), row.clone());
    }
    Ok(map)
}

#[pyfunction]
fn amount_to_satoshi(amount_abs: String) -> PyResult<i64> {
    to_satoshi_inner(&amount_abs)
}

#[pyfunction]
fn amount_apply_delta_satoshi(current_sat: i64, delta_abs: String) -> PyResult<i64> {
    apply_delta_satoshi_inner(current_sat, &delta_abs)
}

#[pyfunction]
fn amount_from_satoshi_float(satoshi: i64) -> PyResult<f64> {
    Ok(from_satoshi_float_inner(satoshi))
}

/// L1 transfer fee split matching Python float math:
/// fee = gas * gas_price_wei (optionally max with gas_used),
/// burned = fee * burn_rate, miner_fee = fee - burned, total = value + fee.
#[pyfunction]
#[pyo3(signature = (gas, gas_price_wei, burn_rate, value, gas_used=None))]
fn plan_transfer_fees(
    gas: u64,
    gas_price_wei: f64,
    burn_rate: f64,
    value: f64,
    gas_used: Option<u64>,
) -> PyResult<(f64, f64, f64, f64)> {
    if !gas_price_wei.is_finite() || !burn_rate.is_finite() || !value.is_finite() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "non_finite_fee_inputs",
        ));
    }
    if gas_price_wei < 0.0 || burn_rate < 0.0 || value < 0.0 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "negative_fee_inputs",
        ));
    }
    let mut fee = (gas as f64) * gas_price_wei;
    if let Some(used) = gas_used {
        fee = fee.max((used as f64) * gas_price_wei);
    }
    let rate = burn_rate.clamp(0.0, 1.0);
    let burned = fee * rate;
    let miner_fee = fee - burned;
    let total_cost = value + fee;
    Ok((fee, burned, miner_fee, total_cost))
}

/// True when sender_sat covers to_satoshi(total_cost_abs).
#[pyfunction]
fn can_afford_transfer(sender_sat: i64, total_cost_abs: f64) -> PyResult<bool> {
    if !total_cost_abs.is_finite() {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "non_finite_total_cost",
        ));
    }
    if total_cost_abs < 0.0 {
        return Ok(false);
    }
    let need = to_satoshi_inner(&total_cost_abs.to_string())?;
    Ok(sender_sat >= need)
}

#[pyfunction]
fn state_engine_apply_transactions(accounts_json: String, txs_json: String) -> PyResult<String> {
    let mut accounts = parse_accounts_map(&accounts_json)?;
    let txs: Value = serde_json::from_str(&txs_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    let txs = txs
        .as_array()
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("txs_json must be an array"))?;
    if txs.len() > MAX_STATE_ENGINE_TXS {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "too_many_txs: {} > {}",
            txs.len(),
            MAX_STATE_ENGINE_TXS
        )));
    }
    for tx in txs {
        apply_one_tx(&mut accounts, tx)?;
    }
    let mut out = Map::new();
    for (addr, row) in accounts {
        out.insert(addr, row);
    }
    serde_json::to_string(&Value::Object(out))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(amount_to_satoshi, m)?)?;
    m.add_function(wrap_pyfunction!(amount_apply_delta_satoshi, m)?)?;
    m.add_function(wrap_pyfunction!(amount_from_satoshi_float, m)?)?;
    m.add_function(wrap_pyfunction!(plan_transfer_fees, m)?)?;
    m.add_function(wrap_pyfunction!(can_afford_transfer, m)?)?;
    m.add_function(wrap_pyfunction!(state_engine_apply_transactions, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn to_satoshi_floors() {
        assert_eq!(to_satoshi_inner("1").unwrap(), 1_000_000);
        assert_eq!(to_satoshi_inner("0.0000001").unwrap(), 0);
        assert_eq!(to_satoshi_inner("1.9999999").unwrap(), 1_999_999);
    }

    #[test]
    fn apply_delta_never_negative() {
        assert_eq!(apply_delta_satoshi_inner(1_000_000, "-0.25").unwrap(), 750_000);
        assert_eq!(apply_delta_satoshi_inner(100, "-1").unwrap(), 0);
    }

    #[test]
    fn plan_transfer_fees_splits_burn() {
        let (fee, burned, miner, total) =
            plan_transfer_fees(21_000, 0.000_000_1, 0.02, 1.0, None).unwrap();
        assert!((fee - 0.0021).abs() < 1e-12);
        assert!((burned - fee * 0.02).abs() < 1e-15);
        assert!((miner - (fee - burned)).abs() < 1e-15);
        assert!((total - (1.0 + fee)).abs() < 1e-15);
    }
}
