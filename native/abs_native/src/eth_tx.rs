//! Ethereum raw transaction decode (legacy / EIP-1559 / EIP-4844) with secp recover.
//! Returns JSON aligned with crypto/eth_tx.py decode_raw_transaction.

use pyo3::prelude::*;
use serde_json::{Map, Number, Value};

use crate::recover_eth_address_keccak_inner;
use crate::rlp::{
    decode_at, decode_single_item, encode_item, int_to_rlp_bytes, item_to_bytes, item_to_u128,
    RlpItem,
};
use crate::keccak256_digest_bytes;

fn json_u128(v: u128) -> Value {
    if v <= i64::MAX as u128 {
        Value::Number(Number::from(v as i64))
    } else if v <= u64::MAX as u128 {
        Value::Number(Number::from(v as u64))
    } else {
        Value::String(v.to_string())
    }
}

fn addr_from_bytes(raw: &[u8]) -> String {
    if raw.is_empty() {
        return String::new();
    }
    let hex = hex::encode(raw);
    let padded = format!("{hex:0>40}");
    format!("0x{}", &padded[padded.len().saturating_sub(40)..])
}

fn pad32(raw: &[u8]) -> Result<[u8; 32], String> {
    if raw.len() > 32 {
        return Err("bad_signature_length".into());
    }
    let mut out = [0u8; 32];
    out[32 - raw.len()..].copy_from_slice(raw);
    Ok(out)
}

fn recovery_id_from_v(v: u128, chain_id: Option<u128>) -> Result<u8, String> {
    if v == 0 || v == 1 {
        return Ok(v as u8);
    }
    if v == 27 || v == 28 {
        return Ok((v - 27) as u8);
    }
    if v >= 35 {
        let cid = chain_id.unwrap_or_else(|| (v - 35) / 2);
        return Ok(((v - 35 - 2 * cid) % 2) as u8);
    }
    Err(format!("unsupported_v:{v}"))
}

fn validate_access_list(item: &RlpItem) -> Result<(), String> {
    let list = match item {
        RlpItem::List(items) => items,
        RlpItem::Bytes(b) if b.is_empty() => return Ok(()),
        _ => return Err("bad_access_list".into()),
    };
    for entry in list {
        let pair = match entry {
            RlpItem::List(p) => p,
            _ => return Err("bad_access_list".into()),
        };
        if pair.len() != 2 {
            return Err("bad_access_list".into());
        }
        item_to_bytes(&pair[0])?;
        match &pair[1] {
            RlpItem::List(keys) => {
                for k in keys {
                    item_to_bytes(k)?;
                }
            }
            _ => return Err("bad_access_list".into()),
        }
    }
    Ok(())
}

fn decode_blob_hashes(item: &RlpItem) -> Result<Vec<Vec<u8>>, String> {
    let list = match item {
        RlpItem::List(items) => items,
        RlpItem::Bytes(b) if b.is_empty() => return Ok(Vec::new()),
        _ => return Err("blob_hashes_not_list".into()),
    };
    let mut out = Vec::new();
    for h in list {
        let raw = item_to_bytes(h)?;
        if raw.len() != 32 {
            return Err("blob_hash_length".into());
        }
        out.push(raw);
    }
    Ok(out)
}

fn recover_from(
    signing_payload: &[u8],
    v_or_y: u128,
    r: &[u8],
    s: &[u8],
    chain_id_for_v: Option<u128>,
) -> Result<String, String> {
    let hash = keccak256_digest_bytes(signing_payload);
    let rec_id = recovery_id_from_v(v_or_y, chain_id_for_v)?;
    let r32 = pad32(r)?;
    let s32 = pad32(s)?;
    recover_eth_address_keccak_inner(&hash, &r32, &s32, rec_id)
}

