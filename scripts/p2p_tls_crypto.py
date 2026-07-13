#!/usr/bin/env python3
"""Pure-Python P2P TLS material (cryptography fallback when openssl is absent)."""

from __future__ import annotations

import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _write_pem_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def _write_pem_cert(path: Path, cert: x509.Certificate) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def generate_ca_material(
    ca_key_path: Path,
    ca_pem_path: Path,
    *,
    common_name: str = "ABS-P2P-CA",
    days: int = 825,
) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    _write_pem_key(ca_key_path, key)
    _write_pem_cert(ca_pem_path, cert)
    return key, cert


def generate_node_material(
    node_key_path: Path,
    node_pem_path: Path,
    *,
    node_cn: str,
    ca_key: rsa.RSAPrivateKey,
    ca_cert: x509.Certificate,
    days: int = 825,
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, node_cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=days))
        .sign(ca_key, hashes.SHA256())
    )
    _write_pem_key(node_key_path, key)
    _write_pem_cert(node_pem_path, cert)


def generate_mesh_tls_crypto(
    out_dir: Path,
    node_ids: list[str],
    *,
    force: bool = False,
    ca_cn: str = "ABS-P2P-Prod-Mesh-CA",
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ca_key_path = out_dir / "ca.key"
    ca_pem_path = out_dir / "ca.pem"

    if force or not ca_pem_path.is_file():
        ca_key, ca_cert = generate_ca_material(ca_key_path, ca_pem_path, common_name=ca_cn)
    else:
        ca_key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        ca_cert = x509.load_pem_x509_certificate(ca_pem_path.read_bytes())
        if not isinstance(ca_key, rsa.RSAPrivateKey):
            raise RuntimeError("CA key is not RSA")

    dirs: dict[str, Path] = {}
    for idx, node_id in enumerate(node_ids, start=1):
        name = f"node{idx}"
        node_dir = out_dir / name
        node_dir.mkdir(parents=True, exist_ok=True)
        node_key = node_dir / "node.key"
        node_pem = node_dir / "node.pem"
        ca_copy = node_dir / "ca.pem"

        if force or not node_pem.is_file():
            generate_node_material(
                node_key,
                node_pem,
                node_cn=node_id,
                ca_key=ca_key,
                ca_cert=ca_cert,
            )

        ca_copy.write_bytes(ca_pem_path.read_bytes())
        dirs[name] = node_dir

    return dirs
