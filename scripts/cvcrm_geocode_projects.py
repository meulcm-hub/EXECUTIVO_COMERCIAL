#!/usr/bin/env python3
"""One-time, privacy-conscious project address geocoding from CV CRM.

Only project records are processed. No buyer, reserve or lead data.
No raw addresses/credentials or geocoder responses are emitted to logs/artifacts.
One request at a time, 1.25-second minimum spacing; no scheduled execution.
"""
import collections
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

from cvcrm_project_address_audit import credentials, get_page, norm, PAGE_SIZE, MAX_PAGES, NoRedirect

OUT=Path("artifacts/cvcrm-project-geocoding-review.json")
GEOCODE="https://nominatim.openstreetmap.org/search"
UF_NAMES={"AC":"Acre","AL":"Alagoas","AP":"Amapá","AM":"Amazonas","BA":"Bahia","CE":"Ceará","DF":"Distrito Federal","ES":"Espírito Santo","GO":"Goiás","MA":"Maranhão","MT":"Mato Grosso","MS":"Mato Grosso do Sul","MG":"Minas Gerais","PA":"Pará","PB":"Paraíba","PR":"Paraná","PE":"Pernambuco","PI":"Piauí","RJ":"Rio de Janeiro","RN":"Rio Grande do Norte","RS":"Rio Grande do Sul","RO":"Rondônia","RR":"Roraima","SC":"Santa Catarina","SP":"São Paulo","SE":"Sergipe","TO":"Tocantins"}
ADDRESS_KEYS=("enderecoempreendimento","enderecodoempreendimento","endereco","address","localizacaoempreendimento")
FIELD_ALIASES={
  "road":("logradouro","endereco","rua","street"),
  "number":("numero","endereconumero","numerologradouro","number","endereco_numero"),
  "city":("cidade","municipio","city"),
  "state":("uf","estado","siglaestado","state"),
  "postcode":("cep","zipcode","postalcode"),
  "project":("nomeempreendimento","empreendimento","nome","name"),
  "identifier":("idempreendimento","empreendimentoid","id"),
}
def field(record,names):
    canonical={norm(k):v for k,v in record.items()}
    for name in names:
        value=canonical.get(norm(name))
        if isinstance(value,(str,int,float)) and not isinstance(value,bool) and str(value).strip():
            return str(value).strip()
    return ""
def project_address(row):
    """Project-only context. Ignore nested units, clients and reservations."""
    if not isinstance(row,dict):return None
    addr=next((v for k,v in row.items() if norm(k) in ADDRESS_KEYS and isinstance(v,dict)),{})
    # Nested explicit project address first; other fields from root.
    parts={}
    for key in ("road","number","city","state","postcode"):
        parts[key]=field(addr,FIELD_ALIASES[key]) or field(row,FIELD_ALIASES[key])
    parts["project"]=field(row,FIELD_ALIASES["project"])
    parts["identifier"]=field(row,FIELD_ALIASES["identifier"])
    if not parts["project"] or not (parts["road"] and parts["number"] and parts["city"] and parts["state"]):
        return {"project":parts["project"],"identifier":parts["identifier"],"status":"incomplete"}
    # Safety: address text is only kept in memory, not the output.
    if not re.fullmatch(r"[0-9A-Za-z/-]{1,20}",parts["number"]):
        return {"project":parts["project"],"identifier":parts["identifier"],"status":"unverified_number"}
    return {**parts,"status":"ready"}

def norm_number(value):
    return re.sub(r"[^a-z0-9]","",norm(value))
def matched_number(address,number):
    candidates=[address.get("house_number"),address.get("house_number:ref")]
    return any(norm_number(x)==norm_number(number) for x in candidates if x)
def verified(item,p):
    """No centroid, road-only, CEP-only or district result can be accepted."""
    if not isinstance(item,dict) or item.get("type") in ("administrative","city","town","village"):
        return False
    adr=item.get("address",{})
    if not isinstance(adr,dict) or not matched_number(adr,p["number"]):return False
    road=adr.get("road") or adr.get("pedestrian") or adr.get("residential") or ""
    if not road or not norm(p["road"]) in norm(road) and norm(road) not in norm(p["road"]):return False
    loc=adr.get("city") or adr.get("town") or adr.get("municipality") or adr.get("village") or ""
    if not loc or norm(loc)!=norm(p["city"]):return False
    state=adr.get("state_code") or adr.get("ISO3166-2-lvl4") or adr.get("state") or ""
    uf=p["state"].upper()
    if len(uf)==2:
        if not (norm(state)==norm(uf) or norm(state)==norm(UF_NAMES.get(uf,"")) or str(state).upper().endswith("-"+uf)):
            return False
    try:lat,lng=float(item["lat"]),float(item["lon"])
    except (ValueError,TypeError,KeyError):return False
    return -34<=lat<=6 and -74<=lng<=-32
