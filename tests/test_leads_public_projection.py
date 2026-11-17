import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import leads_public_projection as public
import leads_commercial_dimensions as commercial
import leads_full_history as full

class PublicRoster(unittest.TestCase):
    def test_only_authorized_fields_leave_collector(self):
        raw={'idlead':1,'nome':'Maria Silva Oliveira','corretor':{'nome':'João Souza Santos'},'cpf':'111.222.333-44','telefone':'(31) 99999-9999','email':'real@example.invalid','origem':'Facebook','midia_principal':'Facebook Ads'}
        data,meta=commercial.collect(lambda offset:{'total':1,'leads':[raw]},public_names=True)
        self.assertEqual(data['1']['public_name'],'Maria Silva')
        self.assertEqual(data['1']['public_owner'],'João Souza')
        cv={'idlead':1,'data_cad':'2026-11-01','empreendimento':'Ipê','origem':'FB','situacao':'CONTATO','referencia_data':'2026-11-17'}
        result=full.collect(lambda page:([cv],1,{}),dt.date(2026,11,17),commercial=data,commercial_meta=meta,include_roster=True)
        roster=result['_public_roster'];self.assertTrue(public.validate(roster))
        row=roster['leads'][0];self.assertEqual(set(row),public.FIELDS)
        text=str(roster)
        for value in ('Oliveira','Santos','111.222.333-44','99999-9999','real@example.invalid','idlead','telefone','cpf','email','reference'):
            self.assertNotIn(value,text)
        self.assertEqual(row['name'],'Maria Silva');self.assertEqual(row['date'],'2026-11-01')
    def test_no_names_by_default(self):
        rows,_=commercial.collect(lambda offset:{'total':1,'leads':[{'idlead':1,'nome':'Maria Silva'}]})
        self.assertNotIn('Maria Silva',str(rows))
    def test_contacts_in_free_fields_are_removed(self):
        for raw in ('Lead 111.222.333-44','Contato (31) 99999-9999','a@example.invalid','https://example.invalid/token'):
            cleaned=public.safe_text(raw)
            self.assertNotIn('@',cleaned)
            self.assertNotIn('99999',cleaned)
            self.assertNotIn('333-44',cleaned)
        self.assertEqual(public.short_name('111.222.333-44'),'Não informado')
    def test_extra_fields_or_incomplete_records_are_rejected(self):
        row={'name':'Maria Silva','date':'2026-11-01','project':'Ipê','origin':'FB','origin_name':'Facebook','lead_media':'Ads','status':'CONTATO','owner':None}
        payload={'schema_version':1,'validated':True,'scope':'all_accessible_leads','total':1,'leads':[row]}
        self.assertTrue(public.validate(payload))
        row['telefone']='123'
        with self.assertRaises(ValueError):public.validate(payload)
        del row['telefone'];payload['total']=2
        with self.assertRaises(ValueError):public.validate(payload)
if __name__=='__main__':unittest.main()
