#![no_main]

use abs_native::fuzz_p2p_frame_feed;
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    if data.is_empty() {
        return;
    }
    let max_bytes = 64usize + (data[0] as usize).saturating_mul(32);
    let mut chunks: Vec<&[u8]> = Vec::new();
    let mut offset = 1usize;
    while offset < data.len() && chunks.len() < 8 {
        let take = 1 + (data[offset] as usize % 64);
        offset = offset.saturating_add(1);
        let end = (offset + take).min(data.len());
        chunks.push(&data[offset..end]);
        offset = end;
    }
    let _ = fuzz_p2p_frame_feed(max_bytes, &chunks);
});
