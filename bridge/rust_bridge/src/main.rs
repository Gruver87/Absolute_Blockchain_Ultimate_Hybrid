use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::env;
use std::io::{self, Read};

#[derive(Debug, Deserialize)]
struct Request {
    command: String,
    args: serde_json::Value,
}

#[derive(Debug, Serialize)]
struct Response {
    tx_hash: String,
    status: String,
    source: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    chain: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    proof_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    confirmations: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    rpc_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    l1_event_bound: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

fn rpc_env_key(chain: &str) -> Option<&'static str> {
    match chain.to_lowercase().as_str() {
        "ethereum" | "eth" => Some("ETH_RPC_URL"),
        "bsc" | "binance" | "bnb" => Some("BSC_RPC_URL"),
        "polygon" | "matic" => Some("POLYGON_RPC_URL"),
        _ => None,
    }
}

fn resolve_rpc(chain: &str) -> Option<String> {
    rpc_env_key(chain)
        .and_then(|k| env::var(k).ok())
        .filter(|s| !s.is_empty())
}

fn min_confirmations() -> u32 {
    env::var("BRIDGE_MIN_CONFIRMATIONS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(12)
        .max(1)
}

fn require_l1_proof() -> bool {
    env::var("BRIDGE_REQUIRE_L1_PROOF")
        .map(|v| matches!(v.to_lowercase().as_str(), "1" | "true" | "yes" | "on"))
        .unwrap_or(false)
}

fn require_l1_event() -> bool {
    env::var("BRIDGE_REQUIRE_L1_EVENT")
        .map(|v| matches!(v.to_lowercase().as_str(), "1" | "true" | "yes" | "on"))
        .unwrap_or(false)
}

fn expected_lock_contract() -> Option<String> {
    env::var("BRIDGE_L1_LOCK_CONTRACT")
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| s.starts_with("0x") && s.len() >= 42)
}

fn allow_synthetic_hash() -> bool {
    env::var("BRIDGE_ALLOW_SYNTHETIC")
        .map(|v| matches!(v.to_lowercase().as_str(), "1" | "true" | "yes" | "on"))
        .unwrap_or(false)
}

fn resolve_tx_hash(command: &str, args: &serde_json::Value) -> Result<String, String> {
    if let Some(l1_tx) = l1_tx_from_args(args) {
        return Ok(l1_tx);
    }
    if allow_synthetic_hash() {
        return Ok(make_tx_hash(command, args));
    }
    Err("l1_tx_hash required (set BRIDGE_ALLOW_SYNTHETIC=1 only for local dev)".into())
}

fn parse_hex_u64(v: &serde_json::Value) -> Option<u64> {
    match v {
        serde_json::Value::Number(n) => n.as_u64(),
        serde_json::Value::String(s) => {
            let t = s.trim();
            if let Some(h) = t.strip_prefix("0x").or_else(|| t.strip_prefix("0X")) {
                u64::from_str_radix(h, 16).ok()
            } else {
                t.parse().ok()
            }
        }
        _ => None,
    }
}

fn receipt_status_ok(receipt: &serde_json::Value) -> bool {
    match receipt.get("status") {
        Some(serde_json::Value::String(s)) => {
            let t = s.trim();
            let value = if let Some(h) = t.strip_prefix("0x").or_else(|| t.strip_prefix("0X")) {
                u64::from_str_radix(h, 16).ok()
            } else {
                t.parse::<u64>().ok()
            };
            value == Some(1)
        }
        Some(serde_json::Value::Number(n)) => n.as_u64() == Some(1),
        // Fail-closed: status-less receipts are not successful.
        _ => false,
    }
}

fn receipt_has_contract_log(receipt: &serde_json::Value, expected: &str) -> bool {
    let logs = match receipt.get("logs") {
        Some(serde_json::Value::Array(arr)) => arr,
        _ => return false,
    };
    if logs.is_empty() {
        return false;
    }
    let want = expected.to_lowercase();
    logs.iter().any(|log| {
        log.get("address")
            .and_then(|a| a.as_str())
            .map(|a| a.to_lowercase() == want)
            .unwrap_or(false)
    })
}

