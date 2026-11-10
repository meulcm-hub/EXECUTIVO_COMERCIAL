#!/usr/bin/env python3
"""Diagnóstico seguro CVDW de novas entradas e reconversões.

Consulta /api/v1/cvdw/leads/conversoes, filtra referência da conversão e
compara a data original de cadastro (data_cad) à data do evento. IDs ficam
somente na memória para deduplicação; NÃO escreve JSON público nem logs de PII.

Um evento não equivale a um lead único. A data de referência deste endpoint
é a data de cadastro da conversão, conforme documentação CV CRM.
"""
import argparse
import collections
import datetime as dt
import json
import os
import sys
import time
import email.utils
import urllib.error
import urllib.parse
import urllib.request

from marketing_consolidate import to_date, norm, classify_channel

LIMIT=500
MAX_PAGES=50

def get_page(base,email,token,since,until,page):
    url=base+"/api/v1/cvdw/leads/conversoes?"+urllib.parse.urlencode({
        "pagina":page,
        "registros_por_pagina":LIMIT,
        "a_partir_data_referencia":since+" 00:00:00",
        "ate_data_referencia":until+" 23:59:59"
    })
    req=urllib.request.Request(url,headers={
        "email":email,"token":token,"Accept":"application/json"
    })
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):return None
    opener=urllib.request.build_opener(NoRedirect())
    for attempt in range(6):
        try:
            with opener.open(req,timeout=45) as response:
                if response.status==204:return [],{"total_de_paginas":0}
                payload=json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code==204:return [],{"total_de_paginas":0}
            if exc.code not in (429,500,502,503,504) or attempt==5:
                raise RuntimeError("CVDW conversões retornou HTTP "+str(exc.code)+
                    " após "+str(attempt+1)+" tentativa(s)") from None
            retry=exc.headers.get("Retry-After")
            wait=None
            if retry:
                try:
                    wait=max(0,int(retry))
                except ValueError:
                    try:
                        server_time=email.utils.parsedate_to_datetime(retry)
                        wait=max(0,(server_time-dt.datetime.now(dt.timezone.utc)).total_seconds())
                    except (TypeError,ValueError,OverflowError):
                        pass
            delay=min(300,max(15,wait if wait is not None else 20*(2**attempt)))
            print("CVDW HTTP "+str(exc.code)+
                  ": respeitando limite da API; nova tentativa após "+str(int(delay))+
                  " segundos ("+str(attempt+1)+"/6).",flush=True)
            time.sleep(delay)
        except (urllib.error.URLError,TimeoutError,ValueError):
            raise RuntimeError("CVDW conversões não respondeu corretamente") from None
    if not isinstance(payload,dict) or not isinstance(payload.get("dados",[]),list):
        raise RuntimeError("Formato da resposta de conversões não reconhecido")
    return payload.get("dados",[]),payload

def source(row):
    # Por conversão, a origem/mídia do evento tem prioridade sobre a original.
    event=dict(row)
    event["origem"]=row.get("origem_conversao") or row.get("origem") or ""
    event["origem_nome"]=event["origem"]
    event["midia_original"]=row.get("midia_conversao") or row.get("midia") or ""
    event["midia_ultimo"]=""
    event["conversao_original"]=""
    return classify_channel(event)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--since",default="2026-10-01")
    parser.add_argument("--until",default="2026-10-31")
    args=parser.parse_args()
    since=dt.date.fromisoformat(args.since);until=dt.date.fromisoformat(args.until)
    if until<since or (until-since).days>90 or until>=dt.date.today():
        raise RuntimeError("Informe datas encerradas e intervalo de no máximo 91 dias")
    base=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    url=urllib.parse.urlsplit(base)
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    if url.scheme!="https" or url.hostname!="lcm.cvcrm.com.br" or url.path not in ("","/") or url.query or url.fragment or url.username or url.password or not email or not token:
        raise RuntimeError("Credenciais CV CRM indisponíveis ou domínio não autorizado")
    seen_events=set()
    unique_leads=set()
    new_leads=set()
    returning_leads=set()
    unknown_leads=set()
    kinds=collections.Counter()
    events=0
    missing_data=0
    pages=0
    completed=False
    for page in range(1,MAX_PAGES+1):
        rows,payload=get_page(base,email,token,args.since,args.until,page)
        pages+=1
        try: total_pages=int(payload.get("total_de_paginas",0))
        except (TypeError,ValueError):raise RuntimeError("Paginação inválida") from None
        if not rows:
            completed=True
            break
        for row in rows:
            if not isinstance(row,dict):continue
            event_id=row.get("idlead_conversao") or row.get("referencia")
            lead_id=row.get("idlead")
            event_date=to_date(row.get("referencia_data"))
            registered=to_date(row.get("data_cad"))
            if not event_id or not lead_id or not event_date:
                missing_data+=1
                continue
            if not since<=event_date<=until:continue
            event_id=str(event_id);lead_id=str(lead_id)
            if event_id in seen_events:continue
            seen_events.add(event_id)
            events+=1
            unique_leads.add(lead_id)
            if registered is None or registered>event_date:
                unknown_leads.add(lead_id)
                kinds["sem_data_cadastro"]+=1
            elif registered<event_date:
                returning_leads.add(lead_id)
                kinds["retorno"]+=1
            else:
                new_leads.add(lead_id)
                kinds["novo_mesma_data"]+=1
            channel=source(row)
            kinds["canal_"+channel]+=1
        if total_pages and page>=total_pages:
            completed=True;break
        if not total_pages and len(rows)<LIMIT:
            completed=True;break
    # Uma pessoa pode ter entrado e retornado no mesmo mês. Para divisão
    # exclusiva, prioriza retorno, depois novo e indeterminado.
    only_returning=returning_leads
    only_new=new_leads-returning_leads
    only_unknown=unique_leads-only_returning-only_new
    print("AUDITORIA CV CRM - EVENTOS DE CONVERSÃO (somente agregados)")
    print("Período: "+args.since+" a "+args.until)
    print("Páginas consultadas: "+str(pages))
    print("Paginação completa: "+str(completed))
    print("Eventos de conversão distintos: "+str(events))
    print("Leads únicos com conversão: "+str(len(unique_leads)))
    print("Leads com alguma conversão posterior ao cadastro: "+str(len(only_returning)))
    print("Leads que converteram apenas na data do cadastro: "+str(len(only_new)))
    print("Leads sem classificação conclusiva: "+str(len(only_unknown)))
    print("Eventos com classificação Meta/Facebook: "+str(sum(v for k,v in kinds.items() if k.startswith("canal_meta_"))))
    print("Eventos sem data ou ID válido: "+str(missing_data))
    print("IMPORTANTE: retorno definido por diferença de DIA, não horário; reconversão no dia do cadastro pode estar em 'novo'.")
    print("Números só devem entrar no dashboard após verificar cobertura, empreendimento e filtro de origem/etiquetas.")
    print("Não foram exportados nomes, telefones, e-mails, IDs ou registros individuais.")
    if not completed:raise RuntimeError("Cobertura incompleta: aumente o limite apenas após revisão")
if __name__=="__main__":
    try:main()
    except (RuntimeError,ValueError) as e:
        print("Diagnóstico interrompido: "+str(e),file=sys.stderr)
        sys.exit(1)