fn decode_legacy(fields: &[RlpItem]) -> Result<Map<String, Value>, String> {
    if fields.len() != 9 {
        return Err("legacy_tx_field_count".into());
    }
    let nonce = item_to_u128(&fields[0])?;
    let gas_price = item_to_u128(&fields[1])?;
    let gas_limit = item_to_u128(&fields[2])?;
    let to_raw = item_to_bytes(&fields[3])?;
    let value = item_to_u128(&fields[4])?;
    let data = item_to_bytes(&fields[5])?;
    let v = item_to_u128(&fields[6])?;
    let r = item_to_bytes(&fields[7])?;
    let s = item_to_bytes(&fields[8])?;
    let chain_id = if v >= 35 { Some((v - 35) / 2) } else { None };

    let mut signing = vec![
        RlpItem::Bytes(int_to_rlp_bytes(nonce)),
        RlpItem::Bytes(int_to_rlp_bytes(gas_price)),
        RlpItem::Bytes(int_to_rlp_bytes(gas_limit)),
        RlpItem::Bytes(to_raw.clone()),
        RlpItem::Bytes(int_to_rlp_bytes(value)),
        RlpItem::Bytes(data.clone()),
    ];
    if let Some(cid) = chain_id {
        signing.push(RlpItem::Bytes(int_to_rlp_bytes(cid)));
        signing.push(RlpItem::Bytes(Vec::new()));
        signing.push(RlpItem::Bytes(Vec::new()));
    }
    let encoded = encode_item(&RlpItem::List(signing));
    let from_addr = recover_from(&encoded, v, &r, &s, chain_id)?;

    let mut out = Map::new();
    out.insert("from".into(), Value::String(from_addr));
    out.insert("to".into(), Value::String(addr_from_bytes(&to_raw)));
    out.insert("value".into(), json_u128(value));
    out.insert("nonce".into(), json_u128(nonce));
    out.insert("gas".into(), json_u128(gas_limit));
    out.insert("gasPrice".into(), json_u128(gas_price));
    out.insert(
        "data".into(),
        Value::String(if data.is_empty() {
            "0x".into()
        } else {
            format!("0x{}", hex::encode(&data))
        }),
    );
    out.insert(
        "chain_id".into(),
        chain_id.map(json_u128).unwrap_or(Value::Null),
    );
    out.insert("eth_signed".into(), Value::Bool(true));
    out.insert("eth_tx_type".into(), Value::String("legacy".into()));
    out.insert(
        "signature".into(),
        Value::String(format!("{}{}{:x}", hex::encode(&r), hex::encode(&s), v)),
    );
    out.insert("public_key".into(), Value::String(String::new()));
    out.insert("eth_v".into(), json_u128(v));
    out.insert("eth_r".into(), Value::String(hex::encode(&r)));
    out.insert("eth_s".into(), Value::String(hex::encode(&s)));
    Ok(out)
}

