#!/usr/bin/env python3
"""Coleta SOMENTE dimensões comerciais de leads CV CRM v1.

GET /api/v1/comercial/leads usa limit/offset, NÃO pagina/registros_por_pagina.
Os dados pessoais retornados NÃO são impressos nem gravados. A saída permanece
apenas em memória para vínculo por idlead com o histórico CVDW.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

PATH="/api/v1/comercial/leads"
REQUEST_LIMIT=200
MAX_RECORDS=500_000
MAX_BYTES=12_000_000

def extract(value):
    if isinstance(value,str):
        return value.strip()
    if isinstance(value,dict):
        for k in ("nome","descricao","titulo"):
            if value.get(k):return extract(value[k])
    return ""

def medias(row):
    """Todas as mídias vinculadas ao lead; duplicidades removidas."""
    values=[]
    for k in ("midia_principal","midia_original","midia_ultimo"):
        v=extract(row.get(k))
        if v:values.append(v)
    media_list=row.get("midias")
    if isinstance(media_list,list):
        values.extend(extract(m) for m in media_list)
    unique=list(dict.fromkeys(v for v in values if v))
    return unique or ["NÃO INFORMADA"]

def media(row):
    """Mídia principal preferida para o rótulo; mídias adicionais ficam disponíveis."""
    main=extract(row.get("midia_principal"))
    return main or medias(row)[0]


def origin(row):
    # API comercial apresenta origem por nome (ex.: Facebook).
    return extract(row.get("origem")) or extract(row.get("origem_nome"))

def page_get(opener,base,email,token,offset,limit=REQUEST_LIMIT):
    params=urllib.parse.urlencode({"limit":limit,"offset":offset})
    req=urllib.request.Request(base+PATH+"?"+params,headers={
        "email":email,"token":token,"Accept":"application/json"})
    for attempt in range(6):
        try:
            with opener.open(req,timeout=60) as response:
                if response.status!=200:raise RuntimeError("Resposta comercial diferente de HTTP 200")
                body=response.read(MAX_BYTES+1)
                if len(body)>MAX_BYTES:raise RuntimeError("Resposta comercial excede limite")
            value=json.loads(body)
            if not isinstance(value,dict) or not isinstance(value.get("leads"),list):
                raise RuntimeError("Formato comercial leads mudou")
            total=value.get("total")
            if isinstance(total,bool) or not str(total).isdigit():
                raise RuntimeError("Total comercial não documentado na resposta")
            return value
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt==5:
                raise RuntimeError("GET comercial leads retornou HTTP "+str(e.code)) from None
            time.sleep(min(60,3*2**attempt))
        except (TimeoutError,urllib.error.URLError):
            if attempt==5:raise RuntimeError("GET comercial leads sem resposta") from None
            time.sleep(min(60,3*2**attempt))
    raise RuntimeError("Leitura comercial não concluída")

def collect(fetch):
    """Valida que todas as páginas comercialmente acessíveis foram percorridas."""
    ids={}
    offset=0
    pages=0
    total_expected=None
    while True:
        if offset>MAX_RECORDS:raise RuntimeError("Limite de registros de proteção excedido")
        data=fetch(offset)
        total=int(data["total"])
        rows=data["leads"]
        if total_expected is None:total_expected=total
        if total!=total_expected:raise RuntimeError("Total comercial mudou durante leitura")
        if offset>=total:break
        if not rows:raise RuntimeError("Página comercial vazia antes do fim")
        if offset+len(rows)>total:raise RuntimeError("Resposta comercial excede total anunciado")
        for row in rows:
            if not isinstance(row,dict):raise RuntimeError("Lead comercial malformado")
            raw=row.get("idlead")
            if isinstance(raw,bool) or not str(raw or "").isdigit():
                raise RuntimeError("Lead comercial sem ID confiável")
            key=str(raw)
            value={"origin_name":origin(row),"lead_media":media(row),"lead_medias":medias(row)}
            if key in ids and ids[key]!=value:
                raise RuntimeError("IDs repetidos conflitantes no endpoint comercial")
            ids[key]=value
        pages+=1
        offset+=len(rows)
        if offset>=total:break
    if len(ids)!=(total_expected or 0):
        raise RuntimeError("Paginação comercial incompleta ou IDs duplicados")
    return ids,{"commercial_total":total_expected or 0,
                "commercial_pages":pages,
                "commercial_unique":len(ids)}

def fetch_all(base,email,token):
    opener=urllib.request.build_opener(
        type("NoRedirect",(urllib.request.HTTPRedirectHandler,),{
            "redirect_request":lambda self,*args,**kwargs:None})())
    def fetch(offset):
        data=page_get(opener,base,email,token,offset)
        # limite menor imposto pelo CRM é aceito; offset progride pelos itens recebidos.
        time.sleep(0.35)
        return data
    return collect(fetch)
