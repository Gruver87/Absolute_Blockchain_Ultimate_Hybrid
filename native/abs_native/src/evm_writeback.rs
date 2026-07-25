//! Nested CALL writeback planner (v1.3.59).
//!
//! Builds concrete persist ops (set_storage / transfer_value / append_logs).
//! Python DB still applies — not in-process Rocks / CREATE write.

use pyo3::prelude::*;
use serde_json::{Map, Number, Value};

fn normalize_kind(kind: &str) -> PyResult<String> {
    let kind = kind.trim().to_ascii_lowercase();
    match kind.as_str() {
        "call" | "callcode" | "delegatecall" | "staticcall" => Ok(kind),
        _ => Err(pyo3::exceptions::PyValueError::new_err(
            "kind must be call|callcode|delegatecall|staticcall",
        )),
    }
}

fn storage_object_from_json(raw: Option<&str>) -> Value {
    let Some(text) = raw else {
        return Value::Object(Map::new());
    };
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return Value::Object(Map::new());
    }
    match serde_json::from_str::<Value>(trimmed) {
        Ok(Value::Object(map)) => {
            let mut out = Map::new();
            for (k, v) in map {
                // Canonicalize keys as decimal strings for DB update_account_storage.
                let key = if let Ok(n) = k.parse::<i128>() {
                    n.to_string()
                } else if let Some(hex) = k.strip_prefix("0x").or_else(|| k.strip_prefix("0X")) {
                    match i128::from_str_radix(hex, 16) {
                        Ok(n) => n.to_string(),
                        Err(_) => k,
                    }
                } else {
                    k
                };
                let val = match v {
                    Value::Number(n) => Value::Number(n),
                    Value::String(s) => {
                        if let Ok(n) = s.parse::<i64>() {
                            Value::Number(n.into())
                        } else {
                            Value::String(s)
                        }
                    }
                    other => other,
                };
                out.insert(key, val);
            }
            Value::Object(out)
        }
        Ok(other) => other,
        Err(_) => Value::Object(Map::new()),
    }
}

fn logs_array_from_json(raw: Option<&str>) -> Value {
    let Some(text) = raw else {
        return Value::Array(vec![]);
    };
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return Value::Array(vec![]);
    }
    match serde_json::from_str::<Value>(trimmed) {
        Ok(Value::Array(arr)) => Value::Array(arr),
        _ => Value::Array(vec![]),
    }
}

/// Plan nested CALL writeback as concrete ops with resolved addresses.
#[pyfunction]
#[pyo3(name = "evm_plan_nested_call_writeback")]
#[pyo3(signature = (kind, parent_read_only, caller, target, value_wei, success, storage_json=None, logs_json=None))]
pub fn evm_plan_nested_call_writeback_py(
    kind: String,
    parent_read_only: bool,
    caller: String,
    target: String,
    value_wei: i64,
    success: bool,
    storage_json: Option<String>,
    logs_json: Option<String>,
) -> PyResult<String> {
    let kind = normalize_kind(&kind)?;
    let value_wei = value_wei.max(0);
    let caller = caller.trim().to_string();
    let target = target.trim().to_string();
    let nested_read_only = parent_read_only || kind == "staticcall";
    let mut persist_storage = false;
    let mut persist_value = false;
    let mut persist_logs = false;
    let storage_owner = if kind == "delegatecall" || kind == "callcode" {
        "caller"
    } else {
        "target"
    };
    let exec_address = storage_owner;
    let mut value_from = "";
    let mut value_to = "";
    let mut effective_value_wei: i64 = 0;
    let reject_create = nested_read_only;

    if success && !nested_read_only {
        persist_storage = true;
        if kind == "delegatecall" || kind == "callcode" {
            persist_logs = true;
        }
        if (kind == "call" || kind == "callcode") && value_wei > 0 {
            persist_value = true;
            value_from = "caller";
            value_to = "target";
            effective_value_wei = value_wei;
        }
    }

    let storage_addr = if storage_owner == "caller" {
        caller.clone()
    } else {
        target.clone()
    };
    let mut ops: Vec<Value> = Vec::new();
    if persist_storage {
        let mut op = Map::new();
        op.insert("op".into(), Value::String("set_storage".into()));
        op.insert("address".into(), Value::String(storage_addr));
        op.insert(
            "storage".into(),
            storage_object_from_json(storage_json.as_deref()),
        );
        ops.push(Value::Object(op));
    }
    if persist_value && effective_value_wei > 0 {
        let from_addr = if value_from == "caller" {
            caller.clone()
        } else {
            target.clone()
        };
        let to_addr = if value_to == "target" {
            target.clone()
        } else {
            caller.clone()
        };
        let mut op = Map::new();
        op.insert("op".into(), Value::String("transfer_value".into()));
        op.insert("from".into(), Value::String(from_addr));
        op.insert("to".into(), Value::String(to_addr));
        op.insert(
            "value_wei".into(),
            Value::Number(Number::from(effective_value_wei)),
        );
        ops.push(Value::Object(op));
    }
    if persist_logs {
        let logs = logs_array_from_json(logs_json.as_deref());
        if matches!(&logs, Value::Array(a) if !a.is_empty()) {
            let mut op = Map::new();
            op.insert("op".into(), Value::String("append_logs".into()));
            // Absolute nested logs are attributed to the caller frame address.
            op.insert("address".into(), Value::String(caller.clone()));
            op.insert("logs".into(), logs);
            ops.push(Value::Object(op));
        }
    }

    let mut out = Map::new();
    out.insert("kind".into(), Value::String(kind));
    out.insert("caller".into(), Value::String(caller));
    out.insert("target".into(), Value::String(target));
    out.insert("nested_read_only".into(), Value::Bool(nested_read_only));
    out.insert("persist_storage".into(), Value::Bool(persist_storage));
    out.insert("persist_value".into(), Value::Bool(persist_value));
    out.insert("persist_logs".into(), Value::Bool(persist_logs));
    out.insert(
        "storage_owner".into(),
        Value::String(storage_owner.to_string()),
    );
    out.insert(
        "exec_address".into(),
        Value::String(exec_address.to_string()),
    );
    out.insert("value_from".into(), Value::String(value_from.to_string()));
    out.insert("value_to".into(), Value::String(value_to.to_string()));
    out.insert(
        "effective_value_wei".into(),
        Value::Number(Number::from(effective_value_wei)),
    );
    out.insert("reject_create".into(), Value::Bool(reject_create));
    out.insert("success".into(), Value::Bool(success));
    out.insert("ops".into(), Value::Array(ops));
    out.insert("native_writeback".into(), Value::Bool(true));
    out.insert("native_plan".into(), Value::Bool(true));
    serde_json::to_string(&Value::Object(out))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(evm_plan_nested_call_writeback_py, m)?)?;
    Ok(())
}
