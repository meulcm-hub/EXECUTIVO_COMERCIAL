import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

path=Path(__file__).resolve().parents[1]/"scripts"/"cvcrm_geocode_projects.py"
sys.path.insert(0,str(path.parent))
spec=importlib.util.spec_from_file_location("cv_geocode",path)
geo=importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)

class CVCRMGeocodingTests(unittest.TestCase):
    def test_project_address_only(self):
        record={"nome":"Village Lagoas","endereco":{"logradouro":"Rua dos Testes","numero":"38","cidade":"Sete Lagoas","estado":"MG","cep":"35700000"},
                "cliente":{"endereco":"PRIVADO","numero":"99"}}
        result=geo.project_address(record)
        self.assertEqual(result["status"],"ready")
        self.assertEqual(result["road"],"Rua dos Testes")
        self.assertNotIn("PRIVADO",str(result))
    def test_incomplete(self):
        self.assertEqual(geo.project_address({"nome":"Projeto","cidade":"Sete Lagoas"})["status"],"incomplete")
    def test_requires_exact_number_and_city(self):
        p={"road":"Rua dos Testes","number":"38","city":"Sete Lagoas","state":"MG"}
        result={"lat":"-19.45","lon":"-44.25","type":"house","address":{
           "road":"Rua dos Testes","house_number":"38","city":"Sete Lagoas","state":"Minas Gerais"}}
        self.assertTrue(geo.verified(result,p))
        self.assertFalse(geo.verified({**result,"address":{**result["address"],"house_number":"88"}},p))
        self.assertFalse(geo.verified({**result,"address":{**result["address"],"city":"Belo Horizonte"}},p))
        self.assertFalse(geo.verified({**result,"type":"city"},p))
    def test_no_address_in_output_and_unverified_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=geo.OUT
            geo.OUT=Path(tmp)/"review.json"
            try:
                row={"status":"ready","project":"Empreendimento Teste","identifier":"42","road":"RUA PRIVADA","number":"10","city":"Goiânia","state":"GO"}
                env={"CVCRM_DOMINIO":"https://lcm.cvcrm.com.br","CVCRM_EMAIL":"hidden@example.invalid",
                     "CVCRM_TOKEN":"HIDDEN_SECRET","LCM_GEOCODER_USER_AGENT":"LCM (https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL)"}
                summary=geo.run(env,fetch=lambda:[row],lookup=lambda p:[{"lat":-16.67,"lng":-49.27}],sleep=lambda _:None)
                content=geo.OUT.read_text()
                self.assertEqual(summary["candidate_exact"],1)
                self.assertIn('"verified": false',content)
                for secret in ["RUA PRIVADA","HIDDEN_SECRET","hidden@example.invalid"]:
                    self.assertNotIn(secret,content)
            finally:geo.OUT=original
if __name__=="__main__":unittest.main()
