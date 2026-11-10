#!/usr/bin/env python3
"""Teste de autenticação CV CRM. Não imprime nem persiste registros pessoais."""
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

def main():
    base = os.environ.get("CVCRM_DOMINIO", "").strip().rstrip("/")
    email = os.environ.get("CVCRM_EMAIL", "").strip()
    token = os.environ.get("CVCRM_TOKEN", "").strip()
    if not all((base, email, token)):
        print("Falha: uma ou mais variáveis CVCRM_* não foram configuradas.")
        return 2
    u = urllib.parse.urlsplit(base)
    if u.scheme != "https" or u.hostname != "lcm.cvcrm.com.br" or u.username or u.password or u.query or u.fragment or u.path not in ("", "/"):
        print("Falha: domínio CV CRM inválido. Esperado https://lcm.cvcrm.com.br")
        return 2
    path = "/api/v1/cvdw/unidades"
    url = base + path + "?pagina=1&registros_por_pagina=1"
    req = urllib.request.Request(url, headers={"email": email, "token": token, "Accept": "application/json"})
    try:
         # Não seguir redirects para outro host e, assim, não transmitir headers secretos.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(req, timeout=25) as resp:
            code = resp.status
            content_type = resp.headers.get("Content-Type", "")
            if code == 200 and "json" in content_type.lower():
                # Não ler nem registrar o corpo, que pode conter dados de clientes.
                print("CV CRM: autenticação e acesso de leitura confirmados (HTTP 200, JSON).")
                return 0
            print("CV CRM: resposta inesperada, HTTP " + str(code) + ".")
            return 1
    except urllib.error.HTTPError as e:
        # Não imprimir e.reason, corpo ou URL.
        status = e.code
        if status in (301, 302, 303, 307, 308):
            print("CV CRM: redirecionamento inesperado; verifique domínio.")
        elif status in (401, 403):
            print("CV CRM: autenticação ou autorização recusada (HTTP " + str(status) + ").")
        elif status == 404:
            print("CV CRM: endpoint de teste não encontrado (HTTP 404).")
        elif status == 429:
            print("CV CRM: limite temporário de requisições (HTTP 429).")
        else:
            print("CV CRM: consulta não concluída (HTTP " + str(status) + ").")
        return 1
    except (urllib.error.URLError, TimeoutError):
        print("CV CRM: falha de conexão ou tempo limite.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
