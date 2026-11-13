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


class SequenceOpener(Opener):
    def __init__(self, payloads):
        super().__init__(None)
        self.payloads = iter(payloads)
    def open(self, request, timeout):
        self.requests.append(request)
        value = next(self.payloads)
        if isinstance(value, Exception):
            raise value
        return Response(value)


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

    def test_root_fields_links_and_scalar_buyer_presence_are_static_counts(self):
        record = {'bairro': 'PRIVATE_BAIRRO', 'cidade': 'PRIVATE_CITY', 'id_pessoa': 'PRIVATE_PERSON_ID',
                  'idcliente': 23456789, 'id_titular': 'PRIVATE_TITULAR', 'cliente': 'PRIVATE_CUSTOMER',
                  'dados_cliente': {}, 'PRIVATE_CUSTOM_FIELD': 'PRIVATE_VALUE'}
        report = d.summarize([record])
        self.assertEqual(report['campos_principais']['bairro'], 1)
        self.assertEqual(report['campos_principais']['cidade'], 1)
        self.assertEqual(report['vinculos_cliente'], {'idpessoa': 1, 'idcliente': 1, 'idtitular': 1})
        self.assertEqual(report['conteineres_cliente']['cliente'], 1)
        self.assertEqual(report['conteineres_cliente']['dados_cliente'], 1)
        self.assertEqual(report['residencia_em_contexto_cliente'], 0)
        self.assertNotIn('PRIVATE', json.dumps(report))

    def test_flat_buyer_qualified_fields_count_but_generic_root_stays_ambiguous(self):
        record = {'endereco_cliente': 'PRIVATE_STREET', 'cliente_numero': '876',
                  'cidade_cliente': 'PRIVATE_CITY', 'cliente_uf': 'ZZ', 'cep_cliente': 'PRIVATE_CEP',
                  'cidade': 'PRIVATE_PROJECT_CITY'}
        report = d.summarize([record])
        self.assertEqual(report['logradouro_numero_cidade_uf_no_mesmo_endereco'], 1)
        self.assertEqual(report['campos_cliente_qualificados_na_raiz']['logradouro'], 1)
        self.assertEqual(report['campos_cliente_qualificados_na_raiz']['cep'], 1)
        self.assertEqual(report['endereco_principal_sem_contexto_cliente'], 1)
        # Separate explicit buyer namespaces must not be merged into an address.
        mixed = {'logradouro_cliente': 'PRIVATE', 'numero_comprador': '1',
                 'cidade_cliente': 'PRIVATE', 'uf_comprador': 'ZZ'}
        self.assertEqual(d.summarize([mixed])['logradouro_numero_cidade_uf_no_mesmo_endereco'], 0)

    def test_detail_uses_only_first_cvdw_numeric_reservation_id_and_never_prints_it(self):
        secret_id = '765432198765'
        op = SequenceOpener([{'dados': [{'idreserva': secret_id, 'cidade': 'PRIVATE_CITY'}]},
                             {'reservas': []}, {'reserva': {'idreserva': secret_id,
                              'cliente': {'endereco': self.address}, 'PRIVATE_KEY': 'PRIVATE_VALUE'}}])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(d.main(self.env, op), 0)
        self.assertEqual(len(op.requests), 3)
        self.assertTrue(op.requests[-1].full_url.endswith('/api/v1/comercial/reservas/' + secret_id))
        self.assertIn('Detalhe Comercial Reserva:', out.getvalue())
        self.assertNotIn(secret_id, out.getvalue())
        self.assertNotIn('PRIVATE', out.getvalue())
        self.assertNotIn('SECRET', out.getvalue())
        self.assertIsNone(d.first_reservation_id([{'id': 12}, {'idreserva': 13}]))

    def test_invalid_detail_id_rejected_before_network(self):
        for invalid in ['0', -1, True, False, 1.2, '-1', '+1', ' 1', '1/../../clientes',
                        'https://evil.example', '1?token=PRIVATE', None, '1' * 21]:
            op = Opener({})
            with self.assertRaises(ValueError):
                d.fetch_reservation_detail(op, 'https://lcm.cvcrm.com.br', 'SECRET_EMAIL', 'SECRET_TOKEN', invalid)
            self.assertEqual(op.requests, [])

    def test_detail_rows_accept_single_and_wrapped_reservations_not_error_payloads(self):
        item = {'idreserva': 12, 'cliente': {'endereco': self.address}}
        for payload in [item, {'reserva': item}, {'dados': item}, {'data': [item]}]:
            self.assertEqual(d.detail_rows(payload), [item])
        with self.assertRaises(ValueError): d.detail_rows({'error': 'PRIVATE_BODY'})

    def test_detail_http_error_does_not_print_reservation_url_or_error_body(self):
        err = urllib.error.HTTPError('https://lcm.cvcrm.com.br/api/v1/comercial/reservas/87654321',
                                     403, 'PRIVATE_REASON', {}, io.BytesIO(b'PRIVATE_BODY'))
        op = SequenceOpener([{'dados': [{'idreserva': 87654321}]}, {'reservas': []}, err])
        out = io.StringIO()
        with contextlib.redirect_stdout(out): self.assertEqual(d.main(self.env, op), 0)
        self.assertIn('Detalhe Comercial Reserva: consulta recusada ou indisponível; HTTP 403.', out.getvalue())
        for forbidden in ['87654321', 'https://', 'PRIVATE', 'SECRET']:
            self.assertNotIn(forbidden, out.getvalue())


if __name__ == '__main__': unittest.main()
