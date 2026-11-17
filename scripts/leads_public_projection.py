"""Projeção pública autorizada: dois nomes e dimensões comerciais; nunca contatos."""
import re

OPERATION_FIELDS={'last_contact','last_interaction','next_action','next_action_at','appointment','history_count','history_key'}
FIELDS={'name','date','project','origin','origin_name','lead_media','status','owner'}

def safe_text(value):
    if not isinstance(value,str):return ''
    value=re.sub(r'https?://\S+|\b[^\s@]+@[^\s@]+\.[^\s@]+','',value)
    value=re.sub(r'(?:\d[\s()./+_-]*){8,}','',value)
    return ' '.join(value.split())[:160]

def short_name(value):
    if isinstance(value,dict):value=value.get('nome','')
    text=safe_text(value)
    words=[re.sub(r"[^\wÀ-ÿ'’-]",'',x) for x in text.split()]
    words=[x for x in words if x and any(c.isalpha() for c in x) and not any(c.isdigit() for c in x)]
    return ' '.join(words[:2]) or 'Não informado'

def project(snapshot,detail):
    return {'name':short_name(detail.get('public_name')),
            'date':snapshot['date'],
            'project':safe_text(snapshot['project']) or 'SEM EMPREENDIMENTO',
            'origin':safe_text(snapshot['origin']),
            'origin_name':safe_text(snapshot['origin_name']),
            'lead_media':safe_text(snapshot['lead_media']),
            'status':safe_text(snapshot['status']) or 'Não informada',
            'owner':short_name(detail.get('public_owner')) if detail.get('public_owner') else None}

def validate(payload):
    if payload.get('schema_version') not in (1,2) or payload.get('validated') is not True or payload.get('scope')!='all_accessible_leads':
        raise ValueError('Contrato público da carteira inválido')
    rows=payload.get('leads')
    if not isinstance(rows,list) or not rows or len(rows)!=payload.get('total'):
        raise ValueError('Carteira pública incompleta')
    version=payload['schema_version']
    if version==2 and not re.fullmatch(r'[a-f0-9]{32}',str(payload.get('history_generation',''))):raise ValueError('Versão histórica inválida')
    for r in rows:
        if set(r)!=(FIELDS|OPERATION_FIELDS if version==2 else FIELDS):raise ValueError('Campo não permitido na carteira pública')
        if len(r['name'].split())>2 or (r['owner'] and len(r['owner'].split())>2):
            raise ValueError('Nome completo recusado')
        for field,value in r.items():
            if field=='history_count':
                if not isinstance(value,int) or isinstance(value,bool) or value<0:raise ValueError('Contagem histórica inválida')
            elif field=='history_key':
                if not re.fullmatch(r'[a-f0-9]{64}',str(value)):raise ValueError('Vínculo histórico inválido')
            elif field in ('last_contact','last_interaction','next_action_at','appointment'):
                from leads_operational_history import timestamp
                if value is not None and timestamp(value)!=value:raise ValueError('Data operacional inválida')
            elif field=='date':
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(value)):raise ValueError('Data inválida')
            elif value is not None and (not isinstance(value,str) or safe_text(value)!=value):
                raise ValueError('Conteúdo público não sanitizado')
    return True
