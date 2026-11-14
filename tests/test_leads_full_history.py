import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import leads_full_history as m

def row(uid,date,project="",origin="FB",reference="2026-11-13 08:00:00"):
    return {"idlead":uid,"data_cad":date,"empreendimento":project,
      "origem":origin,"situacao":"Novo Lead","referencia_data":reference,
      "nome":"Maria Carolina Oliveira Santos","telefone":"31999999999"}

class LeadsAllHistoryTests(unittest.TestCase):
    def test_pagination_deduplication_all_origins_missing_projects(self):
        pages={1:[row(1,"2014-05-12",origin="Indicação"),row(2,"2022-01-01",project="Village Lagoas")],
               2:[row(1,"2014-05-12",reference="2026-11-13 12:00:00"),
                  row(3,"2026-11-01",origin="Google")]}
        def fetch(page):return pages[page],2,{}
        out=m.collect(fetch,dt.date(2026,11,13))
        self.assertEqual(out["unique_leads"],3)
        self.assertEqual(out["snapshots_scanned"],4)
        self.assertEqual(out["earliest_cadastro"],"2014-05-12")
        self.assertEqual(out["pages_scanned"],2)
        self.assertEqual(sum(x["count"] for x in out["by_registration_project_origin_status"]),3)
        self.assertEqual(sum(x["count"] for x in out["by_registration_project_origin_status"] if x["project"]=="SEM EMPREENDIMENTO"),2)
        self.assertNotIn("Maria Carolina",str(out))
        self.assertNotIn("31999999999",str(out))
        self.assertNotIn('"idlead"',str(out))
    def test_midia_visita_is_independent_and_can_be_missing(self):
        with_visit=row(1,"2021-05-12",origin="Facebook")
        with_visit["midia_visita"]="Indicação corretor"
        with_visit["midia_original"]="WhatsApp Facebook"
        without_visit=row(2,"2021-05-13",origin="Google")
        without_visit["midia_original"]="Google Search"
        result=m.collect(lambda page:([with_visit,without_visit],1,{}))
        self.assertEqual(result["schema_version"],3)
        lookup={x["origin"]:x["visit_media"] for x in result["by_registration_project_origin_status"]}
        self.assertEqual(lookup["Facebook"],"Indicação corretor")
        self.assertEqual(lookup["Google"],"NÃO DISPONÍVEL NA API")
        medias={x["origin"]:x["lead_media"] for x in result["by_registration_project_origin_status"]}
        self.assertEqual(medias["Facebook"],"WhatsApp Facebook")
        self.assertEqual(medias["Google"],"Google Search")
        self.assertNotIn("WhatsApp Facebook",str(lookup))
        self.assertNotIn("Google Search",str(lookup))
    def test_origin_name_and_lead_media_use_cv_fields(self):
        lead=row(1,"2024-08-03",origin="FB")
        lead["origem_nome"]="Facebook"
        lead["midia_original"]="Whatsapp Facebook"
        lead["midia_ultimo"]="Outra mídia"
        result=m.collect(lambda page:([lead],1,{}))
        record=result["by_registration_project_origin_status"][0]
        self.assertEqual(record["origin"],"FB")
        self.assertEqual(record["origin_name"],"Facebook")
        self.assertEqual(record["lead_media"],"Whatsapp Facebook")
        self.assertEqual(record["visit_media"],"NÃO DISPONÍVEL NA API")
    def test_empty_visit_media_uses_nao_informada(self):
        self.assertEqual(m.visit_media({"midia_visita":""}),"NÃO INFORMADA")
        self.assertEqual(m.visit_media({"midia_original":"Instagram"}),"NÃO DISPONÍVEL NA API")
    def test_missing_id_or_original_date_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,"IDs/datas"):
            m.collect(lambda page:([row(1,"2026-01-01"),{"idlead":2,"referencia_data":"2026-11-01"}],1,{}))
    def test_incomplete_or_repeated_pagination_fails_closed(self):
        def fake(page):
            return [row(1,"2026-01-01")],2,{}
        with self.assertRaisesRegex(RuntimeError,"repetida"):
            m.collect(fake)
    def test_all_origins_not_marketing_limited(self):
        p=[row(1,"2026-01-01",origin="Google"),row(2,"2026-01-02",origin="Facebook"),
            row(3,"2026-01-03",origin="Indicação"),row(4,"2026-01-04",origin="GE")]
        out=m.collect(lambda page:(p,1,{}))
        origins={x["origin"] for x in out["by_registration_project_origin_status"]}
        self.assertEqual(origins,{"Google","Facebook","Indicação","GE"})
if __name__=="__main__":unittest.main()
