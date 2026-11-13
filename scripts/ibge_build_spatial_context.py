#!/usr/bin/env python3
"""IBGE 2022 spatial integration, strictly gated by approved project coordinates.

Official sources:
 - IBGE Census 2022 Basic sector CSV revised 20 May 2026 (v0001 people,
   v0007 occupied private households); geographic sector boundaries by UF.
 - Area-weighted intersection of sector geometries with true circular buffers.
 - No market potential or income inferred from aggregate population.

Requires geopandas >=1.0, shapely >=2.0, pyproj >=3.6.
Default run produces ONLY JSON with project statuses. No data fabrications.
Use --review to compute preview candidates; preview stays in artifacts/ and
NEVER generates publishable context. Use --publish ONLY for verified=true
centers with review evidence and approved site-specific coordinates.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import math
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen
from zipfile import ZipFile

BASE="https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/"
BASIC=BASE+"Agregados_por_setores_basico_BR_20260520.zip"
SHAPE="https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/setores/shp/UF/{uf}_setores_CD2022.zip"
UF_CODES={"MG":"31","BA":"29","GO":"52"}
RADII=(1,3,5,10)
RADII_DIST={str(x):x for x in RADII}
DATA=Path("config/ibge-project-addresses.json")
POINTS=Path("config/ibge-project-centers-review.json")
CACHE=Path("/tmp/lcm_ibge_official")
PUBLISH=Path("data/ibge-project-context.json")
MAP_DIR=Path("data/ibge-sectors")
ARTIFACT=Path("artifacts/ibge-sector-preview.json")
RESULT=Path("artifacts/ibge-spatial-status.json")

def valid_point(center,allow_review=False):
    if not isinstance(center,dict):return False
    if not (center.get("source")=="CV CRM" and center.get("precision")=="address_number"):return False
    lat,lng=center.get("lat"),center.get("lng")
    if not (isinstance(lat,(int,float)) and isinstance(lng,(int,float)) and not isinstance(lat,bool) and not isinstance(lng,bool)):return False
    if not (-34<=lat<=6 and -74<=lng<=-32):return False
    if center.get("verified") is True:
        return bool(center.get("verified_by") and center.get("verified_at") and center.get("verification_evidence"))
    return allow_review and center.get("verified") is False

def number(value):
    if value is None:return None
    text=str(value).strip()
    if not text or text.lower() in {"-","x","...","nan","null"}:return None
    try:
        n=float(text.replace(",","."))
        return n if math.isfinite(n) and n>=0 else None
    except ValueError:return None

def download(url,path,max_bytes=230_000_000):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file() and path.stat().st_size>10000:return path
    req=Request(url,headers={"User-Agent":"LCM-IBGE-Spatial/1.0 (https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL)"})
    total=0
    with urlopen(req,timeout=180) as res, path.open("wb") as fh:
        while True:
            chunk=res.read(1024*1024)
            if not chunk:break
            total+=len(chunk)
            if total>max_bytes:raise ValueError("Arquivo oficial excede limite de segurança")
            fh.write(chunk)
    if not ZipFile(path).testzip() is None:raise ValueError("Arquivo IBGE corrompido")
    return path

def load_basic_by_uf(zip_path,uf):
    """Load only selected UF into memory; sector identifier stays string to preserve leading zeroes."""
    result={}
    with ZipFile(zip_path) as z:
        candidates=[n for n in z.namelist() if n.endswith(".csv") and "basico" in n.lower()]
        if len(candidates)!=1:raise ValueError("Arquivo básico sem CSV único e reconhecido")
        with z.open(candidates[0]) as raw, io.TextIOWrapper(raw,encoding="latin-1",newline="") as reader:
            rows=csv.DictReader(reader,delimiter=";")
            required={"CD_SETOR","CD_UF","v0001","v0007"}
            if not required<=set(rows.fieldnames or []):raise ValueError("Variáveis de população/domicílios alteradas no IBGE")
            for row in rows:
                if str(row.get("CD_UF","")).zfill(2)!=UF_CODES[uf]:continue
                key=str(row["CD_SETOR"]).strip()
                pop=number(row["v0001"])
                homes=number(row["v0007"])
                if len(key)>=12 and pop is not None and homes is not None:
                    result[key]=(pop,homes)
    if not result:raise ValueError("Nenhum setor com população e domicílios na UF "+uf)
    return result

def find_shapes(zip_path):
    dest=CACHE/("shapes_"+zip_path.stem)
    dest.mkdir(parents=True,exist_ok=True)
    with ZipFile(zip_path) as z:
        members=[m for m in z.namelist() if Path(m).suffix.lower() in {".shp",".shx",".dbf",".prj",".cpg"}]
        if not any(m.lower().endswith(".shp") for m in members):raise ValueError("ZIP geográfico não contém shapefile")
        for member in members:
            filename=Path(member).name
            if not filename:continue
            target=dest/filename
            if not target.exists():
                with z.open(member) as src, target.open("wb") as dst:
                    while chunk:=src.read(1024*1024):dst.write(chunk)
    shapes=list(dest.glob("*.shp"))
    if len(shapes)!=1:raise ValueError("Esperado shapefile único")
    return shapes[0]

def sector_radius_frame(gdf,center,km):
    """Calculate area fractions locally using an azimuthal equidistant metric projection.
    The radius circle is exact in meters; area weighting assumes uniform distribution
    of population within each sector and is labeled an estimate, not observed residents.
    """
    from pyproj import CRS
    from shapely.geometry import Point
    projection=CRS.from_proj4(f"+proj=aeqd +lat_0={center['lat']} +lon_0={center['lng']} +datum=WGS84 +units=m +no_defs")
    localized=gdf.to_crs(projection)
    point=Point(0,0)
    circle=point.buffer(km*1000,resolution=64)
    intersections=localized.geometry.intersection(circle)
    areas=localized.geometry.area
    shares=(intersections.area/areas.replace(0,float("nan"))).fillna(0).clip(lower=0,upper=1)
    return shares,intersections

def calculate_on_frame(gdf,center,counts):
    """Shared math for production and synthetic tests; never uses fabricated production values."""
    if gdf.crs is None:raise ValueError("Setores sem CRS oficial")
    if "CD_SETOR" not in gdf.columns:raise ValueError("Shapefile sem CD_SETOR")
    unique=gdf["CD_SETOR"].astype(str)
    if unique.duplicated().any():raise ValueError("Malha contém setores duplicados")
    available=[str(k) in counts for k in unique]
    import numpy as np
    pop=np.array([counts.get(str(code),(0,0))[0] for code in unique],dtype=float)
    homes=np.array([counts.get(str(code),(0,0))[1] for code in unique],dtype=float)
    output={}
    for km in RADII:
        shares,intersections=sector_radius_frame(gdf,center,km)
        active=shares.to_numpy()>0
        covered=np.logical_and(active,np.array(available))
        if covered.sum()==0:
            output[str(km)]={"status":"no_matching_sector_data"}
            continue
        if active.sum()>covered.sum():
            # Partial coverage cannot silently count missing sectors as zero.
            output[str(km)]={"status":"incomplete_sector_coverage","matched_sectors":int(covered.sum()),"total_sectors":int(active.sum())}
            continue
        p=float((pop*shares.to_numpy()).sum())
        d=float((homes*shares.to_numpy()).sum())
        output[str(km)]={"year":2022,"method":"sector_intersection_area_weighted",
            "population":round(p),"households":round(d),
            "populationDensity":round(p/(math.pi*km*km),1),
            "matched_sectors":int(covered.sum()),"areaKm2":round(math.pi*km*km,3),
            "uncertainty":"Estimativa de área, hipótese de população uniforme dentro de cada setor"}
    return output

def subset_for_center(shp,center):
    import geopandas as gpd
    lat,lng=center["lat"],center["lng"]
    bbox=(lng-0.15,lat-0.15,lng+0.15,lat+0.15)
    frame=gpd.read_file(shp,bbox=bbox,engine="pyogrio")
    if frame.empty:raise ValueError("Nenhum setor da malha cobre a proximidade do ponto")
    if frame.crs is None:raise ValueError("Malha sem definição CRS")
    if "CD_SETOR" not in frame.columns:raise ValueError("Malha sem código censitário")
    return frame

def make_features(frame,center,counts,km):
    from shapely.geometry import mapping
    from pyproj import CRS
    shares,intersections=sector_radius_frame(frame,center,km)
    crs=CRS.from_proj4(f"+proj=aeqd +lat_0={center['lat']} +lon_0={center['lng']} +datum=WGS84 +units=m +no_defs")
    areas_km2=frame.to_crs(crs).geometry.area/1000000
    records=[]
    for i,share in enumerate(shares):
        if share<=0:continue
        code=str(frame.iloc[i]["CD_SETOR"])
        if code not in counts:continue
        p,h=counts[code]
        poly=frame.iloc[[i]].to_crs("EPSG:4326").geometry.iloc[0]
        sector_area=max(float(areas_km2.iloc[i]),0.0001)
        density=p/sector_area
        records.append({"type":"Feature","properties":{
            "ibge_sector_code":code,"population":int(p),"households":int(h),
            "population_density_km2":round(density,1),
            "area_intersection_fraction":round(float(share),4),
            "estimated_people_in_radius":round(p*float(share),1)
          },"geometry":mapping(poly.simplify(0.00003,preserve_topology=True))})
    return records

def compute(addresses,candidates,mode):
    approved=[]
    unresolved=[]
    for site in addresses:
        rec=candidates.get(site["project"],{})
        c=rec.get("center")
        if not valid_point(c,allow_review=(mode=="review")):
            unresolved.append({"project":site["project"],"reason":"coordinate_not_verified"})
            continue
        if site.get("same_reference_address_adjacent_distinct_sites") and c.get("verified") is not True:
            unresolved.append({"project":site["project"],"reason":"adjacent_distinct_site_without_own_verified_center"})
            continue
        approved.append((site,c))
    return approved,unresolved

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--review",action="store_true",help="Only unpublished previews of candidate points")
    parser.add_argument("--publish",action="store_true",help="Write publication data, only verified locations")
    opt=parser.parse_args()
    if opt.review==opt.publish:parser.error("Choose exactly --review or --publish")
    mode="review" if opt.review else "publish"
    source=json.loads(DATA.read_text(encoding="utf-8"))
    raw=json.loads(POINTS.read_text(encoding="utf-8"))
    sites=source["projects"]
    if len(sites)!=14:raise ValueError("Unexpected project count")
    points={p["project"]:p for p in raw["points"]}
    selected,unresolved=compute(sites,points,mode)
    RESULT.parent.mkdir(parents=True,exist_ok=True)
    status={"schema_version":1,"mode":mode,"projects_total":len(sites),
            "processable":len(selected),"unresolved":unresolved,"source_year":2022}
    print("VALIDAÇÃO:",json.dumps({"mode":mode,"processable":len(selected),"unresolved":len(unresolved)}))
    if not selected:
        RESULT.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")
        if mode=="publish":print("BLOQUEADO: nenhum centro individual validado. Sem dados falsos.",file=sys.stderr)
        return
    import geopandas
    basic=download(BASIC,CACHE/"setores_basico_20260520.zip",30_000_000)
    by_uf={}
    by_counts={}
    for site,c in selected:
        uf=site["state"]
        if uf not in UF_CODES:raise ValueError("UF não habilitada")
        if uf not in by_uf:
            z=download(SHAPE.format(uf=uf),CACHE/(uf+"_setores_CD2022.zip"))
            by_uf[uf]=find_shapes(z)
            by_counts[uf]=load_basic_by_uf(basic,uf)
    results=[]
    for site,c in selected:
        uf=site["state"];frame=subset_for_center(by_uf[uf],c)
        values=calculate_on_frame(frame,c,by_counts[uf])
        # Never mark review candidates verified or let them reach the main data directory.
        outcenter={k:v for k,v in c.items() if k in {
            "lat","lng","verified","precision","source","verified_by","verified_at","verification_evidence"}}
        result={"project":site["project"],"center":outcenter,"radii":values}
        results.append(result)
        print("PROCESSADO",site["project"],"SETORES",len(frame),"RAIOS",",".join(values))
        if mode=="publish":
            from shapely.geometry import mapping
            for km in RADII:
                if values[str(km)].get("year")!=2022:continue
                slug=re.sub(r"[^a-z0-9]+","-",site["project"].lower().encode("ascii","ignore").decode()).strip("-")
                file=MAP_DIR/(slug+"-"+str(km)+"km.geojson")
                fc={"type":"FeatureCollection","metadata":{
                    "source":"IBGE","year":2022,"project":site["project"],"radius_km":km,
                    "method":"sector_intersection_area_weighted","population_column":"v0001",
                    "households_column":"v0007","basic_revision":"2026-05-20"},
                    "features":make_features(frame,c,by_counts[uf],km)}
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text(json.dumps(fc,ensure_ascii=False),encoding="utf-8")
                values[str(km)]["geojson"]=str(file)
    if mode=="review":
        ARTIFACT.write_text(json.dumps({"schema_version":1,"review_only":True,"projects":results},
            ensure_ascii=False,indent=2),encoding="utf-8")
        print("REVISÃO APENAS: candidatos não publicados; população estimada depende de centro verificado.")
    else:
        PUBLISH.parent.mkdir(parents=True,exist_ok=True)
        PUBLISH.write_text(json.dumps({"schema_version":1,"projects":results,
            "sources":{"basic":BASIC,"shapes":SHAPE,"year":2022,"method":"area_weighted",
               "population":"v0001","households":"v0007"}},ensure_ascii=False,indent=2),encoding="utf-8")
        print("CONTEXTO GEOGRÁFICO PUBLICÁVEL GERADO PARA CENTROS APROVADOS.")
    status["processed_projects"]=[p["project"] for p in results]
    RESULT.write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":
    main()
