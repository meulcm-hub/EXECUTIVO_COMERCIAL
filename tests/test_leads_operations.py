import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from leads_operations import project_lead,collect

class PrivateLeads(unittest.TestCase):
    def row(self,i=1):
        return {'idlead':i,'nome':'Maria Silva Oliveira','telefone':'123','cpf':'456','email':'a@b','data_cadastro':'2026-11-17 09:00:00','situacao':{'nome':'Contato'},'corretor':{'nome':'João Souza Santos'},'empreendimento':{'nome':'Ipê'},'data_modificacao':'2026-11-17T10:00:00'}
    def test_private_projection(self):
        r=project_lead(self.row())
        self.assertEqual(r['name'],'Maria Silva')
        self.assertEqual(r['owner'],'João Souza')
        self.assertEqual(r['status'],'Contato')
        self.assertIsNone(r['last_contact'])
        for key in ('telefone','cpf','email','nome','data_modificacao'):self.assertNotIn(key,r)
        self.assertNotIn('Oliveira',str(r))
    def test_pagination_and_uniqueness(self):
        pages={0:{'total':2,'leads':[self.row(1)]},1:{'total':2,'leads':[self.row(2)]}}
        self.assertEqual(len(collect(pages.__getitem__)),2)
        pages[1]['leads']=[self.row(1)]
        with self.assertRaises(ValueError):collect(pages.__getitem__)
    def test_changed_total_and_empty_page_fail_closed(self):
        for second in ({'total':3,'leads':[self.row(2)]},{'total':2,'leads':[]}):
            pages={0:{'total':2,'leads':[self.row(1)]},1:second}
            with self.assertRaises(ValueError):collect(pages.__getitem__)
    def test_no_guessed_project_or_contact(self):
        r=self.row();r.pop('empreendimento');r['empreendimentos']=[{'nome':'Ipê'},{'nome':'Jatobá'}]
        self.assertEqual(project_lead(r)['project'],'MÚLTIPLOS EMPREENDIMENTOS')
        r['data_ultimo_contato']='2026-11-17T12:01:00';self.assertEqual(project_lead(r)['last_contact'],r['data_ultimo_contato'])
if __name__=='__main__':unittest.main()
