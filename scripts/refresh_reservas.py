"""Atualiza a seleção de vendas do painel, preservando o histórico validado."""
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import clean, compact, is_sold, number, payment_summary, pick, series_amount, series_label, status_text, SERIES_IDS, unit_id
from leads_operational_history import request
from leads_sales_funnel import read_pages, day
from leads_full_history import credentials
from lcm_lead_display import display_name

START = '2026-11-01'
REFERENCE = ROOT/'Planilha_Executivo_LCM_COM_RENDA_PERFIL_PUBLICO.xlsx'


def key(project, block, unit):
    return tuple(compact(v) for v in (project, block, unit))


def public_id(row):
    # Referência local de apresentação, nunca o identificador do CRM.
    return 'R-' + hashlib.sha256('|'.join((*key(row['project'], row['block'], row['unit']), row['date'])).encode()).hexdigest()[:12]


def name(value):
    result = display_name(value)
    if not re.fullmatch(r"[\wÀ-ÿ .’'-]+", result) or any(c.isdigit() for c in result):
        return 'Não informado'
    return result


def read_conditions(fetch, needed):
    # Campo oficial do CVDW: idreservascondicoes (plural).
    conditions, _ = read_pages(fetch, 'idreservascondicoes')
    grouped = {k: [] for k in needed}
    for row in conditions.values():
        k = str(row.get('idreserva', ''))
        if k in grouped and str(row.get('ativo', 'S')).upper() == 'S':
            if row.get('valor') in (None, '') or not row.get('serie'):
                raise ValueError('Condições financeiras incompletas para venda recente')
            # O schema CVDW descreve valor como valor da condição, não valor
            # unitário da parcela. Preserva o valor sem multiplicá-lo.
            item = {'serie': row['serie'], 'idserie': row.get('idserie'), 'valor': row['valor']}
            for field in ('pro_soluto', 'prosoluto', 'pro_soluto_serie', 'serie_pro_soluto'):
                if field in row:
                    item[field] = row[field]
            grouped[k].append(item)
    if any(not cond for cond in grouped.values()):
        raise ValueError('Condições financeiras ausentes para venda recente')
    return grouped


def dimension(row, aliases):
    value = pick(row, aliases, '')
    if isinstance(value, dict):
        value = pick(value, ['nome', 'descricao', 'numero'], '')
    return clean(value)


def flag(value):
    normalized = compact(str(value))
    if normalized in ('s', 'sim', 'true', '1'): return True
    if normalized in ('n', 'nao', 'false', '0'): return False
    return None


def verified_reference(path=REFERENCE):
    """Read the original CV export; only keep area and series classifications in memory."""
    from openpyxl import load_workbook
    book = load_workbook(path, read_only=True, data_only=True)
    areas, classifications = {}, {}
    try:
        for project, _, _, _, block, unit, area in book['Estoque Original'].iter_rows(min_row=2, max_col=7, values_only=True):
            if project and block and unit and number(area) > 0:
                areas.setdefault(key(project, block, unit), set()).add(number(area))
        for label, marked, _, _, _, _, project in book['Séries Originais'].iter_rows(min_row=2, max_col=7, values_only=True):
            if label and project and flag(marked) is not None:
                classifications.setdefault((compact(project), compact(label)), set()).add(flag(marked))
                classifications.setdefault(('', compact(label)), set()).add(flag(marked))
    finally:
        book.close()
    return areas, classifications


def canonical_series(item):
    return SERIES_IDS.get(str(item.get('idserie') or '')) or series_label(item)


def pro_amount(raw, project, classifications):
    amount = 0.0
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError('Condições financeiras incompletas para venda recente')
        flags = {flag(item[f]) for f in ('pro_soluto', 'prosoluto', 'pro_soluto_serie', 'serie_pro_soluto') if f in item and flag(item[f]) is not None}
        if not flags:
            label = compact(canonical_series(item))
            flags = classifications.get((compact(project), label), classifications.get(('', label), set()))
        if len(flags) != 1:
            raise ValueError('Classificação Pró-Soluto não verificável para série de venda recente')
        if True in flags:
            amount += series_amount(item)
    return amount


