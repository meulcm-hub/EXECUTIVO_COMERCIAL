#!/usr/bin/env python3
"""Auditoria agregada dos resultados de formulários da Meta Ads.

Consulta somente Insights (ads_read). Não acessa leads individuais.
Compara action_report_time=impression e conversion e lista tipos de ações
independentemente: 'lead', 'onsite_conversion.lead_grouped' e 'leadgen_grouped'
podem ser versões sobrepostas de uma mesma conversão e não são somadas.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from meta_ads_collector import request, accounts

TYPES = (
    "onsite_conversion.lead_grouped",
    "leadgen_grouped",
    "onsite_conversion.lead",
    "lead",
    "offsite_conversion.fb_pixel_lead",
    "onsite_conversion.messaging_conversation_started_7d",
)
FORM_TYPES = ("onsite_conversion.lead_grouped", "leadgen_grouped")

def metrics(rows):
    by_campaign = defaultdict(lambda: {"spend": Decimal("0"), "actions": defaultdict(Decimal)})
    for row in rows:
        key=str(row.get("campaign_id") or "")
        if not re.fullmatch(r"\d+",key):
            continue
        by_campaign[key]["spend"] += Decimal(str(row.get("spend") or "0"))
        for action in row.get("actions") or []:
            kind=str(action.get("action_type") or "")
            if kind in TYPES:
                by_campaign[key]["actions"][kind] += Decimal(str(action.get("value") or 0))
    return by_campaign

def aggregate(campaigns):
    totals=defaultdict(Decimal)
    for data in campaigns.values():
        totals["spend"]+=data["spend"]
        for kind,v in data["actions"].items():
            totals[kind]+=v
    return totals

def as_int(x):
    return str(int(x)) if x==int(x) else str(x)

def fetch(account, since, until, report_time):
    return request(account+"/insights",{
        "fields":"campaign_id,campaign_name,spend,actions,date_start,date_stop",
        "level":"campaign",
        "time_range":json.dumps({"since":since,"until":until},separators=(",",":")),
        "action_report_time":report_time,
        "use_unified_attribution_setting":"true",
        "limit":"200"
    })

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--since",default="2026-10-01")
    p.add_argument("--until",default="2026-10-31")
    p.add_argument("--account-id",default="347253318197280",
        help="ID da conta Jacarandá previamente mapeada; sem prefixo act_")
    p.add_argument("--expected-form-leads",type=int,default=665)
    args=p.parse_args()
    start=dt.date.fromisoformat(args.since)
    end=dt.date.fromisoformat(args.until)
    if end<start or (end-start).days>90 or end>=dt.date.today():
        raise RuntimeError("Intervalo inválido: use até 91 dias encerrados.")
    aid=args.account_id.removeprefix("act_")
    allowed={str(a["id"]).removeprefix("act_") for a in accounts()}
    if aid not in allowed:
        raise RuntimeError("Conta Meta não está na lista autorizada.")
    print("Auditoria somente leitura de resultados Meta Ads.")
    print("Período fechado: "+args.since+" até "+args.until)
    print("Métrica visual de referência informada: "+str(args.expected_form_leads)+" leads de formulário.")
    print("Parâmetro: use_unified_attribution_setting=true; atribuição conforme conjunto de anúncios.")
    print("Não somar aliases de conversão; métricas diferentes podem se sobrepor.")
    for mode in ("impression","conversion"):
        result=fetch("act_"+aid,args.since,args.until,mode)
        campaigns=metrics(result)
        totals=aggregate(campaigns)
        print("--- Relatório por data de "+("veiculação" if mode=="impression" else "conversão")+" ---")
        print("Campanhas retornadas: "+str(len(campaigns)))
        print("Investimento total consultado (BRL se a conta estiver em BRL): "+str(totals["spend"]))
        for kind in TYPES:
            print("Tipo de ação "+kind+": "+as_int(totals[kind]))
        top=sorted(campaigns.items(),key=lambda kv: max((kv[1]["actions"].get(k,Decimal(0)) for k in FORM_TYPES),default=Decimal(0)),reverse=True)
        print("Campanhas com ações de formulários, classificadas por volume:")
        for index,(_,values) in enumerate(top[:12],1):
            form=max((values["actions"].get(k,Decimal(0)) for k in FORM_TYPES),default=Decimal(0))
            if not form:continue
            print("  Campanha "+str(index)+": formulários ("+" / ".join(as_int(values["actions"].get(k,Decimal(0))) for k in FORM_TYPES)+"); investimento "+str(values["spend"]))
        if args.expected_form_leads>=0:
            for kind in FORM_TYPES:
                value=totals[kind]
                if value:
                    print("Comparação "+kind+" com print: diferença API - print = "+as_int(value-args.expected_form_leads))
    print("Os IDs de campanha, nomes, identificadores de leads e credenciais não foram impressos.")
    print("Resultado NÃO comprova automaticamente falta de leads no CV CRM.")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except (RuntimeError,ValueError,InvalidOperation) as exc:
        print("Consulta de auditoria não concluída: "+str(exc),file=sys.stderr)
        sys.exit(1)
