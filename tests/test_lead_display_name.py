import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from lcm_lead_display import display_name

class DisplayNameTests(unittest.TestCase):
    def test_two_names_only(self):
        self.assertEqual(display_name("Maria Eduarda Oliveira Santos"),"Maria Eduarda")
        self.assertEqual(display_name("  João   da   Silva  "), "João da")
        self.assertEqual(display_name("Ana"),"Ana")
        self.assertEqual(display_name(""),"Não informado")
    def test_no_phone_in_leads_view_or_public_export(self):
        html=Path("leads.html").read_text(encoding="utf-8")
        js=Path("lcm-leads.js").read_text(encoding="utf-8")
        self.assertNotIn("<th>Telefone</th>",html)
        self.assertNotIn("'Telefone'",js)
        self.assertNotIn('"telefone"',js)
if __name__=="__main__":unittest.main()
