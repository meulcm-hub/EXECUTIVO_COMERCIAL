#!/usr/bin/env python3
"""Auditoria histórica CV CRM em lotes mensais, desde 2022.

Usa endpoint de conversões sem exportar identificadores ou contatos.
Um mesmo lead pode aparecer em vários meses; totais de eventos e pessoas
distintas são contados separadamente. Sem inferir perda para a Meta.
"""
import argparse
import collections
import datetime as dt
import os
import sys
import time
import urllib.parse

from cv_conversion_audit import get_page, source, to_date, LIMIT, MAX_PAGES

def months(start,end):
    cursor=start.replace(day=1)
    while cursor<=end:
        next_month=(cursor.replace(day=28)+dt.timedelta(days=4)).replace(day=1)
        last=next_month-dt.timedelta(days=1)
        yield max(start,cursor),min(end,last)
        cursor=next_month

def run_month(base,email,token,start,end):
    seen=set()
    persons=set()
    returning=set()
    new=set()
    indeterminate=set()
    channel=collections.Counter()
    events=0
    incomplete=0
    complete=False
    page_count=0
    for page in range(1,MAX_PAGES+1):
        rows,payload=get_page(base,email,token,start.isoformat(),end.isoformat(),page)
        page_count+=1
        try: total=int(payload.get("total_de_paginas") or 0)
        except (ValueError,TypeError):
            raise RuntimeError("Paginação inválida em "+start.strftime("%Y-%m"))
        if not rows:
            complete=True
            break
        for row in rows:
            if not isinstance(row,dict):continue
            eid=row.get("idlead_conversao")
            lead=row.get("idlead")
            date=to_date(row.get("referencia_data"))
            registered=to_date(row.get("data_cad"))
            if eid is None or lead is None or date is None:
                incomplete+=1
                continue
            if not start<=date<=end:continue
            eid=str(eid)
            lead=str(lead)
            if eid in seen:continue
            seen.add(eid)
            events+=1
            persons.add(lead)
            if registered is None or registered>date:
                indeterminate.add(lead)
            elif registered<date:
                returning.add(lead)
            else:
                new.add(lead)
            channel[source(row)]+=1
        if total and page>=total:
            complete=True
            break
        if not total and len(rows)<LIMIT:
            complete=True
            break
    if not complete or incomplete:
        raise RuntimeError("Mês "+start.strftime("%Y-%m")+" incompleto ("+
            str(page_count)+" páginas; "+str(incomplete)+" eventos sem identificação válida). "+
            "Nenhum total histórico definitivo foi publicado.")
    return {
        "events":events, "persons":persons, "returning":returning,
        "new":new, "channel":channel, "pages":page_count
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--since",default="2022-01-01")
    ap.add_argument("--until",default="",help="Em branco = data de hoje")
    args=ap.parse_args()
    since=dt.date.fromisoformat(args.since)
    until=dt.date.fromisoformat(args.until) if args.until else dt.date.today()
    if since<dt.date(2022,1,1) or since>until or until>dt.date.today():
        raise RuntimeError("Escolha data inicial desde 2022 e data final até hoje.")
    base=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    parsed=urllib.parse.urlsplit(base)
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    if parsed.scheme!="https" or parsed.hostname!="lcm.cvcrm.com.br" or parsed.path not in ("","/") or parsed.query or parsed.fragment or parsed.username or parsed.password or not email or not token:
        raise RuntimeError("Credenciais CV CRM indisponíveis ou domínio não autorizado")
    all_people=set()
    ever_returned=set()
    ever_new=set()
    total_events=0
    channel_total=collections.Counter()
    month_count=0
    for start,end in months(since,until):
        result=run_month(base,email,token,start,end)
        month_count+=1
        total_events+=result["events"]
        all_people.update(result["persons"])
        ever_returned.update(result["returning"])
        ever_new.update(result["new"])
        channel_total.update(result["channel"])
        print("Mês "+start.strftime("%Y-%m")+": eventos "+str(result["events"])+
              "; leads únicos no mês "+str(len(result["persons"]))+
              "; páginas "+str(result["pages"])+".")
        sys.stdout.flush()
        time.sleep(0.15)
    print("AUDITORIA HISTÓRICA CV CRM — DADOS APENAS AGREGADOS")
    print("Período: "+since.isoformat()+" até "+until.isoformat())
    print("Meses completos consultados: "+str(month_count))
    print("Eventos distintos: "+str(total_events))
    print("Leads únicos em todo o período: "+str(len(all_people)))
    print("Leads com alguma reconversão posterior ao cadastro: "+str(len(ever_returned)))
    print("Leads com evento no mesmo dia do cadastro: "+str(len(ever_new)))
    print("Eventos classificados como Meta/Facebook/WhatsApp/Busca Compartilhada: "+
          str(sum(value for kind,value in channel_total.items() if kind.startswith("meta_"))))
    print("LEITURA: os grupos de novo/retorno podem se sobrepor; o mesmo lead pode retornar várias vezes.")
    print("Classificação do retorno é por dia, ainda não distingue duas conversões no mesmo dia.")
    print("Não publicou arquivo, leads individuais, tokens ou identificadores.")
if __name__=="__main__":
    try: main()
    except (RuntimeError,ValueError) as exc:
        print("Diagnóstico histórico interrompido: "+str(exc),file=sys.stderr)
        sys.exit(1)
