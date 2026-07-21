#!/usr/bin/env python3
"""Production Docker/K8s manifest checks."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_prod_compose_includes_relayer_sidecar():
    text = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "relayer:" in text
    assert "profiles:" in text
    assert "- bridge" in text
    assert "BRIDGE_ENABLED" in text
    assert "BRIDGE_REQUIRE_L1_PROOF" in text
    assert "condition: service_healthy" in text
    assert "bridge_relayer.py" in text
    assert "ABS_REQUIRE_NATIVE_CRYPTO" in text


def test_docker_prod_node_bridge_disabled_by_default():
    cfg = json.loads((ROOT / "docker" / "node.prod.json").read_text(encoding="utf-8"))
    assert cfg.get("bridge_enabled") is False


def test_prod_mesh_compose_has_three_nodes():
    text = (ROOT / "docker-compose.prod.3node.yml").read_text(encoding="utf-8")
    assert "node1:" in text
    assert "node2:" in text
    assert "node3:" in text
    assert "prod_mesh/wallets/validator-1.wallet.json" in text
    assert "BRIDGE_ENABLED" in text
    assert "ABS_PROD_IMAGE" in text
    assert "Dockerfile.prod" in text
    assert "\n  redis:" in text
    assert "REDIS_RATE_LIMIT" in text
    assert "REDIS_URL" in text
    assert "abs-prod-mesh-redis" in text


def test_k8s_includes_relayer_deployment():
    text = (ROOT / "deploy" / "k8s" / "relayer-deployment.yaml").read_text(encoding="utf-8")
    assert "abs-bridge-relayer" in text
    assert "--watch-l1" in text
    assert "BRIDGE_L1_QUEUE_HTTP" in text
    kustomize = (ROOT / "deploy" / "k8s" / "kustomization.yaml").read_text(encoding="utf-8")
    assert "relayer-deployment.yaml" in kustomize


def test_dockerfile_prod_requires_native_crypto():
    text = (ROOT / "Dockerfile.prod").read_text(encoding="utf-8")
    assert "ABS_REQUIRE_NATIVE_CRYPTO=true" in text
    assert "/health/ready" in text
    assert "type=cache" in text
    assert "cargo fetch" in text


def test_prod_gate_requires_rocksdb_on_all_prod_profiles():
    import subprocess
    import sys

    from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID

    proc = subprocess.run(
        [sys.executable, "scripts/prod_gate.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for name in (
        "node.prod.example.json",
        "node.prod.mainnet-v1.example.json",
        "node.prod.mainnet-v1.bridge.example.json",
        "docker/node.prod.json",
        "docker/node.prod.mesh1.json",
    ):
        cfg = json.loads((ROOT / name).read_text(encoding="utf-8"))
        assert cfg.get("db_engine") == "rocksdb", name
        assert int(cfg.get("chain_id", 0)) == MAINNET_V1_CHAIN_ID, name


def test_k8s_prod_gate_passes():
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "scripts/k8s_prod_gate.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
