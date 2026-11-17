import datetime as dt
import io
import http.client
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from cvcrm_read_pacing import ReadPacer,retry_after
import leads_operational_history as ops
import leads_full_history as full

class Clock:
    def __init__(self):self.now=0;self.waits=[]
    def clock(self):return self.now
    def sleep(self,value):self.waits.append(value);self.now+=value

class Response:
    status=200
    headers={'Content-Type':'application/json'}
    def __init__(self,data):self.data=json.dumps(data).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,*args):return self.data

class PacingTests(unittest.TestCase):
    def test_one_queue_stays_below_twenty_per_rolling_minute(self):
        clock=Clock();p=ReadPacer(clock=clock.clock,sleep=clock.sleep);starts=[]
        for _ in range(60):p.wait();starts.append(clock.now)
        for start in starts:self.assertLessEqual(sum(start<=x<start+60 for x in starts),15)
    def test_global_pause_prevents_requests_in_blocked_minute(self):
        clock=Clock();p=ReadPacer(clock=clock.clock,sleep=clock.sleep)
        p.wait();p.cooldown(65);p.wait();self.assertEqual(clock.now,65)
        p.wait();self.assertAlmostEqual(clock.now,69.2)
    def test_retry_after_seconds_and_http_date_are_respected(self):
        self.assertEqual(retry_after({}),65)
        self.assertEqual(retry_after({'Retry-After':'5'}),65)
        self.assertEqual(retry_after({'Retry-After':'180'}),180)
        now=dt.datetime(2026,11,17,20,tzinfo=dt.timezone.utc)
        self.assertEqual(retry_after({'Retry-After':'Tue, 17 Nov 2026 20:02:00 GMT'},now),120)
    def test_operational_429_retries_same_page_after_full_cooldown(self):
        clock=Clock();p=ReadPacer(clock=clock.clock,sleep=clock.sleep)
        error=HTTPError('https://lcm.cvcrm.com.br/',429,'rate limit',{'Retry-After':'120'},None)
        opener=unittest.mock.Mock();opener.open.side_effect=[error,Response({'dados':[]})]
        with patch.object(ops,'PACER',p),patch.object(ops.urllib.request,'build_opener',return_value=opener):
            result=ops.request('https://lcm.cvcrm.com.br','private-email','private-token','/api/v1/cvdw/leads/visitas',3)
        self.assertEqual(result,{'dados':[]});self.assertEqual(clock.now,120)
        urls=[call.args[0].full_url for call in opener.open.call_args_list]
        self.assertEqual(urls[0],urls[1]);self.assertIn('pagina=3',urls[0])
    def test_lead_pages_use_same_throttle_and_keep_reference_window(self):
        clock=Clock();p=ReadPacer(clock=clock.clock,sleep=clock.sleep)
        opener=unittest.mock.Mock();opener.open.side_effect=[HTTPError('https://lcm.cvcrm.com.br/',429,'rate limit',{},None),Response({'dados':[],'total_de_paginas':1})]
        with patch.object(full,'PACER',p):
            full.fetch_page(opener,'https://lcm.cvcrm.com.br','email','token',2,'2026-11-17 16:00:00')
        self.assertEqual(clock.now,65)
        self.assertIn('ate_data_referencia',opener.open.call_args.args[0].full_url)
    def test_sources_are_called_sequentially(self):
        calls=[]
        def source(kind,fetch):
            calls.append(('start',kind));calls.append(('end',kind));return {},{'records':0,'pages':0}
        with patch.object(ops,'collect_source',side_effect=source):ops.fetch_all('base','email','token')
        expected=[(event,kind) for kind in ops.ROUTES for event in ('start','end')]
        self.assertEqual(calls,expected)
    def test_auth_errors_fail_without_retry(self):
        opener=unittest.mock.Mock();opener.open.side_effect=HTTPError('https://lcm.cvcrm.com.br/',401,'unauthorized',{},None)
        with patch.object(ops,'PACER'),patch.object(ops.urllib.request,'build_opener',return_value=opener):
            with self.assertRaisesRegex(RuntimeError,'HTTP 401'):ops.request('https://lcm.cvcrm.com.br','email','token','/api/v1/cvdw/leads/visitas',1)
        self.assertEqual(opener.open.call_count,1)
class InterruptedResponse(Response):
    def read(self,*args):raise http.client.IncompleteRead(b'private response bytes')

class InterruptedTransportTests(unittest.TestCase):
    def test_partial_interaction_response_is_discarded_and_same_page_retried(self):
        clock=Clock();p=ReadPacer(clock=clock.clock,sleep=clock.sleep)
        opener=unittest.mock.Mock()
        expected={'dados':[{'idinteracao':123}],'total_de_paginas':3,'total_de_registros':1001}
        opener.open.side_effect=[InterruptedResponse({}),Response(expected)]
        with patch.object(ops,'PACER',p),patch.object(ops.time,'sleep',side_effect=clock.sleep),patch.object(ops.urllib.request,'build_opener',return_value=opener):
            result=ops.request('https://lcm.cvcrm.com.br','email','token','/api/v1/cvdw/leads/interacoes',430,'2026-11-17 16:00:00')
        self.assertEqual(result,expected)
        self.assertEqual(opener.open.call_args_list[0].args[0].full_url,opener.open.call_args_list[1].args[0].full_url)
        self.assertNotIn('private response bytes',str(result))
    def test_partial_lead_response_is_retried_without_losing_cutoff(self):
        clock=Clock();p=ReadPacer(clock=clock.clock,sleep=clock.sleep)
        opener=unittest.mock.Mock();opener.open.side_effect=[InterruptedResponse({}),Response({'dados':[{'idlead':123}],'total_de_paginas':5})]
        with patch.object(full,'PACER',p),patch.object(full.time,'sleep',side_effect=clock.sleep):
            rows,pages,_=full.fetch_page(opener,'https://lcm.cvcrm.com.br','email','token',3,'2026-11-17 16:00:00')
        self.assertEqual(pages,5);self.assertEqual(len(rows),1)
        urls=[call.args[0].full_url for call in opener.open.call_args_list]
        self.assertEqual(urls[0],urls[1]);self.assertIn('ate_data_referencia',urls[1])
    def test_persistent_transport_failure_still_blocks_publication(self):
        opener=unittest.mock.Mock();opener.open.side_effect=http.client.RemoteDisconnected('private upstream response')
        with patch.object(ops,'PACER'),patch.object(ops.time,'sleep'),patch.object(ops.urllib.request,'build_opener',return_value=opener):
            with self.assertRaisesRegex(RuntimeError,'Fonte operacional indisponível') as error:
                ops.request('https://lcm.cvcrm.com.br','email','token','/api/v1/cvdw/leads/interacoes',430)
        self.assertEqual(opener.open.call_count,6)
        self.assertNotIn('private upstream response',str(error.exception))

if __name__=='__main__':unittest.main()
