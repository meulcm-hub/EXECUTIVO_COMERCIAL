#!/usr/bin/env python3
"""Diagnóstico Meta somente leitura, com saída pública explicitamente limitada.

Não publica token, URL de requisição, resposta bruta, usuários ou ativos.
"""
import datetime as dt
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
API_VERSION = os.environ.get("META_API_VERSION", "v25.0")
PERMISSIONS = ("ads_read", "ads_management", "business_management",
               "pages_read_engagement", "pages_show_list")
PROBE_ACCOUNT = "347253318197280"
ALLOWED_PATHS = {"me", "me/permissions", "debug_token", "act_" + PROBE_ACCOUNT}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Redirecionamento recusado")


OPENER = urllib.request.build_opener(NoRedirect())


def safe_error(payload, status):
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        error = {}
    code = error.get("code") if type(error.get("code")) is int else None
    subcode = error.get("error_subcode") if type(error.get("error_subcode")) is int else None
    # Ler o texto somente para reconhecer categorias fixas; nunca o imprimir.
    message = error.get("message", "")
    message = message.casefold() if isinstance(message, str) else ""
    categories = []
    if code == 190:
        categories.append("token_expirado_ou_invalido")
    if any(word in message for word in ("app review", "advanced access", "standard access", "access level")):
        categories.append("nivel_de_acesso_do_aplicativo")
    if any(word in message for word in ("development mode", "in development")):
        categories.append("modo_desenvolvimento_do_aplicativo")
    if any(word in message for word in ("business verification", "verified business")):
        categories.append("verificacao_do_negocio")
    if any(word in message for word in ("administrator", "not an admin", "app role", "admin role")):
        categories.append("papel_no_aplicativo")
    if "system user" in message:
        categories.append("usuario_do_sistema")
    if code in (10, 200):
        categories.append("permissao_insuficiente")
    return {"ok": False, "http_status": status, "code": code, "subcode": subcode,
            "categories": categories,
            "permissions_mentioned": [p for p in PERMISSIONS if p in message]}


def read_json(path, params=None):
    if path not in ALLOWED_PATHS:
        raise ValueError("Caminho de diagnóstico não permitido")
    if not TOKEN or not re.fullmatch(r"v\d+\.\d+", API_VERSION):
        return None, {"ok": False, "category": "configuracao_ausente_ou_invalida"}
    url = "https://graph.facebook.com/" + API_VERSION + "/" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        request = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + TOKEN, "Accept": "application/json",
            "User-Agent": "LCM-Meta-Permissions-Diagnostic/1.0",
        })
        with OPENER.open(request, timeout=30) as response:
            payload = json.loads(response.read(1024 * 1024))
            status = response.status
        if not isinstance(payload, dict) or "error" in payload:
            return None, safe_error(payload, status)
        return payload, {"ok": True, "http_status": status}
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read(1024 * 1024))
        except (ValueError, TypeError, OSError):
            payload = {}
        return None, safe_error(payload, error.code)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError,
            http.client.IncompleteRead, RuntimeError):
        return None, {"ok": False, "category": "rede_ou_resposta_indisponivel"}


def expiry(value):
    if type(value) is not int or value < 0:
        return "nao_informada"
    if value == 0:
        return "sem_expiracao_informada"
    try:
        return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return "nao_informada"


def permission_projection(payload):
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    result = {permission: "nao_informada" for permission in PERMISSIONS}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or row.get("permission") not in result:
                continue
            status = row.get("status")
            result[row["permission"]] = status if status in ("granted", "declined", "expired") else "nao_informada"
    return result


def token_projection(payload):
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    data = data if isinstance(data, dict) else {}
    token_type = data.get("type")
    scope_values = data.get("scopes") if isinstance(data.get("scopes"), list) else []
    result = {
        "is_valid": data.get("is_valid") if type(data.get("is_valid")) is bool else None,
        "type": token_type if token_type in ("SYSTEM_USER", "USER", "PAGE", "APP") else "nao_informado",
        "expires_at_utc": expiry(data.get("expires_at")),
        "data_access_expires_at_utc": expiry(data.get("data_access_expires_at")),
        "scopes": [permission for permission in PERMISSIONS if permission in scope_values],
        "granular_scope_target_counts": {},
    }
    # O app_id é configuração pública, não uma credencial nem ID de pessoa.
    app_id = data.get("app_id")
    if isinstance(app_id, (str, int)) and not isinstance(app_id, bool) and re.fullmatch(r"\d{5,30}", str(app_id)):
        result["app_id"] = str(app_id)
    granular = data.get("granular_scopes")
    for row in granular if isinstance(granular, list) else []:
        if isinstance(row, dict) and row.get("scope") in PERMISSIONS:
            targets = row.get("target_ids")
            if isinstance(targets, list):
                result["granular_scope_target_counts"][row["scope"]] = len(targets)
    return result


def emit(label, value):
    print(label + ": " + json.dumps(value, ensure_ascii=False, sort_keys=True), flush=True)


def main():
    if not TOKEN:
        emit("Configuracao", {"ok": False, "category": "secret_ausente"})
        return 1
    payload, status = read_json("me/permissions", {"limit": 100})
    emit("Permissoes", {**status, **({"permissions": permission_projection(payload)} if payload else {})})
    payload, status = read_json("debug_token", {"input_token": TOKEN})
    emit("Token", {**status, **({"metadata": token_projection(payload)} if payload else {})})
    payload, status = read_json("me", {"fields": "id"})
    emit("Identidade", {**status, "identity_readable": bool(payload and isinstance(payload.get("id"), (str, int)))})
    payload, status = read_json("act_" + PROBE_ACCOUNT, {"fields": "id,currency"})
    matched = bool(payload and str(payload.get("id", "")).removeprefix("act_") == PROBE_ACCOUNT)
    emit("Conta vinculada de teste", {**status, "account_readable": matched,
         "currency_is_brl": bool(matched and payload.get("currency") == "BRL")})
    print("Diagnóstico concluído: somente metadados permitidos, sem publicar credenciais ou dados pessoais.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Nenhum traceback: até mensagens de exceção podem incluir URL/token.
        print("Diagnóstico interrompido: resposta não reconhecida; credenciais e respostas brutas omitidas.", file=sys.stderr)
        sys.exit(1)
