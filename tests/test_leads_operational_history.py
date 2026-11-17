import datetime as dt
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import leads_operational_history as ops
import leads_full_history as full
import leads_public_projection as public

def page(rows,total=None,pages=1):
    return {'dados':rows,'total_de_registros':len(rows) if total is None else total,'total_de_paginas':pages}
def row(**kw):
    result={'idlead':12,'idinteracao':1,'referencia_data':'2026-11-17 10:00:00','data_cad':'2026-11-16 09:00:00','ativo':'S','tipo':'A','descricao':'CPF 111.222.333-44 email real@example.com telefone 31999999999','audioServidor':'https://private.invalid/audio'}
    result.update(kw);return result

class HistoryTests(unittest.TestCase):
    def test_real_dates_never_reference_or_description(self):
        e=ops.event('interaction',row())
        self.assertEqual(e['date'],'2026-11-16T09:00:00')
        self.assertEqual(e['type'],'Anotação')
        self.assertEqual(set(e),ops.EVENT_FIELDS)
        self.assertNotIn('descricao',e);self.assertNotIn('audioServidor',e)
        self.assertTrue(ops.validate_event(e))
        self.assertIsNone(ops.summary([e])['last_contact'])
    def test_next_action_uses_pending_deadline_including_overdue(self):
        rows=[ops.event('task',row(idtarefa=1,tipo_interacao='L',situacao='P',data='2026-11-01 08:00:00')),
              ops.event('task',row(idtarefa=2,tipo_interacao='W',situacao='C',data='2026-10-01 08:00:00',data_conclusao='2026-11-17 12:00:00')),
              ops.event('task',row(idtarefa=3,tipo_interacao='V',situacao='CA',data='2026-09-01 08:00:00'))]
        summary=ops.summary(rows)
        self.assertEqual(summary['next_action'],'Ligação')
        self.assertEqual(summary['next_action_at'],'2026-11-01T08:00:00')
        self.assertEqual(rows[1]['date'],'2026-11-17T12:00:00')
    def test_inactive_and_missing_dates_not_published(self):
        self.assertIsNone(ops.event('interaction',row(ativo='N')))
        self.assertIsNone(ops.event('interaction',row(data_cad=None)))
    def test_pagination_completeness_and_repetition(self):
        first=row(idinteracao=1);second=row(idinteracao=2)
        result,meta=ops.collect_source('interaction',lambda p:page([first if p==1 else second],2,2))
        self.assertEqual(len(result),2);self.assertEqual(meta['records'],2)
        with self.assertRaises(RuntimeError):ops.collect_source('interaction',lambda p:page([first],2,2))
        with self.assertRaises(RuntimeError):ops.collect_source('interaction',lambda p:page([first],3 if p==1 else 4,2))
    def test_latest_snapshot_and_shared_visit_id(self):
        old=row(idtarefa=3,tipo_interacao='L',situacao='P',data='2026-11-18 09:00:00')
        new=row(idtarefa=3,tipo_interacao='V',situacao='C',referencia_data='2026-11-17 12:00:00',data_conclusao='2026-11-17 12:00:00')
        tasks,_=ops.collect_source('task',lambda p:page([old,new]))
        visits,_=ops.collect_source('visit',lambda p:page([new]))
        grouped=ops.assemble({'task':tasks,'visit':visits},'secret')
        self.assertEqual(len(grouped['12']),1)
        self.assertEqual(grouped['12'][0]['kind'],'visit')
    def test_empty_source_is_valid_and_no_free_text_allowed(self):
        result,meta=ops.collect_source('stage',lambda p:page([],0,0));self.assertEqual(result,{})
        event=ops.event('interaction',row());event['descricao']='anything'
        with self.assertRaises(ValueError):ops.validate_event(event)
    def test_join_by_id_never_name_and_public_keys_are_opaque(self):
        cv=[{'idlead':12,'data_cad':'2026-11-01','empreendimento':'Ipê','origem':'FB','situacao':'CONTATO','referencia_data':'2026-11-17'},
            {'idlead':13,'data_cad':'2026-11-01','empreendimento':'Ipê','origem':'FB','situacao':'CONTATO','referencia_data':'2026-11-17'}]
        details={str(n):{'public_name':'Maria Silva'} for n in (12,13)}
        events=[ops.event('interaction',row(tipo='W'))]
        result=full.collect(lambda p:(cv,1,{}),dt.date(2026,11,17),commercial=details,include_roster=True,operations={'12':events},operations_meta={},history_secret='secret')
        roster=result['_public_roster'];self.assertTrue(public.validate(roster))
        self.assertEqual(sorted(r['history_count'] for r in roster['leads']),[0,1])
        self.assertEqual(len({r['history_key'] for r in roster['leads']}),2)
        text=json.dumps(result)
        for forbidden in ('idlead','idinteracao','descricao','audioServidor','real@example.com','111.222.333-44','secret'):
            self.assertNotIn(forbidden,text)
        self.assertNotEqual(ops.opaque('secret','lead',12),ops.opaque('other','lead',12))
if __name__=='__main__':unittest.main()
