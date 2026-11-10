#!/usr/bin/env python3
"""Consolidação protegida Meta Ads + CV CVDW para auditoria.

Não publica nem imprime dados pessoais, nomes de empreendimentos, gastos ou campanhas.
A opção --output gera JSON agregado LOCAL para análise controlada; nunca faça commit.
Somente fontes com moeda equivalente podem ser totalizadas e atribuição individual
não é inferida por nomenclatura ou origem Facebook.
"""
import argparse
import collections
import datetime as dt
import decimal
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from meta_ads_collector import request as meta_request, accounts as meta_accounts

D=decimal.Decimal

def norm(s):
    import unicodedata
    s=unicodedata.normalize("NFKD",str(s or "")).casefold()
    return re.sub(r"[^a-z0-9]+"," ", "".join(c for c in s if not unicodedata.combining(c))).strip()

def guess_channel(row):
    original=" ".join(str(row.get(k) or "") for k in ("origem","origem_nome","midia_original","conversao_original")).casefold()
    paid=" ".join(str(row.get(k) or "") for k in ("midia_original","midia_ultimo")).casefold()
    if "facebook" in original or "instagram" in original or re.search(r"\bfb\b",original):
        return "meta_declarada"
    if "google" in original:
        return "google_declarada"
    return "outra_ou_nao_informada"

def cv_page(base,email,token,page,size):
    params=urllib.parse.urlencode({"pagina":page,"registros_por_pagina":size})
    req=urllib.request.Request(base+"/api/v1/cvdw/leads?"+params,
        headers={"email":email,"token":token,"Accept":"application/json"})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl): return None
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=45) as resp:
            payload=json.load(resp)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("CV CVDW: HTTP "+str(exc.code)) from None
    except (urllib.error.URLError,TimeoutError,ValueError):
        raise RuntimeError("CV CVDW: consulta falhou ou JSON inválido") from None
    if not isinstance(payload,dict): raise RuntimeError("CV CVDW: formato inesperado")
    records=payload.get("dados",[])
    if isinstance(records,dict): records=[records]
    if not isinstance(records,list): raise RuntimeError("CV CVDW: dados inválidos")
    return records, payload

def to_date(raw):
    if not raw:return None
    try: return dt.date.fromisoformat(str(raw)[:10])
    except ValueError: return None