fn decode_eip1559(raw: &[u8]) -> Result<Map<String, Value>, String> {
    let (payload, _) = decode_at(raw, 1)?;
    let fields = match payload {
        RlpItem::List(items) => items,
        _ => return Err("eip1559_field_count".into()),
    };
    if fields.len() != 12 {
        return Err("eip1559_field_count".into());
    }
    let chain_id = item_to_u128(&fields[0])?;
    let nonce = item_to_u128(&fields[1])?;
    let max_priority = item_to_u128(&fields[2])?;
    let max_fee = item_to_u128(&fields[3])?;
    let gas_limit = item_to_u128(&fields[4])?;
    let to_raw = item_to_bytes(&fields[5])?;
    let value = item_to_u128(&fields[6])?;
    let data = item_to_bytes(&fields[7])?;
    validate_access_list(&fields[8])?;
    let y_parity = item_to_u128(&fields[9])?;
    let r = item_to_bytes(&fields[10])?;
    let s = item_to_bytes(&fields[11])?;

    let signing_body = RlpItem::List(vec![
        RlpItem::Bytes(int_to_rlp_bytes(chain_id)),
        RlpItem::Bytes(int_to_rlp_bytes(nonce)),
        RlpItem::Bytes(int_to_rlp_bytes(max_priority)),
        RlpItem::Bytes(int_to_rlp_bytes(max_fee)),
        RlpItem::Bytes(int_to_rlp_bytes(gas_limit)),
        RlpItem::Bytes(to_raw.clone()),
        RlpItem::Bytes(int_to_rlp_bytes(value)),
        RlpItem::Bytes(data.clone()),
        fields[8].clone(),
    ]);
    let mut signing_payload = vec![0x02u8];
    signing_payload.extend_from_slice(&encode_item(&signing_body));
    let from_addr = recover_from(&signing_payload, y_parity, &r, &s, None)?;
    let v = if chain_id > 0 {
        y_parity + 35 + 2 * chain_id
    } else {
        y_parity + 27
    };

    let mut out = Map::new();
    out.insert("from".into(), Value::String(from_addr));
    out.insert("to".into(), Value::String(addr_from_bytes(&to_raw)));
    out.insert("value".into(), json_u128(value));
    out.insert("nonce".into(), json_u128(nonce));
    out.insert("gas".into(), json_u128(gas_limit));
    out.insert("gasPrice".into(), json_u128(max_fee));
    out.insert("maxFeePerGas".into(), json_u128(max_fee));
    out.insert("maxPriorityFeePerGas".into(), json_u128(max_priority));
    out.insert(
        "data".into(),
        Value::String(if data.is_empty() {
            "0x".into()
        } else {
            format!("0x{}", hex::encode(&data))
        }),
    );
    out.insert("chain_id".into(), json_u128(chain_id));
    out.insert("eth_signed".into(), Value::Bool(true));
    out.insert("eth_tx_type".into(), Value::String("eip1559".into()));
    out.insert(
        "signature".into(),
        Value::String(format!(
            "{}{}{:x}",
            hex::encode(&r),
            hex::encode(&s),
            y_parity
        )),
    );
    out.insert("public_key".into(), Value::String(String::new()));
    out.insert("eth_v".into(), json_u128(v));
    out.insert("eth_y_parity".into(), json_u128(y_parity));
    out.insert("eth_r".into(), Value::String(hex::encode(&r)));
    out.insert("eth_s".into(), Value::String(hex::encode(&s)));
    Ok(out)
}

