#!/usr/bin/env python3
"""Janela histórica diária agregada para o GitHub Pages.

Consulta 90 dias completos de Meta Ads e CV CRM em ambiente GitHub Actions.
Não exporta registros individuais, IDs de leads, campanhas nem credenciais.
Os períodos no navegador são recortes desse histórico. Fonte CV: CVDW por
referência com segunda checagem de data de cadastro; cobertura pode divergir.
"""
import collections
import datetime as dt
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation

from meta_ads_collector import accounts, request
from marketing_consolidate import cv_page, cv_project, guess_channel, norm, to_date

D=Decimal
DAYS=90
MAX_PAGES=50
SIZE=500

def main():
    end=dt.date.today()-dt.timedelta(days=1)
    start=end-dt.timedelta(days=DAYS-1)
    ads=accounts()
    if len(ads)!=8:
        raise RuntimeError("São necessárias exatamente 8 contas para publicar o histórico")
    summary=[]
    for account in ads:
        aid=str(account.get("id",""))
        if not re.fullmatch(r"act_\d+",aid):
            raise RuntimeError("ID Meta inválido")
        currency=str(account.get("currency") or "")
        if currency!="BRL":
            raise RuntimeError("Histórico bloqueado: moeda inesperada em conta Meta")
        rows=request(aid+"/insights",{
            "fields":"date_start,spend,impressions,clicks",
            "level":"account",
            "time_increment":1,
            "time_range":json.dumps({"since":start.isoformat(),"until":end.isoformat()}),
            "limit":100
        })
        daily={}
        for r in rows:
            date=str(r.get("date_start",""))
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",date):
                raise RuntimeError("Data Meta inválida")
            if not start.isoformat()<=date<=end.isoformat():
                raise RuntimeError("Dia Meta fora do período")
            if date in daily:
                raise RuntimeError("Dia duplicado na Meta")
            spend=D(str(r.get("spend") or "0"))
            if not spend.is_finite() or spend<0:
                raise RuntimeError("Gasto inválido")
            daily[date]={
                "spend":str(spend),
                "impressions":int(r.get("impressions") or 0),
                "clicks":int(r.get("clicks") or 0)
            }
        summary.append({
            "account_id":aid[4:],
            "account_name":str(account.get("name") or "")[:80],
            "currency":currency,
            "daily":daily
        })
    base=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    from urllib.parse import urlsplit
    u=urlsplit(base)
    if u.scheme!="https" or u.hostname!="lcm.cvcrm.com.br" or u.path not in ("","/") or u.query or u.fragment or u.username or u.password or not email or not token:
        raise RuntimeError("Credenciais CV inválidas")
    seen=set()
    byday=collections.defaultdict(lambda:collections.Counter())
    complete=False
    invalid_dates=0
    count=0
    for page in range(1,MAX_PAGES+1):
        rows,payload=cv_page(base,email,token,page,SIZE,start,end)
        announced=payload.get("total_de_paginas")
        if announced is not None:
            try:
                announced=int(announced)
            except (ValueError,TypeError):
                raise RuntimeError("Paginação CV inválida")
            if announced<page:
                raise RuntimeError("Paginação CV inconsistente")
        if not rows:
            complete=True
            break
        for row in rows:
            if not isinstance(row,dict):continue
            lead_id=row.get("idlead")
            if lead_id is None:
                # Não há chave para deduplicação: descarta contagem CV.
                invalid_dates+=1
                continue
            lead_id=str(lead_id)
            if lead_id in seen:continue
            seen.add(lead_id)
            date=to_date(row.get("data_cad") or row.get("dataCad") or row.get("data_cadastro") or row.get("datacadastro") or row.get("referencia_data") or row.get("data"))
            if date is None:
                invalid_dates+=1
                continue
            if not start<=date<=end:continue
            project=norm(cv_project(row))
            if not project or project=="nao identificado":continue
            key=(project,date.isoformat())
            byday[key]["leads_period"]+=1
            byday[key][guess_channel(row)]+=1
            count+=1
        if announced is not None and page>=announced:
            complete=True
            break
        if announced is None and len(rows)<SIZE:
            complete=True
            break
    cv_ready=complete and invalid_dates==0
    cv_daily={}
    if cv_ready:
        for (project,date),value in byday.items():
            # A divulgação é apenas de contagens agrupadas, não leads individuais.
            # Pequenos grupos diários ficam suprimidos para mitigar inferência.
            # Isso pode impedir calcular totais exatos em intervalos curtos.
            if value["leads_period"]<5:
                continue
            cv_daily.setdefault(project,{})[date]={
                "leads_period":int(value["leads_period"]),
                "meta_declarada":int(value.get("meta_declarada",0)),
                "google_declarada":int(value.get("google_declarada",0)),
                "outra_ou_nao_informada":int(value.get("outra_ou_nao_informada",0))
            }
    report={
        "schema_version":2,
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "period":{"since":start.isoformat(),"until":end.isoformat()},
        "meta_accounts":summary,
        "cv_by_project_daily":cv_daily,
        "cv_counts_validated":cv_ready,
        "cv_daily_groups_suppressed":True,
        "warning":"CV: dias com menos de 5 leads por empreendimento são ocultados; qualquer período que os inclua terá contagem CV parcial. CPL não prova anúncio pago."
    }
    os.makedirs("data",exist_ok=True)
    path="data/marketing-daily.json"
    with open(path+".tmp","w",encoding="utf-8") as fh:
        json.dump(report,fh,ensure_ascii=False,separators=(",",":"))
    os.replace(path+".tmp",path)
    print("Histórico agregado gerado: "+str(DAYS)+" dias; contas Meta: "+str(len(summary))+".")
    print("CV: "+("disponível com supressão de pequenos grupos" if cv_ready else "indisponível por cobertura incompleta")+".")
    print("Nenhum registro de lead, token ou nome de campanha publicado.")
    return 0

if __name__=="__main__":
    try: sys.exit(main())
    except (RuntimeError, InvalidOperation, ValueError) as ex:
        print("Falha controlada: "+str(ex),file=sys.stderr)
        sys.exit(1)
