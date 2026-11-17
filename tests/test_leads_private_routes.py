"""Verifica a barreira de autenticação sem credenciais ou chamadas reais ao CV CRM."""
import os
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import server

class LeadsRoutes(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(server.app)
    def test_no_anonymous_access(self):
        for path in ('/api/leads/carteira','/leads_privado.html'):
            self.assertEqual(self.client.get(path).status_code,401)
    def test_bad_password_denied(self):
        with patch.dict(os.environ,{'AUDIT_USER':'test','AUDIT_PASSWORD':'test-pass'}):
            self.assertEqual(self.client.get('/api/leads/carteira',auth=('test','wrong')).status_code,401)
    def test_private_cache_headers(self):
        snapshot=(time.time(),{'validated':True,'leads':[],'updated_at':'2026-11-17T00:00:00+00:00'})
        with patch.dict(os.environ,{'AUDIT_USER':'test','AUDIT_PASSWORD':'test-pass'}),patch.object(server,'api_config',return_value=('https://example.invalid','test','not-a-real-token')),patch.object(server,'_LEADS_SNAPSHOT',snapshot):
            r=self.client.get('/api/leads/carteira',auth=('test','test-pass'))
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.headers['cache-control'],'private, no-store')
            self.assertEqual(r.headers['vary'],'Authorization')
            self.assertNotIn('access-control-allow-origin',r.headers)
    def test_write_route_not_available(self):
        self.assertEqual(self.client.post('/api/leads/carteira').status_code,405)
if __name__=='__main__':unittest.main()
