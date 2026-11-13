#!/usr/bin/env python3
"""Project buyer CEP aggregates. Customer identifiers exist only in process memory.

Coordinates describe an approximate street/postal area from AwesomeAPI.
They are never described as an individual home or a house-number location.
"""
import argparse
import base64
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
MIN_GROUP_SIZE = 1
PAGE_SIZE = 500
MAX_PAGES = 200
MAX_BODY_BYTES = 32 * 1024 * 1024
USER_AGENT = 'LCM-Postal-Map/1.0 (https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL)'
STATES = dict(zip(
    'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split(),
    ['Acre','Alagoas','Amapá','Amazonas','Bahia','Ceará','Distrito Federal','Espírito Santo','Goiás','Maranhão','Mato Grosso','Mato Grosso do Sul','Minas Gerais','Pará','Paraíba','Paraná','Pernambuco','Piauí','Rio de Janeiro','Rio Grande do Norte','Rio Grande do Sul','Rondônia','Roraima','Santa Catarina','São Paulo','Sergipe','Tocantins']))
BUYER_KEYS = {'cliente','clientes','comprador','compradores','titular','titulares','pessoa','pessoas','dadoscliente'}


def normalize(value):
    text = unicodedata.normalize('NFKD', str(value or '')).casefold()
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in text if not unicodedata.combining(c)).split())


def field_key(value):
    return normalize(value).replace(' ', '')


def label(value):
    return ' '.join(str(value or '').strip().split())[:180]


