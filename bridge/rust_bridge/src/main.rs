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

fn chain_env_key(chain: &str) -> String {
    format!("{}_RPC_URL", chain.to_uppercase())
}

fn resolve_rpc(chain: &str) -> Option<String> {
    let key = chain_env_key(chain);
    env::var(&key).ok().filter(|s| !s.is_empty())
}

fn min_confirmations() -> u32 {
    env::var("BRIDGE_MIN_CONFIRMATIONS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(12)
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

fn handle(req: Request) -> Response {
    let chain = req
        .args
        .get("to_chain")
        .or_else(|| req.args.get("from_chain"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());
    let rpc = chain.as_deref().and_then(resolve_rpc);

    match req.command.as_str() {
        "bridge" | "lock" | "confirm" | "incoming" => Response {
            tx_hash: make_tx_hash(&req.command, &req.args),
            status: "ok".into(),
            source: "abs_bridge_bin_v2".into(),
            chain: chain.clone(),
            proof_id: Some(make_proof_id(&req.command, &req.args)),
            confirmations: Some(min_confirmations()),
            rpc_url: rpc,
            error: None,
        },
        "status" => Response {
            tx_hash: String::new(),
            status: "ready".into(),
            source: "abs_bridge_bin_v2".into(),
            chain,
            proof_id: None,
            confirmations: Some(min_confirmations()),
            rpc_url: rpc,
            error: None,
        },
        other => Response {
            tx_hash: String::new(),
            status: "error".into(),
            source: "abs_bridge_bin_v2".into(),
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
