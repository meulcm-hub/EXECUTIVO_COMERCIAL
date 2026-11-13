import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import cvcrm_facebook_forms_diagnostic as d

class FormDiagnosticTests(unittest.TestCase):
    def test_presence_counts_without_values(self):
        rows=[{"idlead":123,"idformulario":74,"idintegracao":"fb-lead-abc",
               "integracao":"FB","midia":"Facebook","nome":"Dado privado"},
              {"idlead":456,"idformulario":None,"nome":"Outro dado privado"}]
        result=d.classify_keys(rows)
        self.assertEqual(result["rows"],2)
        self.assertEqual(result["form_field_filled"],1)
        self.assertEqual(result["form_field_empty"],1)
        self.assertEqual(result["integration_id_field_present"],1)
        self.assertNotIn("123",str(result))
        self.assertNotIn("Dado privado",str(result))
    def test_unrecognized_schema_fails_closed(self):
        with self.assertRaises(ValueError):d.records({"message":"unexpected"})
        self.assertEqual(len(d.records({"dados":[]})),0)
if __name__=="__main__":unittest.main()
