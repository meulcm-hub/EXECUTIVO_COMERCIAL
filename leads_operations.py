"""Carteira CV CRM privada: somente leitura, em memória, sem contatos ou CPF.

Contrato já utilizado no projeto: GET comercial/leads com limit/offset.
A carteira só é liberada após validação de todas as páginas e IDs únicos.
"""
import re
from datetime import datetime


def text(value):
    if isinstance(value, dict):
        return str(value.get('nome') or value.get('descricao') or '').strip()
    return str(value or '').strip() if isinstance(value, (str, int)) else ''


def short_name(value):
    return ' '.join(text(value).split()[:2]) or 'Não informado'


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return value
    except ValueError:
        return None


def project(row):
    for key in ('empreendimento', 'empreendimento_ultimo', 'empreendimento_primeiro'):
        value = text(row.get(key))
        if value:
            return value
    projects = row.get('empreendimentos')
    if isinstance(projects, list):
        values = list(dict.fromkeys(text(x) for x in projects if text(x)))
        if len(values) == 1:
            return values[0]
        if len(values) > 1:
            return 'MÚLTIPLOS EMPREENDIMENTOS'
    return 'SEM EMPREENDIMENTO'


def project_lead(row):
    raw_id = row.get('idlead')
    if isinstance(raw_id, bool) or not re.fullmatch(r'[1-9]\d{0,16}', str(raw_id or '')):
        raise ValueError('Lead sem identificador confiável')
    # Não incluir telefone, CPF, e-mail, endereço, observações livres ou nome completo.
    # Responsáveis também são reduzidos a dois nomes.
    created = row.get('data_cadastro') or row.get('data_cad') or row.get('dataCad')
    day = str(created or '')[:10]
    try:
        datetime.strptime(day, '%Y-%m-%d')
    except ValueError:
        day = None
    return {
        'id': str(raw_id), 'name': short_name(row.get('nome')),
        'date': day, 'project': project(row),
        'origin_name': text(row.get('origem')) or text(row.get('origem_nome')) or 'Não informada',
        'lead_media': text(row.get('midia_principal')),
        'status': text(row.get('situacao')) or text(row.get('status')) or 'Não informada',
        'owner': short_name(row.get('corretor')) if text(row.get('corretor')) else None,
        # Campos só são aceitos quando semanticamente explícitos. data_modificacao
        # nunca é usada como contato, e status não substitui evento de atendimento.
        'last_contact': timestamp(row.get('data_ultimo_contato')),
        'first_contact': timestamp(row.get('data_primeiro_contato')),
        'appointment': timestamp(row.get('data_proximo_agendamento')),
        'next_action': None, 'interactions': [], 'campaign': None, 'value': None,
    }


def collect(fetch, pause=lambda: None):
    projected = {}
    offset = 0
    total_expected = None
    while True:
        payload = fetch(offset)
        rows = payload.get('leads') if isinstance(payload, dict) else None
        total = payload.get('total') if isinstance(payload, dict) else None
        if not isinstance(rows, list) or isinstance(total, bool) or not str(total).isdigit():
            raise ValueError('Formato comercial não reconhecido')
        total = int(total)
        if total > 500000:
            raise ValueError('Limite de proteção da carteira excedido')
        if total_expected is None:
            total_expected = total
        if total != total_expected:
            raise ValueError('Total alterado durante leitura; carteira não publicada')
        if offset >= total:
            break
        if not rows or offset + len(rows) > total:
            raise ValueError('Paginação incompleta')
        for row in rows:
            item = project_lead(row)
            if item['id'] in projected:
                raise ValueError('ID repetido; carteira não publicada')
            projected[item['id']] = item
        offset += len(rows)
        if offset >= total:
            break
        pause()
    if len(projected) != total_expected:
        raise ValueError('Carteira incompleta')
    return list(projected.values())
