import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import cvcrm_price_summary as m

class PriceSummaryTests(unittest.TestCase):
    def test_only_valid_current_approved_unit_values(self):
        m.NOW=__import__("datetime").date(2026,11,13)
        rows=[{"idtabela":7,"aprovado":"S","data_vigencia_de":"2026-01-01",
           "unidades":[{"idunidade":1,"valor_total":220000},{"idunidade":2,"valor_total":280000},
                      {"idunidade":2,"valor_total":280000},{"idunidade":3,"valor_total":None}]},
              {"idtabela":8,"aprovado":"N","unidades":[{"idunidade":4,"valor_total":100000}]}]
        self.assertEqual(m.summarize(rows),{"status":"ok","table_id":"7","priced_units":2,
            "minimum":220000.0,"median":250000.0,"maximum":280000.0,"currency":"BRL"})
    def test_no_ambiguous_table_selection(self):
        rows=[{"idtabela":1,"aprovado":"S","unidades":[{"idunidade":1,"valor_total":210000}]},
              {"idtabela":2,"aprovado":"S","unidades":[{"idunidade":1,"valor_total":230000}]}]
        self.assertEqual(m.summarize(rows)["status"],"multiple_current_approved_tables")
    def test_no_units_no_price(self):
        self.assertIsNone(m.summarize([{"idtabela":9,"aprovado":"S","unidades":[]}]))
    def test_project_listing_mock(self):
        items=[{"idempreendimento":10,"empreendimento":"Projeto TESTE"}]
        out=m.collect(lambda page:(items,1),lambda pid:[{"idtabela":3,"aprovado":"S","unidades":[{"idunidade":1,"valor_total":150000}]}])
        self.assertEqual(len(out["projects"]),1)
        self.assertEqual(out["projects"][0]["minimum"],150000)
        self.assertNotIn("unidades",str(out))
if __name__=="__main__":unittest.main()
