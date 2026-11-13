import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import json
import math

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"ibge_build_spatial_context.py"
spec=importlib.util.spec_from_file_location("spatial",SCRIPT)
spatial=importlib.util.module_from_spec(spec);spec.loader.exec_module(spatial)

class SpatialCensus2022Tests(unittest.TestCase):
 def test_unverified_never_publishable(self):
  site=json.loads((ROOT/"config/ibge-project-addresses.json").read_text())["projects"]
  data=json.loads((ROOT/"config/ibge-project-centers-review.json").read_text())["points"]
  selected,unresolved=spatial.compute(site,{p["project"]:p for p in data},"publish")
  self.assertEqual(len(selected),0)
  self.assertEqual(len(unresolved),14)
 def test_review_only_with_existing_candidate_and_no_adjacent_leak(self):
  site=json.loads((ROOT/"config/ibge-project-addresses.json").read_text())["projects"]
  data=json.loads((ROOT/"config/ibge-project-centers-review.json").read_text())["points"]
  selected,_=spatial.compute(site,{p["project"]:p for p in data},"review")
  self.assertEqual({x["project"] for x,_ in selected},{"RESIDENCIAL MONTTEBELO","RESIDENCIAL TURQUESA PARQUE"})
 def test_point_requires_review_evidence(self):
  p={"source":"CV CRM","precision":"address_number","lat":-19.95,"lng":-44.17,"verified":True}
  self.assertFalse(spatial.valid_point(p))
  self.assertTrue(spatial.valid_point({**p,"verified_by":"LCM","verified_at":"2026-11-13",
          "verification_evidence":"confirmed onsite parcel mapping"}))
  self.assertFalse(spatial.valid_point({**p,"verified":False}))
  self.assertTrue(spatial.valid_point({**p,"verified":False},allow_review=True))
 def test_number_suppression(self):
  for v in (None,"-","X","...","nan","","-1","NaN"):
   self.assertIsNone(spatial.number(v),v)
  self.assertEqual(spatial.number("21"),21)
 def test_area_weighted_math(self):
  import geopandas as gpd
  from shapely.geometry import Polygon
  # Synthetic fixture for math-only tests, NOT official output.
  center={"lat":-19.0,"lng":-44.0}
  # Using lon/lat geography; one rectangle centered and one more distant.
  geom=[Polygon([(-44.007,-19.007),(-43.993,-19.007),(-43.993,-18.993),(-44.007,-18.993)]),
        Polygon([(-43.92,-19.007),(-43.90,-19.007),(-43.90,-18.993),(-43.92,-18.993)])]
  frame=gpd.GeoDataFrame({"CD_SETOR":["310000000000001","310000000000002"]},geometry=geom,crs="EPSG:4326")
  data={"310000000000001":(100,40),"310000000000002":(200,60)}
  result=spatial.calculate_on_frame(frame,center,data)
  self.assertTrue(0<result["1"]["population"]<=100)
  self.assertTrue(result["10"]["population"]>result["1"]["population"])
  self.assertEqual(result["10"]["method"],"sector_intersection_area_weighted")
 def test_missing_sector_not_counted_as_zero(self):
  import geopandas as gpd
  from shapely.geometry import Polygon
  c={"lat":-19.0,"lng":-44.0}
  a=Polygon([(-44.006,-19.006),(-44.000,-19.006),(-44.000,-19.000),(-44.006,-19.000)])
  b=Polygon([(-44.000,-19.000),(-43.994,-19.000),(-43.994,-18.994),(-44.000,-18.994)])
  frame=gpd.GeoDataFrame({"CD_SETOR":["A","B"]},geometry=[a,b],crs="EPSG:4326")
  result=spatial.calculate_on_frame(frame,c,{"A":(100,40)})
  self.assertEqual(result["1"]["status"],"incomplete_sector_coverage")
if __name__=="__main__":unittest.main()