fn rpc_call(rpc_url: &str, method: &str, params: serde_json::Value) -> Option<serde_json::Value> {
    let body = serde_json::json!({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    });
    let resp = ureq::post(rpc_url)
        .set("Content-Type", "application/json")
        .send_json(body)
        .ok()?;
    let data: serde_json::Value = resp.into_json().ok()?;
    if data.get("error").is_some() {
        return None;
    }
    data.get("result").cloned()
}

/// Returns (confirmations, l1_event_bound).
fn verify_l1_tx(rpc_url: &str, tx_hash: &str) -> Result<(u32, bool), String> {
    let receipt = rpc_call(
        rpc_url,
        "eth_getTransactionReceipt",
        serde_json::json!([tx_hash]),
    )
    .ok_or_else(|| "L1 RPC check failed".to_string())?;
    if receipt.is_null() {
        return Err("L1 receipt not found".into());
    }
    if !receipt_status_ok(&receipt) {
        return Err("L1 receipt status not successful".into());
    }
    let block_num = parse_hex_u64(
        receipt
            .get("blockNumber")
            .ok_or_else(|| "L1 receipt missing blockNumber".to_string())?,
    )
    .ok_or_else(|| "L1 receipt blockNumber invalid".to_string())?;
    let head_hex = rpc_call(rpc_url, "eth_blockNumber", serde_json::json!([]))
        .ok_or_else(|| "L1 eth_blockNumber failed".to_string())?;
    let head = parse_hex_u64(&head_hex).ok_or_else(|| "L1 head block invalid".to_string())?;
    let conf = if head >= block_num {
        (head - block_num + 1) as u32
    } else {
        0
    };

    let mut event_bound = false;
    if require_l1_event() {
        let contract = expected_lock_contract().ok_or_else(|| {
            "BRIDGE_L1_LOCK_CONTRACT required when BRIDGE_REQUIRE_L1_EVENT=1".to_string()
        })?;
        if !receipt_has_contract_log(&receipt, &contract) {
            return Err("L1 receipt has no log from expected lock contract".into());
        }
        // Address-level binding only — not ABI amount/recipient decode.
        event_bound = true;
    }
    Ok((conf, event_bound))
}

fn l1_tx_from_args(args: &serde_json::Value) -> Option<String> {
    for key in ["l1_tx_hash", "proof_tx"] {
        if let Some(v) = args.get(key).and_then(|x| x.as_str()) {
            if v.starts_with("0x") && v.len() >= 10 {
                return Some(v.to_string());
            }
        }
    }
    None
}

fn make_tx_hash(command: &str, args: &serde_json::Value) -> String {
    let seed = format!("{command}:{args}");
    let digest = Sha256::digest(seed.as_bytes());
    format!("0x{}", hex::encode(digest))
}

fn make_proof_id(command: &str, args: &serde_json::Value) -> String {
    let digest = Sha256::digest(format!("proof:{command}:{args}").as_bytes());
    format!("prf_{}", &hex::encode(digest)[..24])
}

fn verify_l1_if_present(
    _command: &str,
    chain: &Option<String>,
    args: &serde_json::Value,
) -> Result<(u32, bool), String> {
    let need = min_confirmations();
    let chain_name = chain.clone().unwrap_or_else(|| "ethereum".into());
    let rpc = resolve_rpc(&chain_name);
    let l1_tx = l1_tx_from_args(args);
    if require_l1_proof() && l1_tx.is_none() {
        return Err(format!("l1_tx_hash required for {chain_name}"));
    }
    if rpc.is_some() && l1_tx.is_none() {
        return Err(format!(
            "l1_tx_hash required when RPC configured for {chain_name}"
        ));
    }
    let l1_tx = match l1_tx {
        Some(t) => t,
        None => return Ok((need, false)),
    };
    let rpc = rpc.ok_or_else(|| format!("no RPC for chain {chain_name}"))?;
    let (conf, event_bound) = verify_l1_tx(&rpc, &l1_tx)?;
    if conf < need {
        return Err(format!("L1 confirmations {conf} < required {need}"));
    }
    Ok((conf, event_bound))
}

