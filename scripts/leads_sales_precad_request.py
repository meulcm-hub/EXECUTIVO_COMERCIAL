"""Transporte REST paginado com a mesma cadência conservadora das fontes CVDW."""
import http.client
import json
import time
import urllib.error
import urllib.request
from cvcrm_project_address_audit import NoRedirect
from cvcrm_read_pacing import PACER,retry_after

def request_pre(base,email,token,page):
    req=urllib.request.Request(base+'/api/v1/comercial/precadastro?pagina='+str(page)+'&limite=500',headers={'email':email,'token':token,'Accept':'application/json'})
    opener=urllib.request.build_opener(NoRedirect())
    for attempt in range(12):
        PACER.wait()
        try:
            with opener.open(req,timeout=90) as response:
                raw=response.read(16_000_001)
                if len(raw)>16_000_000:raise RuntimeError('Página de pré-cadastro excedeu limite')
                return json.loads(raw)
        except urllib.error.HTTPError as err:
            if err.code==429 and attempt<11:PACER.cooldown(retry_after(err.headers));continue
            if err.code not in (500,502,503,504) or attempt>=5:raise RuntimeError('Pré-cadastro HTTP '+str(err.code)) from None
        except (OSError,http.client.HTTPException,json.JSONDecodeError):
            if attempt>=5:raise RuntimeError('Pré-cadastro indisponível após tentativas') from None
        time.sleep(min(60,3*2**attempt))
    raise RuntimeError('Pré-cadastro não concluído')