def cv_project(row):
    # Primeiro empreendimento evita contar o mesmo lead várias vezes em múltiplos projetos
    raw=row.get("empreendimento_primeiro") or row.get("empreendimento") or "Não identificado"
    if isinstance(raw,dict):
        raw=raw.get("nome") or raw.get("descricao") or raw.get("id") or "Não identificado"
    if isinstance(raw,list):
        raw="Não identificado"
    return str(raw)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--days",type=int,default=30)
    ap.add_argument("--cv-pages",type=int,default=10)
    ap.add_argument("--output",default="",help="Arquivo LOCAL de agregados; nunca publicar automaticamente")
    args=ap.parse_args()
    if not 1<=args.days<=90 or not 1<=args.cv_pages<=50:
        ap.error("days: 1-90; cv-pages: 1-50")
    end=dt.date.today()-dt.timedelta(days=1)
    start=end-dt.timedelta(days=args.days-1)

    url=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    parsed=urllib.parse.urlsplit(url)
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    if parsed.scheme!="https" or parsed.hostname!="lcm.cvcrm.com.br" or parsed.path not in ("","/") or parsed.query or parsed.fragment or parsed.username or parsed.password or not email or not token:
        raise RuntimeError("Credenciais CVCRM_* ausentes ou domínio fora da lista autorizada")

    ads=meta_accounts()
    if len(ads)!=8:
        print("Atenção: contagem atual de contas Meta diferente de oito.")
    per_account=[]
    failures=0
    for a in ads:
        account_id=str(a.get("id",""))
        if not re.fullmatch(r"act_\d+",account_id):
            failures+=1
            continue
        try:
            # /me/adaccounts já retornou nome e moeda; não consultar objeto singular
            # pelo helper paginado, que espera uma coleção em "data".
            detail=a
            rows=meta_request(account_id+"/insights",{
                "fields":"account_id,account_name,campaign_id,campaign_name,date_start,spend,impressions,clicks",
                "level":"campaign","time_increment":1,
                "time_range":json.dumps({"since":start.isoformat(),"until":end.isoformat()}),
                "limit":250
            })
            spend=sum((D(str(r.get("spend") or "0")) for r in rows),D("0"))
            per_account.append({
                "account_id":account_id.removeprefix("act_"),
                "account_name":str(detail.get("name") or a.get("name") or ""),
                "currency":str(detail.get("currency") or a.get("currency") or "DESCONHECIDA"),
                "timezone":str(detail.get("timezone_name") or ""),
                "spend":str(spend),
                "impressions":sum(int(r.get("impressions") or 0) for r in rows),
                "clicks":sum(int(r.get("clicks") or 0) for r in rows),
                "campaign_daily_rows":len(rows)
            })
        except (RuntimeError,decimal.InvalidOperation,ValueError):
            failures+=1
    if failures:
        raise RuntimeError(str(failures)+" conta(s) Meta sem consolidação válida; resultado não publicado")

    size=500
    seen=set()
    per_cv=collections.defaultdict(lambda:collections.Counter())
    inspected=0
    in_period=0
    scanned_pages=0
    exhausted=False
    for page in range(1,args.cv_pages+1):
        rows,payload=cv_page(url,email,token,page,size)
        scanned_pages+=1
        if not rows:
            exhausted=True
            break
        for row in rows:
            if not isinstance(row,dict):
                continue
            inspected+=1
            lead_id=row.get("idlead")
            if lead_id is not None:
                if str(lead_id) in seen: continue
                seen.add(str(lead_id))
            date=to_date(
                row.get("data_cad") or row.get("dataCad") or
                row.get("data_cadastro") or row.get("datacadastro") or
                row.get("referencia_data") or row.get("data")
            )
            if date is None or date<start or date>end:
                continue
            in_period+=1
            project=cv_project(row)
            key=norm(project) or "nao identificado"
            per_cv[key]["leads_period"]+=1
            per_cv[key][guess_channel(row)]+=1
            reservation=row.get("reserva")
            if isinstance(reservation,(int,float,str)) and str(reservation).strip().isdigit() and int(reservation)>0:
                per_cv[key]["leads_with_reservation_flag"]+=1
        # Final de paginação inferido apenas se menos registros que o limite.
        if len(rows)<size:
            exhausted=True
            break

    # Não deduzir vínculo campanha, formulário ou atribuição por similaridade de nomes.
    cv_summary={k:dict(v) for k,v in per_cv.items()}
    currency_set={r["currency"] for r in per_account}
    report={
        "period":{"since":start.isoformat(),"until":end.isoformat()},
        "status":"PARCIAL" if not exhausted else "AMOSTRA_COMPLETA_APENAS_SE_PAGINACAO_VALIDADA",
        "cv_scanned_pages":scanned_pages,"cv_records_scanned":inspected,
        "cv_leads_in_period_in_scanned_pages":in_period,
        "cv_more_pages_possible":not exhausted,
        "meta_accounts":per_account,
        "cv_by_project_normalized":cv_summary,
        "currencies_found":sorted(currency_set),
        "warning":"NÃO atribuir leads ou vendas a campanhas: faltam IDs de campanha/formulário no CV, reconciliação e revisão do período."
    }
    print("Consolidação em memória concluída (sem imprimir valores comerciais).")
    print("Contas Meta consolidadas: "+str(len(per_account)))
    print("Moedas distintas: "+str(len(currency_set))+"; alguma moeda desconhecida: "+str("DESCONHECIDA" in currency_set))
    print("Projetos diferentes na amostra CV: "+str(len(cv_summary)))
    print("Páginas CV examinadas: "+str(scanned_pages)+"; limite atingido: "+str(not exhausted))
    print("Registros CV examinados: "+str(inspected)+"; registros no período dentro da amostra: "+str(in_period))
    print("Atribuição campanha → lead: NÃO VALIDADA")

    # Entrega somente a backend privado, nunca para GitHub Pages ou arquivos públicos.
    ingest_url=os.environ.get("MARKETING_INGEST_URL","").strip()
    ingest_token=os.environ.get("MARKETING_INGEST_TOKEN","").strip()
    if ingest_url or ingest_token:
        if not ingest_url or not ingest_token:
            raise RuntimeError("MARKETING_INGEST_URL e MARKETING_INGEST_TOKEN devem ser configurados juntos")
        endpoint=urllib.parse.urlsplit(ingest_url)
        if (endpoint.scheme!="https" or not endpoint.hostname or
            endpoint.hostname in {"github.com","raw.githubusercontent.com","github.io"} or
            endpoint.hostname.endswith(".github.io") or
            endpoint.username or endpoint.password or endpoint.fragment or endpoint.query):
            raise RuntimeError("Endpoint de ingestão deve ser HTTPS privado, não hospedado no GitHub Pages")
        if not exhausted:
            print("Entrega privada não executada: paginação dos leads CV ainda pode estar incompleta.")
        elif "DESCONHECIDA" in currency_set:
            print("Entrega privada não executada: moeda de uma ou mais contas não confirmada.")
        else:
            # A implantação privada deve validar o Bearer token e restringir leitura por autenticação.
            body=json.dumps(report,ensure_ascii=False,separators=(",",":")).encode("utf-8")
            req=urllib.request.Request(ingest_url,body,headers={
                "Authorization":"Bearer "+ingest_token,
                "Content-Type":"application/json"
            },method="POST")
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self,req,fp,code,msg,headers,newurl):return None
            try:
                with urllib.request.build_opener(NoRedirect()).open(req,timeout=45) as response:
                    if response.status not in (200,201,202,204):
                        raise RuntimeError("Servidor protegido não confirmou a entrega")
            except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError):
                raise RuntimeError("Falha ao enviar consolidação ao backend protegido") from None
            print("Consolidação enviada ao backend protegido (sem imprimir valores).")

    if args.output:
        if os.environ.get("ALLOW_LOCAL_AGGREGATE_EXPORT")!="YES":
            raise RuntimeError("Exportação local bloqueada. Configure ALLOW_LOCAL_AGGREGATE_EXPORT=YES apenas em ambiente privado.")
        if os.environ.get("GITHUB_ACTIONS")=="true":
            raise RuntimeError("Exportação desabilitada em GitHub Actions para evitar exposição em repositório público.")
        with open(args.output,"w",encoding="utf-8") as f:
            json.dump(report,f,ensure_ascii=False,indent=2)
        print("Arquivo agregado salvo apenas no computador local autorizado.")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except RuntimeError as ex:
        print("Erro: "+str(ex),file=sys.stderr)
        sys.exit(1)
