#!/usr/bin/env python3
"""CV CRM CVDW: preços vigentes de unidades, agregados por empreendimento.
Fonte /api/v1/cvdw/unidades/precos. Nunca publica preços por unidade,
credenciais ou resposta bruta. Sem vigência confirmada = indisponível.
"""
from __future__ import annotations
import collections
import datetime as dt
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from statistics import median
from cvcrm_project_address_audit import credentials, NoRedirect

PATH="/api/v1/cvdw/unidades/precos"
DEST=Path("data/cvcrm-approved-price-summary.json")
NOW=dt.date.today()
MAX_PAGES=100
PAGE_SIZE=500
MAX_BYTES=10_000_000

def parse_date(value):
    try:return dt.date.fromisoformat(str(value or "")[:10])
    except (ValueError,TypeError):return None

def parse_datetime(value):
    try:return dt.datetime.fromisoformat(str(value or "").strip().replace("Z","+00:00"))
    except (ValueError,TypeError):return None

def money(value):
    if value is None or isinstance(value,bool):return None
    if isinstance(value,str):
        value=value.strip().replace("R$","").replace(" ","")
        if "," in value:value=value.replace(".","").replace(",",".")
    try:num=float(value)
    except (TypeError,ValueError):return None
    return round(num,2) if math.isfinite(num) and 10_000<=num<=200_000_000 else None

def numeric_id(value):
    s=str(value or "").strip()
    return s if re.fullmatch(r"[1-9][0-9]{0,12}",s) else None

def active_record(row,when=None):
    when=when or NOW
    start=parse_date(row.get("data_vigencia_de"))
    end=parse_date(row.get("data_vigencia_ate"))
    if not start or not end or not start<=when<=end:return None
    if str(row.get("ativo","")).upper().strip() not in ("S","SIM","1","TRUE"):return None
    if not numeric_id(row.get("idempreendimento")) or not numeric_id(row.get("idtabela")):return None
    if not numeric_id(row.get("idunidade")):return None
    value=money(row.get("valor"))
    if value is None:return None
    return start,end,value

def unpack(payload):
    if isinstance(payload,list):return payload,None
    if not isinstance(payload,dict):raise ValueError("unexpected_schema")
    rows=payload.get("dados")
    if not isinstance(rows,list):raise ValueError("missing_dados")
    total=payload.get("total_de_paginas")
    try:pages=int(total) if total is not None else None
    except (TypeError,ValueError):raise ValueError("invalid_pagination")
    if pages is not None and not 1<=pages<=MAX_PAGES:raise ValueError("pagination_limit")
    return rows,pages

def fetch_page(opener,base,email,token,page):
    params=urllib.parse.urlencode({"pagina":page,"registros_por_pagina":PAGE_SIZE})
    request=urllib.request.Request(base+PATH+"?"+params,
        headers={"email":email,"token":token,"Accept":"application/json"})
    with opener.open(request,timeout=45) as response:
        if response.status!=200 or "json" not in response.headers.get("Content-Type","").lower():
            raise ValueError("unexpected_response")
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError("response_too_large")
    return unpack(json.loads(raw))

def aggregate(rows,when=None):
    when=when or NOW
    # A chave unidade+tabela deduplica snapshots; prevalece referência mais recente.
    projects=collections.defaultdict(lambda:collections.defaultdict(dict))
    for row in rows:
        if not isinstance(row,dict):continue
        validity=active_record(row,when)
        if not validity:continue
        start,end,value=validity
        pid=str(row["idempreendimento"]).strip()
        tid=str(row["idtabela"]).strip()
        uid=str(row["idunidade"]).strip()
        name=str(row.get("empreendimento") or "").strip()
        label=str(row.get("tabela") or "").strip()
        reference=parse_datetime(row.get("referencia_data"))
        if reference is None:continue
        previous=projects[pid][tid].get(uid)
        if previous is None or reference>previous["reference"]:
            projects[pid][tid][uid]={"price":value,"start":start,"end":end,
                "reference":reference,"project":name,"table":label}
    output=[]
    for pid,tables in sorted(projects.items(),key=lambda pair:int(pair[0])):
        candidates=[]
        for tid,units in tables.items():
            if not units:continue
            starts={entry["start"] for entry in units.values()}
            if len(starts)!=1:
                # Tabela com vigências conflitantes: não inventar qual é a atual.
                continue
            start=next(iter(starts))
            candidates.append((start,tid,units))
        if not candidates:continue
        latest=max(item[0] for item in candidates)
        winners=[item for item in candidates if item[0]==latest]
        if len(winners)!=1:
            output.append({"project_id":int(pid),"status":"ambiguous_current_tables",
                           "reference_month":when.strftime("%Y-%m")})
            continue
        start,tid,units=winners[0]
        prices=sorted(entry["price"] for entry in units.values())
        sample=next(iter(units.values()))
        output.append({"project_id":int(pid),"project":sample["project"],
            "table_id":int(tid),"table_name":sample["table"],"status":"ok",
            "reference_month":when.strftime("%Y-%m"),"effective_from":start.isoformat(),
            "effective_to":min(entry["end"] for entry in units.values()).isoformat(),
            "priced_units":len(prices),"minimum":prices[0],
            "median":round(median(prices),2),"maximum":prices[-1],"currency":"BRL",
            "price_field":"valor","selection_rule":"active_today_latest_effective_start"})
    return {"schema_version":2,"source":"CV CRM CVDW /api/v1/cvdw/unidades/precos",
            "as_of":when.isoformat(),"projects":output}

def collect(fetch,when=None):
    all_rows=[]
    seen=set()
    pages=None
    for page in range(1,MAX_PAGES+1):
        rows,pages=fetch(page)
        if not isinstance(rows,list):raise ValueError("unexpected_rows")
        if not rows:break
        signature=tuple(str(x.get("referencia")) for x in (rows[0],rows[-1]) if isinstance(x,dict))
        if signature in seen:raise ValueError("repeated_page")
        seen.add(signature)
        all_rows.extend(rows)
        if pages is not None and page>=pages:break
        if pages is None and len(rows)<PAGE_SIZE:break
    else:raise ValueError("pagination_incomplete")
    return aggregate(all_rows,when)

def main():
    try:
        base,email,token=credentials(os.environ)
        opener=urllib.request.build_opener(NoRedirect())
        result=collect(lambda page:fetch_page(opener,base,email,token,page))
        status=collections.Counter(row["status"] for row in result["projects"])
        print("Projetos com precos:",len(result["projects"]),"status:",dict(status))
        if not status["ok"]:
            print("Nenhum preço vigente validado. Sem atualizar o arquivo publicado.",file=sys.stderr)
            return 2
        DEST.parent.mkdir(parents=True,exist_ok=True)
        DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print("Publicado somente resumo dos preços vigentes; sem unidades/credenciais.")
        return 0
    except (ValueError,urllib.error.URLError,urllib.error.HTTPError,TimeoutError,OSError):
        print("Consulta de preços não validada; nenhum dado publicado.",file=sys.stderr)
        return 2
if __name__=="__main__":sys.exit(main())