def identity(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        return str(int(value)) if math.isfinite(value) and value > 0 and value.is_integer() else None
    text = str(value or '').strip()
    return str(int(text)) if re.fullmatch(r'[0-9]{1,20}', text) and int(text) > 0 else None


def postal_code(value):
    """Never pad an unknown leading zero that has already been lost."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    if not re.fullmatch(r'[0-9]{5}-?[0-9]{3}', text):
        return None
    text = text.replace('-', '')
    return text if len(set(text)) > 1 else None


def normalized_fields(row):
    return {field_key(key): value for key, value in row.items()}


def row_identity_project(row):
    fields = normalized_fields(row)
    client = identity(fields.get('idcliente', fields.get('clienteid')))
    project = fields.get('empreendimento')
    if isinstance(project, dict):
        project = project.get('nome') or project.get('empreendimento')
    if not isinstance(project, str):
        project = ''
    return client, normalize(project)


def buyer_postal_codes(row):
    """Generic root CEP might belong to a unit; only buyer-qualified CEP is used."""
    fields = normalized_fields(row)
    candidates = []
    for prefix in ('cliente', 'comprador', 'pessoa', 'titular', 'proponente'):
        candidates.extend(fields.get(key) for key in ('cep'+prefix, prefix+'cep'))
    for key, value in fields.items():
        if key not in BUYER_KEYS:
            continue
        buyers = value if isinstance(value, list) else [value]
        for buyer in buyers:
            if not isinstance(buyer, dict):
                continue
            values = normalized_fields(buyer)
            candidates.extend(values.get(key) for key in ('cep','zipcode','postalcode'))
            for address_key in ('endereco','enderecos','enderecoresidencial','enderecocorrespondencia'):
                addresses = values.get(address_key)
                for address in addresses if isinstance(addresses, list) else [addresses]:
                    if isinstance(address, dict):
                        values2 = normalized_fields(address)
                        candidates.extend(values2.get(key) for key in ('cep','zipcode','postalcode'))
    return {cep for value in candidates if (cep := postal_code(value))}


def buyer_universe(path):
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        rows = book['Perfil Público - Fonte'].iter_rows(values_only=True)
        headers = {str(value or '').strip(): i for i, value in enumerate(next(rows))}
        if not {'Id. Cliente','Empreendimento'} <= headers.keys():
            raise RuntimeError('Colunas de vínculo dos compradores ausentes')
        universe = {}
        for row in rows:
            client, project = identity(row[headers['Id. Cliente']]), normalize(row[headers['Empreendimento']])
            if not client or not project:
                continue
            item = universe.setdefault((client, project), {'cities': set()})
            if 'Cidade' in headers and headers['Cidade'] < len(row) and normalize(row[headers['Cidade']]):
                item['cities'].add(normalize(row[headers['Cidade']]))
        return universe
    finally:
        book.close()


def aggregate_reservations(records, universe):
    candidates = defaultdict(set)
    matched = set()
    coverage = Counter(buyer_project_pairs=len(universe))
    city_hints = defaultdict(set)
    for row in records:
        coverage['reservation_rows_read'] += 1
        client, project = row_identity_project(row)
        key = (client, project)
        if key not in universe:
            continue
        matched.add(key)
        candidates[key].update(buyer_postal_codes(row))
    counts = Counter()
    for key in universe:
        values = candidates.get(key, set())
        if not values:
            coverage['buyers_missing_postal_code'] += 1
        elif len(values) != 1:
            coverage['buyers_conflicting_postal_code'] += 1
        else:
            cep = next(iter(values))
            counts[(key[1], cep)] += 1
            city_hints[(key[1], cep)].update(universe[key].get('cities', set()))
            coverage['buyers_with_postal_code'] += 1
    coverage['matched_buyer_project_pairs'] = len(matched)
    coverage['postal_project_groups'] = len(counts)
    coverage['eligible_postal_project_groups'] = sum(n >= MIN_GROUP_SIZE for n in counts.values())
    coverage['suppressed_postal_project_groups'] = sum(n < MIN_GROUP_SIZE for n in counts.values())
    return counts, dict(coverage), city_hints


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def credentials(environ=None):
    environ = os.environ if environ is None else environ
    base = environ.get('CVCRM_DOMINIO','').strip().rstrip('/')
    email, token = environ.get('CVCRM_EMAIL','').strip(), environ.get('CVCRM_TOKEN','').strip()
    try:
        url = urllib.parse.urlsplit(base)
        valid = (url.scheme == 'https' and url.hostname == 'lcm.cvcrm.com.br' and url.port in (None,443)
                 and url.path in ('','/') and not url.query and not url.fragment and not url.username and not url.password)
    except ValueError:
        valid = False
    if not valid or not email or not token:
        raise RuntimeError('Credenciais CV CRM indisponíveis ou domínio inesperado')
    return base, email, token


def read_json(opener, request, max_bytes=MAX_BODY_BYTES):
    with opener.open(request, timeout=45) as response:
        if response.status == 204:
            return None
        if response.status != 200 or 'json' not in response.headers.get('Content-Type','').lower():
            raise RuntimeError('Resposta JSON esperada não foi recebida')
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise RuntimeError('Resposta excedeu o limite de leitura')
        return json.loads(body)


def crm_page(base, email, token, page, *, opener=None):
    request = urllib.request.Request(base+'/api/v1/cvdw/reservas?'+urllib.parse.urlencode({'pagina':page,'registros_por_pagina':PAGE_SIZE}),
                                     headers={'email':email,'token':token,'Accept':'application/json'})
    opener = opener or urllib.request.build_opener(NoRedirect())
    for attempt in range(4):
        try:
            return read_json(opener, request)
        except urllib.error.HTTPError as error:
            status = int(error.code)
            if status not in (429,500,502,503,504) or attempt == 3:
                raise RuntimeError('Consulta de reservas indisponível; HTTP '+str(status)) from None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            if attempt == 3:
                raise RuntimeError('Consulta de reservas não foi concluída') from None
        time.sleep(min(15,2**(attempt+1)))
    raise RuntimeError('Consulta de reservas não foi concluída')


def page_rows(payload):
    if payload is None:
        return [], None
    if not isinstance(payload, dict):
        raise RuntimeError('Formato de reservas inesperado')
    data = next((payload[key] for key in ('dados','data','reservas') if key in payload), None)
    if data is None:
        data = {key:value for key,value in payload.items() if str(key).isdigit()}
        if not data and payload:
            raise RuntimeError('Coleção de reservas não identificada')
    if isinstance(data, dict):
        data = list(data.values())
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise RuntimeError('Registros de reservas inesperados')
    pages = payload.get('total_de_paginas',payload.get('totalPaginas'))
    if pages is None and isinstance(payload.get('pagination'), dict):
        pages = payload['pagination'].get('totalPaginas')
    if pages is not None:
        if isinstance(pages,bool) or not re.fullmatch(r'[0-9]+',str(pages)) or int(pages)<0:
            raise RuntimeError('Total de páginas inválido')
        pages = int(pages)
    return data, pages


def read_reservations(fetch_page, *, page_size=PAGE_SIZE, max_pages=MAX_PAGES, pause=0.5):
    seen = set()
    expected_pages = None
    for page in range(1,max_pages+1):
        if page > 1 and pause:
            time.sleep(pause)
        records, pages = page_rows(fetch_page(page))
        if pages is not None:
            if expected_pages is not None and pages != expected_pages:
                raise RuntimeError('Total de páginas mudou durante a consulta')
            expected_pages = pages
        if not records:
            if expected_pages is not None and expected_pages >= page and expected_pages != 0:
                raise RuntimeError('Página vazia antes de completar o histórico')
            return
        if expected_pages is not None and (expected_pages < page or expected_pages > max_pages):
            raise RuntimeError('Cobertura de páginas inválida ou excedida')
        signature = hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode()).digest()
        if signature in seen:
            raise RuntimeError('Paginação repetida; histórico não será publicado')
        seen.add(signature)
        yield from records
        if expected_pages is not None and page == expected_pages:
            return
        if expected_pages is None and len(records)<page_size:
            return
    raise RuntimeError('Limite de páginas alcançado sem cobertura completa')


def valid_coordinates(lat,lng):
    return (not isinstance(lat,bool) and not isinstance(lng,bool) and isinstance(lat,(int,float)) and isinstance(lng,(int,float))
            and math.isfinite(lat) and math.isfinite(lng) and -34 <= lat <= 6 and -74 <= lng <= -32)


def postal_metadata(payload, cep):
    """Only a CEP-specific ordinary-road result qualifies; city fallbacks do not."""
    if not isinstance(payload,dict) or postal_code(payload.get('cep')) != cep:
        return None
    city,uf,road_type,road_name,address = (label(payload.get(key)) for key in ('city','state','address_type','address_name','address'))
    allowed_roads={'rua','avenida','av','travessa','alameda','estrada','rodovia','beco','viela','largo','praca','parque','passagem','loteamento','via','quadra','acesso','calcada','servidao','caminho'}
    if not city or uf not in STATES or normalize(road_type) not in allowed_roads or not road_name or not address:
        return None
    if any(str(payload.get(key,'')).casefold() in {'city','municipality','cidade','municipio'} for key in ('precision','location_type','feature_type')):
        return None
    # Do not accept a provider entry that contradicts its own road metadata.
    expected=normalize(road_type+' '+road_name)
    if normalize(address)!=expected:
        return None
    try:
        if isinstance(payload.get('lat'),bool) or isinstance(payload.get('lng'),bool):
            return None
        lat,lng=float(payload['lat']),float(payload['lng'])
    except (KeyError,ValueError,TypeError):
        return None
    if not valid_coordinates(lat,lng):
        return None
    return {'postal_code':cep,'city':city,'uf':uf,'lat':lat,'lng':lng,'precision':'postal_code',
            'coordinate_method':'approximate_postal_street','postal_match':True,'street_available':True,
            'road_digest':hashlib.sha256((expected+'|'+normalize(city)+'|'+uf).encode()).hexdigest()[:16]}


def geocode_postal_code(cep, *, opener=None):
    if postal_code(cep) != cep:
        raise RuntimeError('CEP inválido para consulta geográfica')
    request=urllib.request.Request('https://cep.awesomeapi.com.br/json/'+cep,headers={'User-Agent':USER_AGENT,'Accept':'application/json'})
    payload=read_json(opener or urllib.request.build_opener(NoRedirect()),request,max_bytes=1024*1024)
    return postal_metadata(payload,cep)


def valid_cached_point(point,cep):
    return (isinstance(point,dict) and point.get('status')=='confirmed' and point.get('postal_code')==cep
            and point.get('precision')=='postal_code' and point.get('postal_match') is True
            and point.get('street_available') is True and point.get('coordinate_method')=='approximate_postal_street'
            and isinstance(point.get('road_digest'),str) and re.fullmatch(r'[0-9a-f]{16}',point['road_digest']) is not None
            and point.get('uf') in STATES and bool(label(point.get('city')))
            and valid_coordinates(point.get('lat'),point.get('lng')))


def load_cache(path):
    if not path.exists():
        return {'schema_version':1,'postal_codes':{}}
    cache=json.loads(path.read_text())
    if cache.get('schema_version')!=1 or not isinstance(cache.get('postal_codes'),dict):
        raise RuntimeError('Cache postal inválido')
    return cache


def refresh_cache(cache,ceps,*,geocode=False,one_time=False,max_requests=60,lookup=geocode_postal_code):
    if not geocode:
        return
    last=None
    for cep in sorted(ceps):
        if max_requests<=0:
            break
        existing=cache['postal_codes'].get(cep)
        if valid_cached_point(existing,cep):
            continue
        # A previous deterministic no-match can remain pending without repeating a public service request.
        if isinstance(existing,dict) and existing.get('status')=='unresolved':
            continue
        if last is not None:
            time.sleep(max(0,1.1-(time.monotonic()-last)))
        last=time.monotonic();max_requests-=1
        fatal=False
        try:
            point=lookup(cep)
            entry={'status':'confirmed' if point else 'unresolved',**(point or {})}
        except urllib.error.HTTPError as error:
            entry={'status':'unavailable','http_status':int(error.code)};fatal=error.code in (403,429)
        except (urllib.error.URLError,TimeoutError,ValueError,RuntimeError,OSError):
            entry={'status':'unavailable'};fatal=True
        cache['postal_codes'][cep]={**entry,'checked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
        print('Consultas geográficas concluídas: 1; resultado: '+entry['status']+'.',flush=True)
        if fatal:
            print('Serviço geográfico indisponível; consultas interrompidas e cache confirmado preservado.',flush=True)
            break


def build_report(counts,coverage,city_hints,cache):
    points=[]
    # Reused city-center coordinates for different streets must not become CEP points.
    signatures=defaultdict(set)
    for cep,point in cache['postal_codes'].items():
        if valid_cached_point(point,cep):
            key=(normalize(point['city']),point['uf'],round(point['lat'],6),round(point['lng'],6))
            signatures[key].add(point['road_digest'])
    suspect={key for key,streets in signatures.items() if len(streets)>1}
    ambiguous=0
    for (project,cep),count in sorted(counts.items()):
        if count<MIN_GROUP_SIZE:
            continue
        point=cache['postal_codes'].get(cep)
        if not valid_cached_point(point,cep):
            continue
        coordinate_key=(normalize(point['city']),point['uf'],round(point['lat'],6),round(point['lng'],6))
        if coordinate_key in suspect:
            ambiguous+=1
            continue
        hints=city_hints.get((project,cep),set())
        if len(hints)==1 and normalize(point['city']) not in hints:
            continue
        points.append({'project':project,'postal_code':cep,'city':point['city'],'uf':point['uf'],
                       'lat':point['lat'],'lng':point['lng'],'count':count,'precision':'postal_code'})
    return {'schema_version':1,'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'source':{'system':'CV CRM CVDW reservas','universe':'Perfil Público - Fonte','coordinate_source':'AwesomeAPI CEP',
                      'coordinate_precision':'Localização aproximada da rua/região do CEP; não é residência individual'},
            'postal_codes':points,'coverage':{'min_group_size':MIN_GROUP_SIZE,**coverage,
                                             'published_postal_project_groups':len(points),'ambiguous_coordinate_postal_groups':ambiguous,
                                             'unresolved_eligible_postal_project_groups':sum(n>=MIN_GROUP_SIZE for n in counts.values())-len(points)}}


TRANSPORT_AAD = b'LCM-Buyer-Postal-Transport/v1'
TRANSPORT_ALGORITHM = 'RSA-OAEP-256+A256GCM'
COVERAGE_KEYS = frozenset((
    'buyer_project_pairs','reservation_rows_read','matched_buyer_project_pairs',
    'buyers_missing_postal_code','buyers_conflicting_postal_code','buyers_with_postal_code',
    'postal_project_groups','eligible_postal_project_groups','suppressed_postal_project_groups'))


def encrypt_transport(counts, coverage, hints, public_pem):
    """Wrap aggregate-only data for a designated local recipient; never writes plaintext.

    Envelope v1 uses RSA-3072 OAEP(SHA256, MGF1-SHA256, label=None) around a
    random AES-256 key. AES-GCM has a random 12-byte nonce and fixed TRANSPORT_AAD;
    ciphertext includes its authentication tag. All binary fields use standard base64.
    """
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        raise RuntimeError('Dependência de criptografia indisponível') from None
    if isinstance(public_pem, str):
        public_pem=public_pem.encode('ascii')
    public_key=serialization.load_pem_public_key(public_pem)
    if not isinstance(public_key,rsa.RSAPublicKey) or public_key.key_size != 3072:
        raise ValueError('Chave pública RSA-3072 necessária para o transporte')
    groups=[]
    for (project,cep),count in sorted(counts.items()):
        if (not isinstance(project,str) or not project or postal_code(cep)!=cep
                or isinstance(count,bool) or not isinstance(count,int) or count<MIN_GROUP_SIZE):
            raise ValueError('Agregado postal inválido para transporte')
        groups.append({'project':project,'postal_code':cep,'count':count,
                       'cities':sorted({normalize(city) for city in hints.get((project,cep),set()) if normalize(city)})})
    safe_coverage={key:value for key,value in coverage.items()
                   if key in COVERAGE_KEYS and isinstance(value,int) and not isinstance(value,bool) and value>=0}
    plaintext=json.dumps({'schema_version':1,'groups':groups,'coverage':safe_coverage},
                         ensure_ascii=False,separators=(',',':')).encode('utf-8')
    aes_key=AESGCM.generate_key(bit_length=256)
    nonce=os.urandom(12)
    encrypted=AESGCM(aes_key).encrypt(nonce,plaintext,TRANSPORT_AAD)
    wrapped_key=public_key.encrypt(aes_key,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                                     algorithm=hashes.SHA256(),label=None))
    encode=lambda value:base64.b64encode(value).decode('ascii')
    return {'schema_version':1,'alg':TRANSPORT_ALGORITHM,'key':encode(wrapped_key),
            'nonce':encode(nonce),'ciphertext':encode(encrypted)}


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    temp.replace(path)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook',type=Path,default=ROOT/'Planilha_Executivo_LCM_COM_RENDA_PERFIL_PUBLICO.xlsx')
    parser.add_argument('--output',type=Path,default=ROOT/'data/buyer-postal-locations.json')
    parser.add_argument('--cache',type=Path,default=ROOT/'data/buyer-postal-geocache.json')
    parser.add_argument('--geocode',action='store_true')
    parser.add_argument('--transport-public-key',type=Path)
    parser.add_argument('--encrypted-transport',type=Path)
    parser.add_argument('--one-time',action='store_true',help='Lote manual único; consultas de CEP usam intervalo mínimo de 1,1s')
    parser.add_argument('--max-requests',type=int,default=60)
    args=parser.parse_args(argv)
    if bool(args.transport_public_key) != bool(args.encrypted_transport):
        parser.error('Informe chave pública e saída criptografada juntas')
    if args.encrypted_transport and args.encrypted_transport.resolve() in {path.resolve() for path in (args.workbook,args.output,args.cache,args.transport_public_key)}:
        parser.error('A saída criptografada deve ter um caminho exclusivo')
    if args.one_time and not args.geocode or args.max_requests<0 or args.max_requests>(1000 if args.one_time else 60):
        parser.error('Configuração do lote geográfico inválida')
    universe=buyer_universe(args.workbook)
    if not universe:
        raise RuntimeError('Universo de compradores vazio; saída preservada')
    base,email,token=credentials()
    records=list(read_reservations(lambda page:crm_page(base,email,token,page)))
    if not records or not any(row_identity_project(row)[0] for row in records):
        raise RuntimeError('Reservas sem vínculos de compradores; saída preservada')
    counts,coverage,hints=aggregate_reservations(records,universe)
    print('Cobertura postal: '+json.dumps(coverage,sort_keys=True),flush=True)
    if args.transport_public_key:
        envelope=encrypt_transport(counts,coverage,hints,args.transport_public_key.read_bytes())
        write_json(args.encrypted_transport,envelope)
    cache=load_cache(args.cache)
    refresh_cache(cache,{cep for (_project,cep),n in counts.items() if n>=MIN_GROUP_SIZE},geocode=args.geocode,one_time=args.one_time,max_requests=args.max_requests)
    report=build_report(counts,coverage,hints,cache)
    write_json(args.output,report)
    write_json(args.cache,cache)
    print('Grupos de CEP publicados: '+str(len(report['postal_codes']))+'. Sem identificadores, nomes, números de imóveis ou endereços completos.',flush=True)
    return 0


if __name__=='__main__':
    try:
        sys.exit(main())
    except (RuntimeError,ValueError,KeyError,TypeError,OSError,urllib.error.URLError):
        print('Coleta postal não concluída; dados anteriores preservados. Nenhum conteúdo privado foi exibido.',file=sys.stderr)
        sys.exit(1)
