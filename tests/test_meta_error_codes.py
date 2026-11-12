import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import meta_ads_collector as meta

class MetaErrorTests(unittest.TestCase):
    def test_safe_codes_without_api_message_or_credentials(self):
        for code,subcode,category in [(190,463,'token expirado'),(200,0,'permissão'),(100,0,'parâmetro')]:
            response=io.BytesIO(json.dumps({'error':{'code':code,'error_subcode':subcode,
                'message':'valor-confidencial-nunca-publicar'}}).encode())
            error=urllib.error.HTTPError('https://graph.facebook.com/test',400,'bad',{},response)
            with patch.object(meta,'TOKEN','credencial-ficticia'),patch.object(meta.urllib.request,'urlopen',side_effect=error):
                with self.assertRaises(RuntimeError) as got:meta.request('test')
            text=str(got.exception)
            self.assertIn('código '+str(code),text);self.assertIn(category,text)
            self.assertNotIn('valor-confidencial',text);self.assertNotIn('credencial-ficticia',text)
    def test_non_json_body_is_never_logged(self):
        error=urllib.error.HTTPError('https://graph.facebook.com/test',400,'bad',{},io.BytesIO(b'confidencial'))
        with patch.object(meta,'TOKEN','credencial-ficticia'),patch.object(meta.urllib.request,'urlopen',side_effect=error):
            with self.assertRaises(RuntimeError) as got:meta.request('test')
        self.assertNotIn('confidencial',str(got.exception))