fn handle(req: Request) -> Response {
    let chain = req
        .args
        .get("to_chain")
        .or_else(|| req.args.get("from_chain"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());
    if let Some(ref c) = chain {
        let key = c.to_lowercase();
        if key == "solana" || key == "sol" {
            return Response {
                tx_hash: String::new(),
                status: "error".into(),
                source: "abs_bridge_bin_v5".into(),
                chain,
                proof_id: None,
                confirmations: None,
                rpc_url: None,
                l1_event_bound: Some(false),
                error: Some(
                    "solana L1 RPC not implemented; use ethereum/bsc/polygon in production".into(),
                ),
            };
        }
    }
    let rpc = chain.as_deref().and_then(resolve_rpc);

    // lock/bridge must verify L1 when an escrow hash is supplied (Python debits on lock).
    let l1_result = if matches!(
        req.command.as_str(),
        "confirm" | "incoming" | "lock" | "bridge"
    ) {
        verify_l1_if_present(&req.command, &chain, &req.args)
    } else {
        Ok((min_confirmations(), false))
    };

    match (req.command.as_str(), l1_result) {
        (_, Err(e)) => Response {
            tx_hash: String::new(),
            status: "error".into(),
            source: "abs_bridge_bin_v5".into(),
            chain,
            proof_id: None,
            confirmations: Some(min_confirmations()),
            rpc_url: rpc,
            l1_event_bound: Some(false),
            error: Some(e),
        },
        ("bridge" | "lock" | "confirm" | "incoming", Ok((conf, event_bound))) => {
            match resolve_tx_hash(&req.command, &req.args) {
                Ok(tx_hash) => Response {
                    tx_hash,
                    status: "ok".into(),
                    source: "abs_bridge_bin_v5".into(),
                    chain: chain.clone(),
                    proof_id: Some(make_proof_id(&req.command, &req.args)),
                    confirmations: Some(conf),
                    rpc_url: rpc,
                    l1_event_bound: Some(event_bound),
                    error: None,
                },
                Err(e) => Response {
                    tx_hash: String::new(),
                    status: "error".into(),
                    source: "abs_bridge_bin_v5".into(),
                    chain,
                    proof_id: None,
                    confirmations: Some(conf),
                    rpc_url: rpc,
                    l1_event_bound: Some(event_bound),
                    error: Some(e),
                },
            }
        }
        ("status", _) => Response {
            tx_hash: String::new(),
            status: "ready".into(),
            source: "abs_bridge_bin_v5".into(),
            chain,
            proof_id: None,
            confirmations: Some(min_confirmations()),
            rpc_url: rpc,
            l1_event_bound: Some(require_l1_event() && expected_lock_contract().is_some()),
            error: None,
        },
        (other, _) => Response {
            tx_hash: String::new(),
            status: "error".into(),
            source: "abs_bridge_bin_v5".into(),
            chain: None,
            proof_id: None,
            confirmations: None,
            rpc_url: None,
            l1_event_bound: Some(false),
            error: Some(format!("unknown command: {other}")),
        },
    }
}

fn main() {
    let mut input = String::new();
    if io::stdin().read_to_string(&mut input).is_err() || input.trim().is_empty() {
        eprintln!("abs_bridge_bin: empty stdin");
        std::process::exit(2);
    }
    let req: Request = match serde_json::from_str(&input) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("abs_bridge_bin: invalid json: {e}");
            std::process::exit(2);
        }
    };
    let resp = handle(req);
    println!("{}", serde_json::to_string(&resp).unwrap_or_default());
    if resp.error.is_some() {
        std::process::exit(1);
    }
}