def sale_area(row, inventory, units, areas):
    unit = units.get(unit_id(row), {})
    area = number(pick(unit, ['area_privativa'], None))
    if area > 0 and math.isfinite(area):
        return area
    known = areas.get(key(inventory['project'], inventory['block'], inventory['unit']), set())
    if len(known) == 1:
        return next(iter(known))
    raise ValueError('Área privativa não verificável para venda recente')


def project_row(row, stock, units, areas, classifications):
    project = dimension(row, ['empreendimento', 'nome_empreendimento'])
    block = dimension(row, ['bloco', 'nome_bloco'])
    unit = dimension(row, ['unidade', 'nome_unidade', 'numero_unidade'])
    if not all((project, block, unit)) or key(project, block, unit) not in stock:
        raise ValueError('Venda recente sem vínculo inequívoco com a unidade do inventário')
    inventory = stock[key(project, block, unit)]
    date = day(row.get('data_venda')) or day(row.get('data_ultima_alteracao_situacao'))
    total = number(pick(row, ['valor_venda', 'valor_contrato', 'valor_total', 'vgv', 'valor'], None))
    if not date or not math.isfinite(total) or total <= 0:
        raise ValueError('Venda recente sem data ou valor comprovado')
    raw = row.get('condicao') or row.get('series') or []
    if not raw:
        conditions = row.get('condicoes') or {}
        if isinstance(conditions, str):
            conditions = json.loads(conditions)
        if isinstance(conditions, dict):
            raw = conditions.get('series', [])
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list):
        raw = []
    if not raw:
        raise ValueError('Venda recente sem condições financeiras verificáveis')
    # Prefer the official series catalog for financial categories, not abbreviations.
    canonical = [{**item, 'serie': canonical_series(item)} for item in raw if isinstance(item, dict)]
    if len(canonical) != len(raw):
        raise ValueError('Condições financeiras incompletas para venda recente')
    pay = payment_summary({'condicao': canonical})
    pay['Pró-Soluto'] = pro_amount(canonical, project, classifications)
    series = {}
    labels = {'entrada':'entrada','entrada02':'entrada02','parcela1':'parcela1','parcela2':'parcela2','anual':'anual','semestral':'semestral','chave':'chave','mensal':'mensal','mensais':'mensal','sinal':'sinal','ato':'ato','poshab':'poshab'}
    for item in raw:
        if isinstance(item, dict):
            label = labels.get(compact(canonical_series(item)))
            if label:
                series[label] = series.get(label, 0) + series_amount(item)
    titular = row.get('titular') if isinstance(row.get('titular'), dict) else {}
    client = dimension(row, ['cliente', 'nome_cliente', 'titular_nome']) or clean(titular.get('nome'))
    out = {'client': name(client), 'project':inventory['project'], 'stage':inventory['stage'],
           'agency':dimension(row, ['nome_imobiliaria', 'imobiliaria_nome', 'imobiliaria']), 'block':inventory['block'], 'unit':inventory['unit'],
           'date':date, 'm2':sale_area(row, inventory, units, areas), 'total':total,
           'net':total-pay['AdPremiada']-pay['Ch_Moradia'], 'fgts':pay['FGTS'], 'subsidy':pay['Subsídio'],
           'financing':pay['Financiamento'], 'financed':pay['Total Financiado'], 'adpremiada':pay['AdPremiada'],
           'cheque':pay['Ch_Moradia'], 'pro':pay['Pró-Soluto'], 'risk':pay['Pró-Soluto']/total,
           'series':series, 'series_rows':len(raw)}
    if any(not math.isfinite(v) for v in out.values() if isinstance(v,(int,float))):
        raise ValueError('Valor financeiro inválido')
    out['id'] = public_id(out)
    return out


