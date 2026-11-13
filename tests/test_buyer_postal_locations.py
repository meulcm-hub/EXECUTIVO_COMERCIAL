import contextlib
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import buyer_postal_locations as geo


def row(client,cep='35702265',project='Residencial Village Lagoas',**extra):
    return {'idcliente':client,'empreendimento':project,'cep_cliente':cep,**extra}


def payload(cep='35702265',**extra):
    return {'cep':cep,'city':'Sete Lagoas','state':'MG','address_type':'Rua','address_name':'Suíssa',
            'address':'Rua Suíssa','district':'Nova Cidade','lat':'-19.4246046','lng':'-44.2330108',**extra}


def point(cep='35702265',**extra):
    return {'status':'confirmed',**geo.postal_metadata(payload(cep),cep),**extra}


class PostalBuyerTests(unittest.TestCase):
    def test_cep_normalization_preserves_explicit_leading_zero(self):
        self.assertEqual(geo.postal_code('01310-100'),'01310100')
        self.assertEqual(geo.postal_code('01310100'),'01310100')
        for invalid in (1310100,1310100.0,'1310100','00000000','99999999','35702-265 house',True,None):
            self.assertIsNone(geo.postal_code(invalid))

    def test_only_workbook_customer_and_project_universe_counts(self):
        universe={(str(i),'residencial village lagoas'):{'cities':{'sete lagoas'}} for i in range(1,7)}
        records=[row(i) for i in range(1,7)]+[row(1),row(1),row(999),row(1,project='Outro empreendimento')]
        counts,coverage,_=geo.aggregate_reservations(records,universe)
        self.assertEqual(counts,{('residencial village lagoas','35702265'):6})
        self.assertEqual(coverage['matched_buyer_project_pairs'],6)
        self.assertEqual(coverage['eligible_postal_project_groups'],1)

    def test_conflicting_postal_codes_are_not_chosen_arbitrarily(self):
        universe={('1','p'):{'cities':set()},('2','p'):{'cities':set()}}
        counts,coverage,_=geo.aggregate_reservations([row(1,project='p'),row(1,'35702260',project='p'),row(2,None,project='p')],universe)
        self.assertFalse(counts)
        self.assertEqual(coverage['buyers_conflicting_postal_code'],1)
        self.assertEqual(coverage['buyers_missing_postal_code'],1)

    def test_distinct_postal_groups_remain_available_without_city_threshold(self):
        universe={('1','p'):{'cities':set()},('2','p'):{'cities':set()}}
        counts,coverage,_=geo.aggregate_reservations([row(1,project='p'),row(2,'35702260',project='p')],universe)
        self.assertEqual(len(counts),2)
        self.assertEqual(coverage['eligible_postal_project_groups'],2)
        self.assertEqual(coverage['suppressed_postal_project_groups'],0)

    def test_generic_unit_postcode_is_not_treated_as_buyer_postcode(self):
        self.assertEqual(geo.buyer_postal_codes({'cep':'35702265','unidade':{'cep':'35702260'}}),set())
        self.assertEqual(geo.buyer_postal_codes({'cliente':{'endereco':{'cep':'01310-100'}}}),{'01310100'})
        self.assertEqual(geo.buyer_postal_codes({'cliente_cep':'35702-265'}),{'35702265'})

    def test_workbook_ids_and_projects_are_deduplicated_without_names(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'source.xlsx';book=Workbook();sheet=book.active;sheet.title='Perfil Público - Fonte'
            sheet.append(['Id. Cliente','Empreendimento','Cidade','Cliente'])
            sheet.append([12,'Projeto Árvore','Sete Lagoas','PRIVATE PERSON']);sheet.append([12,'Projeto Arvore','Sete Lagoas','PRIVATE PERSON'])
            book.save(file)
            self.assertEqual(geo.buyer_universe(file),{('12','projeto arvore'):{'cities':{'sete lagoas'}}})

    def test_full_pagination_and_repetition_guard(self):
        pages={1:{'dados':[row(1),row(2)],'total_de_paginas':2},2:{'dados':[row(3)],'total_de_paginas':2}}
        self.assertEqual(len(list(geo.read_reservations(pages.__getitem__,page_size=2,pause=0))),3)
        with self.assertRaisesRegex(RuntimeError,'repetida'):
            list(geo.read_reservations(lambda p:{'dados':[row(1)],'total_de_paginas':2},page_size=1,pause=0))
        with self.assertRaisesRegex(RuntimeError,'vazia'):
            list(geo.read_reservations(lambda p:pages[1] if p==1 else {'dados':[],'total_de_paginas':2},page_size=2,pause=0))
        with self.assertRaisesRegex(RuntimeError,'mudou'):
            list(geo.read_reservations(lambda p:{'dados':[row(p)],'total_de_paginas':2 if p==1 else 3},page_size=1,pause=0))

    def test_unbounded_or_malformed_page_count_fails(self):
        with self.assertRaisesRegex(RuntimeError,'excedida'):
            list(geo.read_reservations(lambda p:{'dados':[row(1)],'total_de_paginas':1000},max_pages=3,pause=0))
        for bad in ('secret text',-1,False):
            with self.assertRaises(RuntimeError):geo.page_rows({'dados':[],'total_de_paginas':bad})
        with self.assertRaises(RuntimeError):geo.page_rows({'dados':['private raw text']})

    def test_postal_geocoder_requires_exact_cep_ordinary_road_city_state_and_coords(self):
        self.assertIsNotNone(geo.postal_metadata(payload(),'35702265'))
        bad=[payload(cep='35702260'),payload(address_type='Condomínio'),payload(address_name=''),payload(state='XX'),
             payload(city=''),payload(lat='NaN'),payload(lng='-100'),payload(lat=True),payload(precision='city'),
             payload(address='Edifício Residencial'),payload(address_type='',address_name='',address='')]
        for value in bad:self.assertIsNone(geo.postal_metadata(value,'35702265'))

    def test_public_projection_whitelist_and_positive_cep_group_size(self):
        counts={('p','35702265'):1,('empty','35702265'):0}
        cache={'postal_codes':{'35702265':point()}}
        report=geo.build_report(counts,{}, {},cache)
        self.assertEqual(len(report['postal_codes']),1)
        self.assertEqual(set(report['postal_codes'][0]),{'project','postal_code','city','uf','lat','lng','count','precision'})
        self.assertNotIn('address',json.dumps(report));self.assertNotIn('idcliente',json.dumps(report))
        self.assertNotIn('Suíssa',json.dumps(report));self.assertEqual(report['coverage']['min_group_size'],1)
        self.assertEqual(report['postal_codes'][0]['count'],1)

    def test_city_hint_mismatch_is_not_silently_mapped(self):
        report=geo.build_report({('p','35702265'):5},{},{('p','35702265'):{'goiania'}},{'postal_codes':{'35702265':point()}})
        self.assertEqual(report['postal_codes'],[])

    def test_reused_municipal_coordinate_for_distinct_streets_is_rejected(self):
        first=point();second=point('35702260',road_digest='f'*16)
        report=geo.build_report({('p','35702265'):5,('p','35702260'):6},{},{},{'postal_codes':{'35702265':first,'35702260':second}})
        self.assertEqual(report['postal_codes'],[])
        self.assertEqual(report['coverage']['ambiguous_coordinate_postal_groups'],2)

    def test_cache_only_mode_does_not_query_a_geocoder(self):
        with patch.object(geo,'geocode_postal_code') as call:
            geo.refresh_cache({'postal_codes':{}},{'35702265'})
            call.assert_not_called()

    def test_cache_does_not_accept_old_unverified_city_points(self):
        old={'status':'confirmed','postal_code':'35702265','city':'Sete Lagoas','uf':'MG','lat':-19.46,'lng':-44.24,'precision':'postal_code'}
        self.assertFalse(geo.valid_cached_point(old,'35702265'))
        result=geo.build_report({('p','35702265'):5},{},{},{'postal_codes':{'35702265':old}})
        self.assertEqual(result['postal_codes'],[])

    def test_encrypted_transport_roundtrip_contains_only_anonymous_aggregates(self):
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        private=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        public=private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        coverage={'buyer_project_pairs':5,'private_name':'PRIVATE BUYER','idcliente':'secret-id'}
        capture=io.StringIO()
        with contextlib.redirect_stdout(capture):
            envelope=geo.encrypt_transport({('test public project','35702265'):5},coverage,
                {('test public project','35702265'):{'Sete Lagoas'}},public)
        self.assertEqual(capture.getvalue(),'')
        encoded=json.dumps(envelope)
        self.assertNotIn('35702265',encoded);self.assertNotIn('test public project',encoded)
        self.assertNotIn('PRIVATE BUYER',encoded);self.assertEqual(envelope['alg'],geo.TRANSPORT_ALGORITHM)
        key=private.decrypt(base64.b64decode(envelope['key']),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
        self.assertEqual(len(key),32);self.assertEqual(len(base64.b64decode(envelope['nonce'])),12)
        clear=AESGCM(key).decrypt(base64.b64decode(envelope['nonce']),base64.b64decode(envelope['ciphertext']),geo.TRANSPORT_AAD)
        data=json.loads(clear)
        self.assertEqual(data,{'schema_version':1,'groups':[{'project':'test public project','postal_code':'35702265','count':5,'cities':['sete lagoas']}],
                               'coverage':{'buyer_project_pairs':5}})
        self.assertNotIn('idcliente',clear.decode());self.assertNotIn('private_name',clear.decode())
        with self.assertRaises(Exception):AESGCM(key).decrypt(base64.b64decode(envelope['nonce']),base64.b64decode(envelope['ciphertext']),b'wrong context')

    def test_transport_rejects_wrong_or_weak_public_keys_and_private_pem(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec, rsa
        keys=[ec.generate_private_key(ec.SECP256R1()).public_key(),rsa.generate_private_key(public_exponent=65537,key_size=2048).public_key()]
        for key in keys:
            pem=key.public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
            with self.assertRaises(ValueError):geo.encrypt_transport({}, {}, {}, pem)
        with self.assertRaises(ValueError):geo.encrypt_transport({}, {}, {}, b'invalid public key')
        private=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        pem=private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        with self.assertRaises(ValueError):geo.encrypt_transport({}, {}, {}, pem)

    def test_transport_cli_arguments_are_required_together(self):
        for args in (['--transport-public-key','public.pem'],['--encrypted-transport','data.enc.json']):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:geo.main(args)
            self.assertEqual(caught.exception.code,2)

    def test_credentials_pin_host_and_never_echo_secret(self):
        env={'CVCRM_DOMINIO':'https://lcm.cvcrm.com.br','CVCRM_EMAIL':'private@example.com','CVCRM_TOKEN':'PRIVATE TOKEN'}
        self.assertEqual(geo.credentials(env)[0],'https://lcm.cvcrm.com.br')
        for domain in ('https://attacker.test','http://lcm.cvcrm.com.br','https://lcm.cvcrm.com.br/private','https://user:pass@lcm.cvcrm.com.br','https://lcm.cvcrm.com.br:123'):
            with self.assertRaisesRegex(RuntimeError,'domínio') as caught:geo.credentials({**env,'CVCRM_DOMINIO':domain})
            self.assertNotIn('PRIVATE',str(caught.exception));self.assertNotIn('attacker',str(caught.exception))


if __name__=='__main__':unittest.main()
