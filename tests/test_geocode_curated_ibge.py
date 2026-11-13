import importlib.util
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import geocode_curated_ibge as geo

class CuratedIBGEGeocodeTests(unittest.TestCase):
    def test_user_address_table_is_complete_and_has_duplicates_flagged(self):
        import json
        cfg=json.loads(geo.SOURCE.read_text(encoding="utf-8"))
        projects=cfg["projects"]
        self.assertEqual(len(projects),14)
        self.assertEqual(len({geo.norm(x["project"]) for x in projects}),14)
        self.assertEqual(sum(bool(x.get("number")) for x in projects),9)
        seen=[x for x in projects if x["project"] in ("Residencial FLAMBOYANT","RESIDENCIAL JATOBÁ")]
        self.assertEqual(geo.location_key(seen[0]),geo.location_key(seen[1]))
    def test_deduplicate_and_no_approval(self):
        a={"project":"A","road":"Rua X","number":"60","city":"Goiânia","state":"GO"}
        b={"project":"B",**{k:v for k,v in a.items() if k!="project"}}
        c={"project":"C","road":"Rua Y","number":"","city":"Porto Seguro","state":"BA"}
        calls=[]
        def lookup(p):
            calls.append(p["project"]);return [{"lat":-16.5,"lng":-49.2}]
        output,counts,lookups=geo.analyze([a,b,c],lookup,sleep=lambda n:None)
        self.assertEqual(calls,["A"])
        self.assertEqual(lookups,1)
        self.assertEqual(counts["candidate_exact_shared_address"],2)
        self.assertEqual(counts["incomplete_address"],1)
        self.assertTrue(all(r["center"] is None or r["center"]["verified"] is False for r in output["records"]))
        self.assertNotIn("Rua X",str(output))
    def test_service_failure_not_fake_coordinates(self):
        p={"project":"P","road":"Rua X","number":"60","city":"Goiânia","state":"GO"}
        def fail(_):raise ValueError("unavailable")
        output,counts,_=geo.analyze([p],fail)
        self.assertEqual(counts["geocoding_service_error"],1)
        self.assertIsNone(output["records"][0]["center"])

if __name__=="__main__":unittest.main()
