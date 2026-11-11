#!/usr/bin/env python3
"""Consolidado CV CRM agregado: cadastros originais e conversões por empreendimento/dia.

O relacionamento por idlead e ID de empreendimento ocorre APENAS na memória
do runner privado. O JSON público contém somente contagens; nunca IDs de leads.
"""
import collections
import datetime as dt
import json
import os
import sys
from cv_join_original_conversions import read_complete, get_lead_page, read_conversion_page
from marketing_consolidate import norm, to_date, classify_channel
from cv_conversion_audit import source as conversion_source

PROJECTS=(
    "residencial flores do cerrado jacaranda",
    "residencial village lagoas",
    "spe arraial costa verde club",
    "residencial jatoba",
)
DAYS=90

def acquisition_channel(row):
    """Facebook inclui Busca Compartilhada e WhatsApp Facebook; Google separado."""
    kind=classify_channel(row)
    if kind.startswith("meta_"):return "facebook"
    if kind=="google_declarada":return "google"
    return None

def event_channel(row):
    """Prioriza a origem e mídia da conversão, não o canal original do lead."""
    kind=conversion_source(row)
    if kind.startswith("meta_"):return "facebook"
    if kind=="google_declarada":return "google"
    return None

def main():
    base=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    from urllib.parse import urlsplit
    u=urlsplit(base)
    if u.scheme!="https" or u.hostname!="lcm.cvcrm.com.br" or u.path not in ("","/") or u.query or u.fragment or u.username or u.password or not email or not token:
        raise RuntimeError("Credenciais CV CRM indisponíveis")
    until=dt.date.today()
    since=until-dt.timedelta(days=DAYS-1)
    history_start=dt.date(2022,1,1)
    if since<history_start:raise RuntimeError("Histórico ainda não disponível")

    # Pré-validação rápida: conversões sem ID do empreendimento do evento
    # não permitem total por empreendimento. Detectar ANTES de consultar
    # todos os cadastros desde 2022 (operação longa).
    preflight=collections.Counter()
    preflight_ids=set()
    for row in read_complete(base,email,token,since,until,read_conversion_page,"pre-validacao-conversoes"):
        if not isinstance(row,dict):
            preflight["registro_invalido"]+=1
            continue
        event_id=row.get("idlead_conversao")
        if event_id is None:
            preflight["sem_id_evento"]+=1
            continue
        event_id=str(event_id)
        if event_id in preflight_ids:continue
        preflight_ids.add(event_id)
        assoc=row.get("empreendimentos_conversao")
        if not isinstance(assoc,list):
            preflight["associacao_invalida"]+=1
        elif not assoc:
            preflight["empreendimento_nao_registrado"]+=1
        elif len(assoc)>1:
            preflight["mais_de_um_empreendimento"]+=1
        else:
            preflight["com_empreendimento_evento"]+=1
    print("Pré-validação CV: "+str(len(preflight_ids))+
          " eventos; com empreendimento do evento "+
          str(preflight["com_empreendimento_evento"])+
          "; sem empreendimento do evento "+
          str(preflight["empreendimento_nao_registrado"])+
          "; associações inválidas "+
          str(preflight["associacao_invalida"])+
          "; associações múltiplas "+
          str(preflight["mais_de_um_empreendimento"])+".",flush=True)
    # Eventos sem empreendimento são excluídos dos indicadores por projeto.
    # Isso NÃO prova que são antigos. Não precisamos ler os cadastros para
    # descobrir isso; a avaliação completa de qualidade segue abaixo.
    if preflight["registro_invalido"] or preflight["sem_id_evento"]:
        raise RuntimeError("Existem conversões sem ID de evento; deduplicação insegura.")
    if preflight["empreendimento_nao_registrado"]:
        print("Eventos sem empreendimento do evento serão excluídos dos indicadores por empreendimento, sem inferir idade do lead.",flush=True)
    if preflight["associacao_invalida"] or preflight["mais_de_um_empreendimento"]:
        print("Associações inválidas ou múltiplas serão tratadas como não atribuíveis.",flush=True)

    original={}
    project_alias=collections.defaultdict(set)
    conflicting=set()
    lead_records=0
    for row in read_complete(base,email,token,history_start,until,get_lead_page,"cadastros"):
        lead=row.get("idlead")
        date=to_date(row.get("data_cad"))
        if lead is None or not date:continue
        lead=str(lead)
        lead_records+=1
        first_project=norm(row.get("empreendimento_primeiro") or row.get("empreendimento"))
        last_project=norm(row.get("empreendimento_ultimo"))
        if lead in original and (date,first_project)!=(original[lead][0],original[lead][1]):
            conflicting.add(lead)
        original[lead]=(date,first_project,acquisition_channel(row),classify_channel(row)=="meta_whatsapp_cv")
        for id_field,name in (("idempreendimento_primeiro",first_project),("idempreendimento_ultimo",last_project)):
            project_id=row.get(id_field)
            if project_id is not None and name:
                project_alias[str(project_id)].add(name)
        # O campo CVDW "idempreendimento" pode conter vários IDs e
        # "empreendimento" vários nomes. Usar apenas quando ambos são
        # inequívocos (um único identificador e um único nome).
        import re
        extra_ids=re.findall(r"\d+",str(row.get("idempreendimento") or ""))
        extra_name=norm(row.get("empreendimento"))
        if len(extra_ids)==1 and extra_name and (
            extra_name==first_project or extra_name==last_project):
            project_alias[extra_ids[0]].add(extra_name)
    # Um ID não pode mapear para nomes diferentes se algum for um dos quatro
    # projetos em exibição. Nunca escolher um nome arbitrariamente.
    project_by_id={}
    ambiguous_ids=set()
    for project_id,names in project_alias.items():
        relevant=names.intersection(PROJECTS)
        if len(names)==1:
            # Identificar também os projetos externos ao recorte para não
            # confundi-los com conversões sem correspondência.
            project_by_id[project_id]=next(iter(names))
        elif relevant:
            ambiguous_ids.add(project_id)

    dates=[(since+dt.timedelta(days=i)).isoformat() for i in range(DAYS)]
    new_by_date=collections.defaultdict(collections.Counter)
    for lead,(first,first_project,channel,is_whatsapp) in original.items():
        if lead in conflicting:continue
        if first_project in PROJECTS and since<=first<=until and channel:
            new_by_date[first_project][first.isoformat()]+=1
            new_by_date[first_project][(first.isoformat(),channel)]+=1
            if is_whatsapp:new_by_date[first_project][(first.isoformat(),"whatsapp")]+=1

    daily_events=collections.defaultdict(collections.Counter)
    daily_unique=collections.defaultdict(lambda:collections.defaultdict(set))
    daily_returning=collections.defaultdict(lambda:collections.defaultdict(set))
    daily_returning_whatsapp=collections.defaultdict(lambda:collections.defaultdict(set))
    daily_unclassified=collections.defaultdict(lambda:collections.defaultdict(set))
    event_ids=set()
    invalid=0
    unknown_project=0
    ambiguous=0
    matched=0
    external_mapped=0
    unknown_evidence=collections.Counter()
    invalid_evidence=collections.Counter()
    for row in read_complete(base,email,token,since,until,read_conversion_page,"conversoes"):
        eid=row.get("idlead_conversao")
        lead=row.get("idlead")
        date=to_date(row.get("referencia_data"))
        if eid is None or lead is None or date is None or date<since or date>until:
            invalid+=1
            invalid_evidence["sem_id_data"]+=1
            continue
        eid=str(eid)
        lead=str(lead)
        if eid in event_ids:continue
        event_ids.add(eid)
        assoc=row.get("empreendimentos_conversao")
        if not isinstance(assoc,list):
            invalid+=1
            invalid_evidence["lista_formato_invalido"]+=1
            continue
        # Quando a lista tem 1 ID, ela representa o empreendimento daquela
        # conversão. Sem lista, usar o empreendimento_ultimo do evento.
        # Listas múltiplas são ambíguas, não distribuímos o evento duas vezes.
        if len(assoc)>1:
            ambiguous+=1
            continue
        # Sem empreendimento historicamente registrado na conversão, o último
        # empreendimento do lead NÃO prova a origem do evento. Não atribuir.
        if not assoc:
            unknown_project+=1
            unknown_evidence["lista_vazia"]+=1
            continue
        project_id=str(assoc[0])
        if project_id in ambiguous_ids:
            ambiguous+=1
            continue
        project=project_by_id.get(project_id)
        if project is None:
            unknown_project+=1
            info=original.get(lead)
            if info is None:unknown_evidence["sem_cadastro_associado"]+=1
            elif info[1] in PROJECTS:unknown_evidence["cadastro_inicial_projeto_alvo"]+=1
            else:unknown_evidence["cadastro_inicial_outro_projeto"]+=1
            continue
        if project not in PROJECTS:
            external_mapped+=1
            continue
        info=original.get(lead)
        channel=event_channel(row)
        if channel is None:continue
        day=date.isoformat()
        matched+=1
        daily_events[project][day]+=1
        daily_events[project][(day,channel)]+=1
        daily_unique[project][day].add(lead)
        if info is None or lead in conflicting or info[0]>date:
            # Conversão e lead único são identificados pelo evento, mas
            # retorno não pode ser inferido sem cadastro original coerente.
            daily_unclassified[project][day].add(lead)
            invalid_evidence["sem_original_ou_conflito"]+=1
        elif info[0]<date:
            daily_returning[project][day].add(lead)
            if info[3]:daily_returning_whatsapp[project][day].add(lead)

    print("Cobertura de eventos (somente contagens): vinculados aos 4 projetos "+str(matched)+
          "; outros projetos reconhecidos "+str(external_mapped)+
          "; sem empreendimento ou sem mapeamento "+str(unknown_project)+
          "; associações múltiplas "+str(ambiguous)+
          "; não classificáveis quanto ao retorno "+str(invalid_evidence.get("sem_original_ou_conflito",0)),flush=True)
    # Não usar os registros sem empreendimento como prova de retorno ou
    # como conversões atribuídas a um dos quatro projetos.
    if invalid:
        raise RuntimeError("Existem eventos sem ID, data ou estrutura válida. Consolidação bloqueada.")

    # Unicidade no período: não somar 'leads únicos por dia', pois um lead
    # pode converter em dois dias da seleção. Pré-calcular todos os intervalos.
    unique_ranges={}
    for i,first in enumerate(dates):
        sets={p:set() for p in PROJECTS}
        returned={p:set() for p in PROJECTS}
        returned_whatsapp={p:set() for p in PROJECTS}
        unknown={p:set() for p in PROJECTS}
        for second in dates[i:]:
            for p in PROJECTS:
                sets[p].update(daily_unique[p].get(second,()))
                returned[p].update(daily_returning[p].get(second,()))
                returned_whatsapp[p].update(daily_returning_whatsapp[p].get(second,()))
                unknown[p].update(daily_unclassified[p].get(second,()))
            unique_ranges[first+"|"+second]={
                "unique":{**{p:len(sets[p]) for p in PROJECTS},
                          "all":len(set().union(*sets.values()))},
                "returning":{**{p:len(returned[p]) for p in PROJECTS},
                             "all":len(set().union(*returned.values()))},
                "returning_whatsapp":{**{p:len(returned_whatsapp[p]) for p in PROJECTS},
                                      "all":len(set().union(*returned_whatsapp.values()))},
                "unclassified_return":{**{p:len(unknown[p]) for p in PROJECTS},
                                        "all":len(set().union(*unknown.values()))},
            }
    def daily_for(p):
        return {d:{"new":new_by_date[p][d],
                   "facebook_new":new_by_date[p][(d,"facebook")],
                   "whatsapp_new":new_by_date[p][(d,"whatsapp")],
                   "google_new":new_by_date[p][(d,"google")],
                   "conversions":daily_events[p][d],
                   "facebook_conversions":daily_events[p][(d,"facebook")],
                   "google_conversions":daily_events[p][(d,"google")]}
                for d in dates}
    report={
        "schema_version":3,
        "channel_scope":"facebook_google",
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "period":{"since":since.isoformat(),"until":until.isoformat()},
        "validated":True,
        "coverage":"identified_events_only",
        "identification_scope":"Conversões incluídas somente se o empreendimento da conversão for identificado inequivocamente. Retornos somente com cadastro original consistente.",
        "projects":list(PROJECTS),
        "daily":{p:daily_for(p) for p in PROJECTS},
        "range_unique":unique_ranges,
        "method":"Novos por data_cad original, primeiro empreendimento e origem Facebook/Google; conversões com empreendimento e origem de evento Facebook/Google; retornos posteriores ao dia do cadastro; sem dupla contagem por ID.",
        "caveat":"Indicadores limitados a eventos com empreendimento de conversão identificado. Eventos sem vínculo de empreendimento foram excluídos; isso não indica que sejam antigos. Retornos sem cadastro original válido ficam indeterminados. Conversões múltiplas no dia do cadastro não contam como retorno; não há atribuição a campanhas Meta.",
    }
    os.makedirs("data",exist_ok=True)
    path="data/marketing-conversions.json"
    with open(path+".tmp","w",encoding="utf-8") as fh:
        json.dump(report,fh,ensure_ascii=False,separators=(",",":"))
    os.replace(path+".tmp",path)
    print("CONSOLIDADO CV - FACEBOOK E GOOGLE - PREPARADO PARA PUBLICAÇÃO")
    print("Dias: "+str(DAYS)+"; projetos: "+str(len(PROJECTS)))
    print("Leads históricos válidos: "+str(len(original)))
    print("Eventos CV de projetos vinculados: "+str(matched))
    print("Registros de cadastro lidos: "+str(lead_records))
    print("Intervalos únicos calculados: "+str(len(unique_ranges)))
    print("Somente contagens agregadas, sem IDs, nomes ou contatos no arquivo.")
if __name__=="__main__":
    try:main()
    except (RuntimeError,ValueError,TypeError) as exc:
        print("Consolidação de conversões bloqueada: "+str(exc),file=sys.stderr)
        sys.exit(1)
