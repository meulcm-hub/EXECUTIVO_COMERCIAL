#!/usr/bin/env python3
"""Auditoria privada: vínculos entre cadastro original e eventos CVDW.

Varre snapshots do endpoint de leads em meses e cruza em memória pelo idlead
com eventos de conversão do período. Nenhuma informação identificável, data
individual ou registro é escrita, armazenada em arquivo ou impressa.
"""
import argparse
import collections
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from cv_conversion_history import months
from marketing_consolidate import to_date
from cv_conversion_audit import get_page

PAGE_SIZE=500
MAX_PAGES=100

def get_lead_page(base, email, token, start, end, page):
    qs=urllib.parse.urlencode({
        "pagina":page,"registros_por_pagina":PAGE_SIZE,
        "a_partir_data_referencia":start.isoformat()+" 00:00:00",
        "ate_data_referencia":end.isoformat()+" 23:59:59",
    })
    request=urllib.request.Request(base+"/api/v1/cvdw/leads?"+qs,
        headers={"email":email,"token":token,"Accept":"application/json"})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener=urllib.request.build_opener(NoRedirect())
    for attempt in range(6):
        try:
            with opener.open(request,timeout=45) as response:
                if response.status==204:return [], {"total_de_paginas":0}
                obj=json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code==204:return [], {"total_de_paginas":0}
            if exc.code not in (429,500,502,503,504) or attempt==5:
                raise RuntimeError("Consulta CV leads: HTTP "+str(exc.code)) from None
            retry=exc.headers.get("Retry-After")
            try:delay=min(300,max(15,int(retry))) if retry else min(300,20*2**attempt)
            except (TypeError,ValueError):delay=min(300,20*2**attempt)
            print("Limite temporário da API; respeitando espera antes de nova tentativa.",flush=True)
            time.sleep(delay)
    if not isinstance(obj,dict) or not isinstance(obj.get("dados"),list):
        raise RuntimeError("Formato do endpoint de leads inesperado")
    return obj["dados"],obj

def read_complete(base,email,token,start,end,getter,kind):
    for first,last in months(start,end):
        completed=False
        seen_in_month=set()
        for page in range(1,MAX_PAGES+1):
            time.sleep(3)
            rows,payload=getter(base,email,token,first,last,page)
            try:count=int(payload.get("total_de_paginas") or 0)
            except (ValueError,TypeError):raise RuntimeError("Paginação inválida: "+kind)
            if not rows:
                completed=True
                break
            for record in rows:
                if not isinstance(record,dict):continue
                yield record
            if count and page>=count:
                completed=True
                break
            if not count and len(rows)<PAGE_SIZE:
                completed=True
                break
        if not completed:
            raise RuntimeError("Cobertura incompleta do endpoint "+kind+" em "+first.strftime("%Y-%m"))
        print("Janela "+first.strftime("%Y-%m")+" do endpoint "+kind+" consultada.",flush=True)

def read_conversion_page(base,email,token,start,end,page):
    return get_page(base,email,token,start.isoformat(),end.isoformat(),page)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--since",default="2026-10-01")
    p.add_argument("--until",default="2026-10-31")
    p.add_argument("--history-start",default="2022-01-01")
    args=p.parse_args()
    since=dt.date.fromisoformat(args.since)
    until=dt.date.fromisoformat(args.until)
    first=dt.date.fromisoformat(args.history_start)
    if not (dt.date(2022,1,1)<=first<=since<=until<=dt.date.today()):
        raise RuntimeError("Datas inválidas")
    base=os.getenv("CVCRM_DOMINIO","").strip().rstrip("/")
    url=urllib.parse.urlsplit(base)
    email=os.getenv("CVCRM_EMAIL","").strip()
    token=os.getenv("CVCRM_TOKEN","").strip()
    if url.scheme!="https" or url.hostname!="lcm.cvcrm.com.br" or url.path not in ("","/") or url.query or url.fragment or not email or not token:
        raise RuntimeError("Credenciais CV inválidas ou ausentes")
    originals={}
    conflicting=set()
    scanned=0
    for record in read_complete(base,email,token,first,dt.date.today(),get_lead_page,"cadastros"):
        lead=record.get("idlead")
        if lead is None:continue
        lead=str(lead)
        registered=to_date(record.get("data_cad"))
        if not registered:continue
        scanned+=1
        if lead in originals and registered!=originals[lead]:
            conflicting.add(lead)
            originals[lead]=min(originals[lead],registered)
        else:originals[lead]=registered

    events_by_lead=collections.Counter()
    first_event_date={}
    per_lead_kind=collections.defaultdict(set)
    seen_events=set()
    n_events=0
    for record in read_complete(base,email,token,since,until,read_conversion_page,"conversoes"):
        eid=record.get("idlead_conversao")
        lead=record.get("idlead")
        converted=to_date(record.get("referencia_data"))
        if eid is None or lead is None or converted is None or not since<=converted<=until:
            raise RuntimeError("Evento sem vínculo ou data: período não pode ser validado")
        eid=str(eid);lead=str(lead)
        if eid in seen_events:continue
        seen_events.add(eid)
        n_events+=1
        events_by_lead[lead]+=1
        if lead not in first_event_date or converted<first_event_date[lead]:
            first_event_date[lead]=converted
        registered=originals.get(lead)
        if lead in conflicting or registered is None or registered>converted:
            per_lead_kind[lead].add("sem_vinculo")
        elif registered<converted:
            per_lead_kind[lead].add("retornante")
        else:
            per_lead_kind[lead].add("primeira_data")

    n_matched=sum(1 for lead in events_by_lead if lead in originals and lead not in conflicting)
    repeated=sum(1 for count in events_by_lead.values() if count>1)
    returning=sum(1 for kinds in per_lead_kind.values() if "retornante" in kinds and "sem_vinculo" not in kinds)
    first_only=sum(1 for kinds in per_lead_kind.values() if kinds=={"primeira_data"})
    unresolved=len(events_by_lead)-returning-first_only
    print("AUDITORIA PRIVADA CV CRM - CADASTRO ORIGINAL x CONVERSÕES")
    print("Período eventos: "+since.isoformat()+" a "+until.isoformat())
    print("Período snapshots leads: "+first.isoformat()+" a "+dt.date.today().isoformat())
    print("Registros de leads examinados: "+str(scanned))
    print("IDs distintos nos snapshots: "+str(len(originals)))
    print("Eventos de conversão: "+str(n_events))
    print("Leads distintos com conversão: "+str(len(events_by_lead)))
    print("Vínculos cadastro/conversão com data consistente: "+str(n_matched))
    print("Leads com múltiplas conversões no período: "+str(repeated))
    print("Leads que converteram depois do cadastro original: "+str(returning))
    print("Leads com conversão somente no dia do cadastro: "+str(first_only))
    print("Leads sem classificação segura: "+str(unresolved))
    print("A mesma pessoa pode gerar várias conversões; conversões na data de cadastro podem incluir retornos no mesmo dia.")
    print("NÃO foram exportados leads, identificadores, nomes, telefones ou arquivos.")
    if unresolved:
        print("ATENÇÃO: cobertura incompleta; não publicar divisão novo/retornante como definitiva.")
if __name__=="__main__":
    try:main()
    except (RuntimeError,ValueError) as e:
        print("Auditoria não concluída: "+str(e),file=sys.stderr)
        sys.exit(1)
