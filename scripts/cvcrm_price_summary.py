#!/usr/bin/env python3
"""Diagnóstico de preços aprovados no CV CRM, sem publicar unidades ou credenciais.
Consulta o cadastro de empreendimentos e suas tabelas detalhadas (API v1).
Publica somente indicadores agregados por empreendimento, se a resposta
contiver valores de unidades verificáveis, data de vigência e aprovação.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from statistics import median
from cvcrm_project_address_audit import credentials, get_page, NoRedirect, norm

DEST=Path("data/cvcrm-approved-price-summary.json")
NOW=dt.date.today()
MAX_BYTES=10_000_000

def get_json(opener,base,email,token,path,params):
    url=base+path+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"email":email,"token":token,"Accept":"application/json"})
    with opener.open(req,timeout=45) as res:
        if res.status==204:return []
        if res.status!=200 or "json" not in res.headers.get("Content-Type","").lower():
            raise ValueError("expected_json")
        raw=res.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError("too_large")
    return json.loads(raw)

def valid_id(row):
    for key in ("idempreendimento","idEmpreendimento","id_empreendimento","id"):
        v=row.get(key)
        if not isinstance(v,bool) and re.fullmatch(r"[1-9][0-9]{0,8}",str(v or "")):
            return int(v)
    return None

def name_of(row):
    for k in ("empreendimento","nome","nome_empreendimento","descricao"):
        v=row.get(k)
        if isinstance(v,str) and 2<=len(v.strip())<=180:return v.strip()
    return None

def unpack_tables(payload):
    if isinstance(payload,list):return payload
    if isinstance(payload,dict):
        for key in ("dados","data","tabelas","items","registros"):
            candidate=payload.get(key)
            if isinstance(candidate,list):return candidate
            if isinstance(candidate,dict):
                for sub in ("dados","items","tabelas"):
                    if isinstance(candidate.get(sub),list):return candidate[sub]
        if "idtabela" in payload:return [payload]
    return []

def date_ok(row):
    start=row.get("data_vigencia_de")
    end=row.get("data_vigencia_ate")
    try:
        if start and dt.date.fromisoformat(str(start)[:10])>NOW:return False
        if end and dt.date.fromisoformat(str(end)[:10])<NOW:return False
    except ValueError:
        return False
    return True

def approved(row):
    return str(row.get("aprovado","")).strip().upper() in ("S","SIM","1","TRUE")

def currency_value(v):
    if isinstance(v,bool) or v is None:return None
    if isinstance(v,str):
        v=v.strip().replace("R$","").replace(" ","")
        if "," in v:v=v.replace(".","").replace(",",".")
    try:n=float(v)
    except (ValueError,TypeError):return None
    return round(n,2) if 10000<=n<=200000000 else None

def summarize(tables):
    """Não somar séries ao valor_total, para evitar dupla contagem."""
    selected=[]
    for row in tables:
        if not isinstance(row,dict) or not approved(row) or not date_ok(row):continue
        tid=row.get("idtabela")
        if tid is None:continue
        units=row.get("unidades")
        if not isinstance(units,list):continue
        values={}
        for unit in units:
            if not isinstance(unit,dict):continue
            uid=unit.get("idunidade")
            price=currency_value(unit.get("valor_total"))
            if uid is None or price is None:continue
            key=str(uid)
            if key in values and values[key]!=price:continue
            values[key]=price
        if values:
            selected.append((str(tid),values))
    if not selected:return None
    # Quando mais de uma tabela está vigente, nunca misturar valores de tabelas
    # diferentes ou alegar uma tabela única sem aprovação da política comercial.
    if len(selected)!=1:return {"status":"multiple_current_approved_tables","table_count":len(selected)}
    tid,values=selected[0]
    prices=sorted(values.values())
    return {"status":"ok","table_id":tid,"priced_units":len(prices),
      "minimum":prices[0],"median":round(median(prices),2),
      "maximum":prices[-1],"currency":"BRL"}

def collect(fetch_projects,fetch_tables):
    projects=[];seen=set()
    for page in range(1,51):
        items,total=fetch_projects(page)
        if not items:break
        for row in items:
            name=name_of(row);pid=valid_id(row)
            if not name or pid is None or pid in seen:continue
            seen.add(pid);projects.append((pid,name))
        if total is not None and page>=total:break
        if total is None and len(items)<200:break
    out=[]
    for pid,name in projects[:100]:
        try:
            data=fetch_tables(pid)
            result=summarize(unpack_tables(data))
        except (ValueError,urllib.error.HTTPError,urllib.error.URLError,TimeoutError,OSError):
            result=None
        # Não incluir ID pessoal, unidade, series, pagamento ou dados de clientes.
        out.append({"project":name,"project_id":pid,**(result or {"status":"unavailable"})})
    return {"schema_version":1,"source":"CV CRM - tabela de preços aprovada",
      "as_of":NOW.isoformat(),"projects":out}

def main():
    try:
        base,email,token=credentials(os.environ)
        opener=urllib.request.build_opener(NoRedirect())
        result=collect(
           lambda page:get_page(opener,base,email,token,page),
           lambda pid:get_json(opener,base,email,token,
             "/api/v1/cadastros/empreendimentos/"+str(pid)+"/tabelasdepreco/detalhada",
             {"aprovado":"S","tabelasemjson":"true"}))
        statuses={}
        for p in result["projects"]:statuses[p["status"]]=statuses.get(p["status"],0)+1
        print("Empreendimentos consultados:",len(result["projects"]))
        print("Status agregado:",json.dumps(statuses,sort_keys=True))
        if not any(p["status"]=="ok" for p in result["projects"]):
            print("Nenhuma tabela detalhada única e vigente comprovada; dados anteriores preservados.")
            return 2
        DEST.parent.mkdir(parents=True,exist_ok=True)
        DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print("Sumário de preços revisável gravado sem detalhamento de unidades.")
        return 0
    except (ValueError,urllib.error.URLError,urllib.error.HTTPError,OSError,TimeoutError):
        print("CV CRM preços não disponíveis ou formato incompatível; sem publicação.",file=sys.stderr)
        return 2

if __name__=="__main__":sys.exit(main())
