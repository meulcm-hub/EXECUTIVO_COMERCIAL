#!/usr/bin/env python3
"""Mapa público de localidades agregadas; identificadores existem só em memória.

O modo padrão usa somente geocodificações já verificadas no cache. A coleta
opcional consulta nomes de localidades, nunca nomes ou endereços de clientes.
"""
import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
import io
import json
import math
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
WORKBOOK = ROOT / 'Planilha_Executivo_LCM_COM_RENDA_PERFIL_PUBLICO.xlsx'
SHEET = 'Perfil Público - Fonte'
MIN_GROUP_SIZE = 5
NEIGHBORHOOD_TYPES = {'neighbourhood', 'neighborhood', 'suburb', 'quarter', 'city_district', 'borough', 'residential'}
CSV_BASE = 'https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/'
NOMINATIM = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'LCM-Buyer-Localities/1.0 (+https://github.com/meulcm-hub/EXECUTIVO_COMERCIAL)'
MISSING = {'', '-', '--', 'n/a', 'null', 'none', 'nao informado', 'nao informada', 'nao cadastrado', 'nao cadastrada'}


def normalize(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(value or '').strip().casefold())
                            if not unicodedata.combining(c)).split())


def label(value):
    return ' '.join(str(value or '').strip().split())[:180]


def http_text(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/csv'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode('utf-8-sig')


def municipality_index(municipalities_text, states_text):
    states = {row['codigo_uf']: row for row in csv.DictReader(io.StringIO(states_text.lstrip('\ufeff')))}
    cities = defaultdict(list)
    for row in csv.DictReader(io.StringIO(municipalities_text.lstrip('\ufeff'))):
        state = states.get(row['codigo_uf'])
        if state is None:
            raise RuntimeError('Município sem UF correspondente na fonte geográfica')
        lat, lng = float(row['latitude']), float(row['longitude'])
        if not valid_coordinates(lat, lng):
            raise RuntimeError('Coordenadas municipais inválidas')
        cities[normalize(row['nome'])].append({
            'city': label(row['nome']), 'uf': state['uf'], 'state': label(state['nome']),
            'lat': lat, 'lng': lng,
        })
    return dict(cities)


def valid_coordinates(lat, lng):
    return (isinstance(lat, (float, int)) and isinstance(lng, (float, int))
            and math.isfinite(lat) and math.isfinite(lng) and -34 <= lat <= 6 and -74 <= lng <= -32)


def workbook_rows(path=WORKBOOK):
    book = load_workbook(path, data_only=True, read_only=True)
    try:
        sheet = book[SHEET]
        rows = sheet.iter_rows(values_only=True)
        headers = {str(value or '').strip(): i for i, value in enumerate(next(rows))}
        required = ('Id. Cliente', 'Empreendimento', 'Cidade', 'Bairro')
        if not all(name in headers for name in required):
            raise RuntimeError('Colunas de localização ausentes na planilha de origem')
        for row in rows:
            yield {name: row[headers[name]] if headers[name] < len(row) else None for name in required}
    finally:
        book.close()


def aggregate_locations(rows, cities):
    """Deduplica cliente/projeto antes de suprimir grupos menores que cinco."""
    people = {}
    coverage = Counter()
    for row in rows:
        identity = str(row.get('Id. Cliente') or '').strip()
        project = normalize(row.get('Empreendimento'))
        if not identity or not project or project in MISSING:
            coverage['ignored_rows_without_key'] += 1
            continue
        coverage['source_rows'] += 1
        person = people.setdefault((project, identity), {'cities': set(), 'neighborhoods': defaultdict(set)})
        city, neighborhood = normalize(row.get('Cidade')), normalize(row.get('Bairro'))
        if city not in MISSING:
            person['cities'].add(city)
            if neighborhood not in MISSING:
                person['neighborhoods'][city].add(neighborhood)

    city_counts, neighborhood_counts = Counter(), Counter()
    per_project = defaultdict(Counter)
    for (project, _identity), person in people.items():
        coverage['customer_project_pairs'] += 1
        if not person['cities']:
            coverage['customers_missing_city'] += 1
            continue
        if len(person['cities']) != 1:
            coverage['customers_conflicting_city'] += 1
            continue
        city = next(iter(person['cities']))
        matches = cities.get(city, [])
        if len(matches) != 1:
            coverage['customers_unresolved_city'] += 1
            per_project[project]['unresolved_city_groups'] += 1
            continue
        city_counts[project, city] += 1
        neighborhoods = person['neighborhoods'][city]
        if not neighborhoods:
            coverage['customers_missing_neighborhood'] += 1
        elif len(neighborhoods) != 1:
            coverage['customers_conflicting_neighborhood'] += 1
        else:
            neighborhood_counts[project, city, next(iter(neighborhoods))] += 1

    for (project, _city), count in city_counts.items():
        per_project[project]['city_points' if count >= MIN_GROUP_SIZE else 'suppressed_city_groups'] += 1
    for (project, _city, _neighborhood), count in neighborhood_counts.items():
        if count < MIN_GROUP_SIZE:
            per_project[project]['suppressed_neighborhood_groups'] += 1
    return city_counts, neighborhood_counts, coverage, per_project


def cache_key(city, neighborhood):
    return normalize(city['city']) + '|' + city['uf'] + '|' + normalize(neighborhood)


def distance_km(lat1, lng1, lat2, lng2):
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlat, dlng = lat2-lat1, math.radians(lng2-lng1)
    part = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
    return 6371 * 2 * math.asin(min(1, math.sqrt(part)))


def verified_neighborhood(results, city, neighborhood):
    """Confere país, UF, cidade e nome do bairro; não aceita centro municipal."""
    matches = []
    if not isinstance(results, list):
        return None
    requested = normalize(neighborhood)
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get('address'), dict):
            continue
        feature_type = result.get('addresstype', result.get('type'))
        if feature_type not in NEIGHBORHOOD_TYPES:
            continue
        address = result['address']
        if str(address.get('country_code', '')).lower() != 'br':
            continue
        state_matches = (address.get('ISO3166-2-lvl4') == 'BR-' + city['uf']
                         or normalize(address.get('state')) == normalize(city['state']))
        localities = [address.get(key) for key in ('city', 'town', 'village', 'municipality', 'county')]
        if not state_matches or normalize(city['city']) not in {normalize(value) for value in localities}:
            continue
        district_matches = requested in {normalize(address.get(key)) for key in NEIGHBORHOOD_TYPES}
        if not district_matches:
            district_matches = (normalize(result.get('name')) == requested
                                and feature_type in NEIGHBORHOOD_TYPES)
        if not district_matches:
            continue
        try:
            lat, lng = float(result['lat']), float(result['lon'])
        except (ValueError, TypeError, KeyError):
            continue
        if not valid_coordinates(lat, lng) or distance_km(lat, lng, city['lat'], city['lng']) > 100:
            continue
        matches.append((lat, lng, feature_type))
    if not matches:
        return None
    first = matches[0]
    if any(distance_km(*first[:2], *point[:2]) > 1 for point in matches[1:]):
        return None
    return {'lat': first[0], 'lng': first[1], 'precision': 'neighborhood', 'feature_type': first[2]}


