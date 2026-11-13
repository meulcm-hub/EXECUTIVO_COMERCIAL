import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import cvcrm_price_summary as m

NOW=dt.date(2026,11,13)
def row(pid=10,tid=12,uid=101,value="250000.00",start="2026-11-01",end="2026-11-30",
        active="S",reference="2026-11-12 10:00:00"):
    return {"idempreendimento":pid,"empreendimento":"Projeto Teste","idtabela":tid,
            "tabela":"Tabela Novembro","idunidade":uid,"unidade":"001",
            "ativo":active,"data_vigencia_de":start,"data_vigencia_ate":end,
            "valor":value,"valor_avaliacao":"300000.00","referencia_data":reference}

class PriceSummaryTests(unittest.TestCase):
    def test_official_shape_current_and_value_not_appraisal(self):
        out=m.aggregate([row(),row(uid=102,value="350000.00")],NOW)["projects"][0]
        self.assertEqual(out["status"],"ok")
        self.assertEqual(out["priced_units"],2)
        self.assertEqual(out["minimum"],250000)
        self.assertEqual(out["maximum"],350000)
        self.assertEqual(out["median"],300000)
        self.assertEqual(out["reference_month"],"2026-11")
        self.assertEqual(out["price_field"],"valor")
        self.assertNotIn("unidades",str(out))

    def test_expired_future_inactive_and_undated_filtered(self):
        rows=[row(uid=1,end="2026-11-12"),row(uid=2,start="2026-11-14"),
              row(uid=3,active="N"),row(uid=4,start=""),row(uid=5)]
        out=m.aggregate(rows,NOW)["projects"][0]
        self.assertEqual(out["priced_units"],1)

    def test_newest_effective_table_wins(self):
        a=row(tid=1,uid=1,start="2026-10-01",end="2026-12-31",value="210000")
        b=row(tid=2,uid=1,start="2026-11-01",value="280000")
        self.assertEqual(m.aggregate([a,b],NOW)["projects"][0]["minimum"],280000)

    def test_duplicate_unit_latest_reference_wins(self):
        a=row(value="230000",reference="2026-11-10 09:00:00")
        b=row(value="260000",reference="2026-11-12 09:00:00")
        out=m.aggregate([a,b],NOW)["projects"][0]
        self.assertEqual(out["priced_units"],1)
        self.assertEqual(out["median"],260000)

    def test_same_start_distinct_tables_blocked(self):
        out=m.aggregate([row(tid=1),row(tid=2)],NOW)["projects"][0]
        self.assertEqual(out["status"],"ambiguous_current_tables")
        self.assertNotIn("minimum",out)

    def test_not_published_without_reference(self):
        self.assertEqual(m.aggregate([row(reference=None)],NOW)["projects"],[])

    def test_pagination_and_schema(self):
        payload={"pagina":1,"total_de_paginas":1,"dados":[row()]}
        self.assertEqual(m.unpack(payload)[1],1)
        self.assertEqual(len(m.collect(lambda p:m.unpack(payload),NOW)["projects"]),1)

if __name__=="__main__":unittest.main()
