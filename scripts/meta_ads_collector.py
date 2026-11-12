#!/usr/bin/env python3
"""LCM Meta Ads: coleta somente leitura, sem publicação automática de dados.
Requisitos: Python 3.10+ (biblioteca padrão). Nunca imprima ou envie o token.
"""
import argparse
import datetime as dt
import decimal
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = os.environ.get("META_API_VERSION", "v25.0")
BASE = "https://graph.facebook.com/" + API_VERSION
TOKEN = os.environ.get("META_ACCESS_TOKEN", "").strip()
FIELDS = "account_id,account_name,campaign_id,campaign_name,date_start,date_stop,spend,impressions,clicks"
DECIMAL = decimal.Decimal


def request(path, params=None):
    if not TOKEN:
        raise RuntimeError("META_ACCESS_TOKEN ausente. Configure como segredo; nunca no código.")
    url = BASE + "/" + path.lstrip("/")
    if params:
        url += "?" + urllib.parse.urlencode(params)
    all_rows = []
    for page in range(100):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "graph.facebook.com":
            raise RuntimeError("Paginação recusada: domínio inesperado.")
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={
                    "Authorization": "Bearer " + TOKEN,
                    "Accept": "application/json",
                    "User-Agent": "LCM-Marketing-Collector/1.0"
                })
                with urllib.request.urlopen(req, timeout=40) as response:
                    data = json.load(response)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                # Não imprimir URL, cabeçalhos ou corpo: podem conter credenciais.
                # Somente códigos e categorias fixas; nunca registrar mensagem,
                # URL ou corpo da resposta, que podem conter dados sensíveis.
                code = subcode = None
                try:
                    detail = json.loads(exc.read()).get("error", {})
                    if type(detail.get("code")) is int: code = detail["code"]
                    if type(detail.get("error_subcode")) is int: subcode = detail["error_subcode"]
                except (ValueError, TypeError, AttributeError):
                    pass
                category = ("token expirado ou inválido; atualize META_ACCESS_TOKEN nos secrets" if code == 190
                            else "permissão de anúncios insuficiente; verifique ads_read e acesso à conta" if code in (10, 200)
                            else "parâmetro ou conta não aceito pela Meta" if code == 100
                            else "verifique ads_read, conta e token")
                raise RuntimeError("Meta API retornou HTTP " + str(exc.code) +
                    " (código " + str(code) + ", subcódigo " + str(subcode) + "): " + category) from None
            except urllib.error.URLError:
                raise RuntimeError("Falha de rede ao consultar a Meta API.") from None
        if "error" in data:
            raise RuntimeError("Meta API recusou a consulta. Confira permissões e conta.")
        # Consultas diretas a uma conta retornam objeto, sem envelope data.
        if "data" not in data and re.fullmatch(r"act_\d{5,25}", path.lstrip("/")):
            if str(data.get("id", "")).removeprefix("act_") != path.lstrip("/").removeprefix("act_"):
                raise RuntimeError("Resposta de conta Meta sem identificador correspondente")
            return data
        all_rows.extend(data.get("data", []))
        url = data.get("paging", {}).get("next")
        if not url:
            return all_rows
    raise RuntimeError("Limite de paginação atingido. Reduza o período.")


# Contas já vinculadas às visões do dashboard; IDs públicos, sem credenciais.
DASHBOARD_ACCOUNT_IDS = ("578753212923958", "379393907144068", "332967835423799",
                         "626593228944023", "272429171879216", "1349139385694575",
                         "347253318197280", "1183301460107081")

DASHBOARD_ACCOUNT_LABELS = {
    "578753212923958": "LCM - Residencial Monte Belo",
    "379393907144068": "LCM - Turquesa Parque",
    "332967835423799": "LCM - Arraial Costa Verde",
    "626593228944023": "LCM - Village Sete Lagoas",
    "272429171879216": "LCM - Residencial Green Plaza",
    "1349139385694575": "LCM - Flamboyant",
    "347253318197280": "LCM - Jacarandá",
    "1183301460107081": "LCM - Jatobá"
}


