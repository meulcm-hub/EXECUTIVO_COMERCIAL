#!/usr/bin/env python3
"""Introspect official IBGE 2022 sector archives without ever outputting row values."""
import csv
import io
import json
import os
import sys
from urllib.request import Request, urlopen
from zipfile import ZipFile
from pathlib import Path
ROOT="https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/"
URLS={
 "basico":ROOT+"Agregados_por_setores_basico_BR_20260520.zip",
 "domicilios":ROOT+"Agregados_por_setores_caracteristicas_domicilio1_BR_20261021.zip"
}
def scan(name,url):
 path=Path("/tmp/ibge_"+name+".zip")
 if not path.exists():
  req=Request(url,headers={"User-Agent":"LCM-IBGE-Data-Validation/1.0"})
  with urlopen(req,timeout=120) as resp, path.open("wb") as f:
   while True:
    chunk=resp.read(1048576)
    if not chunk:break
    f.write(chunk)
 with ZipFile(path) as z:
  info=[]
  for item in z.infolist():
   if item.is_dir() or not item.filename.lower().endswith(".csv"):continue
   with z.open(item) as raw:
    sample=raw.read(8192)
   data=sample.decode("utf-8-sig",errors="replace")
   reader=csv.reader(io.StringIO(data),delimiter=";")
   header=next(reader,[])
   info.append({"filename":item.filename,"size":item.file_size,"columns":header})
  return info
if __name__=="__main__":
 data={name:scan(name,url) for name,url in URLS.items()}
 Path("artifacts").mkdir(exist_ok=True)
 Path("artifacts/ibge-sector-schema.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
 for name,items in data.items():
  print("ARQUIVO",name,"N",len(items))
  for item in items:print("ESQUEMA",item["filename"],"COLUNAS",",".join(item["columns"][:60]))
