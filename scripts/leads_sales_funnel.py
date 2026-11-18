"""Funil de vendas integral: vínculos apenas em memória; saída sem IDs CRM ou textos livres."""
import collections
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import urllib.parse
from pathlib import Path
from leads_operational_history import request, opaque
from leads_full_history import credentials
from leads_public_projection import validate as validate_roster

SOLD={'VENDIDA','CONTRATO ASSINADO POR TODOS','AGUARDANDO ASSINATURA INTERNA','BOLETO/PIX','ENVIADO PARA UAU','CONTRATO ASSINADO CLIENTE(S)'}
def norm(value):
    import unicodedata
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',str(value or '')) if not unicodedata.combining(c)).upper().split())
def day(value):
    try:return dt.date.fromisoformat(str(value)[:10]).isoformat()
    except (ValueError,TypeError):return None

def links(row):
    ids=set()
    value=row.get('idlead')
    if isinstance(value,(str,int)) and re.fullmatch(r'\s*\d+(?:\s*,\s*\d+)*\s*',str(value)):
        ids.update(re.findall(r'\d+',str(value)))
    associated=row.get('leads_associados') or []
    if isinstance(associated,dict):associated=list(associated.values())
    for item in associated:
        if isinstance(item,dict) and str(item.get('idlead','')).isdigit():ids.add(str(item['idlead']))
    return ids

def read_pages(fetch,identity,*,precad=False):
    latest={};seen=set();scanned=0;expected=None;pages=None
    for page in range(1,10001):
        payload=fetch(page)
        if not isinstance(payload,dict):raise RuntimeError('Formato inesperado na fonte do funil')
        batch=payload.get('precadastros' if precad else 'dados')
        if not isinstance(batch,list):raise RuntimeError('Lista ausente na fonte do funil')
        total=int(payload['total' if precad else 'total_de_registros'])
        capacity=int(payload.get('limite' if precad else 'registros') or 500)
        n=math.ceil(total/capacity) if precad else int(payload['total_de_paginas'])
        if expected is None:expected,pages=total,n
        if (total,n)!=(expected,pages):raise RuntimeError('Fonte do funil mudou durante leitura; base válida preservada')
        if total==0 and not batch:return {},{'records':0,'pages':0}
        if not batch or n<1:raise RuntimeError('Página incompleta na fonte do funil')
        signature=hashlib.sha256(json.dumps(batch,sort_keys=True).encode()).hexdigest()
        if signature in seen:raise RuntimeError('Página repetida na fonte do funil')
        seen.add(signature);scanned+=len(batch)
        for row in batch:
            if not isinstance(row,dict) or row.get(identity) is None:raise RuntimeError('Identidade ausente na fonte do funil')
            key=str(row[identity]);reference=str(row.get('referencia_data') or row.get('data_cad') or '')
            old=latest.get(key)
            if old and old[0]==reference and old[1]!=row:raise RuntimeError('Snapshot conflitante na fonte do funil')
            if not old or reference>old[0]:latest[key]=(reference,row)
        if page==n:break
        if page%25==0:print('Funil:',identity,'páginas',page,'de',n,flush=True)
    if scanned!=expected or len(seen)!=pages:raise RuntimeError('Total da fonte do funil não conferiu')
    return {key:value[1] for key,value in latest.items()},{'records':scanned,'pages':pages}

