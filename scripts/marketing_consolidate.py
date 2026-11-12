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
import http.client
import time
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

def classify_channel(row):
    """Prioridade: mídia WhatsApp Facebook > origem Busca Compartilhada > demais Meta.

    Uma linha CV entra em exatamente um subtipo, evitando contagem dupla.
    As denominações são regras de negócio informadas pela LCM, não provas de
    atribuição publicitária por campanha.
    """
    origin=norm(" ".join(str(row.get(k) or "") for k in (
        "origem", "origem_nome", "conversao_original")))
    media=norm(" ".join(str(row.get(k) or "") for k in (
        "midia_original", "midia_ultimo", "midia", "midia_nome")))
    if "whatsapp facebook" in media or "facebook whatsapp" in media:
        return "meta_whatsapp_cv"
    if "busca compartilhada" in origin:
        return "meta_busca_compartilhada_cv"
    if any(v in origin+" "+media for v in ("facebook", "instagram")) or re.search(r"\\bfb\\b",origin+" "+media):
        return "meta_outros_cv"
    if "google" in origin+" "+media:
        return "google_declarada"
    return "outra_ou_nao_informada"

def guess_channel(row):
    kind=classify_channel(row)
    return "meta_declarada" if kind.startswith("meta_") else kind

def cv_page(base,email,token,page,size,start,end):
    params=urllib.parse.urlencode({
        "pagina":page,
        "registros_por_pagina":size,
        "a_partir_data_referencia":start.isoformat()+" 00:00:00",
        "ate_data_referencia":end.isoformat()+" 23:59:59"
    })
    req=urllib.request.Request(base+"/api/v1/cvdw/leads?"+params,
        headers={"email":email,"token":token,"Accept":"application/json"})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl): return None
    opener=urllib.request.build_opener(NoRedirect())
    for attempt in range(4):
        delay=2**attempt
        try:
            with opener.open(req,timeout=45) as resp:
                payload=json.load(resp)
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt==3:
                raise RuntimeError("CV CVDW: HTTP "+str(exc.code)) from None
            try: delay=min(60,max(delay,int(exc.headers.get("Retry-After",delay))))
            except (AttributeError,TypeError,ValueError): pass
        except (urllib.error.URLError,TimeoutError,ValueError,http.client.IncompleteRead,ConnectionResetError):
            if attempt==3:
                raise RuntimeError("CV CVDW: resposta incompleta ou indisponível após quatro tentativas") from None
        time.sleep(delay)
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
    ap.add_argument("--public-output",default="",help="JSON de indicadores agregados, autorizados para GitHub Pages")
    args=ap.parse_args()
    if not 1<=args.days<=90 or not 1<=args.cv_pages<=50:
        ap.error("days: 1-90; cv-pages: 1-50")
    end=dt.date.today()
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
    missing_dates=0
    duplicates=0
    pages_announced=None
    page_end_seen=False
    for page in range(1,args.cv_pages+1):
        try:
            rows,payload=cv_page(url,email,token,page,size,start,end)
        except RuntimeError:
            print("Resumo CV não validado nesta coleta; indicadores Meta completos serão preservados.",flush=True)
            exhausted=False
            break
        scanned_pages+=1
        if "total_de_paginas" in payload:
            try:
                pages_announced=int(payload["total_de_paginas"])
            except (ValueError, TypeError):
                raise RuntimeError("CVDW retornou total_de_paginas inválido")
        if not rows:
            exhausted=True
            break
        for row in rows:
            if not isinstance(row,dict):
                continue
            inspected+=1
            lead_id=row.get("idlead")
            if lead_id is not None:
                if str(lead_id) in seen:
                    duplicates+=1
                    continue
                seen.add(str(lead_id))
            date=to_date(
                row.get("data_cad") or row.get("dataCad") or
                row.get("data_cadastro") or row.get("datacadastro") or
                row.get("referencia_data") or row.get("data")
            )
            if date is None:
                missing_dates+=1
                continue
            if date<start or date>end:
                continue
            in_period+=1
            project=cv_project(row)
            key=norm(project) or "nao identificado"
            per_cv[key]["leads_period"]+=1
            subtype=classify_channel(row)
            per_cv[key]["meta_declarada" if subtype.startswith("meta_") else subtype]+=1
            if subtype.startswith("meta_"):
                per_cv[key][subtype]+=1
            reservation=row.get("reserva")
            if isinstance(reservation,(int,float,str)) and str(reservation).strip().isdigit() and int(reservation)>0:
                per_cv[key]["leads_with_reservation_flag"]+=1
        # Final de paginação inferido apenas se menos registros que o limite.
        if pages_announced is not None:
            if page>=pages_announced:
                exhausted=True
                break
        elif len(rows)<size:
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
        "cv_missing_dates":missing_dates,
        "cv_duplicate_ids":duplicates,
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
    print("Datas de cadastro ausentes na amostra: "+str(missing_dates))
    print("Paginação CV completa dentro da janela de referência: "+str(exhausted))
    print("Atribuição campanha → lead: NÃO VALIDADA")
    if args.public_output:
        if not args.public_output.startswith("data/marketing-") or not args.public_output.endswith(".json"):
            raise RuntimeError("Arquivo público deve estar em data/marketing-*.json")
        if len(per_account)!=8 or failures:
            raise RuntimeError("Publicação recusada: não foram consultadas as oito contas")
        if "DESCONHECIDA" in currency_set:
            raise RuntimeError("Publicação recusada: moeda não validada em todas as contas")
        if not all(re.fullmatch(r"[A-Z]{3}",c) for c in currency_set):
            raise RuntimeError("Publicação recusada: código de moeda inesperado")
        if len(per_account)!=len({a["account_id"] for a in per_account}):
            raise RuntimeError("Publicação recusada: contas duplicadas")
        # Dados de leads só são liberados com todas as páginas e datas validadas.
        # CVDW filtra por data de referência; o cadastro é filtrado separadamente.
        # Uma alteração com referência posterior pode afetar a cobertura histórica.
        # Suprimir pequenos grupos para evitar exposição indireta de clientes.
        cv_ready=exhausted and missing_dates==0 and in_period>0 and inspected>=in_period
        public_cv={}
        suppressed=0
        if cv_ready:
            for project,counts in cv_summary.items():
                if counts.get("leads_period",0)>=10 and project!="nao identificado":
                    public_cv[project]={
                        "leads_period":int(counts["leads_period"]),
                        "meta_declarada":int(counts.get("meta_declarada",0)),
                        "meta_whatsapp_cv":int(counts.get("meta_whatsapp_cv",0)),
                        "meta_busca_compartilhada_cv":int(counts.get("meta_busca_compartilhada_cv",0)),
                        "meta_outros_cv":int(counts.get("meta_outros_cv",0)),
                        "google_declarada":int(counts.get("google_declarada",0)),
                        "outra_ou_nao_informada":int(counts.get("outra_ou_nao_informada",0))
                    }
        # Se CV for parcial, manter os indicadores indisponíveis e não inventar zeros.
        public={
            "schema_version":1,
            "cv_channel_rules_version":2,
            "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "period":{"since":start.isoformat(),"until":end.isoformat()},
            "status":"COMPLETO_META_CV_AGREGADO" if cv_ready else "COMPLETO_META_CV_NAO_VALIDADO",
            "meta_accounts":[{
                "account_id":a["account_id"],
                "account_name":a["account_name"][:90],
                "currency":a["currency"],
                "spend":a["spend"],
                "impressions":a["impressions"],
                "clicks":a["clicks"]
            } for a in per_account],
            "cv_by_project_normalized":public_cv,
            "cv_counts_validated":bool(cv_ready),
            "cv_date_scope":"referencia_filtrada_e_cadastro_validado",
            "cv_completeness_warning":"CVDW usa data de referência na consulta; registros históricos alterados fora da janela podem ficar de fora.",
            "cv_more_pages_possible":not exhausted,
            "currencies_found":sorted(currency_set),
            "warning":"Origem Facebook/Instagram não comprova campanha paga; vendas atribuídas indisponíveis."
        }
        os.makedirs("data",exist_ok=True)
        temp=args.public_output+".tmp"
        with open(temp,"w",encoding="utf-8") as handle:
            json.dump(public,handle,ensure_ascii=False,indent=2)
        os.replace(temp,args.public_output)
        print("JSON público de indicadores agregados validado e gerado sem registros individuais.")
        print("CV liberado: "+str(bool(cv_ready))+"; grupos grandes: "+str(len(public_cv)))

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
