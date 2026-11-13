#!/usr/bin/env python3
"""Confere campos de residência na reserva sem registrar valores ou identificadores.

A resposta da API permanece apenas em memória. O relatório contém nomes canônicos
fixos e contagens de uma amostra de no máximo dez reservas por endpoint.
"""
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

SAMPLE_SIZE = 10
MAX_BODY_BYTES = 4 * 1024 * 1024
BUYERS = frozenset(('cliente', 'clientes', 'comprador', 'compradores', 'pessoa',
                    'pessoas', 'titular', 'titulares', 'proponente', 'proponentes',
                    'dadoscliente', 'dadoscomprador', 'dadospessoa'))
ADDRESSES = frozenset(('endereco', 'enderecos', 'address', 'addresses',
                       'enderecoresidencial', 'enderecocorrespondencia'))
FIELDS = {
    'logradouro': ('logradouro', 'rua', 'endereco', 'street', 'addressline1'),
    'numero': ('numero', 'numeroendereco', 'numeroresidencial', 'number'),
    'complemento': ('complemento', 'addressline2'),
    'bairro': ('bairro', 'neighborhood', 'neighbourhood'),
    'cidade': ('cidade', 'municipio', 'city'),
    'uf': ('uf', 'estado', 'state'),
    'cep': ('cep', 'zipcode', 'postalcode'),
    'latitude': ('latitude', 'lat'),
    'longitude': ('longitude', 'lng', 'lon'),
}
BUYER_CONTAINERS = {
    'cliente': ('cliente', 'clientes'),
    'comprador': ('comprador', 'compradores'),
    'pessoa': ('pessoa', 'pessoas'),
    'titular': ('titular', 'titulares'),
    'proponente': ('proponente', 'proponentes'),
    'dados_cliente': ('dadoscliente',),
    'dados_comprador': ('dadoscomprador',),
    'dados_pessoa': ('dadospessoa',),
}
LINK_FIELDS = ('idpessoa', 'idcliente', 'idtitular')
BUYER_PREFIXES = ('cliente', 'comprador', 'pessoa', 'titular', 'proponente')


def norm(value):
    text = unicodedata.normalize('NFKD', str(value)).casefold()
    return ''.join(c for c in text if c.isalnum() and not unicodedata.combining(c))


def scalar_present(value):
    return isinstance(value, (str, int, float)) and not isinstance(value, bool) and str(value).strip() != ''


def address_fields(value):
    if not isinstance(value, dict):
        return set()
    keys = {norm(key): item for key, item in value.items()}
    return {name for name, aliases in FIELDS.items()
            if any(scalar_present(keys.get(alias)) for alias in aliases)}


def qualified_root_candidates(record):
    """Flat fields need an explicit buyer prefix/suffix, never generic address keys."""
    keys = {norm(key): item for key, item in record.items()}
    return [{name for name, aliases in FIELDS.items()
             if any(scalar_present(keys.get(alias + prefix))
                    or scalar_present(keys.get(prefix + alias)) for alias in aliases)}
            for prefix in BUYER_PREFIXES]


def qualified_root_fields(record):
    return set().union(*qualified_root_candidates(record))


def objects(value):
    if isinstance(value, dict):
        yield value
    elif isinstance(value, list):
        yield from (item for item in value[:SAMPLE_SIZE] if isinstance(item, dict))


def buyer_addresses(record):
    """Only explicit buyer containers qualify; project/unit addresses never do."""
    candidates = qualified_root_candidates(record)
    for key, value in record.items():
        if norm(key) not in BUYERS:
            continue
        for buyer in objects(value):
            candidates.append(address_fields(buyer))
            for address_key, address in buyer.items():
                if norm(address_key) in ADDRESSES:
                    candidates.extend(address_fields(item) for item in objects(address))
    return [item for item in candidates if item]


def rows(payload):
    if isinstance(payload, list):
        data = payload
    elif isinstance(payload, dict):
        data = None
        for key in ('dados', 'data', 'reservas'):
            if key in payload:
                data = payload[key]
                break
        if data is None:
            numeric = [value for key, value in payload.items() if str(key).isdigit()]
            if numeric or not payload:
                data = numeric
            else:
                raise ValueError('unexpected schema')
        if isinstance(data, dict):
            if all(str(key).isdigit() for key in data):
                data = list(data.values())
            elif any(norm(key) in BUYERS or norm(key) in ('idreserva', 'id') for key in data):
                data = [data]
            else:
                raise ValueError('unexpected schema')
    else:
        raise ValueError('unexpected schema')
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data[:SAMPLE_SIZE]):
        raise ValueError('unexpected schema')
    return data[:SAMPLE_SIZE]


def summarize(records):
    summary = {'reservas_na_amostra': len(records), 'residencia_em_contexto_cliente': 0,
               'logradouro_numero_cidade_uf_no_mesmo_endereco': 0,
               'endereco_principal_sem_contexto_cliente': 0,
               'campos_cliente': {name: 0 for name in FIELDS},
               'campos_principais': {name: 0 for name in FIELDS},
               'campos_cliente_qualificados_na_raiz': {name: 0 for name in FIELDS},
               'vinculos_cliente': {name: 0 for name in LINK_FIELDS},
               'conteineres_cliente': {name: 0 for name in BUYER_CONTAINERS}}
    for record in records:
        normalized = {norm(key): value for key, value in record.items()}
        for name in address_fields(record):
            summary['campos_principais'][name] += 1
        for name in qualified_root_fields(record):
            summary['campos_cliente_qualificados_na_raiz'][name] += 1
        for name in LINK_FIELDS:
            summary['vinculos_cliente'][name] += int(scalar_present(normalized.get(name)))
        for name, aliases in BUYER_CONTAINERS.items():
            summary['conteineres_cliente'][name] += int(any(
                alias in normalized and (isinstance(normalized[alias], (dict, list))
                                         or scalar_present(normalized[alias]))
                for alias in aliases))
        candidates = buyer_addresses(record)
        fields = set().union(*candidates) if candidates else set()
        if fields:
            summary['residencia_em_contexto_cliente'] += 1
        if any({'logradouro', 'numero', 'cidade', 'uf'} <= item for item in candidates):
            summary['logradouro_numero_cidade_uf_no_mesmo_endereco'] += 1
        # Flat address data is ambiguous: it may refer to a purchased unit.
        ambiguous = bool(address_fields(record))
        for key, value in record.items():
            if norm(key) in ADDRESSES and any(address_fields(item) for item in objects(value)):
                ambiguous = True
        summary['endereco_principal_sem_contexto_cliente'] += int(ambiguous)
        for name in fields:
            summary['campos_cliente'][name] += 1
    return summary


