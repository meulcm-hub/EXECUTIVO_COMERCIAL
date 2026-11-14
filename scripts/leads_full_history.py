#!/usr/bin/env python3
"""Coleta histórica integral de leads CV CRM, sem filtrar origem ou empreendimento.

API CVDW /api/v1/cvdw/leads. Registros com IDs são processados SOMENTE em
memória do GitHub runner; no Pages publica-se APENAS agregados sem PII.
Sem total/paginação comprovada, a publicação é interrompida (fail closed).
"""
import collections
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cvcrm_project_address_audit import credentials, NoRedirect
from leads_commercial_dimensions import fetch_all as fetch_commercial_all

API="/api/v1/cvdw/leads"
OUT=Path("data/leads-all-summary.json")
PAGE_SIZE=500
MAX_PAGES=3000
MAX_BYTES=14_000_000
CUTOFF=dt.date.today()

def iso_day(v):
    try:
        s=str(v or "")[:10]
        value=dt.date.fromisoformat(s)
        return value.isoformat() if value<=CUTOFF else None
    except (ValueError,TypeError):return None

def text_value(v):
    if isinstance(v,dict):
        for field in ("nome","descricao","situacao","origem","titulo"):
            if v.get(field):return text_value(v[field])
        return ""
    if isinstance(v,(str,int,float)):return str(v).strip()
    return ""

def project(row):
    for key in ("empreendimento_ultimo","empreendimento_primeiro","empreendimento"):
        v=text_value(row.get(key))
        if v and v.casefold() not in ("null","não informado","nao informado","não identificado","nao identificado","sem empreendimento","-"):
            return v
    return "SEM EMPREENDIMENTO"

def origin(row):
    # Manter o código como chave estável, pois nome e código podem coexistir.
    for k in ("origem_original","origem","origem_cadastro"):
        v=text_value(row.get(k))
        if v:return v
    return "ND"

def origin_name(row):
    # A API CVDW documenta origem_nome como a descrição oficial da origem.
    for k in ("origem_nome","origem_original_nome"):
        v=text_value(row.get(k))
        if v:return v
    return ""

def media_original(row):
    # Fonte real de mídia do LEAD, não da visita: nunca inventar uma mídia.
    for k in ("midia_original","midia_nome","midia","midia_ultimo"):
        v=text_value(row.get(k))
        if v:return v
    return "NÃO INFORMADA"

def visit_media(row):
    """Somente campo explicitamente relacionado à visita; não usar mídia de cadastro."""
    for k in ("midia_visita","midia_visita_nome","midia_da_visita","midiaVisita","midia_visita_original"):
        if k in row:
            return text_value(row.get(k)) or "NÃO INFORMADA"
    return "NÃO DISPONÍVEL NA API"

def status(row):
    for k in ("situacao","situacao_lead","status"):
        v=text_value(row.get(k))
        if v:return v
    return "NÃO INFORMADA"

def record_id(row):
    v=row.get("idlead")
    if isinstance(v,bool):return None
    s=str(v or "").strip()
    return s if re.fullmatch(r"[1-9]\d{0,16}",s) else None

def pick_date(row):
    # data_cad é data do cadastro original. referencia_data é snapshot CVDW;
    # não substituir a data original pela data da atualização.
    return iso_day(row.get("data_cad") or row.get("data_cadastro") or row.get("dataCad"))

def ref(row):
    return str(row.get("referencia_data") or "")

def fetch_page(opener,base,email,token,page):
    qs=urllib.parse.urlencode({"pagina":page,"registros_por_pagina":PAGE_SIZE})
    req=urllib.request.Request(base+API+"?"+qs,headers={"email":email,"token":token,"Accept":"application/json"})
    for attempt in range(5):
        try:
            with opener.open(req,timeout=60) as resp:
                if resp.status!=200 or "json" not in resp.headers.get("Content-Type","").casefold():
                    raise RuntimeError("Resposta CV CRM não é JSON 200")
                raw=resp.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES:raise RuntimeError("Resposta muito grande")
            payload=json.loads(raw)
            if not isinstance(payload,dict) or not isinstance(payload.get("dados"),list):
                raise RuntimeError("Esquema CVDW mudou")
            if "total_de_paginas" not in payload:
                raise RuntimeError("API não comprovou paginação total")
            pages=int(payload["total_de_paginas"])
            if not 1<=pages<=MAX_PAGES:raise RuntimeError("Quantidade de páginas fora do limite de segurança")
            return payload["dados"],pages,payload
        except urllib.error.HTTPError as err:
            if err.code not in (429,500,502,503,504) or attempt==4:
                raise RuntimeError("API leads HTTP "+str(err.code)) from None
            time.sleep(min(45,2**attempt*3))
        except (TimeoutError,urllib.error.URLError):
            if attempt==4:raise RuntimeError("CV CRM sem resposta após tentativas") from None
            time.sleep(min(45,2**attempt*3))
    raise RuntimeError("Requisição não concluída")

