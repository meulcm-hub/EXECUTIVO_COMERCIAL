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
from server import clean, compact, is_sold, number, payment_summary, pick, series_amount, series_label, status_text
from leads_operational_history import request
from leads_sales_funnel import read_pages, day
from leads_full_history import credentials
from lcm_lead_display import display_name

START = '2026-11-01'


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


def dimension(row, aliases):
    value = pick(row, aliases, '')
    if isinstance(value, dict):
        value = pick(value, ['nome', 'descricao', 'numero'], '')
    return clean(value)


def project_row(row, stock):
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
    pay = payment_summary(row)
    if not pay['_has_conditions']:
        raise ValueError('Venda recente sem condições financeiras verificáveis')
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
    series = {}
    labels = {'entrada':'entrada','entrada02':'entrada02','parcela1':'parcela1','parcela2':'parcela2','anual':'anual','semestral':'semestral','chave':'chave','mensal':'mensal','mensais':'mensal','sinal':'sinal','ato':'ato','poshab':'poshab'}
    for item in raw:
        if isinstance(item, dict):
            label = labels.get(compact(series_label(item)))
            if label:
                series[label] = series.get(label, 0) + series_amount(item)
    titular = row.get('titular') if isinstance(row.get('titular'), dict) else {}
    client = dimension(row, ['cliente', 'nome_cliente', 'titular_nome']) or clean(titular.get('nome'))
    out = {'client': name(client), 'project':inventory['project'], 'stage':inventory['stage'],
           'agency':dimension(row, ['nome_imobiliaria', 'imobiliaria_nome', 'imobiliaria']), 'block':inventory['block'], 'unit':inventory['unit'],
           'date':date, 'm2':number(pick(row, ['area_privativa','area','m2'], 0)), 'total':total,
           'net':total-pay['AdPremiada']-pay['Ch_Moradia'], 'fgts':pay['FGTS'], 'subsidy':pay['Subsídio'],
           'financing':pay['Financiamento'], 'financed':pay['Total Financiado'], 'adpremiada':pay['AdPremiada'],
           'cheque':pay['Ch_Moradia'], 'pro':pay['Pró-Soluto'], 'risk':pay['Pró-Soluto']/total,
           'series':series, 'series_rows':len(raw)}
    if any(not math.isfinite(v) for v in out.values() if isinstance(v,(int,float))):
        raise ValueError('Valor financeiro inválido')
    out['id'] = public_id(out)
    return out


def update_html(html, reservations, updated):
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
        sale = project_row(row, stock)
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
    # As condições podem vir separadamente no CVDW. Consulta apenas se faltarem
    # na fonte de reservas; usa o mesmo limitador e corte temporal.
    needed = {k for k,row in rows.items() if is_sold(status_text(row))
              and str(row.get('ativo','S')).upper() == 'S' and not row.get('data_cancelamento') and not row.get('data_distrato')
              and (day(row.get('data_venda')) or day(row.get('data_ultima_alteracao_situacao')) or '') >= START
              and not payment_summary(row)['_has_conditions']}
    if needed:
        payload = request(base,email,token,'/api/v1/cvdw/reservas/condicoes',1,cutoff)
        batch = payload.get('dados', [])
        identity = next((k for k in ('idreserva_condicao','idreservacondicao','idcondicao','idreserva_serie','id')
                         if batch and all(isinstance(r,dict) and r.get(k) is not None for r in batch)),None)
        if not identity:
            raise ValueError('Condições sem identidade verificável')
        conditions, _ = read_pages(lambda p:payload if p==1 else request(base,email,token,'/api/v1/cvdw/reservas/condicoes',p,cutoff),identity)
        grouped = {k:[] for k in needed}
        for row in conditions.values():
            k = str(row.get('idreserva',''))
            if k in grouped and str(row.get('ativo','S')).upper() == 'S':
                grouped[k].append(row)
        for k,cond in grouped.items():
            if not cond:
                raise ValueError('Condições financeiras ausentes para venda recente')
            rows[k] = {**rows[k], 'condicao':cond}
    path = ROOT/'index.html'
    html, count = update_html(path.read_text(), rows.values(), dt.datetime.now(dt.timezone.utc).isoformat())
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
        safe_prefixes = ('Venda recente sem', 'Venda confirmada sem', 'Inventário com', 'Mais de uma venda recente', 'Novembro ainda não conciliado', 'Venda anteriormente publicada', 'Condições sem identidade', 'Condições financeiras ausentes', 'Valor financeiro inválido', 'Fonte operacional /api/v1/cvdw/reservas: HTTP ', 'Fonte operacional /api/v1/cvdw/reservas/condicoes: HTTP ')
        reason = str(exc)
        if any(reason.startswith(p) for p in safe_prefixes) and len(reason) < 180:
            print(reason,file=sys.stderr)
        sys.exit(1)