def credentials(environ):
    base = environ.get('CVCRM_DOMINIO', '').strip().rstrip('/')
    email = environ.get('CVCRM_EMAIL', '').strip()
    token = environ.get('CVCRM_TOKEN', '').strip()
    url = urllib.parse.urlsplit(base)
    if (url.scheme != 'https' or url.hostname != 'lcm.cvcrm.com.br' or url.port not in (None, 443)
            or url.path not in ('', '/') or url.query or url.fragment or url.username or url.password
            or not email or not token):
        raise ValueError('invalid credentials')
    return base, email, token


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_payload(opener, request):
    with opener.open(request, timeout=30) as response:
        if response.status == 204:
            return []
        if response.status != 200 or 'json' not in response.headers.get('Content-Type', '').lower():
            raise ValueError('unexpected response')
        body = response.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise ValueError('oversize response')
        return json.loads(body)


def fetch(opener, base, email, token, path, commercial=False):
    params = {'pagina': 1, 'registros_por_pagina': SAMPLE_SIZE}
    if commercial:
        params.update({'faturar': 'false', 'retornar_integradas': 'true'})
    request = urllib.request.Request(base + path + '?' + urllib.parse.urlencode(params),
                                     headers={'email': email, 'token': token, 'Accept': 'application/json'})
    return rows(read_payload(opener, request))


def positive_reservation_id(value):
    # A path segment must never accept a URL, sign, float, bool or arbitrary text.
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError('invalid reservation identifier')
    value = str(value)
    if not re.fullmatch(r'[0-9]{1,20}', value) or int(value) <= 0:
        raise ValueError('invalid reservation identifier')
    return str(int(value))


def first_reservation_id(records):
    for record in records[:1]:
        for key, value in record.items():
            if norm(key) == 'idreserva':
                try:
                    return positive_reservation_id(value)
                except ValueError:
                    continue
    return None


def detail_rows(payload):
    """Detail endpoint may return a single reservation without a list wrapper."""
    if isinstance(payload, dict):
        for key in ('dados', 'data', 'reserva'):
            if key in payload:
                return detail_rows(payload[key])
        if (any(norm(key) in BUYERS or norm(key) == 'idreserva' for key in payload)
                or address_fields(payload) or qualified_root_fields(payload)):
            return [payload]
    return rows(payload)


def fetch_reservation_detail(opener, base, email, token, reservation_id):
    reservation_id = positive_reservation_id(reservation_id)
    request = urllib.request.Request(base + '/api/v1/comercial/reservas/' + reservation_id,
                                     headers={'email': email, 'token': token, 'Accept': 'application/json'})
    return detail_rows(read_payload(opener, request))


def main(environ=None, opener=None):
    try:
        base, email, token = credentials(os.environ if environ is None else environ)
    except (ValueError, TypeError):
        print('CV CRM: credenciais indisponíveis ou domínio inesperado.')
        return 2
    opener = opener or urllib.request.build_opener(NoRedirect())
    successful = 0
    reservation_id = None
    for label, path, commercial in (
            ('CVDW Reservas', '/api/v1/cvdw/reservas', False),
            ('Comercial Reservas', '/api/v1/comercial/reservas', True)):
        try:
            records = fetch(opener, base, email, token, path, commercial)
            report = summarize(records)
            if not commercial:
                reservation_id = first_reservation_id(records)
        except urllib.error.HTTPError as error:
            print(label + ': consulta recusada ou indisponível; HTTP ' + str(int(error.code)) + '.')
            continue
        except (urllib.error.URLError, TimeoutError, ValueError, TypeError, OSError, OverflowError):
            print(label + ': consulta incompleta ou estrutura inesperada; nenhum dado exibido.')
            continue
        successful += 1
        print(label + ': ' + json.dumps(report, ensure_ascii=False, sort_keys=True))
    if reservation_id is not None:
        label = 'Detalhe Comercial Reserva'
        try:
            records = fetch_reservation_detail(opener, base, email, token, reservation_id)
            print(label + ': ' + json.dumps(summarize(records), ensure_ascii=False, sort_keys=True))
            successful += 1
        except urllib.error.HTTPError as error:
            print(label + ': consulta recusada ou indisponível; HTTP ' + str(int(error.code)) + '.')
        except (urllib.error.URLError, TimeoutError, ValueError, TypeError, OSError, OverflowError):
            print(label + ': consulta incompleta ou estrutura inesperada; nenhum dado exibido.')
    else:
        print('Detalhe Comercial Reserva: não consultado; identificador válido indisponível na amostra CVDW.')
    print('Diagnóstico limitado à amostra; nenhum endereço, identificador ou valor pessoal foi publicado.')
    return 0 if successful else 1


if __name__ == '__main__':
    sys.exit(main())
