#!/usr/bin/env python3
"""Diagnóstico agregado de origem dos leads do CV CRM.
Consulta amostra limitada. Não registra nem publica PII ou valores originais.
"""
import argparse
import collections
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_HOST = "lcm.cvcrm.com.br"

def norm_key(v):
    return re.sub(r"[^a-z0-9]", "", str(v).casefold())

def flatten_fields(value, prefix="", depth=0):
    if depth>3:
        return
    if isinstance(value,dict):
        for k,v in value.items():
            key=norm_key(k)
            if isinstance(v,(dict,list)):
                yield from flatten_fields(v,key,depth+1)
            else:
                yield (key,v)
    elif isinstance(value,list):
        for item in value[:15]:
            if isinstance(item,(dict,list)):
                yield from flatten_fields(item,prefix,depth+1)

def text(v):
    if isinstance(v,(str,int,float)) and not isinstance(v,bool):
        return str(v).strip().casefold()
    return ""

def category(values):
    s=" ".join(values)
    if re.search(r"facebook|meta|\bfb\b",s):
        return "Facebook/Meta (origem declarada)"
    if re.search(r"instagram|\big\b",s):
        return "Instagram (origem declarada)"
    if "google" in s or re.search(r"\bgo\b",s):
        return "Google (origem declarada)"
    if "whatsapp" in s or re.search(r"\bwa\b",s):
        return "WhatsApp (origem declarada)"
    if "tiktok" in s:
        return "TikTok (origem declarada)"
    if any(w in s for w in ("site","website","portal","imobiliaria")):
        return "Site/portal/imobiliária"
    if not s:
        return "Não informada"
    return "Outra/não classificada"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--pages",type=int,default=3)
    parser.add_argument("--page-size",type=int,default=100)
    args=parser.parse_args()
    if not 1<=args.pages<=10 or not 1<=args.page_size<=200:
        parser.error("Limites: 1-10 páginas e 1-200 registros por página.")
    domain=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    u=urllib.parse.urlsplit(domain)
    if not all((email,token)) or u.scheme!="https" or u.hostname!=BASE_HOST or u.path not in ("","/") or u.query or u.fragment or u.username or u.password:
        print("Falha de configuração CVCRM_*; domínio deve ser https://"+BASE_HOST)
        return 2
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,url):
            return None
    opener=urllib.request.build_opener(NoRedirect())
    counts=collections.Counter()
    signals=collections.Counter()
    seen=set()
    sample_count=0
    used_pages=0
    for page in range(1,args.pages+1):
        query=urllib.parse.urlencode({"pagina":page,"registros_por_pagina":args.page_size})
        req=urllib.request.Request(domain+"/api/v1/cvdw/leads?"+query,headers={"email":email,"token":token,"Accept":"application/json"})
        try:
            with opener.open(req,timeout=40) as resp:
                payload=json.load(resp)
        except urllib.error.HTTPError as e:
            print("CV CRM: erro HTTP "+str(e.code)+" na consulta agregada.")
            return 1
        except (ValueError,TimeoutError,urllib.error.URLError):
            print("CV CRM: falha na consulta ou no JSON.")
            return 1
        rows=payload.get("dados",[]) if isinstance(payload,dict) else []
        if isinstance(rows,dict): rows=[rows]
        if not isinstance(rows,list):
            print("CV CRM: formato de resposta inesperado.")
            return 1
        used_pages+=1
        if not rows:
            break
        for r in rows:
            if not isinstance(r,dict):
                continue
            # Referência pode se repetir entre páginas/snapshots do CVDW.
            identifier=r.get("idlead")
            if identifier is not None:
                identifier=str(identifier)
                if identifier in seen:
                    continue
                seen.add(identifier)
            sample_count+=1
            fields=list(flatten_fields(r))
            origin_values=[text(v) for k,v in fields if k in {"origem","origemnome","origemultimo","origemultimonome","midia","midiaoriginal","midiaultimo","midias"} and text(v)]
            counts[category(origin_values)]+=1
            keys={k for k,_ in fields}
            if any(k in keys for k in ("origem","origemnome","origemultimo","origemultimonome","midia","midiaoriginal","midiaultimo")):
                signals["Origem ou mídia presente"]+=1
            campaign_keys=("utmcampaign","campaignid","idcampanha","campanha","fbclid","utmcontent","utmmedium","utmsource","adid","adsetid")
            if any(k in keys for k in campaign_keys):
                signals["Campo de rastreamento encontrado"]+=1
            if any(text(v) for k,v in fields if k in ("utmcampaign","campaignid","idcampanha","adid","adsetid")):
                signals["Identificador/nome de campanha preenchido"]+=1
            paid_fields=[text(v) for k,v in fields if k in {"utmmedium","midia","midiaoriginal","midiaultimo","origemnome","origem"}]
            if any(re.search(r"\b(cpc|paid|paid_social|ads|patrocinad|anuncio|m[ií]dia paga)\b",s) for s in paid_fields):
                signals["Indício explícito de mídia paga"]+=1
            if any(k in keys for k in ("idempreendimento","empreendimento","empreendimentos","codigointernoempreendimento")):
                signals["Empreendimento informado"]+=1
    print("CV CRM CVDW: amostra processada com segurança.")
    print("Páginas examinadas: "+str(used_pages))
    print("Leads únicos na amostra: "+str(sample_count))
    print("Canais agrupados (amostra; não total geral):")
    for key in ("Facebook/Meta (origem declarada)","Instagram (origem declarada)","Google (origem declarada)","WhatsApp (origem declarada)","TikTok (origem declarada)","Site/portal/imobiliária","Não informada","Outra/não classificada"):
        if counts[key]:
            print(" - "+key+": "+str(counts[key]))
    print("Cobertura dos campos (amostra):")
    for key in ("Origem ou mídia presente","Campo de rastreamento encontrado","Identificador/nome de campanha preenchido","Indício explícito de mídia paga","Empreendimento informado"):
        print(" - "+key+": "+str(signals[key])+" de "+str(sample_count))
    print("Nenhum valor original de lead, campanha ou mídia foi registrado ou publicado.")
    print("IMPORTANTE: indicação de Facebook/Instagram não comprova anúncio pago ou atribuição a uma campanha.")
    return 0

if __name__=="__main__":
    sys.exit(main())
