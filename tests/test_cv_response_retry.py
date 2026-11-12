import datetime as dt
import http.client
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import marketing_consolidate as collector

class CvRetryTests(unittest.TestCase):
    def test_interrupted_response_retries_without_publishing_partial_bytes(self):
        response=io.BytesIO(json.dumps({'dados':[{'idlead':1}],'total_de_paginas':1}).encode())
        opener=Mock();opener.open.side_effect=[http.client.IncompleteRead(b'private-data'),response]
        with patch.object(collector.urllib.request,'build_opener',return_value=opener),patch.object(collector.time,'sleep'):
            rows,payload=collector.cv_page('https://lcm.cvcrm.com.br','a','b',1,500,dt.date(2026,1,1),dt.date(2026,11,12))
        self.assertEqual(rows,[{'idlead':1}]);self.assertEqual(opener.open.call_count,2)
    def test_exhausted_retries_raise_controlled_error_without_partial_payload(self):
        opener=Mock();opener.open.side_effect=http.client.IncompleteRead(b'private-data')
        with patch.object(collector.urllib.request,'build_opener',return_value=opener),patch.object(collector.time,'sleep'):
            with self.assertRaises(RuntimeError) as got:collector.cv_page('https://lcm.cvcrm.com.br','a','b',1,500,dt.date(2026,1,1),dt.date(2026,11,12))
        self.assertEqual(opener.open.call_count,4);self.assertNotIn('private-data',str(got.exception))


    def test_valid_annual_meta_is_published_when_complementary_cv_is_unavailable(self):
        import contextlib,os,tempfile
        import marketing_daily as daily
        catalog=[{'id':'act_'+str(1234560+i),'currency':'BRL','name':'Conta fictícia'} for i in range(8)]
        old=os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                with patch.object(daily,'accounts',return_value=catalog),patch.object(daily,'request',return_value=[{'date_start':'2026-01-02','spend':'1','impressions':2,'clicks':1}]),patch.object(daily,'cv_page',side_effect=RuntimeError('unavailable')),patch.dict(os.environ,{'CVCRM_DOMINIO':'https://lcm.cvcrm.com.br','CVCRM_EMAIL':'ficticio','CVCRM_TOKEN':'ficticio'}),contextlib.redirect_stdout(io.StringIO()):
                    daily.main()
                report=json.loads(Path('data/marketing-daily.json').read_text())
            finally:os.chdir(old)
        self.assertEqual(report['period']['since'],'2026-01-01')
        self.assertEqual(len(report['meta_accounts']),8)
        self.assertFalse(report['cv_counts_validated'])
        self.assertEqual(report['cv_by_project_daily'],{})
        self.assertEqual(sum(float(a['daily']['2026-01-02']['spend']) for a in report['meta_accounts']),8)