def geocode_neighborhood(city, neighborhood):
    params = {'format': 'jsonv2', 'addressdetails': 1, 'limit': 5, 'countrycodes': 'br',
              'accept-language': 'pt-BR', 'q': ', '.join((neighborhood, city['city'], city['state'], 'Brasil'))}
    request = urllib.request.Request(NOMINATIM + '?' + urllib.parse.urlencode(params),
                                     headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=25) as response:
        results = json.load(response)
    return verified_neighborhood(results, city, neighborhood)


def load_cache(path):
    if not path.exists():
        return {'schema_version': 1, 'neighborhoods': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('neighborhoods'), dict):
        raise RuntimeError('Cache geográfico inválido')
    return data


def refresh_cache(cache, queries, geocode=False, interval=15.1, max_requests=60):
    if not geocode:
        return
    last_request = None
    requested = 0
    for key, (city, neighborhood) in sorted(queries.items()):
        if key in cache['neighborhoods'] or requested >= max_requests:
            continue
        if last_request is not None:
            time.sleep(max(0, interval - (time.monotonic() - last_request)))
        last_request = time.monotonic()
        requested += 1
        fatal = False
        try:
            point = geocode_neighborhood(city, neighborhood)
            entry = {'status': 'confirmed' if point else 'unresolved', **(point or {})}
        except urllib.error.HTTPError as error:
            entry = {'status': 'unavailable', 'http_status': int(error.code)}
            fatal = error.code in (403, 429)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            entry = {'status': 'unavailable'}
            fatal = True
        cache['neighborhoods'][key] = {
            'city': city['city'], 'uf': city['uf'], 'neighborhood': label(neighborhood),
            'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), **entry,
        }
        print('Localidades consultadas: ' + str(requested) + '; resultado: ' + entry['status'] + '.', flush=True)
        if fatal:
            print('Serviço geográfico indisponível; cache preservado e cidades confirmadas continuam disponíveis.', flush=True)
            break


