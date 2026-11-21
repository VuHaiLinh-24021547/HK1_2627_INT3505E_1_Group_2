"""RSA key management for the JWT signer (dev/test) and verifier."""
from __future__ import annotations

import logging
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

log = logging.getLogger(__name__)


def generate_rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return private_pem, public_pem


def write_keypair(private_path: str, public_path: str, overwrite: bool = False) -> bool:
    priv, pub = Path(private_path), Path(public_path)
    if priv.exists() and pub.exists() and not overwrite:
        return False
    priv.parent.mkdir(parents=True, exist_ok=True)
    pub.parent.mkdir(parents=True, exist_ok=True)
    private_pem, public_pem = generate_rsa_keypair()
    priv.write_text(private_pem)
    priv.chmod(0o600)
    pub.write_text(public_pem)
    return True


def init_keys(app) -> None:
    cfg = app.config
    priv_path, pub_path = cfg.get("JWT_PRIVATE_KEY_PATH"), cfg.get("JWT_PUBLIC_KEY_PATH")
    if cfg.get("AUTO_GENERATE_KEYS") and not cfg.get("JWT_PUBLIC_KEY_PEM") and priv_path and pub_path:
        if write_keypair(priv_path, pub_path):
            log.info("Generated development JWT key pair in %s", Path(priv_path).parent)
    if not cfg.get("JWT_PRIVATE_KEY_PEM") and priv_path and Path(priv_path).exists():
        cfg["JWT_PRIVATE_KEY_PEM"] = Path(priv_path).read_text()
    if not cfg.get("JWT_PUBLIC_KEY_PEM") and pub_path and Path(pub_path).exists():
        cfg["JWT_PUBLIC_KEY_PEM"] = Path(pub_path).read_text()