def build(roster,histories,conversions,precads,reservations,secret):
    validate_roster(roster)
    rows={r['history_key']:{'key':r['history_key'],'registered':r['date'],'entries':{r['date']},'events':set()} for r in roster['leads']}
    audit=collections.Counter()
    def event(key,date,level,source):
        if key in rows and date:rows[key]['events'].add((date,level,source))
    for key,events in histories.items():
        if key not in rows:raise RuntimeError('Histórico não pertence à carteira')
        for e in events:
            # Tarefas de visita são agendamentos explícitos. Tarefa genérica não comprova visita.
            if e['kind'] in ('task','visit') and (e['kind']=='visit' or e['type']=='Visita') and e['state']!='Cancelada':
                event(key,day(e['date']),1,'task')
                if e['state']=='Concluída':event(key,day(e['date']),2,'visit')
    for row in conversions.values():
        if norm(row.get('ativo','S'))!='S':continue
        key=opaque(secret,'lead',row.get('idlead'));date=day(row.get('referencia_data'))
        if key in rows and date and date>rows[key]['registered']:rows[key]['entries'].add(date)
    for row in precads.values():
        if row.get('data_cancelamento'):continue
        date=day(row.get('data_cad'))
        if not date:raise RuntimeError('Pré-cadastro sem data; funil não publicado')
        for lead in links(row):event(opaque(secret,'lead',lead),date,3,'pre_registration')
    for row in reservations.values():
        if norm(row.get('ativo','S'))!='S' or row.get('data_cancelamento') or row.get('data_distrato'):continue
        ids=links(row);audit['reservations']+=1
        if not ids:audit['reservations_without_lead']+=1
        date=day(row.get('data_cad'))
        if ids and not date:raise RuntimeError('Reserva vinculada sem data; funil não publicado')
        sold=norm(row.get('situacao')) in SOLD
        sale_date=day(row.get('data_venda')) or day(row.get('data_ultima_alteracao_situacao'))
        for lead in ids:
            key=opaque(secret,'lead',lead)
            if key not in rows:audit['reservation_links_outside_roster']+=1;continue
            event(key,date,3,'reservation_rule')
            if sold:
                if not sale_date:raise RuntimeError('Reserva vendida sem data comprovada')
                event(key,sale_date,4,'reservation_sale')
    result=[]
    for key,r in sorted(rows.items()):
        result.append({'key':key,'registered':r['registered'],'entries':sorted(r['entries']),
                       'events':[{'date':d,'level':l,'source':s} for d,l,s in sorted(r['events'])]})
    return {'schema_version':1,'validated':True,'history_generation':roster['history_generation'],
            'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'return_date_basis':'cvdw_conversion_reference_date','leads':result,'audit':dict(audit)}

def validate(data,roster):
    if data.get('schema_version')!=1 or data.get('validated') is not True or data.get('history_generation')!=roster['history_generation']:raise RuntimeError('Funil de geração inválida')
    if not isinstance(data.get('leads'),list) or len(data['leads'])!=roster['total']:raise RuntimeError('Funil incompleto')
    expected={r['history_key'] for r in roster['leads']};seen=set()
    for row in data['leads']:
        if set(row)!={'key','registered','entries','events'} or row['key'] not in expected or row['key'] in seen:raise RuntimeError('Projeção do funil inválida')
        seen.add(row['key'])
        if day(row['registered'])!=row['registered'] or not row['entries'] or any(day(d)!=d for d in row['entries']):raise RuntimeError('Datas do funil inválidas')
        for e in row['events']:
            if set(e)!={'date','level','source'} or day(e['date'])!=e['date'] or e['level'] not in (1,2,3,4) or e['source'] not in ('task','visit','pre_registration','reservation_rule','reservation_sale'):raise RuntimeError('Evento público inválido')
    return True

def main():
    base,email,token=credentials(os.environ)
    root=Path('data');roster=json.loads((root/'leads-roster.json').read_text())
    summary=json.loads((root/'leads-all-summary.json').read_text());cutoff=summary['reference_cutoff']
    histories={}
    for file in (root/'leads-history'/roster['history_generation']).glob('*.json'):
        shard=json.loads(file.read_text())
        if shard['generation']!=roster['history_generation']:raise RuntimeError('Geração histórica divergente')
        histories.update(shard['leads'])
    if len(histories)!=roster['total'] or any(len(histories.get(r['history_key'],[]))!=r['history_count'] for r in roster['leads']):raise RuntimeError('Histórico incompleto para o funil')
    conversions,cm=read_pages(lambda p:request(base,email,token,'/api/v1/cvdw/leads/conversoes',p,cutoff),'idlead_conversao')
    reservations,rm=read_pages(lambda p:request(base,email,token,'/api/v1/cvdw/reservas',p,cutoff),'idreserva')
    # REST pré-cadastro usa pagina/limite, e não registros_por_pagina.
    from leads_sales_precad_request import request_pre
    precads,pm=read_pages(lambda p:request_pre(base,email,token,p),'idprecadastro',precad=True)
    result=build(roster,histories,conversions,precads,reservations,token)
    validate(result,roster)
    result['source_reference_cutoff']=cutoff;result['sources']={'conversions':cm,'reservations':rm,'pre_registrations':{**pm,'reference_cutoff_supported':False}}
    out=root/'leads-sales-funnel.json';temp=out.with_suffix('.json.tmp');temp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')));temp.replace(out)
    print('Funil validado:',len(result['leads']),'leads. Fontes:',result['sources'],flush=True)
if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,TypeError,KeyError) as exc:
        print('Funil não publicado: '+str(exc),file=sys.stderr);sys.exit(1)
