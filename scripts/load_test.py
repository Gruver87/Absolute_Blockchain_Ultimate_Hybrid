#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Лёгкий load test для CI / smoke HA.
Проверяет /health/live под параллельной нагрузкой.
"""

import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _request(url: str, timeout: float) -> tuple:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, time.perf_counter() - started, body
    except urllib.error.HTTPError as e:
        return e.code, time.perf_counter() - started, e.read()
    except Exception as e:
        return 0, time.perf_counter() - started, str(e).encode()


def run_load(url: str, workers: int, requests_per_worker: int, timeout: float) -> dict:
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in range(workers * requests_per_worker):
            tasks.append(pool.submit(_request, url, timeout))
        results = [t.result() for t in concurrent.futures.as_completed(tasks)]

    ok = sum(1 for code, _, _ in results if code == 200)
    latencies = [lat for code, lat, _ in results if code == 200]
    p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else 0.0
    return {
        "total": len(results),
        "ok": ok,
        "errors": len(results) - ok,
        "p95_seconds": round(p95, 4),
        "max_seconds": round(max(latencies) if latencies else 0.0, 4),
    }


def spawn_local_server(port: int):
    from runtime.config import Config
    from storage.database import Database
    from kernel.event_bus import EventBus
    from core.blockchain import Blockchain
    from blockchain.mempool import Mempool
    from api.http import create_http_server

    cfg = Config()
    cfg.db_path = f"data/loadtest_{port}.db"
    cfg.http_port = port
    cfg.rate_limit_rpm = 10_000
    db = Database(cfg.db_path)
    db.initialize()
    bc = Blockchain(cfg, db, EventBus())
    mp = Mempool(max_size=100, min_fee=0.001)
    server = create_http_server(bc, mp, db, cfg)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.4)
    return server, f"http://127.0.0.1:{port}/health/live"


def main():
    parser = argparse.ArgumentParser(description="Load test /health/live")
    parser.add_argument("--url", default="", help="Target URL (default: spawn local server)")
    parser.add_argument("--port", type=int, default=19080)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--requests", type=int, default=25, help="Requests per worker")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--min-ok-ratio", type=float, default=0.95)
    parser.add_argument("--spawn-local", action="store_true", help="Start embedded test server")
    args = parser.parse_args()

    server = None
    url = args.url
    if args.spawn_local or not url:
        server, url = spawn_local_server(args.port)

    print(f"Load test: {url} workers={args.workers} req/worker={args.requests}")
    stats = run_load(url, args.workers, args.requests, args.timeout)
    print(json.dumps(stats, indent=2))

    if server:
        server.shutdown()

    ratio = stats["ok"] / stats["total"] if stats["total"] else 0
    if ratio < args.min_ok_ratio:
        print(f"FAIL: ok ratio {ratio:.2%} < {args.min_ok_ratio:.0%}")
        sys.exit(1)
    print(f"PASS: ok ratio {ratio:.2%}")
    sys.exit(0)


if __name__ == "__main__":
    main()
