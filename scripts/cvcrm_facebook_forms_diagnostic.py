#!/usr/bin/env python3
"""Diagnóstico seguro, read-only: formulário Facebook associado às conversões CV CRM.

Usa credenciais v1 já configuradas no GitHub Actions. Não exibe nomes, IDs,
formulários específicos, mídia literal, contatos, token ou respostas brutas.
Consulta uma amostra limitada para conferir disponibilidade de campos; NÃO
reclassifica nem publica o funil antes de validar vínculo/escopo.
"""
import collections
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from cvcrm_project_address_audit import credentials, NoRedirect

MAX_BYTES=2_000_000
def fetch(opener,base,email,token,path,params):
    url=base+path+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"email":email,"token":token,"Accept":"application/json"})
    with opener.open(req,timeout=40) as r:
        if r.status!=200 or "json" not in r.headers.get("Content-Type","").lower():
            raise ValueError("non_json")
        raw=r.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError("oversized")
    return json.loads(raw)

def records(payload):
    if isinstance(payload,list):return payload
    if not isinstance(payload,dict):raise ValueError("schema")
    for key in ("dados","data","conversoes","conversoes_leads","items"):
        value=payload.get(key)
        if isinstance(value,list):return value
        if isinstance(value,dict):
            for inner in ("items","dados","conversoes"):
                if isinstance(value.get(inner),list):return value[inner]
            # Exemplo oficial v1 apresenta "dados" como objeto único.
            # Não considerar esse formato uma falha na integração.
            if "idlead" in value or "data_conversao" in value:return [value]
            indexed=[item for key,item in value.items() if str(key).isdigit() and isinstance(item,dict)]
            if indexed:return indexed
    raise ValueError("schema")

def classify_keys(rows):
    """Somente presença e tipo de campos, nunca valores reais."""
    group=collections.Counter()
    for row in rows:
        if not isinstance(row,dict):continue
        group["rows"]+=1
        for k,v in row.items():
            name=str(k).casefold().replace("_","")
            if "formulario" in name: group["form_field_"+("filled" if v not in (None,"",[]) else "empty")]+=1
            if "integracao" in name:group["integration_field_present"]+=1
            if "midia" in name:group["media_field_present"]+=1
            if name in ("idlead","leadid"):group["lead_id_field_present"]+=1
            if "campanha" in name:group["campaign_field_present"]+=1
            if name in ("idintegracao","integrationid"):group["integration_id_field_present"]+=1
    return dict(sorted(group.items()))

def main():
    try:
        base,email,token=credentials(os.environ)
        opener=urllib.request.build_opener(NoRedirect())
        # Primeira consulta: conversões recentes, limitada. O retorno pode
        # conter linhas com PII, jamais serializar ou imprimir o payload.
        payload=fetch(opener,base,email,token,"/api/v1/comercial/leads-conversao",
                      {"pagina":1,"registros_por_pagina":100,
                       "data_de":"2026-11-01","data_ate":"2026-11-13"})
        items=records(payload)
        counts=classify_keys(items)
        print("Endpoint de conversões v1: resposta HTTP 200, estrutura reconhecida")
        print("Diagnóstico agregado de campos: "+json.dumps(counts,sort_keys=True))
        if not items:print("Amostra vazia; cobertura não validada.")
        if not counts.get("form_field_filled"):
            print("A resposta v1 não demonstrou ID de formulário. Campo NÃO documentado no contrato da API v1; usar nome/data/idlead apenas como indícios, não atribuição de anúncio.")
        else:
            print("Campo de formulário presente; validar formato e correspondência em ambiente privado antes de atribuir campanhas.")
        return 0
    except urllib.error.HTTPError as e:
        print("Endpoint v1 indisponível: HTTP "+str(e.code)+".",file=sys.stderr)
        return 2
    except (ValueError,urllib.error.URLError,OSError,TimeoutError,TypeError):
        print("Resposta v1 não validada. Nenhum lead exposto.",file=sys.stderr)
        return 2

if __name__=="__main__":sys.exit(main())
