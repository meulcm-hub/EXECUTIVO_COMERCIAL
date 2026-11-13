import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class LeadsContract(unittest.TestCase):
    def test_validated_anonymous_source(self):
        data=json.loads((ROOT/'data/cv-funnel.json').read_text(encoding='utf-8'))
        self.assertEqual((data['schema_version'],data['classification_version']), (2,1))
        self.assertTrue(data['validated'])
        self.assertEqual(data['cohort_mode'],'prospect_date')
        self.assertTrue(data['prospects'])
        self.assertTrue(all(isinstance(x.get('whatsapp_acquisition'),bool) for x in data['prospects']))
        self.assertTrue(all(x['entries'] and all(0<=e['stage']<=4 for e in x['entries']) for x in data['prospects']))
        self.assertTrue(all('idlead' not in g and 'cliente' not in g and 'telefone' not in g for g in data['prospects']))
    def test_isolation_and_navigation(self):
        html=(ROOT/'leads.html').read_text(encoding='utf-8')
        shell=(ROOT/'lcm-shell.js').read_text(encoding='utf-8')
        js=(ROOT/'lcm-leads.js').read_text(encoding='utf-8')
        self.assertIn('data-lcm-page="leads"',html)
        self.assertIn('lcm-leads.js',html)
        self.assertIn("['leads','Gestão de Leads','leads.html'",shell)
        self.assertIn("data/cv-funnel.json",js)
        self.assertNotIn('data/cv-audit.json',js)
        self.assertNotIn('api/v1',js)
    def test_no_fake_sdr_sla(self):
        html=(ROOT/'leads.html').read_text(encoding='utf-8')
        self.assertIn('Integração operacional pendente',html)
        self.assertIn('ambiente autenticado',html)
        self.assertIn('Fonte de interações necessária',html)
if __name__=='__main__':unittest.main()
