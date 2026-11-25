"""Diagnóstico temporário de autoria: resultados agregados, sem dados pessoais."""
import collections
import datetime as dt
import json
import os
import re
import unicodedata

from leads_full_history import credentials
from leads_operational_history import request
from leads_sales_funnel import read_pages


def normalize(value):
    return ' '.join(re.findall(r'[a-z0-9]+', unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()))


# Referências reduzidas, na ordem solicitada; o relatório contém somente contagens.
TARGETS = ('gleice', 'vitoria cristina', 'rayana', 'mislaine silva',
           'amanda correa', 'ronysteberte seabra', 'aniely bruna')
ACTOR = re.compile(r'usuario|user|autor|responsavel|analista|correspondente|gestor|corretor|operador|executad|alterad|criad|movimentad|atendente', re.I)
FIELD = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,79}$')


def scan(rows):
    fields = collections.Counter()
    matches = collections.defaultdict(collections.Counter)
    folders = collections.defaultdict(lambda: collections.defaultdict(set))
    for row in rows:
        for field, value in row.items():
            if not FIELD.fullmatch(field) or not ACTOR.search(field):
                continue
            if value is not None and value != '': fields[field] += 1
            candidates = [(field, value)] if isinstance(value, str) else []
            if isinstance(value, dict):
                candidates.extend((field+'.'+k, v) for k,v in value.items() if k in ('nome','name','nome_usuario','usuario_nome') and isinstance(v,str))
            for path, name in candidates:
                normalized = ' '+normalize(name)+' '
                for i, target in enumerate(TARGETS,1):
                    if ' '+target+' ' in normalized:
                        matches[path][i] += 1
                        if row.get('idprecadastro') is not None:
                            folders[path][i].add(str(row['idprecadastro']))
    return {'candidate_fields':dict(fields), 'matched_events':{k:dict(v) for k,v in matches.items()},
            'matched_folders':{k:{i:len(ids) for i,ids in v.items()} for k,v in folders.items()}}


def main():
    base,email,token=credentials(os.environ)
    cutoff=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    rows,meta=read_pages(lambda p:request(base,email,token,'/api/v1/cvdw/precadastro/historico/situacoes',p,cutoff),'idhistorico')
    print('Diagnóstico autoria:',json.dumps({'events':len(rows),'pages':meta['pages'],**scan(rows.values())},sort_keys=True))


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('Diagnóstico interrompido:',type(exc).__name__)
        raise SystemExit(1) from None
