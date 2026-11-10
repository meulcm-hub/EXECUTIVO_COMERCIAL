#!/usr/bin/env python3
"""Diagnóstico read-only de vínculos anúncio -> formulário Meta.
Não imprime identificadores, nomes de campanhas, URLs, token ou dados de leads.
Utiliza somente ads_read; a visibilidade depende do tipo de criativo.
"""
import collections
import re
import sys

from meta_ads_collector import accounts, request

def form_ids(value, depth=0):
    if depth > 10:
        return set()
    found=set()
    if isinstance(value,dict):
        for key, child in value.items():
            if key in ("lead_gen_form_id", "leadgen_form_id", "lead_form_id"):
                if isinstance(child,(str,int)) and re.fullmatch(r"\d+",str(child)):
                    found.add(str(child))
            elif isinstance(child,(dict,list)):
                found.update(form_ids(child,depth+1))
    elif isinstance(value,list):
        for child in value:
            found.update(form_ids(child,depth+1))
    return found

def main():
    all_accounts=accounts()
    if not all_accounts:
        print("Nenhuma conta de anúncios acessível.")
        return 1
    totals=collections.Counter()
    all_form_ids=set()
    errors=0
    print("Diagnóstico Meta Ads: somente leitura, sem dados pessoais ou identificadores individuais.")
    for account in all_accounts:
        aid=str(account.get("id",""))
        if not re.fullmatch(r"act_\d+",aid):
            errors+=1
            continue
        try:
            # A consulta de criativos não coleta leads, textos ou arquivos.
            rows=request(aid+"/ads",{
                "fields":"id,campaign_id,creative{id,object_story_spec,effective_object_story_id}",
                "limit":"100"
            })
        except RuntimeError as e:
            errors+=1
            print("Conta consultada: acesso a anúncios/criativos não confirmado ("+str(e)+").")
            continue
        attached=0
        unresolved=0
        account_forms=set()
        for ad in rows:
            creative=ad.get("creative") or {}
            ids=form_ids(creative.get("object_story_spec",{}))
            if ids:
                attached+=1
                account_forms.update(ids)
            else:
                unresolved+=1
        all_form_ids.update(account_forms)
        totals["ads"]+=len(rows)
        totals["mapped"]+=attached
        totals["unresolved"]+=unresolved
        totals["forms_account_sum"]+=len(account_forms)
        totals["ok_accounts"]+=1
        print("Conta "+str(totals["ok_accounts"]+errors)+": "+str(len(rows))+" anúncios; "+str(attached)+" com ID de formulário no criativo; "+str(len(account_forms))+" formulários distintos.")
    print("RESUMO: "+str(totals["ok_accounts"])+" de "+str(len(all_accounts))+" contas consultadas.")
    print("Anúncios inspecionados: "+str(totals["ads"]))
    print("Anúncios com formulário identificado no criativo: "+str(totals["mapped"]))
    print("Anúncios sem formulário identificado nesse campo: "+str(totals["unresolved"]))
    print("Formulários Meta únicos identificados: "+str(len(all_form_ids)))
    print("Contas com falha: "+str(errors))
    print("ATENÇÃO: não identificado não significa não existente: criativos que usam posts existentes, vídeos ou formulários externos podem exigir outra consulta.")
    print("Os números #122 etc. do CV CRM são IDs internos; não são equiparáveis automaticamente aos IDs Meta.")
    return 1 if errors else 0

if __name__=="__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print("Consulta não concluída: "+str(e),file=sys.stderr)
        sys.exit(1)
