import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import leads_commercial_dimensions as api
import leads_full_history as full

class CommercialLeadTests(unittest.TestCase):
    def test_limit_offset_and_lead_fields(self):
        items=[
          {"idlead":1,"origem":"Facebook","midia_principal":"Facebook Ads",
           "nome":"Maria das Neves","telefone":"79999999999"},
          {"idlead":2,"origem":"Painel Gestor","midias":["WhatsApp Facebook","Feirão"]},
          {"idlead":3,"origem":"Google","midias":[]},
        ]
        offsets=[]
        def fetch(offset):
            offsets.append(offset)
            return {"total":3,"limit":2,"offset":offset,"leads":items[offset:offset+2]}
        result,meta=api.collect(fetch)
        self.assertEqual(offsets,[0,2])
        self.assertEqual(meta["commercial_total"],3)
        self.assertEqual(meta["commercial_unique"],3)
        self.assertEqual(result["1"],{"origin_name":"Facebook","lead_media":"Facebook Ads",
          "lead_medias":["Facebook Ads"]})
        self.assertEqual(result["2"],{"origin_name":"Painel Gestor","lead_media":"WhatsApp Facebook",
          "lead_medias":["WhatsApp Facebook","Feirão"]})
        self.assertEqual(result["3"]["lead_media"],"NÃO INFORMADA")
        self.assertEqual(result["3"]["lead_medias"],["NÃO INFORMADA"])
        self.assertNotIn("Maria das Neves",str(result))
        self.assertNotIn("79999999999",str(result))

    def test_commercial_page_missing_or_repeated_fails(self):
        with self.assertRaisesRegex(RuntimeError,"vazia"):
            api.collect(lambda offset:{"total":10,"leads":[]})
        with self.assertRaisesRegex(RuntimeError,"mudou"):
            api.collect(lambda offset:{"total":2 if offset==0 else 3,
               "leads":[{"idlead":offset+1}]})

    def test_commercial_overrides_cvdw_descriptive_fields_without_losing_ids(self):
        row={"idlead":1,"data_cad":"2018-11-27","empreendimento":"Green Plaza",
          "origem":"FB","situacao":"Novo Lead","referencia_data":"2026-11-14 10:00:00"}
        other={"idlead":2,"data_cad":"2019-02-01","empreendimento":None,
          "origem":"GE","situacao":"Descartado","referencia_data":"2026-11-14 10:00:00"}
        report=full.collect(lambda page:([row,other],1,{}),dt.date(2026,11,14),
          commercial={"1":{"origin_name":"Facebook","lead_media":"Facebook Ads",
                  "lead_medias":["Facebook Ads","WhatsApp Facebook"]}},
          commercial_meta={"commercial_total":1,"commercial_pages":1,"commercial_unique":1})
        self.assertEqual(report["unique_leads"],2)
        self.assertEqual(report["commercial_matched"],1)
        cells=report["by_registration_project_origin_status"]
        facebook=next(x for x in cells if x["origin"]=="FB")
        self.assertEqual(facebook["origin_name"],"Facebook")
        self.assertEqual(facebook["lead_media"],"Facebook Ads")
        self.assertEqual(facebook["lead_medias"],["Facebook Ads","WhatsApp Facebook"])
        self.assertTrue(any(x["project"]=="SEM EMPREENDIMENTO" for x in cells))
        self.assertNotIn("idlead",str(cells))

if __name__=="__main__":unittest.main()
