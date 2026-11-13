import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
import urllib.error

FILE = Path(__file__).resolve().parents[1] / 'scripts/buyer_reservation_address_diagnostic.py'
spec = importlib.util.spec_from_file_location('diagnostic', FILE)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class Response:
    status = 200
    headers = {'Content-Type': 'application/json'}
    def __init__(self, payload): self.body = json.dumps(payload).encode()
    def read(self, limit): return self.body[:limit]
    def __enter__(self): return self
    def __exit__(self, *args): pass


class Opener:
    def __init__(self, payload): self.payload = payload; self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        if isinstance(self.payload, Exception): raise self.payload
        return Response(self.payload)


class DiagnosticTest(unittest.TestCase):
    env = {'CVCRM_DOMINIO': 'https://lcm.cvcrm.com.br', 'CVCRM_EMAIL': 'SECRET_EMAIL', 'CVCRM_TOKEN': 'SECRET_TOKEN'}
    address = {'logradouro': 'PRIVATE_STREET', 'numero': '987', 'cidade': 'PRIVATE_CITY', 'uf': 'ZZ', 'cep': 'PRIVATE_POSTCODE'}

    def test_nested_buyer_address_is_qualified_and_no_values_reach_stdout(self):
        item = {'cliente': {'nome': 'PRIVATE_NAME', 'id': 'PRIVATE_ID', 'endereco': self.address}}
        op = Opener({'dados': [item]})
        out = io.StringIO()
        with contextlib.redirect_stdout(out): self.assertEqual(d.main(self.env, op), 0)
        text = out.getvalue()
        for secret in ['SECRET_EMAIL', 'SECRET_TOKEN', 'PRIVATE_STREET', '987', 'PRIVATE_CITY', 'PRIVATE_NAME', 'PRIVATE_ID', 'PRIVATE_POSTCODE']:
            self.assertNotIn(secret, text)
        report = d.summarize([item])
        self.assertEqual(report['logradouro_numero_cidade_uf_no_mesmo_endereco'], 1)
        self.assertEqual(report['campos_cliente']['logradouro'], 1)
        self.assertEqual(len(op.requests), 2)
        for request in op.requests: self.assertIn('registros_por_pagina=10', request.full_url)

    def test_project_unit_and_flat_addresses_not_counted_as_buyer_residence(self):
        records = [{'empreendimento': {'endereco': self.address}}, {'unidade': self.address}, self.address, {'endereco': self.address}]
        report = d.summarize(records)
        self.assertEqual(report['residencia_em_contexto_cliente'], 0)
        self.assertEqual(report['endereco_principal_sem_contexto_cliente'], 2)

    def test_completeness_not_combined_across_different_buyers(self):
        record = {'compradores': [{'endereco': {'rua': 'PRIVATE', 'numero': '1'}}, {'endereco': {'cidade': 'PRIVATE', 'uf': 'ZZ'}}]}
        self.assertEqual(d.summarize([record])['logradouro_numero_cidade_uf_no_mesmo_endereco'], 0)

    def test_rows_known_wrappers_numeric_index_and_sample_limit(self):
        data = [{'cliente': {'bairro': 'PRIVATE'}} for _ in range(12)]
        for payload in [data, {'dados': data}, {'reservas': {str(i): v for i, v in enumerate(data)}}, {str(i): v for i, v in enumerate(data)}]:
            self.assertEqual(len(d.rows(payload)), 10)
        self.assertEqual(len(d.rows({'dados': {'idreserva': 1, 'cliente': {}}})), 1)

    def test_malformed_response_and_http_body_never_exposed(self):
        for payload in [None, 'PRIVATE_VALUE', {'error': 'PRIVATE_VALUE'}, {'dados': ['PRIVATE_VALUE']}]:
            with self.assertRaises(ValueError): d.rows(payload)
        err = urllib.error.HTTPError('https://lcm.cvcrm.com.br/?PRIVATE_URL', 403, 'PRIVATE_REASON', {}, io.BytesIO(b'PRIVATE_BODY'))
        out = io.StringIO()
        with contextlib.redirect_stdout(out): self.assertEqual(d.main(self.env, Opener(err)), 1)
        self.assertNotIn('PRIVATE', out.getvalue())
        self.assertIn('HTTP 403', out.getvalue())

    def test_invalid_domain_rejected_before_network(self):
        for domain in ['http://lcm.cvcrm.com.br', 'https://evil.example', 'https://lcm.cvcrm.com.br.evil.example', 'https://user:pass@lcm.cvcrm.com.br', 'https://lcm.cvcrm.com.br?secret=x', 'https://lcm.cvcrm.com.br:444']:
            op = Opener({})
            out = io.StringIO()
            with contextlib.redirect_stdout(out): self.assertEqual(d.main({**self.env, 'CVCRM_DOMINIO': domain}, op), 2)
            self.assertEqual(op.requests, [])

    def test_redirects_disabled(self):
        self.assertIsNone(d.NoRedirect().redirect_request(None, None, 302, 'private', {}, 'https://evil.example'))


if __name__ == '__main__': unittest.main()
