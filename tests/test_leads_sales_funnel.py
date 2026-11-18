import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from leads_sales_funnel import build,read_pages,links,SOLD,validate
from leads_operational_history import opaque,summary
from leads_public_projection import project
class Sales(unittest.TestCase):
 def fixture(self):
  key=opaque('secret','lead',120)
  row=project({'date':'2026-01-01','project':'Ipê','origin':'FB','origin_name':'Facebook','lead_media':'Ads','status':'CONTATO'},{'public_name':'Maria Silva'})
  row.update(summary([]));row['history_key']=key
  return key,{'schema_version':2,'validated':True,'scope':'all_accessible_leads','total':1,'history_generation':'a'*32,'leads':[row]}
 def test_reservation_rule_sale_statuses_and_no_pii(self):
  key,roster=self.fixture()
  for status in SOLD:
   r=build(roster,{key:[]},{},{},{'1':{'idlead':'120','data_cad':'2026-11-01','data_venda':'2026-11-02','situacao':status,'nome':'Sensitive Person','cpf':'999','descricao':'secret note'}},'secret')
   self.assertEqual([e['level'] for e in r['leads'][0]['events']],[3,4]);self.assertNotIn('Sensitive',json.dumps(r));self.assertNotIn('idlead',json.dumps(r))
  r=build(roster,{key:[]},{},{},{'1':{'idlead':'120','data_cad':'2026-11-01','situacao':'Reserva'}},'secret');self.assertEqual([e['level'] for e in r['leads'][0]['events']],[3])
 def test_cancelled_reservations_excluded_and_return_after_registration(self):
  key,roster=self.fixture();r=build(roster,{key:[]},{'1':{'idlead':120,'referencia_data':'2026-11-02','ativo':'S'}},{},{'1':{'idlead':'120','data_cad':'2026-11-01','data_cancelamento':'2026-11-03','situacao':'Vendida'}},'secret')
  self.assertEqual(r['leads'][0]['entries'],['2026-01-01','2026-11-02']);self.assertEqual(r['leads'][0]['events'],[])
 def test_completed_visit_and_pre_registration(self):
  key,roster=self.fixture();e={'kind':'visit','type':'Visita','state':'Concluída','date':'2026-11-01'}
  r=build(roster,{key:[e]},{},{'1':{'data_cad':'2026-11-02','leads_associados':[{'idlead':120}]}},{},'secret');self.assertEqual([x['level'] for x in r['leads'][0]['events']],[1,2,3])
 def test_strict_pagination_repetition_and_total_changes(self):
  def payload(p):return {'total_de_registros':2,'total_de_paginas':2,'dados':[{'idreserva':p,'referencia_data':'2026-11-01'}]}
  r,m=read_pages(payload,'idreserva');self.assertEqual(len(r),2)
  with self.assertRaises(RuntimeError):read_pages(lambda p:payload(1),'idreserva')
  with self.assertRaises(RuntimeError):read_pages(lambda p:{**payload(p),'total_de_registros':p},'idreserva')
 def test_explicit_scheduling_tasks_and_completed_without_appointment(self):
  key,roster=self.fixture()
  tasks={'1':{'idlead':120,'data_cad':'2026-11-01','descricao':'SEM AGENDAMENTO','situacao':'C','data_conclusao':'2026-11-02'},'2':{'idlead':120,'data_cad':'2026-11-02','descricao':'AGENDAMENTO','situacao':'CA'},'3':{'idlead':120,'data_cad':'2026-11-03','descricao':'Ligar amanhã','situacao':'P'}}
  r=build(roster,{key:[]},{},{},{},'secret',tasks=tasks)
  self.assertEqual([(e['date'],e['level']) for e in r['leads'][0]['events']],[('2026-11-01',1),('2026-11-02',2)])
 def test_public_projection_rejects_extra_fields(self):
  key,roster=self.fixture();r=build(roster,{key:[]},{},{},{},'secret');self.assertTrue(validate(r,roster));r['leads'][0]['email']='private'
  with self.assertRaises(RuntimeError):validate(r,roster)
 def test_links_use_ids_never_names_or_documents(self):
  self.assertEqual(links({'idlead':'120,121','leads_associados':[{'idlead':122}],'cpf':'12345'}),{'120','121','122'})
if __name__=='__main__':unittest.main()
