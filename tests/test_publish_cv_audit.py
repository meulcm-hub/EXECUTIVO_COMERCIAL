"""Publicação mínima da auditoria, com dados exclusivamente fictícios."""
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_cv_audit as audit


class PublicAuditTests(unittest.TestCase):
    def fixture(self):
        return {"schema_version": 1, "period": {"since": "2026-11-01", "until": "2026-11-12"},
                "rows": [{"cliente": "Cliente fictício çã", "empreendimento": "Jatobá",
                          "origem": "Google", "data_entrada": "2026-11-03", "data_venda": "",
                          "situacao_lead": "Em atendimento", "situacao_precadastro": "Aprovado",
                          "situacao_reserva": "Reservada", "project": "residencial jatoba",
                          "idlead": "123", "cpf": "fictício", "email": "teste@example.invalid",
                          "telefone": "fictício", "tipo_entrada": "Retorno",
                          "api_payload": {"qualquer_dado": "descartar"}}]}

    def test_only_display_columns_and_project_are_published(self):
        source = self.fixture()
        result = audit.public_report(source)
        self.assertEqual(set(result["rows"][0]), set(audit.FIELDS)|{"entry_dates"})
        self.assertEqual(result["rows"][0]["cliente"], "Cliente fictício çã")
        self.assertEqual(result["period"], source["period"])
        self.assertNotIn("123", json.dumps(result))
        self.assertNotIn("teste@example.invalid", json.dumps(result))
        self.assertNotIn("api_payload", json.dumps(result))
        self.assertIn("idlead", source["rows"][0])  # Fonte permanece intacta.

    def test_missing_or_non_string_status_is_rejected(self):
        for invalid in [None, 1, {}, []]:
            with self.subTest(invalid=invalid):
                source = self.fixture()
                source["rows"][0]["situacao_reserva"] = invalid
                with self.assertRaises(ValueError):
                    audit.public_report(source)
        source = self.fixture()
        del source["rows"][0]["cliente"]
        with self.assertRaises(ValueError):
            audit.public_report(source)

    def test_period_and_row_dates_are_validated(self):
        for date in ["2026-02-30", "20261103", "03/11/2026", "2026-10-31", "2026-11-13"]:
            source = self.fixture()
            source["rows"][0]["data_entrada"] = date
            with self.subTest(date=date), self.assertRaises(ValueError):
                audit.public_report(source)
        source = self.fixture()
        source["rows"][0]["data_venda"] = "sem data"
        with self.assertRaises(ValueError):
            audit.public_report(source)
        source = self.fixture()
        source["period"] = {"since": "2026-12-01", "until": "2026-11-01"}
        with self.assertRaises(ValueError):
            audit.public_report(source)

    def test_malformed_report_is_rejected(self):
        for source in [None, [], {}, {"schema_version": 2}, {"schema_version": 1, "rows": []}]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                audit.public_report(source)
        source = self.fixture()
        source["rows"][0]["project"] = "fora da vinculação"
        with self.assertRaises(ValueError):
            audit.public_report(source)

    def test_file_publication_and_empty_valid_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "private.json"
            output = Path(directory) / "data" / "cv-audit.json"
            source.write_text(json.dumps(self.fixture()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                result = audit.publish(source, output)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)
            self.assertFalse(Path(str(output) + ".tmp").exists())
            self.assertIn("idlead", json.loads(source.read_text())["rows"][0])
        source = self.fixture()
        source["rows"] = []
        self.assertEqual(audit.public_report(source)["rows"], [])

    def test_encrypted_migration_removes_identifiers(self):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            self.skipTest("cryptography é necessário somente para migração")
        import base64
        import hashlib
        salt, nonce = os.urandom(16), os.urandom(12)
        password = "senha-ficticia-somente-teste-2026"
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 250_000, dklen=32)
        ciphertext = AESGCM(key).encrypt(nonce, json.dumps(self.fixture()).encode(), None)
        envelope = {"encryption": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iterations": 250_000,
                    "salt": base64.b64encode(salt).decode(), "nonce": base64.b64encode(nonce).decode(),
                    "ciphertext": base64.b64encode(ciphertext).decode()}
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "encrypted.json", Path(directory) / "public.json"
            source.write_text(json.dumps(envelope), encoding="utf-8")
            with patch.dict(os.environ, {"CV_AUDIT_PASSWORD": password}), contextlib.redirect_stdout(io.StringIO()):
                result = audit.publish(source, target, encrypted=True)
            self.assertNotIn("idlead", result["rows"][0])
            with self.assertRaisesRegex(ValueError, "Não foi possível"):
                audit.read_encrypted(source, "incorreta")


if __name__ == "__main__":
    unittest.main()

