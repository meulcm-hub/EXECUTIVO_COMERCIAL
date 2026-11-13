#!/usr/bin/env python3
"""Auditoria segura do cadastro de endereços de empreendimentos do CV CRM.

Não registra nomes/IDs, endereços, CEPs ou coordenadas.
Lê somente endpoint de cadastro; não consulta reservas nem pessoas.
"""
import collections
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

HOST = "lcm.cvcrm.com.br"
PATH = "/api/v1/cadastros/empreendimentos"
MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 50
PAGE_SIZE = 200
FIELDS = {
    "logradouro": ("endereco", "logradouro", "rua", "address", "street"),
    "numero": ("numero", "endereco_numero", "endereconumero", "addressnumber"),
    "bairro": ("bairro", "district", "neighborhood"),
    "cidade": ("cidade", "municipio", "city"),
    "uf": ("uf", "estado", "siglaestado", "state"),
    "cep": ("cep", "zipcode", "postalcode"),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lng", "lon"),
}

def norm(value):
    base = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return "".join(c for c in base if c.isalnum() and not unicodedata.combining(c))

def scalar(value):
    return isinstance(value, (str, int, float)) and not isinstance(value, bool) and str(value).strip() != ""

def fields(row):
    """Only root or explicit project address; never traverse buyer or unit data."""
    if not isinstance(row, dict):
        return set()
    candidates = [row]
    for key, value in row.items():
        if norm(key) in {"enderecoempreendimento", "enderecodoempreendimento", "endereco", "address", "localizacao", "localizacaoempreendimento"} and isinstance(value, dict):
            candidates.append(value)
    found=set()
    for candidate in candidates:
        indexed={norm(k):v for k,v in candidate.items()}
        for label, aliases in FIELDS.items():
            if any(scalar(indexed.get(norm(alias))) for alias in aliases):
                found.add(label)
    return found

def unpack(payload):
    if isinstance(payload,list):
        value=payload
    elif isinstance(payload,dict):
        value=next((payload[k] for k in ("dados","empreendimentos","data","items") if k in payload),None)
        if isinstance(value,dict):
            value=value.get("items") or value.get("dados") or list(value.values())
        if value is None:
            raise ValueError("schema")
    else:
        raise ValueError("schema")
    if not isinstance(value,list) or any(not isinstance(x,dict) for x in value):
        raise ValueError("schema")
    return value

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def credentials(environ):
    domain=environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    url=urllib.parse.urlsplit(domain)
    email=environ.get("CVCRM_EMAIL","").strip()
    token=environ.get("CVCRM_TOKEN","").strip()
    if not (url.scheme=="https" and url.hostname==HOST and url.port in (None,443)
            and url.path in ("","/") and not url.query and not url.fragment
            and not url.username and not url.password and email and token):
        raise ValueError("credentials")
    return domain,email,token

def get_page(opener,base,email,token,page):
    url=base+PATH+"?"+urllib.parse.urlencode({"pagina":page,"registros_por_pagina":PAGE_SIZE})
    req=urllib.request.Request(url,headers={"email":email,"token":token,"Accept":"application/json"})
    with opener.open(req,timeout=30) as response:
        if response.status==204:return [],0
        if response.status!=200 or "json" not in response.headers.get("Content-Type","").lower():
            raise ValueError("response")
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ValueError("size")
    payload=json.loads(raw)
    pages=payload.get("total_de_paginas") if isinstance(payload,dict) else None
    if pages is not None and (isinstance(pages,bool) or not re.fullmatch(r"\d+",str(pages)) or int(pages)>MAX_PAGES):
        raise ValueError("pagination")
    return unpack(payload),int(pages) if pages is not None else None

def audit(fetch):
    stats=collections.Counter()
    seen=set()
    for page in range(1,MAX_PAGES+1):
        items,pages=fetch(page)
        if pages is not None and page>pages:break
        if not items:break
        signature=json.dumps(items,sort_keys=True,ensure_ascii=False)
        if signature in seen:raise ValueError("repeated page")
        seen.add(signature)
        for row in items:
            present=fields(row)
            stats["empreendimentos_lidos"]+=1
            for field in FIELDS:
                stats["com_"+field]+=int(field in present)
            if {"logradouro","numero","cidade","uf"}<=present:
                stats["endereco_completo_com_numero"]+=1
            if {"logradouro","cidade","uf"}<=present:
                stats["endereco_localizavel_sem_numero"]+=1
            if {"latitude","longitude"}<=present:
                stats["coordenadas_declaradas_na_api"]+=1
        if pages is not None and page>=pages:break
        if pages is None and len(items)<PAGE_SIZE:break
    else:
        raise ValueError("pagination incomplete")
    return {k:stats[k] for k in ["empreendimentos_lidos","endereco_completo_com_numero",
      "endereco_localizavel_sem_numero","coordenadas_declaradas_na_api"]+
      ["com_"+k for k in FIELDS]}

def main():
    try:
        base,email,token=credentials(os.environ)
        opener=urllib.request.build_opener(NoRedirect())
        result=audit(lambda page:get_page(opener,base,email,token,page))
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        if not result["empreendimentos_lidos"]:
            print("Nenhum empreendimento retornado; confirmar permissão e endpoint.",file=sys.stderr)
            return 1
        print("Auditoria concluída sem nomes, IDs, logradouros ou coordenadas no log.")
        return 0
    except urllib.error.HTTPError as exc:
        print("Consulta de empreendimentos recusada; HTTP "+str(exc.code)+". Verificar permissão e endpoint.",file=sys.stderr)
        return 1
    except (ValueError,TypeError,urllib.error.URLError,OSError,TimeoutError,OverflowError):
        print("Consulta de empreendimentos não validada; nenhuma localização foi publicada.",file=sys.stderr)
        return 1

if __name__=="__main__":
    sys.exit(main())