def geocode(p,opener,agent):
    query={
      "street":p["number"]+" "+p["road"],
      "city":p["city"],
      "state":UF_NAMES.get(p["state"].upper(),p["state"]),
      "country":"Brazil",
      "format":"jsonv2","addressdetails":"1","limit":"5"
    }
    url=GEOCODE+"?"+urllib.parse.urlencode(query)
    req=urllib.request.Request(url,headers={"User-Agent":agent,"Accept":"application/json"})
    with opener.open(req,timeout=25) as resp:
        if resp.status!=200:raise ValueError("geocoder failed")
        raw=resp.read(256001)
        if len(raw)>256000:raise ValueError("oversized geocoding reply")
    candidates=json.loads(raw)
    return [{"lat":float(x["lat"]),"lng":float(x["lon"])} for x in candidates if verified(x,p)]
def collect_projects(opener,base,email,token):
    rows=[];seen=set()
    for page in range(1,MAX_PAGES+1):
        items,pages=get_page(opener,base,email,token,page)
        if not items:break
        for item in items:
            p=project_address(item)
            if p is None:continue
            key=p["identifier"] or norm(p["project"])
            if key in seen:continue
            seen.add(key);rows.append(p)
        if (pages is not None and page>=pages) or (pages is None and len(items)<PAGE_SIZE):break
    return rows
def run(environ=None,fetch=None,lookup=None,sleep=None):
    environ=os.environ if environ is None else environ
    base,email,token=credentials(environ)
    agent=environ.get("LCM_GEOCODER_USER_AGENT","").strip()
    if not agent or "https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL" not in agent:
        raise ValueError("Identify application and contact in LCM_GEOCODER_USER_AGENT")
    opener=urllib.request.build_opener(NoRedirect())
    records=(fetch or (lambda:collect_projects(opener,base,email,token)))()
    if not 1<=len(records)<=60:raise ValueError("Unexpected project universe")
    lookup=lookup or (lambda p:geocode(p,opener,agent))
    sleep=sleep or time.sleep
    counts=collections.Counter()
    output=[]
    last=0.
    for p in records:
        name=p.get("project","")
        if not name:counts["missing_project_name"]+=1;continue
        entry={"project":name,"status":p["status"]}
        if p["status"]=="ready":
            # One-time bulk: sequential and strictly below 1 req/s.
            if last:sleep(1.25)
            last=time.monotonic() or 1.0
            try:
                results=lookup(p)
                if len(results)==1:
                    entry.update({"status":"candidate_exact","center":{"lat":results[0]["lat"],"lng":results[0]["lng"],"source":"OSM Nominatim","precision":"address_number","verified":False}})
                else:entry["status"]="ambiguous" if results else "not_found_exact"
            except (ValueError,urllib.error.HTTPError,urllib.error.URLError,TimeoutError,OSError):
                entry["status"]="geocoder_failed"
        counts[entry["status"]]+=1
        output.append(entry)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"schema_version":1,"publication_status":"review_only",
      "source":"CV CRM project register","geocoding_source":"OpenStreetMap Nominatim (ODbL)",
      "records":output},ensure_ascii=False,indent=2),encoding="utf-8")
    print("Empreendimentos verificados no cadastro:",len(records))
    print("Resumo do geocoding (sem endereços):",json.dumps(dict(counts),sort_keys=True))
    print("Coordenadas são candidatos, não verificadas para publicação. Artefato privado para revisão.")
    return counts
if __name__=="__main__":
    try:run()
    except (ValueError,TypeError,urllib.error.HTTPError,urllib.error.URLError,OSError,TimeoutError):
        print("Falha de configuração/consulta; nenhum endereço foi divulgado.",file=sys.stderr);sys.exit(1)
