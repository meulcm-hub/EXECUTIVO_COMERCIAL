import sys
import unittest
import datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import cvcrm_price_summary as m

class PriceSummaryTests(unittest.TestCase):
    def setUp(self):
        m.NOW=dt.date(2026,11,13)

    def table(self,tid,price,start="2026-11-01",end="2026-11-30",approved="S"):
        return {"idtabela":tid,"aprovado":approved,
                "data_vigencia_de":start,"data_vigencia_ate":end,
                "unidades":[{"idunidade":tid,"valor_total":price}]}

    def test_only_current_month_approved(self):
        data=[self.table(1,210000,"2026-10-01","2026-10-31"),
              self.table(2,230000),self.table(3,100000,approved="N")]
        x=m.summarize(data)
        self.assertEqual(x["table_id"],"2")
        self.assertEqual(x["reference_month"],"2026-11")
        self.assertEqual(x["minimum"],230000)

    def test_latest_effective_start_wins(self):
        data=[self.table(1,210000,"2026-09-01","2026-12-31"),
              self.table(2,230000,"2026-11-10","2026-11-30")]
        self.assertEqual(m.summarize(data)["table_id"],"2")

    def test_not_yet_started_in_same_month(self):
        self.assertIsNone(m.summarize([self.table(2,230000,"2026-11-20","2026-11-30")]))

    def test_expired_earlier_this_month(self):
        self.assertIsNone(m.summarize([self.table(2,230000,"2026-11-01","2026-11-10")]))

    def test_ambiguous_same_start_date(self):
        data=[self.table(1,210000),self.table(2,230000)]
        self.assertEqual(m.summarize(data)["status"],"ambiguous_same_start_date")

    def test_missing_dates_not_assumed_valid(self):
        self.assertIsNone(m.summarize([{"idtabela":2,"aprovado":"S",
               "unidades":[{"idunidade":1,"valor_total":230000}]}]))

    def test_no_units_no_price(self):
        self.assertIsNone(m.summarize([{"idtabela":9,"aprovado":"S",
             "data_vigencia_de":"2026-11-01","data_vigencia_ate":"2026-11-30","unidades":[]}]))

    def test_project_listing_mock(self):
        items=[{"idempreendimento":10,"empreendimento":"Projeto TESTE"}]
        out=m.collect(lambda page:(items,1),lambda pid:[self.table(3,150000)])
        self.assertEqual(len(out["projects"]),1)
        self.assertEqual(out["projects"][0]["minimum"],150000)
        self.assertNotIn("unidades",str(out))

if __name__=="__main__":unittest.main()
