#!/usr/bin/env python3
"""Diagnostica formatos e cobertura do empreendimento de conversões sem valores de leads."""
import collections
import datetime as dt
import os
import sys
import urllib.parse
from cv_conversion_audit import get_page
from marketing_consolidate import cv_page,norm
PROJECTS={
  "jacaranda":"residencial flores do cerrado jacaranda",
  "village":"residencial village lagoas",
  "arraial":"spe arraial costa verde club",
  "jatoba":"residencial jatoba",
}
FIELDS=("empreendimento_ultimo","empreendimentos_conversao","empreendimento","idempreendimento","idempreendimento_ultimo","empreendimento_primeiro")
def describe(value):
    if value is None:return "null"
    if isinstance(value,str):return "string"
    if isinstance(value,list):return "list"
    if isinstance(value,dict):return "object"
    return type(value).__name__
def main():
    base=os.getenv("CVCRM_DOMINIO","").strip().rstrip("/")
    u=urllib.parse.urlsplit(base)
    email=os.getenv("CVCRM_EMAIL","").strip()
    token=os.getenv("CVCRM_TOKEN","").strip()
    if u.scheme!="https" or u.hostname!="lcm.cvcrm.com.br" or u.path not in ("","/") or not email or not token:
        raise RuntimeError("Configuração CV ausente")
    rows,_=get_page(base,email,token,"2026-10-01","2026-10-31",1)
    leads,_=cv_page(base,email,token,1,100,dt.date(2026,10,1),dt.date(2026,10,31))
    for name,data in (("CONVERSOES",rows),("LEADS",leads)):
        print(name+" quantidade "+str(len(data)))
        for field in FIELDS:
            kinds=collections.Counter(describe(r.get(field)) for r in data if isinstance(r,dict))
            print("Campo "+field+": "+str(dict(kinds)))
            shapes=collections.Counter()
            matches=collections.Counter()
            for r in data:
                if not isinstance(r,dict):continue
                v=r.get(field)
                if isinstance(v,list):
                    for el in v:
                        if isinstance(el,dict):shapes.update(el.keys())
                        elif isinstance(el,str):shapes["list<string>"]+=1
                elif isinstance(v,dict):shapes.update(v.keys())
                elif isinstance(v,str):
                    n=norm(v)
                    for k,project in PROJECTS.items():
                        if n==project:matches[k]+=1
            if shapes:print("  Chaves/estrutura de itens: "+", ".join(sorted(shapes.keys())))
            if matches:print("  Correspondencias exatas de nomes conhecidos: "+str(dict(matches)))
    lengths=collections.Counter()
    member_types=collections.Counter()
    relation=collections.Counter()
    for row in rows:
        v=row.get("empreendimentos_conversao")
        if isinstance(v,list):
            lengths[len(v)]+=1
            for item in v:member_types[describe(item)]+=1
            relation["ultimo_presente_na_lista" if row.get("empreendimento_ultimo") in v else "ultimo_ausente_da_lista"]+=1
    print("Tamanho da lista de empreendimentos por conversão: "+str(dict(lengths)))
    print("Tipos de itens da lista: "+str(dict(member_types)))
    print("Relação com empreendimento_ultimo: "+str(dict(relation)))
    print("Apenas formatos, nomes de campos e contagens; nenhum dado individual.")
if __name__=="__main__":
    try:main()
    except (RuntimeError,ValueError) as e:
        print("Erro: "+str(e),file=sys.stderr);sys.exit(1)
