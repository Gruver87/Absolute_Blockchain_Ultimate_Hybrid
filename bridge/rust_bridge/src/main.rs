use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
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
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

fn make_tx_hash(command: &str, args: &serde_json::Value) -> String {
    let seed = format!("{command}:{args}");
    let digest = Sha256::digest(seed.as_bytes());
    format!("0x{}", hex::encode(digest))
}

fn handle(req: Request) -> Response {
    match req.command.as_str() {
        "bridge" | "lock" | "confirm" => Response {
            tx_hash: make_tx_hash(&req.command, &req.args),
            status: "ok".into(),
            error: None,
        },
        other => Response {
            tx_hash: String::new(),
            status: "error".into(),
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
