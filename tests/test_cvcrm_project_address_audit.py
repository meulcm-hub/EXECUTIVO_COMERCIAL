import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/"scripts"/"cvcrm_project_address_audit.py"
spec=importlib.util.spec_from_file_location("address_audit",path)
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class ProjectAddressAuditTests(unittest.TestCase):
    def test_root_project_fields(self):
        record={"nome":"Exemplo","endereco":"Rua A","endereco_numero":"100",
                "cidade":"Sete Lagoas","uf":"MG","cep":"35700000"}
        self.assertEqual({"logradouro","numero","cidade","uf","cep"},audit.fields(record))

    def test_nested_explicit_project_address(self):
        row={"nome":"Projeto","endereco_empreendimento":{
            "logradouro":"Rua das Flores","numero":17,"cidade":"Goiânia","estado":"GO"}}
        self.assertEqual({"logradouro","numero","cidade","uf"},audit.fields(row))

    def test_customer_address_is_not_project_address(self):
        row={"nome":"Projeto","cliente":{"endereco":"Rua particular","numero":22,
             "cidade":"Sete Lagoas","uf":"MG"}}
        self.assertEqual(set(),audit.fields(row))

    def test_unwrap_list_and_wrapped(self):
        records=[{"nome":"Exemplo"}]
        for obj in (records,{"dados":records},{"empreendimentos":records},{"data":{"items":records}}):
            self.assertEqual(audit.unpack(obj),records)

    def test_only_counts_are_reported(self):
        rows=[{"nome":"PRIVADO","idempreendimento":723,
               "endereco":"RUA PRIVADA","numero":"12","cidade":"Cidade","uf":"MG"},
              {"nome":"SEGUNDO","endereco":"Rua B","cidade":"Cidade","uf":"MG"}]
        data=audit.audit(lambda page:(rows,1))
        self.assertEqual(data["empreendimentos_lidos"],2)
        self.assertEqual(data["endereco_completo_com_numero"],1)
        self.assertEqual(data["endereco_localizavel_sem_numero"],2)
        self.assertNotIn("PRIVADO",str(data))
        self.assertNotIn("RUA PRIVADA",str(data))
        self.assertNotIn("723",str(data))

    def test_repeated_page_rejected(self):
        with self.assertRaisesRegex(ValueError,"repeated"):
            audit.audit(lambda page:([{"endereco":"Rua","cidade":"Cidade"}],2))

    def test_credentials_host_pinned(self):
        good={"CVCRM_DOMINIO":"https://lcm.cvcrm.com.br","CVCRM_EMAIL":"e","CVCRM_TOKEN":"t"}
        self.assertEqual(audit.credentials(good)[0],good["CVCRM_DOMINIO"])
        for bad in ["http://lcm.cvcrm.com.br","https://evil.example",
                    "https://lcm.cvcrm.com.br/other","https://lcm.cvcrm.com.br:8443"]:
            with self.assertRaises(ValueError):
                audit.credentials({**good,"CVCRM_DOMINIO":bad})

if __name__=="__main__":
    unittest.main()