def accounts():
    configured = os.environ.get("META_AD_ACCOUNT_IDS", "").strip()
    if configured:
        ids = [s.strip().removeprefix("act_") for s in configured.split(",") if s.strip()]
        if not ids or any(not re.fullmatch(r"\d{5,25}", n) for n in ids):
            raise RuntimeError("META_AD_ACCOUNT_IDS deve conter IDs numéricos separados por vírgulas.")
        wanted = tuple(dict.fromkeys(ids))
    else:
        wanted = DASHBOARD_ACCOUNT_IDS
    # O catálogo preserva os metadados de moeda usados por todos os coletores.
    result = request("me/adaccounts", {
        "fields": "id,name,account_status,currency",
        "limit": "100"
    })
    by_id = {str(row.get("id", "")).removeprefix("act_"):row for row in result}
    # Contas atribuídas por um negócio podem não aparecer em me/adaccounts.
    # Conferir diretamente somente os IDs já vinculados antes de concluir falta de acesso.
    missing = []
    for aid in wanted:
        if aid in by_id: continue
        try:
            item = request("act_" + aid, {"fields":"id,name,account_status,currency"})
            if not isinstance(item, dict) or str(item.get("id", "")).removeprefix("act_") != aid:
                raise RuntimeError("Metadados da conta não confirmados")
            by_id[aid] = item
        except RuntimeError:
            missing.append(aid)
    if missing:
        names = ", ".join(DASHBOARD_ACCOUNT_LABELS.get(aid, "Conta vinculada") for aid in missing)
        raise RuntimeError("Token sem acesso a " + str(len(missing)) +
                           " das " + str(len(wanted)) + " contas vinculadas: " + names +
                           ". Revise as permissões dessas contas na Meta.")
    return [by_id[aid] for aid in wanted]

def main():
    parser = argparse.ArgumentParser(description="Teste de leitura Meta Ads sem publicar dados")
    parser.add_argument("--days", type=int, default=7, help="Dias fechados, terminando ontem")
    parser.add_argument("--output", default="", help="Salvar JSON local; não suba ao GitHub público")
    args = parser.parse_args()
    if not 1 <= args.days <= 90:
        parser.error("--days deve ficar entre 1 e 90")
    if not re.fullmatch(r"v\d+\.\d+", API_VERSION):
        parser.error("META_API_VERSION inválida")
    yesterday = dt.date.today() - dt.timedelta(days=1)
    since = yesterday - dt.timedelta(days=args.days - 1)
    found = accounts()
    print("Contas identificadas: " + str(len(found)))
    result = []
    failed = 0
    for a in found:
        acc_id = str(a["id"])
        if not re.fullmatch(r"act_\d+", acc_id):
            print("Conta ignorada: ID inválido.")
            failed += 1
            continue
        try:
            rows = request(acc_id + "/insights", {
                "fields": FIELDS, "level": "campaign", "time_increment": "1",
                "time_range": json.dumps({"since": since.isoformat(), "until": yesterday.isoformat()}),
                "limit": "250"
            })
            # Nunca coletar nomes de pessoas, leads, criativos ou identificadores individuais.
            for r in rows:
                result.append({
                    "account_id": r.get("account_id", acc_id[4:]),
                    "campaign_id": r.get("campaign_id", ""),
                    "campaign_name": r.get("campaign_name", ""),
                    "date": r.get("date_start", ""),
                    "spend": str(DECIMAL(str(r.get("spend", "0")))),
                    "impressions": int(r.get("impressions", 0)),
                    "clicks": int(r.get("clicks", 0)),
                })
            print("Conta " + acc_id[4:] + ": consulta concluída; " + str(len(rows)) + " linhas.")
        except RuntimeError as exc:
            failed += 1
            print("Conta " + acc_id[4:] + ": " + str(exc), file=sys.stderr)
    print("Resumo: " + str(len(result)) + " linhas; " + str(failed) + " contas com falha.")
    if args.output and not failed:
        if os.path.abspath(args.output).startswith(os.path.abspath(".git") + os.sep):
            raise RuntimeError("Não grave resultados dentro de .git")
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({"since": since.isoformat(), "until": yesterday.isoformat(), "records": result},
                      f, ensure_ascii=False, indent=2)
        print("Arquivo local criado. NÃO envie ao repositório público sem revisão.")
    if failed:
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print("Erro: " + str(exc), file=sys.stderr)
        sys.exit(1)
