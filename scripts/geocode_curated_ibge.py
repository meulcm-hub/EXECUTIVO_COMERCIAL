#!/usr/bin/env python3
"""One-off geocoding of owner-provided project addresses, with no false positives.

Emits only review candidates, never approved geography or IBGE statistics.
Does not read customer data or credentials. One request per unique numbered address.
"""
import collections
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

from cvcrm_geocode_projects import geocode, norm

SOURCE=Path("config/ibge-project-addresses.json")
OUTPUT=Path("artifacts/ibge-geocode-curated-review.json")
def location_key(p):
    return tuple(norm(p.get(k,"")) for k in ("road","number","city","state"))
def qualified(p):
    return bool(all(p.get(k) for k in ("road","number","city","state")))
def analyze(projects,geocoder,sleep=time.sleep):
    lookup_cache={}
    counts=collections.Counter()
    duplicate_groups=collections.Counter(location_key(p) for p in projects if qualified(p))
    result=[]
    for p in projects:
        key=location_key(p)
        entry={"project":p["project"],"status":"pending_location_verification",
          "input_source":"provided_by_user","center":None,
          "adjacent_distinct_sites":bool(p.get("same_reference_address_adjacent_distinct_sites"))}
        if not qualified(p):
            entry["status"]="incomplete_address"
        else:
            if key not in lookup_cache:
                if lookup_cache:sleep(1.25)
                try:
                    found=geocoder(p)
                    lookup_cache[key]=found if isinstance(found,list) else []
                except (ValueError,urllib.error.HTTPError,urllib.error.URLError,TimeoutError,OSError):
                    lookup_cache[key]=None
            found=lookup_cache[key]
            if found is None:entry["status"]="geocoding_service_error"
            elif len(found)==1:
                geo=found[0]
                if all(isinstance(geo.get(k), (int,float)) for k in ("lat","lng")):
                    if duplicate_groups[key]>1 or entry["adjacent_distinct_sites"]:
                        entry["status"]="adjacent_distinct_site_requires_own_point"
                        # Reusing a postal reference is not a distinct parcel center.
                        entry["center"]=None
                    else:
                        entry["status"]="candidate_exact"
                        entry["center"]={"lat":geo["lat"],"lng":geo["lng"],
                          "precision":"address_number","source":"OpenStreetMap Nominatim",
                          "verified":False}
                else: entry["status"]="geocoder_invalid_response"
            elif len(found)>1:entry["status"]="ambiguous_candidates"
            else:entry["status"]="not_found_exact"
        counts[entry["status"]]+=1
        result.append(entry)
    return {"schema_version":1,"publication_status":"review_only",
      "dataset":"curated project addresses provided by LCM representative",
      "records":result},counts,len(lookup_cache)
def run():
    cfg=json.loads(SOURCE.read_text(encoding="utf-8"))
    projects=cfg["projects"]
    if len(projects)!=14 or len({norm(p["project"]) for p in projects})!=14:
        raise ValueError("Expected 14 unique projects")
    agent="LCM-IBGE/1.0 (https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL)"
    opener=urllib.request.build_opener(urllib.request.HTTPSHandler())
    output,counts,lookups=analyze(projects,lambda p:geocode(p,opener,agent))
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Empreendimentos cadastrais analisados:",len(projects))
    print("Endereços distintos consultados:",lookups)
    print("Resultados (sem endereços):",json.dumps(dict(counts),sort_keys=True))
    print("Somente candidatos não verificados. Dados setoriais não foram publicados.")
if __name__=="__main__":
    try:run()
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError):
        print("Falha de validação da fonte ou da consulta de mapas, sem endereço no log.",file=sys.stderr)
        sys.exit(1)