def build_report(city_counts, neighborhood_counts, coverage, per_project, cities, cache, workbook=WORKBOOK):
    city_points, neighborhood_points = [], []
    for (project, city_key), count in sorted(city_counts.items()):
        if count < MIN_GROUP_SIZE:
            continue
        city = cities[city_key][0]
        city_points.append({'project': project, 'city': city['city'], 'uf': city['uf'],
                            'lat': city['lat'], 'lng': city['lng'], 'count': count, 'precision': 'city'})
    for (project, city_key, neighborhood), count in sorted(neighborhood_counts.items()):
        if count < MIN_GROUP_SIZE:
            continue
        city = cities[city_key][0]
        point = cache['neighborhoods'].get(cache_key(city, neighborhood), {})
        if (point.get('status') != 'confirmed' or point.get('precision') != 'neighborhood'
                or point.get('feature_type') not in NEIGHBORHOOD_TYPES
                or point.get('uf') != city['uf'] or normalize(point.get('city')) != city_key
                or normalize(point.get('neighborhood')) != neighborhood
                or not valid_coordinates(point.get('lat'), point.get('lng'))):
            per_project[project]['unresolved_neighborhood_groups'] += 1
            continue
        neighborhood_points.append({'project': project, 'city': city['city'], 'uf': city['uf'],
                                    'neighborhood': label(neighborhood), 'lat': point['lat'], 'lng': point['lng'],
                                    'count': count, 'precision': 'neighborhood'})
        per_project[project]['neighborhood_points'] += 1
    coverage_fields = ('city_points', 'neighborhood_points', 'unresolved_city_groups',
                       'unresolved_neighborhood_groups', 'suppressed_city_groups', 'suppressed_neighborhood_groups')
    by_project = [{'project': project, **{key: stats[key] for key in coverage_fields}}
                  for project, stats in sorted(per_project.items())]
    return {
        'schema_version': 1,
        'source': {'workbook': Path(workbook).name, 'sheet': SHEET,
                   'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                   'coordinate_source': 'https://github.com/kelvins/municipios-brasileiros',
                   'coordinate_license': 'MIT; Copyright (c) 2016 Kelvin S. do Prado',
                   'geocoding_source': 'Nominatim / OpenStreetMap contributors (ODbL)',
                   'counting': 'Clientes únicos por empreendimento; localidades agregadas sem endereço individual.'},
        'cities': city_points, 'neighborhoods': neighborhood_points,
        'coverage': {'min_group_size': MIN_GROUP_SIZE, **dict(coverage),
                     **{key: sum(item[key] for item in by_project) for key in coverage_fields},
                     'by_project': by_project},
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, default=WORKBOOK)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/buyer-locations.json')
    parser.add_argument('--cache', type=Path, default=ROOT / 'data/buyer-geocache.json')
    parser.add_argument('--geocode', action='store_true', help='Preencher cache de bairros; não agendar sem respeitar limites Nominatim')
    parser.add_argument('--one-time', action='store_true', help='Lote manual único: intervalo de 1,1 s em vez de 15,1 s')
    parser.add_argument('--max-requests', type=int, default=60)
    args = parser.parse_args(argv)
    if not 0 <= args.max_requests <= 100:
        parser.error('--max-requests deve ficar entre 0 e 100')
    cities = municipality_index(http_text(CSV_BASE + 'municipios.csv'), http_text(CSV_BASE + 'estados.csv'))
    city_counts, neighborhoods, coverage, per_project = aggregate_locations(workbook_rows(args.workbook), cities)
    queries = {cache_key(cities[city_key][0], neighborhood): (cities[city_key][0], neighborhood)
               for (_project, city_key, neighborhood), count in neighborhoods.items() if count >= MIN_GROUP_SIZE}
    cache = load_cache(args.cache)
    refresh_cache(cache, queries, args.geocode, 1.1 if args.one_time else 15.1, args.max_requests)
    report = build_report(city_counts, neighborhoods, coverage, per_project, cities, cache, args.workbook)
    write_json(args.cache, cache)
    write_json(args.output, report)
    print('Mapa agregado: ' + str(len(report['cities'])) + ' grupos de cidades e ' +
          str(len(report['neighborhoods'])) + ' grupos de bairros confirmados; sem dados individuais.', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, KeyError):
        print('Mapa não atualizado: fonte ou serviço geográfico indisponível; arquivos anteriores preservados.', file=sys.stderr)
        sys.exit(1)
