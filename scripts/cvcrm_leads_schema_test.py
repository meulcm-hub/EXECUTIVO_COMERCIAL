#!/usr/bin/env python3
"""Diagnóstico seguro do endpoint analítico de leads do CV CRM.
Não imprime nem salva dados pessoais; somente status e presença de campos.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

def main():
    domain=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    u=urllib.parse.urlsplit(domain)
    if not email or not token or u.scheme!="https" or u.hostname!="lcm.cvcrm.com.br" or u.path not in ("","/") or u.username or u.password or u.query or u.fragment:
        print("Credenciais incompletas ou domínio inesperado; confira os segredos CVCRM_*.")
        return 2
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            return None
    opener=urllib.request.build_opener(NoRedirect())
    query=urllib.parse.urlencode({"pagina":1,"registros_por_pagina":1})
    url=domain+"/api/v1/cvdw/leads?"+query
    req=urllib.request.Request(url,headers={"email":email,"token":token,"Accept":"application/json"})
    try:
        with opener.open(req,timeout=30) as response:
            if response.status!=200:
                print("CVDW Leads: resposta não esperada.")
                return 1
            payload=json.load(response)
    except urllib.error.HTTPError as exc:
        status=exc.code
        if status==403:
            print("CVDW Leads: HTTP 403; verificar permissão ou contratação/habilitação de CVDW.")
        elif status==404:
            print("CVDW Leads: HTTP 404; rota analítica não disponível nesta base.")
        elif status in (401,):
            print("CVDW Leads: HTTP 401; autenticação recusada.")
        else:
            print("CVDW Leads: HTTP "+str(status)+".")
        return 1
    except (urllib.error.URLError,TimeoutError,ValueError):
        print("CVDW Leads: falha de rede ou resposta inválida.")
        return 1

    if not isinstance(payload,dict):
        print("CVDW Leads: resposta JSON de formato inesperado.")
        return 1
    rows=payload.get("dados",[])
    if isinstance(rows,dict): rows=[rows]
    if not isinstance(rows,list):
        print("CVDW Leads: formato de dados inesperado.")
        return 1
    print("CVDW Leads: acesso HTTP 200 confirmado.")
    # Total informado pelo servidor pode diferir da amostra 1; não exibir valores individuais.
    print("Amostra de lead disponível: "+("sim" if bool(rows) else "não"))
    if not rows:
        print("Sem lead na amostra; conferir filtros de referência e permissões com o CV CRM.")
        return 0
    item=rows[0]
    if not isinstance(item,dict):
        print("Registro inesperado, sem exposição de conteúdo.")
        return 1
    def norm(k):
        return "".join(x for x in str(k).casefold() if x.isalnum())
    keys={norm(k) for k in item}
    groups={
        "ID do lead":("idlead","id"),
        "Empreendimento":("idempreendimento","empreendimento"),
        "Data de referência/cadastro":("referenciadata","datacad","datacadastro"),
        "Origem/mídia":("idorigem","origem","idmidia","midia"),
        "Campanha/UTM":("utmcampaign","idcampanha","campaignid","campanha"),
        "Situação":("idsituacao","situacao","status")
    }
    for label,options in groups.items():
        print(label+": "+("campo no nível principal" if any(norm(v) in keys for v in options) else "não identificado no nível principal"))
    print("Não foram impressos dados, nomes de campos brutos nem valores pessoais.")
    return 0

if __name__=="__main__":
    sys.exit(main())
