#!/usr/bin/env python3
"""Publica somente as colunas autorizadas da auditoria CV CRM."""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
from lcm_lead_display import display_name

FIELDS = ("cliente", "empreendimento", "origem", "data_entrada", "data_venda",
          "situacao_lead", "situacao_precadastro", "situacao_reserva", "project")
PROJECTS = frozenset(("residencial flores do cerrado jacaranda",
                      "residencial village lagoas",
                      "spe arraial costa verde club", "residencial jatoba"))


def iso_date(value):
    if not isinstance(value, str):
        raise ValueError("Data da auditoria inválida")
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("Data da auditoria inválida") from None
    if parsed.isoformat() != value:
        raise ValueError("Data da auditoria inválida")
    return parsed


def public_report(report):
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("Esquema da auditoria inválido")
    period = report.get("period")
    if not isinstance(period, dict):
        raise ValueError("Período da auditoria ausente")
    since, until = iso_date(period.get("since")), iso_date(period.get("until"))
    if since > until:
        raise ValueError("Período da auditoria invertido")
    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("Linhas da auditoria inválidas")
    selected = []
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in FIELDS):
            raise ValueError("Campos obrigatórios da auditoria ausentes ou inválidos")
        if row["project"] not in PROJECTS:
            raise ValueError("Empreendimento da auditoria não reconhecido")
        if not since <= iso_date(row["data_entrada"]) <= until:
            raise ValueError("Entrada fora do histórico da auditoria")
        if row["data_venda"]:
            iso_date(row["data_venda"])
        # Projeção positiva: IDs, contatos e quaisquer outros campos são descartados.
        dates=row.get("entry_dates",[row["data_entrada"]])
        if not isinstance(dates,list) or not dates or any(not since<=iso_date(day)<=until for day in dates):
            raise ValueError("Entradas da auditoria inválidas")
        projected={key:row[key] for key in FIELDS}
        projected["cliente"]=display_name(row["cliente"])
        projected["entry_dates"]=sorted(set(dates))
        selected.append(projected)
    return {
        "schema_version": 1,
        "source": "CV CRM - auditoria pública autorizada",
        "period": {"since": since.isoformat(), "until": until.isoformat()},
        "published_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rows": selected,
    }


def read_encrypted(source, password):
    """Migração única do formato antigo; a senha não é usada na coleta futura."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        envelope = json.loads(Path(source).read_text(encoding="utf-8"))
        if (not isinstance(envelope, dict) or envelope.get("encryption") != "AES-256-GCM"
                or envelope.get("kdf") != "PBKDF2-SHA256"
                or envelope.get("iterations") != 250_000 or not password):
            raise ValueError()
        salt = base64.b64decode(envelope["salt"], validate=True)
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        if len(salt) != 16 or len(nonce) != 12 or len(ciphertext) < 16:
            raise ValueError()
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 250_000, dklen=32)
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        return json.loads(plaintext)
    except Exception:
        # Nunca copiar o payload, a senha ou a mensagem criptográfica para logs.
        raise ValueError("Não foi possível migrar a auditoria criptografada existente") from None


def publish(source, target, *, encrypted=False):
    report = (read_encrypted(source, os.environ.get("CV_AUDIT_PASSWORD", ""))
              if encrypted else json.loads(Path(source).read_text(encoding="utf-8")))
    projected = public_report(report)
    output = Path(target)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(projected, ensure_ascii=False, separators=(",", ":")),
                         encoding="utf-8")
    temporary.replace(output)
    print("Auditoria pública validada: " + str(len(projected["rows"])) +
          " linhas; somente colunas autorizadas.")
    return projected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encrypted", action="store_true",
                        help="Migrar o arquivo criptografado já coletado, sem consultar a API")
    parser.add_argument("source")
    parser.add_argument("target")
    args = parser.parse_args()
    try:
        publish(args.source, args.target, encrypted=args.encrypted)
    except (OSError, ValueError, TypeError):
        raise SystemExit("Auditoria não publicada: formato, período ou arquivo inválido") from None


if __name__ == "__main__":
    main()

