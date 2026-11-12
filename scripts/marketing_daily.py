#!/usr/bin/env python3
"""Janela histórica diária agregada para o GitHub Pages.

Consulta o histórico desde janeiro de 2026 de Meta Ads e CV CRM em ambiente GitHub Actions.
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
from pathlib import Path
from decimal import Decimal, InvalidOperation

from meta_ads_collector import accounts, request
from marketing_consolidate import cv_page, cv_project, guess_channel, classify_channel, norm, to_date

D=Decimal
HISTORY_START=dt.date(2026,1,1)
MAX_PAGES=50
SIZE=500

def main():
    end=dt.date.today()
    start=HISTORY_START
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
    # Conversões/funil têm coleta completa própria. Não refazer a mesma
    # leitura anual apenas para a amostragem legada deste arquivo Meta.
    dedicated_cv=False
    try:
        dedicated=json.loads(Path("data/marketing-conversions.json").read_text(encoding="utf-8"))
        dedicated_cv=(dedicated.get("validated") is True and dedicated.get("schema_version",0)>=3
                      and dedicated.get("channel_scope")=="facebook_google"
                      and isinstance(dedicated.get("daily"),dict))
    except (OSError,ValueError,TypeError):
        pass
    if dedicated_cv:
        print("CV consultado pelos relatórios dedicados; coleta Meta não repete a leitura anual CV.",flush=True)
    seen=set()
    byday=collections.defaultdict(lambda:collections.Counter())
    complete=False
    invalid_dates=0
    count=0
    for page in range(1,(0 if dedicated_cv else MAX_PAGES)+1):
        try:
            rows,payload=cv_page(base,email,token,page,SIZE,start,end)
        except RuntimeError:
            # A amostragem diária CV é complementar às conversões/funil.
            # Nunca publicar contagens parciais nem bloquear a coleta Meta válida.
            print("Resumo diário CV indisponível; contagens CV não serão publicadas neste arquivo.",flush=True)
            complete=False
            break
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
            subtype=classify_channel(row)
            if subtype.startswith("meta_") and subtype!="meta_declarada":
                byday[key][subtype]+=1
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
            # Exporta APENAS contagens agregadas por empreendimento, data e origem.
            # Usuário autorizou publicação pública de indicadores agregados.
            # Nenhum ID, nome ou outro atributo individual é persistido.
            cv_daily.setdefault(project,{})[date]={
                "leads_period":int(value["leads_period"]),
                "meta_declarada":int(value.get("meta_declarada",0)),
                "meta_whatsapp_cv":int(value.get("meta_whatsapp_cv",0)),
                "meta_busca_compartilhada_cv":int(value.get("meta_busca_compartilhada_cv",0)),
                "meta_outros_cv":int(value.get("meta_outros_cv",0)),
                "google_declarada":int(value.get("google_declarada",0)),
                "outra_ou_nao_informada":int(value.get("outra_ou_nao_informada",0))
            }
    report={
        "schema_version":3,
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "period":{"since":start.isoformat(),"until":end.isoformat()},
        "meta_accounts":summary,
        "cv_by_project_daily":cv_daily,
        "cv_known_projects":sorted({project for project,date in byday}),
        "cv_counts_validated":cv_ready,
        "cv_daily_groups_suppressed":False,
        "warning":"Busca Compartilhada e mídia WhatsApp Facebook classificadas como Meta por regra LCM. Contagens agregadas públicas, sem atribuição individual comprovada."
    }
    os.makedirs("data",exist_ok=True)
    path="data/marketing-daily.json"
    with open(path+".tmp","w",encoding="utf-8") as fh:
        json.dump(report,fh,ensure_ascii=False,separators=(",",":"))
    os.replace(path+".tmp",path)
    print("Histórico agregado gerado: "+str((end-start).days+1)+" dias; contas Meta: "+str(len(summary))+".")
    print("CV: "+("contagens diárias agregadas disponíveis" if cv_ready else "indisponível por cobertura incompleta")+".")
    print("Nenhum registro de lead, token ou nome de campanha publicado.")
    print("Atenção: apenas contagens diárias por empreendimento e origem são publicadas.")
    return 0

if __name__=="__main__":
    try: sys.exit(main())
    except (RuntimeError, InvalidOperation, ValueError) as ex:
        print("Falha controlada: "+str(ex),file=sys.stderr)
        sys.exit(1)
