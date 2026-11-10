#!/usr/bin/env python3
"""Diagnóstico do esquema CVDW conversões, sem expor valores individuais."""
import collections
import os
import sys
import urllib.parse
from cv_conversion_audit import get_page, to_date

def main():
    base=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    host=urllib.parse.urlsplit(base)
    if host.scheme!="https" or host.hostname!="lcm.cvcrm.com.br" or host.path not in ("","/") or not email or not token:
        raise RuntimeError("Configuração CV indisponível")
    rows,_=get_page(base,email,token,"2026-10-01","2026-10-31",1)
    counts=collections.Counter()
    values=collections.Counter()
    for row in rows:
        if not isinstance(row,dict):continue
        counts.update(row.keys())
        registered=to_date(row.get("data_cad"))
        reference=to_date(row.get("referencia_data"))
        if registered and reference:
            values["ambas_datas"]+=1
            values["datas_iguais" if registered==reference else "datas_diferentes"]+=1
        if row.get("idlead") is not None:values["idlead_presente"]+=1
        if row.get("idlead_conversao") is not None:values["id_conversao_presente"]+=1
    print("Esquema do endpoint CVDW /leads/conversoes; outubro de 2026")
    print("Amostra de eventos: "+str(len(rows)))
    keys=sorted(k for k in counts if any(x in k.casefold() for x in
        ("data","cad","referencia","conversao","origem","midia","empreend")))
    print("Campos relacionados a datas/origens (somente chaves):")
    for key in keys:print("  "+key+": presente em "+str(counts[key])+" linhas")
    for name in sorted(values):print("Resumo "+name+": "+str(values[name]))
    print("Nenhuma informação pessoal ou identificador individual impresso.")
if __name__=="__main__":
    try:main()
    except (RuntimeError,ValueError) as ex:
        print("Diagnóstico não concluído: "+str(ex),file=sys.stderr)
        sys.exit(1)