def update_html(html, reservations, updated, units=None, areas=None, classifications=None):
    units, areas, classifications = units or {}, areas or {}, classifications or {}
    start = html.index('const D=') + len('const D=')
    data, end = json.JSONDecoder().raw_decode(html[start:])
    tail = html[start+end:]
    override = re.search(r"const targetSale=SALES\.find\(x=>String\(x\.id\)==='([^']+)'\);if\(targetSale\)targetSale\.date='([^']+)';", tail)
    if override:
        tail = tail[:override.start()] + tail[override.end():]
    stock = {key(r['project'], r['block'], r['unit']):r for r in data['stock']}
    if len(stock) != len(data['stock']):
        raise ValueError('Inventário com unidades ambíguas')
    sales = {}
    for row in data['sales']:
        row['client'] = name(row['client'])
        # Preserva a correção histórica já presente na interface.
        if override and str(row['id']) == override.group(1):
            row['date'] = override.group(2)
        row['id'] = public_id(row)
        sales[key(row['project'], row['block'], row['unit'])] = row
    recent = {}
    for row in reservations:
        if str(row.get('ativo','S')).upper() != 'S' or row.get('data_cancelamento') or row.get('data_distrato') or not is_sold(status_text(row)):
            continue
        date = day(row.get('data_venda')) or day(row.get('data_ultima_alteracao_situacao'))
        if not date:
            raise ValueError('Venda confirmada sem data verificável')
        if date < START:
            continue
        sale = project_row(row, stock, units, areas, classifications)
        k = key(sale['project'], sale['block'], sale['unit'])
        if k in recent:
            raise ValueError('Mais de uma venda recente para a mesma unidade')
        recent[k] = sale
    # O usuário confirmou duas vendas em novembro; não substitui a base por uma leitura vazia.
    if sum(v['date'].startswith('2026-11') for v in recent.values()) < 2:
        raise ValueError('Novembro ainda não conciliado: menos de duas vendas confirmadas')
    # Se houve distrato, não manter a venda recente como ativa.
    for k in list(sales):
        if sales[k]['date'] >= START and k not in recent:
            raise ValueError('Venda anteriormente publicada não conciliada; revisão necessária')
    for k, row in recent.items():
        sales[k] = row
        stock[k]['status'] = 'Vendida'
    data['sales'] = sorted(sales.values(), key=lambda r: (r['date'],r['project'],r['block'],r['unit']))
    data['reservations_updated_at'] = updated
    return html[:start] + json.dumps(data, ensure_ascii=False, separators=(',',':'),allow_nan=False).replace('</','<\\/') + tail, len(recent)


def main():
    base, email, token = credentials(os.environ)
    cutoff = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    rows, _ = read_pages(lambda p:request(base,email,token,'/api/v1/cvdw/reservas',p,cutoff),'idreserva')
    # Consultar todas as condições recentes: valores parciais na reserva não
    # comprovam que foram retornadas todas as séries.
    needed = {k for k,row in rows.items() if is_sold(status_text(row))
              and str(row.get('ativo','S')).upper() == 'S' and not row.get('data_cancelamento') and not row.get('data_distrato')
              and (day(row.get('data_venda')) or day(row.get('data_ultima_alteracao_situacao')) or '') >= START}
    if needed:
        grouped = read_conditions(lambda p:request(base,email,token,'/api/v1/cvdw/reservas/condicoes',p,cutoff), needed)
        for k,cond in grouped.items():
            rows[k] = {**rows[k], 'condicao':cond}
    path = ROOT/'index.html'
    units, _ = read_pages(lambda p:request(base,email,token,'/api/v1/cvdw/unidades',p,cutoff),'idunidade')
    areas, classifications = verified_reference()
    html, count = update_html(path.read_text(), rows.values(), dt.datetime.now(dt.timezone.utc).isoformat(), units, areas, classifications)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(html,encoding='utf-8')
    tmp.replace(path)
    print('Vendas recentes conciliadas:', count)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Não imprimir respostas, parâmetros ou valores da API.
        print('Atualização de reservas interrompida; base anterior preservada. Classe:', type(exc).__name__,file=sys.stderr)
        safe_prefixes = ('Venda recente sem', 'Venda confirmada sem', 'Inventário com', 'Mais de uma venda recente', 'Novembro ainda não conciliado', 'Venda anteriormente publicada', 'Condições financeiras ausentes', 'Condições financeiras incompletas', 'Valor financeiro inválido', 'Área privativa não verificável', 'Classificação Pró-Soluto não verificável', 'Fonte operacional /api/v1/cvdw/reservas: HTTP ', 'Fonte operacional /api/v1/cvdw/reservas/condicoes: HTTP ', 'Fonte operacional /api/v1/cvdw/unidades: HTTP ', 'Identidade ausente na fonte', 'Fonte do funil mudou', 'Total da fonte do funil', 'Página repetida', 'Página incompleta', 'Snapshot conflitante')
        reason = str(exc)
        if any(reason.startswith(p) for p in safe_prefixes) and len(reason) < 180:
            print(reason,file=sys.stderr)
        sys.exit(1)
