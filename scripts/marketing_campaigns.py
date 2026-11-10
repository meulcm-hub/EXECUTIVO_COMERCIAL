#!/usr/bin/env python3
"""Relatório agregado de formulários Meta por campanha e data (ads_read).

Não acessa, persiste ou publica leads individuais. Os indicadores de formulário
são actions.onsite_conversion.lead_grouped, validados contra o Gerenciador da
Meta no Jacarandá (outubro/2026). Outros tipos são diagnóstico, sem somá-los.
O gasto para CPL é SOMENTE das campanhas que geraram leads de formulário
no período selecionado, não de campanhas de reconhecimento ou mensagens.
"""
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from meta_ads_collector import accounts, request

D = Decimal
DAYS = 90
FORM_ACTION = "onsite_conversion.lead_grouped"
MESSAGE_ACTION = "onsite_conversion.messaging_conversation_started_7d"

def number(value):
    result = D(str(value or "0"))
    if not result.is_finite() or result < 0:
        raise RuntimeError("Valor de métricas inválido")
    return result

def actions(row, kind):
    items = [x for x in (row.get("actions") or [])
             if x.get("action_type") == kind]
    if len(items) > 1:
        raise RuntimeError("A Meta retornou um tipo de ação duplicado")
    return number(items[0].get("value") if items else 0)

def main():
    last = dt.date.today() - dt.timedelta(days=1)
    first = last - dt.timedelta(days=DAYS - 1)
    catalog = accounts()
    if len(catalog) != 8:
        raise RuntimeError("Esperadas exatamente oito contas de anúncios")
    result = []
    for acc in catalog:
        account_id = str(acc.get("id", ""))
        if not re.fullmatch(r"act_\d+", account_id):
            raise RuntimeError("Conta de anúncios inválida")
        if acc.get("currency") != "BRL":
            raise RuntimeError("Moeda da conta não confirmada como BRL")
        rows = request(account_id + "/insights", {
            "fields": "campaign_id,campaign_name,date_start,spend,actions",
            "level": "campaign",
            "time_increment": 1,
            "action_report_time": "impression",
            "use_unified_attribution_setting": "true",
            "time_range": json.dumps({
                "since": first.isoformat(), "until": last.isoformat()
            }, separators=(",", ":")),
            "limit": 200
        })
        campaign_data = {}
        for row in rows:
            cid = str(row.get("campaign_id") or "")
            date = str(row.get("date_start") or "")
            if not re.fullmatch(r"\d+", cid):
                raise RuntimeError("Campanha sem ID válido")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or not first.isoformat() <= date <= last.isoformat():
                raise RuntimeError("Data de campanha fora da janela")
            item = campaign_data.setdefault(cid, {
                "campaign_name": str(row.get("campaign_name") or "Campanha")[:120],
                "daily": {}
            })
            if date in item["daily"]:
                raise RuntimeError("Campanha/data duplicada: dados seriam contados duas vezes")
            spend = number(row.get("spend"))
            forms = actions(row, FORM_ACTION)
            messages = actions(row, MESSAGE_ACTION)
            if forms != int(forms) or messages != int(messages):
                raise RuntimeError("Quantidade de conversões não integral")
            item["daily"][date] = {
                "spend": str(spend),
                "form_leads": int(forms),
                "messages": int(messages)
            }
        # IDs de campanhas não são exportados: somente nome e contagens agregadas.
        published = list(campaign_data.values())
        result.append({
            "account_id": account_id[4:],
            "campaigns": published
        })
        print("Conta consultada: campanhas "+str(len(published))+
              "; dias de campanha "+str(sum(len(x["daily"]) for x in published)))
    output = {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "period": {"since": first.isoformat(), "until": last.isoformat()},
        "action_type": FORM_ACTION,
        "action_report_time": "impression",
        "attribution": "use_unified_attribution_setting=true",
        "accounts": result,
        "warning": "Resultados da Meta não são registros individuais. Não somar indicadores lead e onsite_conversion.lead_grouped; a classificação de origem CV não comprova a atribuição por campanha."
    }
    os.makedirs("data", exist_ok=True)
    filename = "data/marketing-campaigns.json"
    with open(filename+".tmp", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, separators=(",",":"))
    os.replace(filename+".tmp", filename)
    print("Indicadores diários agregados por campanha preparados para publicação.")
    print("Nenhum token, lead, telefone ou email individual foi armazenado.")
    return 0

if __name__ == "__main__":
    try: sys.exit(main())
    except (RuntimeError, InvalidOperation, ValueError) as error:
        print("Auditoria não concluída: "+str(error),file=sys.stderr)
        sys.exit(1)
