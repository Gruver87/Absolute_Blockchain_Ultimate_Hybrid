//! Pure-Rust entry points for fuzzing / property smoke (v1.3.88).
//!
//! These call the same inner kernels as the PyO3 surface without allocating
//! Python objects — suitable for `cargo fuzz` (Linux CI) and Windows smoke.

use crate::p2p_frame::P2PLineFramer;
use crate::p2p_rate_limit::P2PRateLimitTable;
use crate::p2p_wire::{
    encode_p2p_wire_message_inner, parse_p2p_wire_line_inner, DEFAULT_MAX_P2P_LINE_BYTES,
};
use std::collections::HashSet;

/// Feed one or more chunks into a line framer. Returns Ok(line_count) or Err(reason).
/// Never panics on arbitrary input (fail-closed).
pub fn fuzz_p2p_frame_feed(max_bytes: usize, chunks: &[&[u8]]) -> Result<usize, String> {
    let mut framer = P2PLineFramer::rust_new(max_bytes);
    let mut total = 0usize;
    for chunk in chunks {
        match framer.rust_feed(chunk) {
            Ok(lines) => total = total.saturating_add(lines.len()),
            Err(reason) => return Err(reason),
        }
    }
    Ok(total)
}

/// Parse a single wire line. Ok(()) means envelope accepted; Err is reject reason.
pub fn fuzz_p2p_wire_parse(line: &[u8], max_bytes: usize) -> Result<(), String> {
    parse_p2p_wire_line_inner(line, max_bytes, None).map(|_| ())
}

/// Encode then parse round-trip when both succeed (no panic).
pub fn fuzz_p2p_wire_roundtrip(msg_type: &str, data_json: &str) -> Result<(), String> {
    let encoded = encode_p2p_wire_message_inner(msg_type, data_json)?;
    let (got_type, _) =
        parse_p2p_wire_line_inner(&encoded, DEFAULT_MAX_P2P_LINE_BYTES, None)?;
    if got_type != msg_type {
        return Err(format!("type_mismatch:{got_type}"));
    }
    Ok(())
}

/// Rate-limit + egress admit smoke for random peer/type/size sequences.
pub fn fuzz_p2p_rate_limit_sequence(
    seed_limit: u64,
    byte_limit: u64,
    egress_limit: u64,
    events: &[(String, String, f64, u64)],
) {
    let mut table = P2PRateLimitTable::rust_new(
        seed_limit.max(1),
        5,
        300,
        None,
        seed_limit.max(1),
        byte_limit,
        egress_limit,
    );
    for (peer, msg_type, now, nbytes) in events {
        let _ = table.admit_rate_inner(peer, msg_type, *now, *nbytes);
        let _ = table.admit_egress_inner(peer, msg_type, *now, *nbytes);
    }
}

/// Allowlist parse helper used by ingress-shaped fuzz.
pub fn fuzz_p2p_wire_parse_allowlist(
    line: &[u8],
    max_bytes: usize,
    allowed: &[&str],
) -> Result<(), String> {
    let set: HashSet<String> = allowed.iter().map(|s| (*s).to_string()).collect();
    parse_p2p_wire_line_inner(line, max_bytes, Some(&set)).map(|_| ())
}

#[cfg(test)]
mod smoke {
    use super::*;
    use rand::{Rng, RngCore, SeedableRng};
    use rand::rngs::StdRng;

    #[test]
    fn fuzz_p2p_frame_smoke_10k() {
        let mut rng = StdRng::seed_from_u64(0x0A85_0088);
        for i in 0..10_000u64 {
            let max_bytes = 64 + (rng.gen::<usize>() % 4096);
            let n_chunks = 1 + (rng.gen::<usize>() % 8);
            let mut chunks: Vec<Vec<u8>> = Vec::with_capacity(n_chunks);
            for _ in 0..n_chunks {
                let len = rng.gen::<usize>() % 512;
                let mut buf = vec![0u8; len];
                rng.fill_bytes(&mut buf);
                if rng.gen_bool(0.4) {
                    buf.push(b'\n');
                }
                chunks.push(buf);
            }
            let refs: Vec<&[u8]> = chunks.iter().map(|c| c.as_slice()).collect();
            let _ = fuzz_p2p_frame_feed(max_bytes, &refs);
            // Deterministic progress marker every 2k (keeps CI logs quiet).
            if i % 2000 == 0 {
                let _ = i;
            }
        }
    }

    #[test]
    fn fuzz_p2p_wire_smoke_10k() {
        let mut rng = StdRng::seed_from_u64(0x0A85_1188);
        for _ in 0..10_000u64 {
            let len = rng.gen::<usize>() % 1024;
            let mut buf = vec![0u8; len];
            rng.fill_bytes(&mut buf);
            let _ = fuzz_p2p_wire_parse(&buf, 8192);
            // Sometimes valid-ish JSON envelope.
            if rng.gen_bool(0.25) {
                let tlen = 1 + (rng.gen::<usize>() % 16);
                let mut t = String::new();
                for _ in 0..tlen {
                    t.push(char::from(b'a' + (rng.gen::<u8>() % 26)));
                }
                let line = format!("{{\"type\":\"{t}\",\"data\":null}}\n");
                let _ = fuzz_p2p_wire_parse(line.as_bytes(), 8192);
                let _ = fuzz_p2p_wire_roundtrip(&t, "null");
            }
        }
    }

    #[test]
    fn fuzz_p2p_rate_limit_smoke_5k() {
        let mut rng = StdRng::seed_from_u64(0x0A85_2288);
        for _ in 0..5_000u64 {
            let n = 1 + (rng.gen::<usize>() % 32);
            let mut events = Vec::with_capacity(n);
            for j in 0..n {
                let peer = format!("p{}", rng.gen::<u8>());
                let msg = if rng.gen_bool(0.3) {
                    "ping".to_string()
                } else if rng.gen_bool(0.3) {
                    "blocks".to_string()
                } else {
                    format!("t{}", rng.gen::<u8>())
                };
                let now = (j as f64) * 0.01 + rng.gen::<f64>();
                let nbytes = rng.gen::<u64>() % 10_000;
                events.push((peer, msg, now, nbytes));
            }
            fuzz_p2p_rate_limit_sequence(
                1 + (rng.gen::<u64>() % 50),
                rng.gen::<u64>() % 50_000,
                rng.gen::<u64>() % 50_000,
                &events,
            );
        }
    }
}
