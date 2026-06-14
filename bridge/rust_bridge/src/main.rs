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

fn get_tx_confirmations(rpc_url: &str, tx_hash: &str) -> Option<u32> {
    let receipt = rpc_call(
        rpc_url,
        "eth_getTransactionReceipt",
        serde_json::json!([tx_hash]),
    )?;
    let block_num = parse_hex_u64(receipt.get("blockNumber")?)?;
    let head_hex = rpc_call(rpc_url, "eth_blockNumber", serde_json::json!([]))?;
    let head = parse_hex_u64(&head_hex)?;
    if head >= block_num {
        Some((head - block_num + 1) as u32)
    } else {
        Some(0)
    }
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

fn verify_l1_if_present(_command: &str, chain: &Option<String>, args: &serde_json::Value) -> Result<u32, String> {
    let need = min_confirmations();
    let chain_name = chain.clone().unwrap_or_else(|| "ethereum".into());
    let rpc = resolve_rpc(&chain_name);
    let l1_tx = l1_tx_from_args(args);
    if rpc.is_some() && l1_tx.is_none() {
        return Err(format!("l1_tx_hash required when RPC configured for {chain_name}"));
    }
    let l1_tx = match l1_tx {
        Some(t) => t,
        None => return Ok(need),
    };
    let rpc = rpc.ok_or_else(|| format!("no RPC for chain {chain_name}"))?;
    let conf = get_tx_confirmations(&rpc, &l1_tx).ok_or_else(|| "L1 RPC check failed".to_string())?;
    if conf < need {
        return Err(format!("L1 confirmations {conf} < required {need}"));
    }
    Ok(conf)
}

fn handle(req: Request) -> Response {
    let chain = req
        .args
        .get("to_chain")
        .or_else(|| req.args.get("from_chain"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());
    let rpc = chain.as_deref().and_then(resolve_rpc);

    let l1_result = if matches!(req.command.as_str(), "confirm" | "incoming") {
        verify_l1_if_present(&req.command, &chain, &req.args)
    } else {
        Ok(min_confirmations())
    };

    match (req.command.as_str(), l1_result) {
        (_, Err(e)) => Response {
            tx_hash: String::new(),
            status: "error".into(),
            source: "abs_bridge_bin_v4".into(),
            chain,
            proof_id: None,
            confirmations: Some(min_confirmations()),
            rpc_url: rpc,
            error: Some(e),
        },
        ("bridge" | "lock" | "confirm" | "incoming", Ok(conf)) => Response {
            tx_hash: make_tx_hash(&req.command, &req.args),
            status: "ok".into(),
            source: "abs_bridge_bin_v4".into(),
            chain: chain.clone(),
            proof_id: Some(make_proof_id(&req.command, &req.args)),
            confirmations: Some(conf),
            rpc_url: rpc,
            error: None,
        },
        ("status", _) => Response {
            tx_hash: String::new(),
            status: "ready".into(),
            source: "abs_bridge_bin_v4".into(),
            chain,
            proof_id: None,
            confirmations: Some(min_confirmations()),
            rpc_url: rpc,
            error: None,
        },
        (other, _) => Response {
            tx_hash: String::new(),
            status: "error".into(),
            source: "abs_bridge_bin_v4".into(),
            chain: None,
            proof_id: None,
            confirmations: None,
            rpc_url: None,
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
    if resp.error.is_some() {
        std::process::exit(1);
    }
    println!("{}", serde_json::to_string(&resp).unwrap_or_default());
}