fn decode_eip4844(raw: &[u8]) -> Result<Map<String, Value>, String> {
    let (payload, _) = decode_at(raw, 1)?;
    let fields = match payload {
        RlpItem::List(items) => items,
        _ => return Err("eip4844_field_count".into()),
    };
    if fields.len() != 14 {
        return Err("eip4844_field_count".into());
    }
    let chain_id = item_to_u128(&fields[0])?;
    let nonce = item_to_u128(&fields[1])?;
    let max_priority = item_to_u128(&fields[2])?;
    let max_fee = item_to_u128(&fields[3])?;
    let gas_limit = item_to_u128(&fields[4])?;
    let to_raw = item_to_bytes(&fields[5])?;
    let value = item_to_u128(&fields[6])?;
    let data = item_to_bytes(&fields[7])?;
    validate_access_list(&fields[8])?;
    let max_fee_per_blob_gas = item_to_u128(&fields[9])?;
    let blob_hashes = decode_blob_hashes(&fields[10])?;
    let y_parity = item_to_u128(&fields[11])?;
    let r = item_to_bytes(&fields[12])?;
    let s = item_to_bytes(&fields[13])?;

    let signing_body = RlpItem::List(vec![
        RlpItem::Bytes(int_to_rlp_bytes(chain_id)),
        RlpItem::Bytes(int_to_rlp_bytes(nonce)),
        RlpItem::Bytes(int_to_rlp_bytes(max_priority)),
        RlpItem::Bytes(int_to_rlp_bytes(max_fee)),
        RlpItem::Bytes(int_to_rlp_bytes(gas_limit)),
        RlpItem::Bytes(to_raw.clone()),
        RlpItem::Bytes(int_to_rlp_bytes(value)),
        RlpItem::Bytes(data.clone()),
        fields[8].clone(),
        RlpItem::Bytes(int_to_rlp_bytes(max_fee_per_blob_gas)),
        fields[10].clone(),
    ]);
    let mut signing_payload = vec![0x03u8];
    signing_payload.extend_from_slice(&encode_item(&signing_body));
    let from_addr = recover_from(&signing_payload, y_parity, &r, &s, None)?;
    let v = if chain_id > 0 {
        y_parity + 35 + 2 * chain_id
    } else {
        y_parity + 27
    };

    let blob_hex: Vec<Value> = blob_hashes
        .iter()
        .map(|h| Value::String(format!("0x{}", hex::encode(h))))
        .collect();
    let blob_int: Vec<Value> = blob_hashes
        .iter()
        .map(|h| {
            let mut acc = num_bigint::BigUint::from(0u32);
            for b in h {
                acc = (acc << 8) + num_bigint::BigUint::from(*b);
            }
            Value::String(acc.to_str_radix(10))
        })
        .collect();

    let mut out = Map::new();
    out.insert("from".into(), Value::String(from_addr));
    out.insert("to".into(), Value::String(addr_from_bytes(&to_raw)));
    out.insert("value".into(), json_u128(value));
    out.insert("nonce".into(), json_u128(nonce));
    out.insert("gas".into(), json_u128(gas_limit));
    out.insert("gasPrice".into(), json_u128(max_fee));
    out.insert("maxFeePerGas".into(), json_u128(max_fee));
    out.insert("maxPriorityFeePerGas".into(), json_u128(max_priority));
    out.insert("maxFeePerBlobGas".into(), json_u128(max_fee_per_blob_gas));
    out.insert("blob_versioned_hashes".into(), Value::Array(blob_hex));
    out.insert("blob_hashes".into(), Value::Array(blob_int));
    out.insert(
        "data".into(),
        Value::String(if data.is_empty() {
            "0x".into()
        } else {
            format!("0x{}", hex::encode(&data))
        }),
    );
    out.insert("chain_id".into(), json_u128(chain_id));
    out.insert("eth_signed".into(), Value::Bool(true));
    out.insert("eth_tx_type".into(), Value::String("eip4844".into()));
    out.insert(
        "signature".into(),
        Value::String(format!(
            "{}{}{:x}",
            hex::encode(&r),
            hex::encode(&s),
            y_parity
        )),
    );
    out.insert("public_key".into(), Value::String(String::new()));
    out.insert("eth_v".into(), json_u128(v));
    out.insert("eth_y_parity".into(), json_u128(y_parity));
    out.insert("eth_r".into(), Value::String(hex::encode(&r)));
    out.insert("eth_s".into(), Value::String(hex::encode(&s)));
    Ok(out)
}

fn decode_raw_inner(raw: &[u8]) -> Result<Map<String, Value>, String> {
    if raw.is_empty() {
        return Err("empty_raw_transaction".into());
    }
    match raw[0] {
        0x02 => decode_eip1559(raw),
        0x03 => decode_eip4844(raw),
        0x01 | 0x04 => Err(format!("unsupported_typed_tx:{:#x}", raw[0])),
        _ => {
            let item = decode_single_item(raw)?;
            match item {
                RlpItem::List(fields) => decode_legacy(&fields),
                _ => Err("raw_tx_not_list".into()),
            }
        }
    }
}

#[pyfunction]
fn decode_eth_raw_tx(raw: Vec<u8>) -> PyResult<String> {
    let map = decode_raw_inner(&raw).map_err(pyo3::exceptions::PyValueError::new_err)?;
    serde_json::to_string(&Value::Object(map))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[pyfunction]
fn decode_eth_raw_tx_hex(raw_hex: String) -> PyResult<String> {
    let cleaned = raw_hex.trim().trim_start_matches("0x").trim_start_matches("0X");
    let raw = hex::decode(cleaned).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    decode_eth_raw_tx(raw)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(decode_eth_raw_tx, m)?)?;
    m.add_function(wrap_pyfunction!(decode_eth_raw_tx_hex, m)?)?;
    Ok(())
}
