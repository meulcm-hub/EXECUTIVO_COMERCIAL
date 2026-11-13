import contextlib
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import meta_permissions_diagnostic as diagnostic


class DiagnosticProjectionTests(unittest.TestCase):
    def test_token_projection_never_transports_user_or_target_ids_names_and_tokens(self):
        secret = "private-test-token"
        raw = {"data": {"app_id": "12345678", "user_id": "user-id-private", "application": "Pessoa privada",
                       "is_valid": True, "type": "SYSTEM_USER", "expires_at": 0,
                       "scopes": ["ads_read", secret, "public_profile"], "access_token": secret,
                       "granular_scopes": [{"scope": "ads_read", "target_ids": ["private-asset", "other-id"]},
                                           {"scope": secret, "target_ids": ["private-asset"]}]}}
        result = diagnostic.token_projection(raw)
        self.assertEqual(result["type"], "SYSTEM_USER")
        self.assertEqual(result["scopes"], ["ads_read"])
        self.assertEqual(result["granular_scope_target_counts"], {"ads_read": 2})
        self.assertEqual(result["app_id"], "12345678")
        self.assertEqual(result["expires_at_utc"], "sem_expiracao_informada")
        encoded = json.dumps(result)
        for forbidden in (secret, "user-id-private", "Pessoa privada", "private-asset", "other-id", "access_token"):
            self.assertNotIn(forbidden, encoded)

    def test_permission_projection_is_allowlisted_and_status_is_not_arbitrary_text(self):
        raw = {"data": [{"permission": "ads_read", "status": "granted"},
                        {"permission": "pages_show_list", "status": "secret-value"},
                        {"permission": "secret-name", "status": "granted"}]}
        result = diagnostic.permission_projection(raw)
        self.assertEqual(result["ads_read"], "granted")
        self.assertEqual(result["pages_show_list"], "nao_informada")
        self.assertNotIn("secret", json.dumps(result))

    def test_error_message_is_only_used_for_fixed_categories(self):
        raw = {"error": {"code": 200, "error_subcode": 5258005,
                         "message": "private-test-token https://example.test/?token=secret advanced access ads_read system user"}}
        result = diagnostic.safe_error(raw, 400)
        self.assertEqual((result["code"], result["subcode"]), (200, 5258005))
        self.assertIn("nivel_de_acesso_do_aplicativo", result["categories"])
        self.assertEqual(result["permissions_mentioned"], ["ads_read"])
        for forbidden in ("private-test-token", "example.test", "token=secret", "message"):
            self.assertNotIn(forbidden, json.dumps(result))

    def test_http_errors_and_network_exceptions_never_expose_urls(self):
        body = io.BytesIO(json.dumps({"error": {"code": 190, "error_subcode": 463,
                                                "message": "https://graph.facebook.com/?input_token=secret"}}).encode())
        error = urllib.error.HTTPError("https://graph.facebook.com/?input_token=secret", 401, "secret", {}, body)
        with patch.object(diagnostic, "TOKEN", "secret"), patch.object(diagnostic.OPENER, "open", side_effect=error):
            payload, result = diagnostic.read_json("debug_token", {"input_token": "secret"})
        self.assertIsNone(payload)
        self.assertEqual(result["code"], 190)
        self.assertNotIn("secret", json.dumps(result))
        with patch.object(diagnostic, "TOKEN", "secret"), patch.object(diagnostic.OPENER, "open", side_effect=ValueError("URL secret")):
            _, result = diagnostic.read_json("me")
        self.assertEqual(result["category"], "rede_ou_resposta_indisponivel")
        self.assertNotIn("secret", json.dumps(result))

    def test_main_only_prints_explicitly_projected_fields(self):
        results = [({"data": [{"permission": "ads_read", "status": "granted"}], "token": "secret"}, {"ok": True}),
                   ({"data": {"is_valid": True, "type": "SYSTEM_USER", "expires_at": 0,
                              "user_id": "private-user", "token": "secret"}}, {"ok": True}),
                   ({"id": "private-user", "name": "Pessoa privada"}, {"ok": True}),
                   ({"id": "act_" + diagnostic.PROBE_ACCOUNT, "currency": "BRL", "name": "Conta privada"}, {"ok": True})]
        stream = io.StringIO()
        with patch.object(diagnostic, "TOKEN", "secret"), patch.object(diagnostic, "read_json", side_effect=results), contextlib.redirect_stdout(stream):
            self.assertEqual(diagnostic.main(), 0)
        output = stream.getvalue()
        for forbidden in ("secret", "private-user", "Pessoa privada", "Conta privada", diagnostic.PROBE_ACCOUNT):
            self.assertNotIn(forbidden, output)
        self.assertIn('"account_readable": true', output)

    def test_unexpected_paths_and_redirects_are_refused(self):
        with self.assertRaises(ValueError):
            diagnostic.read_json("https://other.test/")
        with self.assertRaises(RuntimeError):
            diagnostic.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test/")
        self.assertEqual(diagnostic.expiry(-1), "nao_informada")
        self.assertEqual(diagnostic.expiry(0), "sem_expiracao_informada")
        self.assertEqual(diagnostic.expiry("secret"), "nao_informada")


if __name__ == "__main__":
    unittest.main()
