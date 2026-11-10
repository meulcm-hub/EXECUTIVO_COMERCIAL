#!/usr/bin/env python3
"""Compara estrutura de datas dos endpoints CVDW leads e conversões.

O relatório mostra somente nomes de campos e contagens agregadas; IDs e
informações pessoais não são gravados nem impressos.
"""
import collections
import datetime as dt
import os
import sys
import time
import urllib.parse

from marketing_consolidate import cv_page, to_date
from cv_conversion_audit import get_page

def relevant_keys(rows):
    counts=collections.Counter()
    for row in rows:
        if not isinstance(row,dict):continue
        for k in row:
            key=k.casefold()
            if any(x in key for x in ("data","cad","referencia","conversao","empreend","origem","midia")):
                counts[k]+=1
    return counts

def main():
    base=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    url=urllib.parse.urlsplit(base)
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    if url.scheme!="https" or url.hostname!="lcm.cvcrm.com.br" or url.path not in ("","/") or url.query or url.fragment or not email or not token:
        raise RuntimeError("Credenciais CV não disponíveis")
    since=dt.date(2026,10,1)
    until=dt.date(2026,10,31)
    leads,_=cv_page(base,email,token,1,100,since,until)
    time.sleep(4)
    conversions,_=get_page(base,email,token,since.isoformat(),until.isoformat(),1)
    print("COMPARAÇÃO DE ESTRUTURAS — OUTUBRO 2026")
    print("Amostra de cadastros: "+str(len(leads)))
    print("Amostra de eventos: "+str(len(conversions)))
    for label,rows in (("LEADS",leads),("CONVERSÕES",conversions)):
        print("Endpoint "+label+":")
        for k,n in sorted(relevant_keys(rows).items()):
            print("  "+k+": presente em "+str(n)+" registros")
        dates=collections.Counter()
        for row in rows:
            if not isinstance(row,dict):continue
            first=to_date(row.get("data_cad"))
            ref=to_date(row.get("referencia_data"))
            if first and ref:
                dates["datas_iguais" if first==ref else "datas_distintas"]+=1
        print("Comparação de datas (mesmo registro): "+str(dict(dates)))
    print("Esta análise NÃO prova a data original do cadastro até validar a semântica dos campos.")
    print("Não foram publicados nem exibidos IDs, nomes, contatos ou valores de registros.")
if __name__=="__main__":
    try:main()
    except (RuntimeError,ValueError) as exc:
        print("Diagnóstico não concluído: "+str(exc),file=sys.stderr)
        sys.exit(1)
