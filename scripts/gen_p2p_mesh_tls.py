#!/usr/bin/env python3
"""Generate P2P TLS material for prod Docker 3-node mesh."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NODES = (
    "docker-prod-mesh-1",
    "docker-prod-mesh-2",
    "docker-prod-mesh-3",
)


def _run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}")


def _openssl_available() -> bool:
    try:
        proc = subprocess.run(
            ["openssl", "version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def generate_mesh_tls(
    out_dir: Path,
    node_ids: list[str],
    *,
    force: bool = False,
) -> dict[str, Path]:
    """Return map node_dir_name -> cert directory (node1, node2, ...)."""
    if not _openssl_available():
        raise RuntimeError("openssl not found in PATH")

    out_dir.mkdir(parents=True, exist_ok=True)
    ca_key = out_dir / "ca.key"
    ca_pem = out_dir / "ca.pem"

    if force or not ca_pem.is_file():
        _run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(ca_key),
                "-out",
                str(ca_pem),
                "-days",
                "825",
                "-nodes",
                "-subj",
                "/CN=ABS-P2P-Prod-Mesh-CA",
            ],
            out_dir,
        )

    dirs: dict[str, Path] = {}
    for idx, node_id in enumerate(node_ids, start=1):
        name = f"node{idx}"
        node_dir = out_dir / name
        node_dir.mkdir(parents=True, exist_ok=True)
        node_key = node_dir / "node.key"
        node_csr = node_dir / "node.csr"
        node_pem = node_dir / "node.pem"
        ca_copy = node_dir / "ca.pem"

        if force or not node_pem.is_file():
            _run(
                [
                    "openssl",
                    "req",
                    "-newkey",
                    "rsa:2048",
                    "-keyout",
                    str(node_key),
                    "-out",
                    str(node_csr),
                    "-nodes",
                    "-subj",
                    f"/CN={node_id}",
                ],
                node_dir,
            )
            _run(
                [
                    "openssl",
                    "x509",
                    "-req",
                    "-in",
                    str(node_csr),
                    "-CA",
                    str(ca_pem),
                    "-CAkey",
                    str(ca_key),
                    "-CAcreateserial",
                    "-out",
                    str(node_pem),
                    "-days",
                    "825",
                ],
                node_dir,
            )
            if node_csr.is_file():
                node_csr.unlink()

        shutil.copyfile(ca_pem, ca_copy)
        dirs[name] = node_dir

    return dirs


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate prod mesh P2P TLS certs")
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "data" / "p2p_tls_prod_mesh"),
        help="Output root (node1/, node2/, node3/ + ca.pem)",
    )
    parser.add_argument(
        "--nodes",
        default=",".join(DEFAULT_NODES),
        help="Comma-separated certificate CN list (one per mesh node)",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate existing material")
    args = parser.parse_args()

    node_ids = [n.strip() for n in args.nodes.split(",") if n.strip()]
    if len(node_ids) < 2:
        print("FAIL: need at least 2 node IDs", file=sys.stderr)
        return 1

    try:
        dirs = generate_mesh_tls(Path(args.out_dir), node_ids, force=args.force)
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"OK: P2P TLS prod mesh material in {args.out_dir}")
    for name, path in dirs.items():
        print(f"  {name}: {path}")
    print("Docker mount: ./data/p2p_tls_prod_mesh/<nodeN>:/app/p2p_tls:ro")
    print("  P2P_TLS_ENABLED=true")
    print("  P2P_TLS_CERT_PATH=/app/p2p_tls/node.pem")
    print("  P2P_TLS_KEY_PATH=/app/p2p_tls/node.key")
    print("  P2P_TLS_CA_PATH=/app/p2p_tls/ca.pem")
    return 0


if __name__ == "__main__":
    sys.exit(main())
