#!/usr/bin/env python3
"""Generate dev P2P TLS material (self-signed CA + node cert)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dev P2P TLS certs")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "data" / "p2p_tls_dev"),
        help="Output directory for ca.pem, node.pem, node.key",
    )
    parser.add_argument("--node-id", default="dev-node", help="Certificate CN / SAN")
    args = parser.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ca_key = out / "ca.key"
    ca_pem = out / "ca.pem"
    node_key = out / "node.key"
    node_csr = out / "node.csr"
    node_pem = out / "node.pem"

    if not ca_pem.is_file():
        _run(
            [
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", str(ca_key), "-out", str(ca_pem),
                "-days", "825", "-nodes", "-subj", "/CN=ABS-P2P-Dev-CA",
            ],
            out,
        )

    _run(
        [
            "openssl", "req", "-newkey", "rsa:2048",
            "-keyout", str(node_key), "-out", str(node_csr),
            "-nodes", "-subj", f"/CN={args.node_id}",
        ],
        out,
    )
    _run(
        [
            "openssl", "x509", "-req", "-in", str(node_csr),
            "-CA", str(ca_pem), "-CAkey", str(ca_key), "-CAcreateserial",
            "-out", str(node_pem), "-days", "825",
        ],
        out,
    )

    print(f"OK: P2P TLS dev material in {out}")
    print("  P2P_TLS_ENABLED=true")
    print(f"  P2P_TLS_CERT_PATH={node_pem}")
    print(f"  P2P_TLS_KEY_PATH={node_key}")
    print(f"  P2P_TLS_CA_PATH={ca_pem}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
