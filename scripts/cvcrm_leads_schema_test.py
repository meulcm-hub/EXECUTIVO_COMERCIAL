#!/usr/bin/env python3
"""CV CRM: verifica acesso de leitura a leads e informa somente existência de campos."""
import json, os, sys, urllib.error, urllib.parse, urllib.request

def main():
    domain=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    u=urllib.parse.urlsplit(domain)
    if not email or not token or u.scheme!="https" or u.hostname!="lcm.cvcrm.com.br" or u.path not in ("","/") or u.username or u.password or u.query or u.fragment:
        print("Configuração inválida ou incompleta; confira secrets CVCRM_*.")
        return 2
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            return None
    opener=urllib.request.build_opener(NoRedirect())
    params=urllib.parse.urlencode({"pagina":1,"registros_por_pagina":1,"limit":1})
    req=urllib.request.Request(domain+"/api/v1/comercial/leads?"+params,headers={"email":email,"token":token,"Accept":"application/json"})
    try:
        with opener.open(req,timeout=30) as response:
            if response.status!=200:
                print("Consulta de leads não retornou HTTP 200.")
                return 1
            payload=json.load(response)
    except urllib.error.HTTPError as exc:
        print("Consulta de leads: HTTP "+str(exc.code)+". Verifique permissões e endpoint.")
        return 1
    except (urllib.error.URLError,TimeoutError,ValueError):
        print("Consulta de leads: falha de conexão ou resposta inválida.")
        return 1
    # Não imprimir valores, chaves brutas, emails, nomes, IDs ou dados individualizados.
    rows=payload.get("dados",[]) if isinstance(payload,dict) else []
    if isinstance(rows,dict):
        rows=[rows]
    if not isinstance(rows,list):
        print("Formato do resultado inesperado; nenhum dado exposto.")
        return 1
    print("Leads: endpoint de leitura respondeu HTTP 200.")
    if not rows:
        print("Nenhum lead retornado nesta amostra; estrutura ainda não validada.")
        return 0
    sample=rows[0]
    if not isinstance(sample,dict):
        print("Estrutura de lead inesperada.")
        return 1
    keys={str(k).casefold().replace("_","") for k in sample.keys()}
    groups={
       "identificador de lead":("idlead","id"),
       "empreendimento":("idempreendimento","empreendimento","empreendimentos"),
       "data de cadastro":("datacad","datacadastro","createdat"),
       "origem":("origem","idorigem","midia","midiaorigem"),
       "campanha / UTM":("utmcampaign","campaignid","idcampanha","campanha"),
       "situação do lead":("idsituacao","situacao","status"),
    }
    for label, candidates in groups.items():
        print(label+": "+("campo direto presente" if any(x in keys for x in candidates) else "não identificado no nível principal"))
    print("Nota: ausência no nível principal não descarta informações aninhadas ou outros endpoints.")
    return 0

if __name__=="__main__":
    sys.exit(main())
