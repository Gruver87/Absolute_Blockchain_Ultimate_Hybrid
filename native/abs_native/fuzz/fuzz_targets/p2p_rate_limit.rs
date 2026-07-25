#![no_main]

use abs_native::fuzz_p2p_rate_limit_sequence;
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    if data.len() < 4 {
        return;
    }
    let seed_limit = 1u64 + (data[0] as u64);
    let byte_limit = (data[1] as u64).saturating_mul(256);
    let egress_limit = (data[2] as u64).saturating_mul(256);
    let n = 1 + (data[3] as usize % 24);
    let mut events = Vec::with_capacity(n);
    let mut i = 4usize;
    for j in 0..n {
        if i + 3 > data.len() {
            break;
        }
        let peer = format!("p{}", data[i] % 16);
        let msg = match data[i + 1] % 5 {
            0 => "ping".to_string(),
            1 => "blocks".to_string(),
            2 => "new_tx".to_string(),
            3 => "status".to_string(),
            _ => format!("t{}", data[i + 2] % 32),
        };
        let now = (j as f64) * 0.05 + f64::from(data[i + 2]);
        let nbytes = u64::from(data.get(i + 3).copied().unwrap_or(1)).saturating_mul(17);
        events.push((peer, msg, now, nbytes));
        i = i.saturating_add(4);
    }
    fuzz_p2p_rate_limit_sequence(seed_limit, byte_limit, egress_limit, &events);
});
