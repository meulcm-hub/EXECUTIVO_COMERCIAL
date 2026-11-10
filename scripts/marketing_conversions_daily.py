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
from marketing_consolidate import norm, to_date

PROJECTS=(
    "residencial flores do cerrado jacaranda",
    "residencial village lagoas",
    "spe arraial costa verde club",
    "residencial jatoba",
)
DAYS=90

def main():
    base=os.environ.get("CVCRM_DOMINIO","").strip().rstrip("/")
    email=os.environ.get("CVCRM_EMAIL","").strip()
    token=os.environ.get("CVCRM_TOKEN","").strip()
    from urllib.parse import urlsplit
    u=urlsplit(base)
    if u.scheme!="https" or u.hostname!="lcm.cvcrm.com.br" or u.path not in ("","/") or u.query or u.fragment or u.username or u.password or not email or not token:
        raise RuntimeError("Credenciais CV CRM indisponíveis")
    until=dt.date.today()-dt.timedelta(days=1)
    since=until-dt.timedelta(days=DAYS-1)
    history_start=dt.date(2022,1,1)
    if since<history_start:raise RuntimeError("Histórico ainda não disponível")

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
        if lead in original and (date,first_project)!=original[lead]:
            conflicting.add(lead)
        original[lead]=(date,first_project)
        for id_field,name in (("idempreendimento_primeiro",first_project),("idempreendimento_ultimo",last_project),("idempreendimento",norm(row.get("empreendimento")))):
            project_id=row.get(id_field)
            if project_id is not None and name:
                project_alias[str(project_id)].add(name)
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
    for lead,(first,first_project) in original.items():
        if lead in conflicting:continue
        if first_project in PROJECTS and since<=first<=until:
            new_by_date[first_project][first.isoformat()]+=1

    daily_events=collections.defaultdict(collections.Counter)
    daily_unique=collections.defaultdict(lambda:collections.defaultdict(set))
    daily_returning=collections.defaultdict(lambda:collections.defaultdict(set))
    event_ids=set()
    invalid=0
    unknown_project=0
    ambiguous=0
    matched=0
    for row in read_complete(base,email,token,since,until,read_conversion_page,"conversoes"):
        eid=row.get("idlead_conversao")
        lead=row.get("idlead")
        date=to_date(row.get("referencia_data"))
        if eid is None or lead is None or date is None or date<since or date>until:
            invalid+=1
            continue
        eid=str(eid)
        lead=str(lead)
        if eid in event_ids:continue
        event_ids.add(eid)
        assoc=row.get("empreendimentos_conversao")
        if not isinstance(assoc,list):
            invalid+=1
            continue
        # Quando a lista tem 1 ID, ela representa o empreendimento daquela
        # conversão. Sem lista, usar o empreendimento_ultimo do evento.
        # Listas múltiplas são ambíguas, não distribuímos o evento duas vezes.
        if len(assoc)>1:
            ambiguous+=1
            continue
        project_id=str(assoc[0] if assoc else row.get("empreendimento_ultimo"))
        if project_id in ambiguous_ids:
            ambiguous+=1
            continue
        project=project_by_id.get(project_id)
        if project is None:
            unknown_project+=1
            continue
        if project not in PROJECTS:continue
        info=original.get(lead)
        if info is None or lead in conflicting or info[0]>date:
            invalid+=1
            continue
        day=date.isoformat()
        matched+=1
        daily_events[project][day]+=1
        daily_unique[project][day].add(lead)
        if info[0]<date:
            daily_returning[project][day].add(lead)

    # Cobertura: IDs de empreendimento que não foram mapeados poderiam
    # corresponder aos projetos mostrados; nessas condições não publicar.
    if invalid or ambiguous or unknown_project:
        raise RuntimeError(
            "Cobertura de conversões não validada: "+str(invalid)+
            " registros inválidos; "+str(ambiguous)+
            " projetos ambíguos; "+str(unknown_project)+
            " projetos sem correspondência. Nenhum novo agregado publicado.")
    if conflicting:
        raise RuntimeError("Datas originais conflitantes: classificação bloqueada")

    # Unicidade no período: não somar 'leads únicos por dia', pois um lead
    # pode converter em dois dias da seleção. Pré-calcular todos os intervalos.
    unique_ranges={}
    for i,first in enumerate(dates):
        sets={p:set() for p in PROJECTS}
        returned={p:set() for p in PROJECTS}
        for second in dates[i:]:
            for p in PROJECTS:
                sets[p].update(daily_unique[p].get(second,()))
                returned[p].update(daily_returning[p].get(second,()))
            unique_ranges[first+"|"+second]={
                "unique":{**{p:len(sets[p]) for p in PROJECTS},
                          "all":len(set().union(*sets.values()))},
                "returning":{**{p:len(returned[p]) for p in PROJECTS},
                             "all":len(set().union(*returned.values()))},
            }
    def daily_for(p):
        return {d:{"new":new_by_date[p][d],"conversions":daily_events[p][d]}
                for d in dates}
    report={
        "schema_version":1,
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "period":{"since":since.isoformat(),"until":until.isoformat()},
        "validated":True,
        "projects":list(PROJECTS),
        "daily":{p:daily_for(p) for p in PROJECTS},
        "range_unique":unique_ranges,
        "method":"Novos por data_cad original e primeiro empreendimento; conversões por referência/data e ID do empreendimento de conversão; retornos após o dia do cadastro; unicidade por ID deduplicada no runner privado.",
        "caveat":"Conversões múltiplas no dia do cadastro não contam como retornos; origens Meta não foram atribuídas a campanhas.",
    }
    os.makedirs("data",exist_ok=True)
    path="data/marketing-conversions.json"
    with open(path+".tmp","w",encoding="utf-8") as fh:
        json.dump(report,fh,ensure_ascii=False,separators=(",",":"))
    os.replace(path+".tmp",path)
    print("CONSOLIDADO DE CONVERSÕES VALIDADO PARA PUBLICAÇÃO")
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