def collect(fetch,as_of=None,commercial=None,commercial_meta=None):
    """No single page is silently accepted as complete if pagination says more."""
    as_of=as_of or CUTOFF
    leaders={}
    scanned=0
    missing=0
    invalid_date=0
    pages_total=None
    signatures=set()
    for page in range(1,MAX_PAGES+1):
        rows,n,payload=fetch(page)
        if pages_total is None:pages_total=n
        if pages_total!=n:raise RuntimeError("Paginação alterou durante a coleta; reiniciar")
        if page>n:break
        if not rows:raise RuntimeError("Página vazia antes de concluir paginação")
        sig=(record_id(rows[0]),record_id(rows[-1]),len(rows),ref(rows[0]),ref(rows[-1]))
        if sig in signatures:raise RuntimeError("Página repetida; consulta não é completa")
        signatures.add(sig)
        for item in rows:
            scanned+=1
            if not isinstance(item,dict):raise RuntimeError("Registro malformado")
            key=record_id(item)
            if key is None:
                missing+=1;continue
            day=pick_date(item)
            if not day:
                invalid_date+=1;continue
            old=leaders.get(key)
            detail=(commercial or {}).get(key,{})
            snapshot={"date":day,"reference":ref(item),"project":project(item),
                       "origin":origin(item),
                       "origin_name":detail.get("origin_name") or origin_name(item),
                       "lead_media":detail.get("lead_media") or media_original(item),
                       "visit_media":visit_media(item),"status":status(item)}
            if old is None or snapshot["reference"]>old["reference"]:
                leaders[key]=snapshot
            elif snapshot["reference"]==old["reference"] and snapshot!=old:
                raise RuntimeError("Snapshots conflitantes do mesmo ID sem ordem segura")
        if page>=n:break
    if pages_total is None or len(signatures)!=pages_total:raise RuntimeError("Coleta incompleta")
    if missing or invalid_date:raise RuntimeError("IDs/datas ausentes: coleta íntegra não comprovada")
    if not leaders:raise RuntimeError("API retornou nenhum lead")
    from collections import Counter
    cube=Counter()
    earliest=min(x["date"] for x in leaders.values())
    latest=max(x["date"] for x in leaders.values())
    for item in leaders.values():
        cube[(item["date"],item["project"],item["origin"],item["origin_name"],
              item["lead_media"],item["visit_media"],item["status"])]+=1
    cells=[{"date":d,"project":p,"origin":o,"origin_name":on,
            "lead_media":lm,"visit_media":m,"status":st,"count":n}
           for (d,p,o,on,lm,m,st),n in sorted(cube.items())]
    result={"schema_version":3,"validated":True,
      "source":"CV CRM CVDW leads /api/v1/cvdw/leads (todos os canais)",
      "scope":"all_accessible_leads","as_of":as_of.isoformat(),
      "earliest_cadastro":earliest,"latest_cadastro":latest,
      "unique_leads":len(leaders),"snapshots_scanned":scanned,
      "pages_scanned":pages_total,
      "commercial_details":commercial_meta or {"commercial_total":0,"commercial_pages":0,"commercial_unique":0},
      "commercial_matched":sum(1 for key in leaders if key in (commercial or {})),
      "by_registration_project_origin_status":cells}
    assert sum(x["count"] for x in cells)==len(leaders)
    return result

def main():
    base,email,token=credentials(os.environ)
    opener=urllib.request.build_opener(NoRedirect())
    # Na API comercial, origem e mídia são campos distintos do cadastro.
    # Coleta integral via limit/offset e cruzamento somente em memória por idlead.
    commercial,commercial_meta=fetch_commercial_all(base,email,token)
    result=collect(lambda page:fetch_page(opener,base,email,token,page),
                   commercial=commercial,commercial_meta=commercial_meta)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    temp.replace(OUT)
    print("CV CRM integral: páginas",result["pages_scanned"],
          "snapshots",result["snapshots_scanned"],
          "leads únicos",result["unique_leads"],
          "primeiro cadastro",result["earliest_cadastro"],
          "leads comerciais vinculados",result["commercial_matched"])
    print("Nenhum ID, nome, telefone ou CPF publicado.")
if __name__=="__main__":
    try:main()
    except (RuntimeError,ValueError,TypeError) as err:
        print("Coleta integral não publicada: "+str(err),file=sys.stderr)
        sys.exit(1)
