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
class CvdwStableDimensions(unittest.TestCase):
    def test_main_starts_lead_pagination_after_operational_collection(self):
        from unittest.mock import patch
        import leads_operational_history as ops
        calls=[]
        sample=([{"nome":"Maria Silva","corretor":"Ana Lima","origem_nome":"Facebook"}],1,{"total_de_registros":1})
        def operations(*args,end_reference):
            calls.append(("operations",end_reference))
            return {},{}
        def page(opener,base,email,token,number,end_reference):
            calls.append(("page",end_reference))
            self.assertEqual(number,1)
            return sample
        def collect(fetch,**kwargs):
            self.assertEqual(fetch(1),sample)
            raise RuntimeError("stop before publication")
        with patch.object(m,"credentials",return_value=("base","email","token")), patch.object(ops,"fetch_all",side_effect=operations), patch.object(m,"fetch_page",side_effect=page), patch.object(m,"collect",side_effect=collect):
            with self.assertRaisesRegex(RuntimeError,"stop before publication"):
                m.main()
        self.assertEqual([kind for kind,_ in calls],["operations","page"])
        self.assertEqual(calls[0][1],calls[1][1])

    def test_cvdw_names_and_dimensions_use_latest_snapshot_without_live_listing(self):
        import leads_public_projection as public
        rows=[{'idlead':1,'data_cad':'2018-01-01','nome':'Maria Silva Antiga','corretor':'João Souza Santos','origem':'FB','origem_nome':'Facebook','midia_original':'Formulário','midia_ultimo':'WhatsApp','situacao':'CONTATO','referencia_data':'2026-11-16 10:00:00'},
              {'idlead':1,'data_cad':'2018-01-01','nome':'Maria Souza Nova','corretor':'Ana Lima Santos','origem':'FB','origem_nome':'Facebook','midia_original':'Formulário','midia_ultimo':'WhatsApp','situacao':'CONTATO','referencia_data':'2026-11-17 10:00:00'}]
        result=m.collect(lambda page:(rows,1,{'total_de_registros':2}),dt.date(2026,11,17),include_roster=True,use_cvdw_details=True)
        self.assertEqual(result['dimension_source'],'cvdw')
        self.assertEqual(result['cvdw_detail_leads'],1)
        roster=result['_public_roster'];self.assertTrue(public.validate(roster))
        self.assertEqual(roster['leads'][0]['name'],'Maria Souza')
        self.assertEqual(roster['leads'][0]['owner'],'Ana Lima')
        self.assertEqual(result['by_registration_project_origin_status'][0]['origin_name'],'Facebook')
        self.assertEqual(result['by_registration_project_origin_status'][0]['lead_medias'],['Formulário','WhatsApp'])
        self.assertNotIn('Antiga',str(result));self.assertNotIn('Santos',str(result))
    def test_cvdw_totals_still_fail_closed(self):
        row={'idlead':1,'data_cad':'2026-11-01','nome':'Maria Silva','referencia_data':'2026-11-17'}
        with self.assertRaises(RuntimeError):
            m.collect(lambda page:([dict(row,idlead=page)],2,{'total_de_registros':2 if page==1 else 3}),dt.date(2026,11,17),use_cvdw_details=True)
        with self.assertRaises(RuntimeError):
            m.collect(lambda page:([row],1,{'total_de_registros':2}),dt.date(2026,11,17),use_cvdw_details=True)

if __name__=="__main__":unittest.main()
