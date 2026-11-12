#!/usr/bin/env python3
"""Criptografa auditoria individual CV CRM antes de armazenar em GitHub Actions."""
import base64
import hashlib
import json
import os
import pathlib
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITERATIONS = 250_000

def encrypt(source, target, password):
    if len(password) < 16:
        raise ValueError("CV_AUDIT_PASSWORD deve possuir pelo menos 16 caracteres")
    plaintext = pathlib.Path(source).read_bytes()
    # Validar formato antes de criptografar.
    report = json.loads(plaintext)
    if report.get("schema_version") != 1 or not isinstance(report.get("rows"), list):
        raise ValueError("Auditoria JSON individual inválida")
    salt, nonce = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS, dklen=32)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    result = {
        "encryption": "AES-256-GCM",
        "kdf": "PBKDF2-SHA256",
        "iterations": ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii")
    }
    pathlib.Path(target).write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print("Auditoria criptografada: " + str(len(report["rows"])) + " registros")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Uso: encrypt_cv_audit.py ENTRADA.json SAIDA.enc.json")
    secret = os.environ.get("CV_AUDIT_PASSWORD", "")
    if not secret:
        raise SystemExit("CV_AUDIT_PASSWORD ausente")
    encrypt(sys.argv[1], sys.argv[2], secret)
