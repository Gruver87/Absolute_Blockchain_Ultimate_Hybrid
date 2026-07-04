#!/usr/bin/env python3
"""Production Docker/K8s manifest checks."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_prod_compose_includes_relayer_sidecar():
    text = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "relayer:" in text
    assert "BRIDGE_REQUIRE_L1_PROOF" in text
    assert "condition: service_healthy" in text
    assert "bridge_relayer.py" in text
    assert "ABS_REQUIRE_NATIVE_CRYPTO" in text


def test_k8s_includes_relayer_deployment():
    text = (ROOT / "deploy" / "k8s" / "relayer-deployment.yaml").read_text(encoding="utf-8")
    assert "abs-bridge-relayer" in text
    assert "--watch-l1" in text
    kustomize = (ROOT / "deploy" / "k8s" / "kustomization.yaml").read_text(encoding="utf-8")
    assert "relayer-deployment.yaml" in kustomize


def test_dockerfile_prod_requires_native_crypto():
    text = (ROOT / "Dockerfile.prod").read_text(encoding="utf-8")
    assert "ABS_REQUIRE_NATIVE_CRYPTO=true" in text
    assert "/health/ready" in text
