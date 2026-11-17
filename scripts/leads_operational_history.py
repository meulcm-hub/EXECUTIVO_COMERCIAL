"""Histórico estruturado público; IDs e textos livres ficam somente em memória."""
import datetime as dt
import hashlib
import hmac
import json
import http.client
import time
import urllib.error
import urllib.parse
import urllib.request
from leads_public_projection import safe_text
from cvcrm_project_address_audit import NoRedirect
from cvcrm_read_pacing import PACER, retry_after

ROUTES={'interaction':'interacoes','task':'tarefas','visit':'visitas','stage':'historico/situacoes'}
TYPES={'A':'Anotação','L':'Ligação','E':'E-mail','S':'SMS','W':'WhatsApp','V':'Visita','T':'Tarefa'}
STATES={'P':'Pendente','A':'Em andamento','C':'Concluída','CA':'Cancelada'}

def timestamp(value):
    if not isinstance(value,str):return None
    try:
        parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.year<1990:return None
        return parsed.replace(tzinfo=None).isoformat(timespec='seconds')
    except ValueError:return None

def opaque(secret,namespace,value):
    return hmac.new(secret.encode(),(namespace+':'+str(value)).encode(),hashlib.sha256).hexdigest()

def request(base,email,token,path,page,end_reference=None):
    opener=urllib.request.build_opener(NoRedirect())
    params={'pagina':page,'registros_por_pagina':500}
    if end_reference:params['ate_data_referencia']=end_reference
    url=base+path+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'email':email,'token':token,'Accept':'application/json'})
    for attempt in range(12):
        PACER.wait()
        try:
            with opener.open(req,timeout=90) as response:
                if response.status==204:return {'dados':[],'total_de_paginas':0,'total_de_registros':0}
                raw=response.read(16_000_001)
                if len(raw)>16_000_000:raise RuntimeError('Página operacional excedeu limite')
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            if error.code==429 and attempt<11:
                delay=retry_after(error.headers)
                print('CV CRM: limite CVDW atingido; pausa de',round(delay),'segundos antes de repetir a mesma página.',flush=True)
                PACER.cooldown(delay)
                continue
            if error.code not in (500,502,503,504) or attempt>=5:
                raise RuntimeError('Fonte operacional '+path+': HTTP '+str(error.code)) from None
        except (OSError,http.client.HTTPException,json.JSONDecodeError):
            if attempt>=5:raise RuntimeError('Fonte operacional indisponível: '+path) from None
            print('CV CRM: resposta interrompida ou inválida; repetindo página',page,'da fonte',path,'· tentativa',attempt+2,flush=True)
        time.sleep(min(60,3*2**attempt))
    raise RuntimeError('Fonte operacional não concluída: '+path)

def collect_source(kind,fetch):
    latest={};signatures=set();expected=None;pages=None;scanned=0
    for page in range(1,10001):
        payload=fetch(page)
        if not isinstance(payload,dict) or not isinstance(payload.get('dados'),list):raise RuntimeError('Esquema operacional inválido')
        count=int(payload['total_de_registros']);n=int(payload['total_de_paginas'])
        if expected is None:expected,pages=count,n
        if (count,n)!=(expected,pages):raise RuntimeError('Fonte operacional mudou durante a coleta; publicação interrompida')
        batch=payload['dados']
        if count==0 and n==0 and not batch:return {},{'records':0,'pages':0}
        if not batch or not 1<=n<=10000:raise RuntimeError('Paginação operacional incompleta')
        signature=hashlib.sha256(json.dumps(batch,sort_keys=True).encode()).hexdigest()
        if signature in signatures:raise RuntimeError('Página operacional repetida')
        signatures.add(signature);scanned+=len(batch)
        for row in batch:
            if not isinstance(row,dict):raise RuntimeError('Registro operacional inválido')
            idfield={'interaction':'idinteracao','task':'idtarefa','visit':'idtarefa','stage':'idhistorico'}[kind]
            identity=str(row.get(idfield) or row.get('referencia') or '')
            lead=str(row.get('idlead') or '')
            if not identity or not lead:raise RuntimeError('Vínculo operacional ausente')
            reference=timestamp(row.get('referencia_data')) or timestamp(row.get('data_cad'))
            if not reference:raise RuntimeError('Referência operacional ausente')
            old=latest.get(identity)
            if old and old['reference']==reference and old['raw']!=row:raise RuntimeError('Snapshot operacional conflitante')
            if not old or reference>old['reference']:latest[identity]={'lead':lead,'reference':reference,'raw':row}
        if page==n:break
        if page%50==0:print('Histórico:',kind,'páginas',page,'de',n,flush=True)
        time.sleep(.15)
    if len(signatures)!=pages or scanned!=expected:raise RuntimeError('Total operacional não conferiu')
    return latest,{'records':scanned,'pages':pages}

