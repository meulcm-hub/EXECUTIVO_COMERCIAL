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

