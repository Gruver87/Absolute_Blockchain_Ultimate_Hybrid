#![no_main]

use abs_native::{fuzz_p2p_wire_parse, fuzz_p2p_wire_parse_allowlist, fuzz_p2p_wire_roundtrip};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let max_bytes = if data.is_empty() {
        8192
    } else {
        256 + (data[0] as usize).saturating_mul(64)
    };
    let _ = fuzz_p2p_wire_parse(data, max_bytes);
    let _ = fuzz_p2p_wire_parse_allowlist(data, max_bytes, &["ping", "pong", "blocks", "status"]);

    // Structured round-trip when we can form a short type name from bytes.
    if data.len() >= 3 {
        let tlen = 1 + (data[1] as usize % 12);
        let mut msg_type = String::new();
        for b in data.iter().skip(2).take(tlen) {
            msg_type.push(char::from(b'a' + (b % 26)));
        }
        if !msg_type.is_empty() {
            let _ = fuzz_p2p_wire_roundtrip(&msg_type, "null");
            let _ = fuzz_p2p_wire_roundtrip(&msg_type, "{}");
        }
    }
});
