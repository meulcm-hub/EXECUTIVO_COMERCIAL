"""Projeção pública autorizada: dois nomes e dimensões comerciais; nunca contatos."""
import re

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
    if payload.get('schema_version')!=1 or payload.get('validated') is not True or payload.get('scope')!='all_accessible_leads':
        raise ValueError('Contrato público da carteira inválido')
    rows=payload.get('leads')
    if not isinstance(rows,list) or not rows or len(rows)!=payload.get('total'):
        raise ValueError('Carteira pública incompleta')
    for r in rows:
        if set(r)!=FIELDS:raise ValueError('Campo não permitido na carteira pública')
        if len(r['name'].split())>2 or (r['owner'] and len(r['owner'].split())>2):
            raise ValueError('Nome completo recusado')
        for field,value in r.items():
            if field=='date':
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(value)):raise ValueError('Data inválida')
            elif value is not None and (not isinstance(value,str) or safe_text(value)!=value):
                raise ValueError('Conteúdo público não sanitizado')
    return True