def event(kind,row):
    if str(row.get('ativo','S')).upper()!='S':return None
    date=timestamp(row.get('data_cad'))
    if not date:return None
    if kind=='stage':
        return {'kind':'stage','date':date,'type':'Mudança de etapa','state':None,
                'from':safe_text(row.get('de_nome','')),'to':safe_text(row.get('para_nome','')),'scheduled_at':None}
    code=str(row.get('tipo') if kind=='interaction' else row.get('tipo_interacao') or '').upper()
    state=STATES.get(str(row.get('situacao') or '').upper()) if kind!='interaction' else None
    due=timestamp(row.get('data')) if kind in ('task','visit') else None
    if state=='Concluída':date=timestamp(row.get('data_conclusao')) or date
    elif state=='Cancelada':date=timestamp(row.get('data_cancelamento')) or date
    return {'kind':kind,'date':date,'type':TYPES.get(code,'Visita' if kind=='visit' else 'Interação' if kind=='interaction' else 'Tarefa'),
            'state':state,'from':None,'to':None,'scheduled_at':due}

def assemble(sources,secret):
    grouped={}
    for kind in ('interaction','task','visit','stage'):
        for identity,item in sources.get(kind,{}).items():
            value=event(kind,item['raw'])
            if not value:continue
            lead=item['lead'];events=grouped.setdefault(lead,{})
            # Visitas e tarefas compartilham o ID: a fonte de visitas é mais específica.
            key=('task' if kind=='visit' else kind)+':'+identity
            events[key]=value
    return {lead:sorted(values.values(),key=lambda x:(x['date'],x['kind'],x['type']),reverse=True)
            for lead,values in grouped.items()}

def fetch_all(base,email,token,*,end_reference=None):
    from zoneinfo import ZoneInfo
    end_reference=end_reference or dt.datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d %H:%M:%S')
    sources={};metadata={}
    # A cota CVDW é compartilhada entre rotas; não paralelizar as fontes.
    for kind,route in ROUTES.items():
        path='/api/v1/cvdw/leads/'+route
        print('Iniciando fonte histórica:',kind,flush=True)
        sources[kind],metadata[kind]=collect_source(kind,lambda page,p=path:request(base,email,token,p,page,end_reference))
        print('Fonte histórica validada:',kind,metadata[kind],flush=True)
    return assemble(sources,token),metadata

def summary(events):
    # Registro de contato não prova ligação atendida ou mensagem respondida.
    contacts=[e['date'] for e in events if e['kind']=='interaction' and e['type'] in ('Ligação','E-mail','SMS','WhatsApp','Visita')]
    tasks=[e for e in events if e['kind'] in ('task','visit') and e['state'] in ('Pendente','Em andamento') and e['scheduled_at']]
    next_task=min(tasks,key=lambda e:e['scheduled_at']) if tasks else None
    return {'last_contact':max(contacts) if contacts else None,
            'last_interaction':max((e['date'] for e in events if e['kind']=='interaction'),default=None),
            'next_action':next_task['type'] if next_task else None,
            'next_action_at':next_task['scheduled_at'] if next_task else None,
            'appointment':min((e['scheduled_at'] for e in tasks if e['kind']=='visit' or e['type']=='Visita'),default=None),
            'history_count':len(events)}

EVENT_FIELDS={'kind','date','type','state','from','to','scheduled_at'}
def validate_event(e):
    if not isinstance(e,dict) or set(e)!=EVENT_FIELDS or e['kind'] not in ROUTES or timestamp(e['date'])!=e['date']:raise ValueError('Evento público inválido')
    allowed=set(TYPES.values())|{'Mudança de etapa','Interação'}
    if e['type'] not in allowed or e['state'] not in (None,*STATES.values()):raise ValueError('Tipo ou situação não permitido')
    if e['scheduled_at'] is not None and timestamp(e['scheduled_at'])!=e['scheduled_at']:raise ValueError('Agendamento inválido')
    for key in ('from','to'):
        if e[key] is not None and safe_text(e[key])!=e[key]:raise ValueError('Etapa não sanitizada')
    return True
