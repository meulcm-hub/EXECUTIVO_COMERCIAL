"""Coleta somente leitura, com projeção explícita e sem documentos pessoais."""
import datetime as dt
import json
import os
from pathlib import Path
from leads_sales_funnel import read_pages, norm, links
from leads_sales_precad_request import request_pre
from leads_operational_history import opaque, timestamp, request
from leads_full_history import credentials
from leads_public_projection import safe_text, short_name, validate as validate_roster

def label(value):
    if isinstance(value, dict):
        value = value.get('nome') or value.get('situacao') or value.get('status')
    return safe_text(value) or None

def classify(value):
    status = norm(value)
    mapping = {
        'APROVADO INTEGRAL': 'Aprovado integral',
        'APROVADO CONDICIONADO': 'Aprovado condicionado',
        'APROVADO EM OUTRO CCA': 'Aprovado em outro CCA',
        'APROVADO': 'Aprovado', 'REPROVADO': 'Reprovado',
        'PENDENTE': 'Pendente', 'PENDENTE DOCUMENTACAO': 'Pendente de documentação',
        'PENDENTE DE DOCUMENTACAO': 'Pendente de documentação',
        'PENDENTE RESTRICAO': 'Pendente de restrição',
        'PENDENTE DE RESTRICAO': 'Pendente de restrição',
        'EM PROCESSAMENTO': 'Em processamento',
    }
    return mapping.get(status)

def origin_index(roster):
    validate_roster(roster)
    if roster['schema_version'] != 2:
        raise RuntimeError('Carteira histórica de leads necessária para cruzar origens')
    index = {}
    for lead in roster['leads']:
        key = lead['history_key']
        if key in index:
            raise RuntimeError('Vínculo duplicado na carteira de leads')
        name = label(lead.get('origin_name'))
        if norm(name) in ('', 'ND', 'NÃO INFORMADA', 'NAO INFORMADA', 'NÃO INFORMADO', 'NAO INFORMADO', 'SEM ORIGEM'):
            name = None
        index[key] = name
    return index


def folder_origin(row, secret, index):
    ids = links(row)
    keys = {opaque(secret, 'lead', identity) for identity in ids}
    matched = keys & index.keys()
    names = {norm(index[k]): index[k] for k in sorted(matched) if index[k]}
    if len(names) > 1:
        return 'Origens múltiplas', 'multiple'
    if len(names) == 1:
        return next(iter(names.values())), 'identified'
    return 'Origem não identificada', 'matched_without_origin' if matched else ('unmatched' if ids else 'no_link')


def project(rows, history, secret, now, index):
    grouped = {}
    for row in history.values():
        key = str(row.get('idprecadastro') or '')
        date = timestamp(row.get('data_cad'))
        stage = label(row.get('para_nome'))
        if key and date and stage and norm(row.get('ativo', 'S')) == 'S':
            grouped.setdefault(key, []).append({'date': date, 'stage': stage})
    folders = []
    for identity, row in rows.items():
        date = timestamp(row.get('data_cad'))
        if not date:
            raise RuntimeError('Pré-cadastro sem data válida')
        status = label(row.get('situacao') or row.get('status'))
        events = sorted(grouped.get(identity, []), key=lambda e: e['date'])
        for event, following in zip(events, events[1:]):
            event['hours'] = round((dt.datetime.fromisoformat(following['date']) -
                                    dt.datetime.fromisoformat(event['date'])).total_seconds()/3600, 2)
        decision = next((event for event in events if classify(event['stage']) in
                         {'Aprovado', 'Aprovado integral', 'Aprovado condicionado',
                          'Aprovado em outro CCA', 'Reprovado'}), None)
        analysis_hours = ((dt.datetime.fromisoformat(decision['date']) -
                           dt.datetime.fromisoformat(date)).total_seconds()/3600
                          if decision else None)
        last = timestamp(row.get('data_ultima_alteracao_situacao')) or (events[-1]['date'] if events else None)
        age = max(0, (now - dt.datetime.fromisoformat(last)).total_seconds()/3600) if last else None
        # Apenas nomes reduzidos e dimensões comerciais explicitamente permitidas.
        client = row.get('cliente') or row.get('nome')
        origin, _ = folder_origin(row, secret, index)
        folders.append({
            'key': opaque(secret, 'precadastro', identity),
            'client': short_name(client) if client else None,
            'project': label(row.get('empreendimento')),
            'unit': label(row.get('unidade')),
            'broker': short_name(row['corretor']) if row.get('corretor') else None,
            'agency': label(row.get('imobiliaria')),
            'correspondent': short_name(row['correspondente']) if row.get('correspondente') else None,
            'manager': short_name(row['gestor']) if row.get('gestor') else None,
            'origin': origin,
            'date': date[:10], 'last_move': last, 'status': status,
            'approval': classify(status), 'age_hours': round(age, 1) if age is not None else None,
            'analysis_hours': round(analysis_hours, 2) if analysis_hours is not None and analysis_hours >= 0 else None,
            'history': events,
        })
    return folders

def main():
    base, email, token = credentials(os.environ)
    rows, meta = read_pages(lambda p: request_pre(base,email,token,p), 'idprecadastro', precad=True)
    if not rows:
        raise RuntimeError('Fonte vazia; publicação preservada')
    now = dt.datetime.now(dt.timezone.utc)
    history, history_meta = read_pages(lambda p: request(base,email,token,'/api/v1/cvdw/precadastro/historico/situacoes',p,now.strftime('%Y-%m-%d %H:%M:%S')), 'idhistorico')
    roster = json.loads(Path('data/leads-roster.json').read_text())
    index = origin_index(roster)
    from collections import Counter
    counts = Counter(folder_origin(row, token, index)[1] for row in rows.values())
    if not (counts['identified'] or counts['multiple'] or counts['matched_without_origin']):
        raise RuntimeError('Nenhum vínculo com a carteira de leads; publicação preservada')
    folders = project(rows,history,token,now.replace(tzinfo=None),index)
    if not any(r['status'] for r in folders):
        raise RuntimeError('Situação não reconhecida na fonte')
    payload = {'schema_version':1,'validated':True,'generated_at_utc':now.isoformat(),
               'folders':folders,'sources':{'folders':meta,'history':history_meta,'origin_links':dict(counts)}}
    out = Path('data/precadastro.json')
    temp = out.with_suffix('.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
    temp.replace(out)
    print('Pré-cadastros publicados:',len(folders))
    print('Origem das pastas:', json.dumps(dict(counts), sort_keys=True))

if __name__ == '__main__':
    main()
