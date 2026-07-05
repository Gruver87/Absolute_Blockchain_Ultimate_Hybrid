#!/usr/bin/env python3
"""Benchmark block commit latency: SQLite vs RocksDB (honest, local)."""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _has_rocks() -> bool:
    try:
        import abs_native  # type: ignore

        return hasattr(abs_native, "RocksEngine")
    except Exception:
        return False


def _sample_block(height: int, proposer: str) -> dict:
    return {
        "height": height,
        "hash": f"{height:064x}",
        "parent_hash": f"{height - 1:064x}" if height else "0" * 64,
        "timestamp": 1_700_000_000 + height,
        "miner": proposer,
        "tx_count": 1,
        "transactions": [],
    }


def _sample_tx(height: int, idx: int) -> dict:
    sender = f"0x{idx:040x}"
    recipient = f"0x{(idx + 1):040x}"
    return {
        "hash": f"{height:032x}{idx:032x}",
        "block_height": height,
        "from_addr": sender,
        "to_addr": recipient,
        "value": 1.0,
        "gas": 21000,
        "fee": 0.1,
        "burned": 0.05,
        "nonce": 0,
        "status": 1,
        "timestamp": 1_700_000_000 + height,
    }


def _bench_sqlite(tmp: str, blocks: int, warmup: int) -> dict:
    from storage.database import Database

    path = os.path.join(tmp, "bench.db")
    db = Database(path)
    db.initialize()
    proposer = "0x" + "a1" * 20
    burn = "0x" + "d" * 40
    for i in range(3):
        db.set_balance(f"0x{i:040x}", 1000.0)

    timings: list[float] = []
    height = 0
    for _ in range(warmup + blocks):
        height += 1
        block = _sample_block(height, proposer)
        txs = [_sample_tx(height, height % 3)]
        t0 = time.perf_counter()
        ok = db.persist_block_atomic(block, txs, burned_amount=0.05, burn_address=burn)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if not ok:
            db.close()
            raise RuntimeError(f"sqlite persist failed at height {height}")
        if _ >= warmup:
            timings.append(elapsed_ms)
    tip = int(db.get_chain_tip() or 0)
    db.close()
    return _summary("sqlite", timings, tip)


def _bench_rocksdb(tmp: str, blocks: int, warmup: int) -> dict:
    from storage.rocks_store import RocksChainStore

    path = os.path.join(tmp, "chainstore")
    store = RocksChainStore(path, synchronous="FULL", block_cache_mb=256, write_buffer_mb=64)
    store.initialize()
    proposer = "0x" + "a1" * 20
    burn = "0x" + "d" * 40
    for i in range(3):
        store.set_balance(f"0x{i:040x}", 1000.0)

    timings: list[float] = []
    height = 0
    for _ in range(warmup + blocks):
        height += 1
        block = _sample_block(height, proposer)
        txs = [_sample_tx(height, height % 3)]
        t0 = time.perf_counter()
        ok = store.persist_block_atomic(block, txs, burned_amount=0.05, burn_address=burn)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if not ok:
            store.close()
            raise RuntimeError(f"rocksdb persist failed at height {height}")
        if _ >= warmup:
            timings.append(elapsed_ms)
    tip = int(store.get_chain_tip() or 0)
    store.close()
    return _summary("rocksdb", timings, tip)


def _summary(engine: str, timings: list[float], tip: int) -> dict:
    if not timings:
        return {"engine": engine, "samples": 0, "tip": tip}
    ordered = sorted(timings)
    p95_idx = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    return {
        "engine": engine,
        "samples": len(timings),
        "tip": tip,
        "mean_ms": round(statistics.mean(timings), 3),
        "median_ms": round(statistics.median(timings), 3),
        "p95_ms": round(ordered[p95_idx], 3),
        "min_ms": round(min(timings), 3),
        "max_ms": round(max(timings), 3),
    }


def run_benchmark(blocks: int = 20, warmup: int = 3) -> int:
    tmp = tempfile.mkdtemp(prefix="abs_bench_storage_")
    results: list[dict] = []
    try:
        results.append(_bench_sqlite(tmp, blocks, warmup))
        if _has_rocks():
            results.append(_bench_rocksdb(tmp, blocks, warmup))
        else:
            print("SKIP: rocksdb (abs_native.RocksEngine not built)", file=sys.stderr)
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)

    print(f"bench_storage_commit blocks={blocks} warmup={warmup}")
    for row in results:
        if row.get("samples", 0) == 0:
            print(f"  {row['engine']}: no samples")
            continue
        print(
            f"  {row['engine']}: mean={row['mean_ms']}ms "
            f"median={row['median_ms']}ms p95={row['p95_ms']}ms "
            f"min={row['min_ms']}ms max={row['max_ms']}ms tip={row['tip']}"
        )
    if len(results) >= 2 and results[0].get("mean_ms") and results[1].get("mean_ms"):
        ratio = round(results[1]["mean_ms"] / results[0]["mean_ms"], 2)
        print(f"  rocks/sqlite mean ratio: {ratio}x")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark storage block commit latency")
    parser.add_argument("--blocks", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args()
    try:
        return run_benchmark(blocks=max(1, args.blocks), warmup=max(0, args.warmup))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
