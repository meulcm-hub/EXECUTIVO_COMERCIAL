#!/usr/bin/env python3
"""Extrai rendimento mensal médio do RESPONSÁVEL com rendimento, Censo 2022.
Não representa renda familiar/domiciliar total. Fonte IBGE, revisão 08/05/2026.
"""
import csv
import io
import json
from pathlib import Path
from urllib.request import urlopen, Request
from zipfile import ZipFile

URL=("https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/"
"Agregados_por_Setores_Censitarios_Rendimento_do_Responsavel/"
"Agregados_por_municipios_renda_responsavel_BR_20260508_csv.zip")
OUT=Path("data/ibge-municipal-responsible-income.json")

def build(raw):
    with ZipFile(io.BytesIO(raw)) as archive:
        names=[n for n in archive.namelist() if n.lower().endswith(".csv")]
        if len(names)!=1:
            raise ValueError("Esperado CSV único no ZIP oficial")
        data=archive.read(names[0])
    rows=None
    for encoding in ("utf-8-sig","latin-1"):
        try:
            text=data.decode(encoding)
            rows=list(csv.DictReader(io.StringIO(text),delimiter=";"))
            if rows and "CD_MUN" in rows[0] and "V06004" in rows[0]:
                break
        except UnicodeDecodeError:
            pass
    if not rows or "V06004" not in rows[0]:
        raise ValueError("Esquema IBGE mudou: falta CD_MUN ou V06004")
    result={}
    for row in rows:
        code=str(row["CD_MUN"]).strip()
        value=str(row["V06004"]).strip().replace(",",".")
        try:
            amount=float(value)
        except ValueError:
            continue
        if len(code)==7 and 0<=amount<1_000_000:
            result[code]=round(amount,2)
    if len(result)<5000:
        raise ValueError("Cobertura municipal insuficiente: "+str(len(result)))
    return {"schema_version":1,"year":2022,"source":"IBGE Censo 2022",
       "source_url":URL,"revision":"2026-05-08","variable":"V06004",
       "indicator":"Rendimento nominal médio mensal das pessoas responsáveis pelo domicílio com rendimento",
       "not_household_income":True,"municipalities":result}

def main():
    req=Request(URL,headers={"User-Agent":"LCM-IBGE/1.0 (https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL)"})
    with urlopen(req,timeout=180) as response:
        raw=response.read(6_000_001)
    if len(raw)>6_000_000:
        raise ValueError("ZIP ultrapassou tamanho esperado")
    obj=build(raw)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(obj,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print("Indicador oficial publicado:",len(obj["municipalities"]),"municípios")
if __name__=="__main__":
    main()
