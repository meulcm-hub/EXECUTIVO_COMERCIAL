#!/usr/bin/env python3
"""Funil CV CRM por safra. IDs permanecem apenas na memória do runner privado."""
import collections
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from cv_join_original_conversions import read_complete, get_lead_page, read_conversion_page
from marketing_consolidate import norm, to_date, classify_channel
from cv_conversion_audit import source as conversion_source

PROJECTS = ("residencial flores do cerrado jacaranda", "residencial village lagoas",
            "spe arraial costa verde club", "residencial jatoba")
DAYS = 90
PAGE_SIZE = 500
MAX_PAGES = 200
SOLD = ("VENDID", "CONTRATO ASSINADO", "ASSINADO POR CLIENTES E ASSOCIADOS",
        "CONTRATO ASSINADO CLIENTE", "ENVIADO PARA UAU", "BOLETO/PIX",
        "BOLETO PIX", "AGUARDANDO ASSINATURA INTERNA", "FATURAD", "PODE FATURAR")

def credentials():
    base = os.getenv("CVCRM_DOMINIO", "").strip().rstrip("/")
    u = urllib.parse.urlsplit(base)
    email = os.getenv("CVCRM_EMAIL", "").strip()
    token = os.getenv("CVCRM_TOKEN", "").strip()
    if (u.scheme != "https" or u.hostname != "lcm.cvcrm.com.br" or u.path not in ("", "/")
            or u.username or u.password or u.query or u.fragment or not email or not token):
        raise RuntimeError("Credenciais CV indisponíveis ou domínio inesperado")
    return base, email, token

def get(base, email, token, path, params):
    url = base + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"email": email, "token": token,
                                               "Accept": "application/json"})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(5):
        try:
            with opener.open(req, timeout=60) as response:
                if response.status == 204:
                    return None
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 204:
                return None
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise RuntimeError("CV CRM " + path + ": HTTP " + str(exc.code)) from None
            time.sleep(min(90, 5 * (2 ** attempt)))
        except (TimeoutError, urllib.error.URLError, ValueError) as exc:
            if attempt == 4:
                raise RuntimeError("CV CRM " + path + ": falha de consulta") from exc
            time.sleep(min(90, 5 * (2 ** attempt)))
    raise RuntimeError("Consulta não concluída")

def rows(payload, keys):
    if payload is None:
        return []
    if not isinstance(payload, dict):
        raise RuntimeError("Estrutura de resposta inesperada")
    for key in keys:
        data = payload.get(key)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.values())
    # Reservas comerciais são indexadas pelo ID numérico da reserva.
    # Alguns retornos também incluem metadados da paginação.
    indexed = [v for k, v in payload.items() if str(k).isdigit() and isinstance(v, dict)]
    if indexed or payload == {}:
        return indexed
    raise RuntimeError("Chaves de resposta não reconhecidas")

def paged(base, email, token, path, start, end, *, collection, commercial=False, precadastro=False):
    seen = set()
    all_rows = []
    for page in range(1, MAX_PAGES + 1):
        params = {"pagina": page, "limite" if precadastro else "registros_por_pagina": PAGE_SIZE}
        if precadastro:
            pass  # Pré-cadastro v1 não documenta filtros por data; consultar tudo.
        elif path == "/api/v1/cvdw/reservas":
            pass  # Snapshot CVDW: consultar histórico completo, filtrar safra após obter IDs.
        elif commercial:
            # CV CRM: 'situacao' e 'faturar' são filtros mutuamente exclusivos.
            # 'faturar=false' abrange diferentes situações; incluir integradas.
            params.update({"faturar": "false", "retornar_integradas": "true"})
        else:
            params.update({"a_partir_data_referencia": start.isoformat() + " 00:00:00",
                           "ate_data_referencia": end.isoformat() + " 23:59:59"})
        payload = get(base, email, token, path, params)
        batch = rows(payload, collection)
        if not batch:
            return all_rows
        # Page content must change: repeated pages must not be accepted as complete.
        signature = json.dumps(batch[:2], sort_keys=True, ensure_ascii=False)
        if signature in seen:
            raise RuntimeError("Paginação repetida em " + path)
        seen.add(signature)
        if not all(isinstance(r, dict) for r in batch):
            raise RuntimeError("Registro não estruturado em " + path)
        all_rows.extend(batch)
        pages = payload.get("total_de_paginas") or payload.get("totalPaginas")
        if isinstance(payload.get("pagination"), dict):
            pages = pages or payload["pagination"].get("totalPaginas")
        if precadastro and "total" in payload:
            total = int(payload["total"])
            if total < 0:
                raise RuntimeError("Total inválido em pré-cadastros")
            if len(all_rows) >= total:
                return all_rows
        elif pages is not None:
            if page >= int(pages):
                return all_rows
        elif len(batch) < PAGE_SIZE:
            return all_rows
        time.sleep(0.5)
    raise RuntimeError("Cobertura de páginas excedida em " + path)

def channel(row):
    kind = classify_channel(row)
    return kind.startswith("meta_") or kind == "google_declarada"

def conversion_channel(row):
    kind = conversion_source(row)
    return kind.startswith("meta_") or kind == "google_declarada"

def sold(row):
    # O CV também expõe a flag de venda efetivada, além da situação comercial.
    if norm(row.get("venda") or row.get("vendida")) in ("s", "sim", "true", "1"):
        return True
    value = row.get("situacao") or row.get("status_reserva") or row.get("situacao_reserva")
    if isinstance(value, dict):
        value = value.get("situacao") or value.get("status") or value.get("nome") or ""
    state = norm(value).upper()
    terms = tuple(norm(s).upper() for s in SOLD)
    return any(term in state for term in terms)

def event_day(row):
    for key in ("data", "data_visita", "dataVisita", "data_cad", "dataCad",
                "referencia_data", "data_conclusao", "dataConclusao"):
        d = to_date(row.get(key))
        if d:
            return d
    return None

def lead_ids(row):
    associated = row.get("leads_associados") or row.get("leadsAssociados")
    if isinstance(associated, dict):
        associated = list(associated.values())
    ids = set()
    if isinstance(associated, list):
        for element in associated:
            if isinstance(element, dict) and element.get("idlead") is not None:
                ids.add(str(element["idlead"]))
    if row.get("idlead") is not None:
        value = row["idlead"]
        # CVDW reservas: idlead pode conter "168523,4322", não apenas ID único.
        if isinstance(value, (str, int)):
            ids.update(re.findall(r"\d+", str(value)))
        elif isinstance(value, list):
            ids.update(str(v) for v in value if isinstance(v, int) and v>0)
    return ids

def main():
    base, email, token = credentials()
    today = dt.date.today()
    begin = today - dt.timedelta(days=DAYS - 1)
    historical = dt.date(2022, 1, 1)
    # Validar o endpoint de reservas primeiro: evita percorrer anos de leads
    # antes de descobrir erros de parâmetros/autorização comercial.
    reservation_preflight = get(base, email, token, "/api/v1/cvdw/reservas",
                                {"pagina": 1, "registros_por_pagina": 1})
    if reservation_preflight is not None:
        rows(reservation_preflight, ("dados",))
    print("Pré-validação de reservas concluída.", flush=True)
    original = {}
    original_details = {}
    entry_origins = {}
    conflicts = set()
    aliases = collections.defaultdict(set)
    for row in read_complete(base, email, token, historical, today,
                             get_lead_page, "prospects-funil"):
        if not isinstance(row, dict) or row.get("idlead") is None:
            continue
        lead = str(row["idlead"])
        day = to_date(row.get("data_cad"))
        project = norm(row.get("empreendimento_primeiro") or row.get("empreendimento"))
        if not day:
            continue
        current = (day, project, channel(row))
        if lead in original and original[lead] != current:
            conflicts.add(lead)
        else:
            original[lead] = current
            original_details[lead] = {
                "cliente": str(row.get("nome") or row.get("nome_lead") or row.get("cliente") or "Não informado"),
                "situacao_lead": str(row.get("situacao") or row.get("status") or row.get("situacao_lead") or "Não informado"),
                "origem": str(row.get("origem") or row.get("midia") or row.get("origem_cadastro") or "Não informado")
            }
        for idkey, projectkey in (
            ("idempreendimento_primeiro", "empreendimento_primeiro"),
            ("idempreendimento_ultimo", "empreendimento_ultimo")):
            if row.get(idkey) is not None and row.get(projectkey):
                aliases[str(row[idkey])].add(norm(row[projectkey]))
    if not original:
        raise RuntimeError("Nenhum prospect original recebido")
    # Período de entrada: novo cadastro original OU retorno em conversão identificada.
    entry = collections.defaultdict(dict)  # (project, lead) -> earliest day in window
    for lead, (day, project, accepted) in original.items():
        if lead not in conflicts and accepted and project in PROJECTS and begin <= day <= today:
            entry[(project, lead)] = day
            entry_origins[(project, lead)] = "Novo cadastro"
    possible = {k: next(iter(v)) for k, v in aliases.items() if len(v) == 1}
    seen_events = set()
    for row in read_complete(base, email, token, begin, today,
                             read_conversion_page, "retornos-funil"):
        if not isinstance(row, dict) or row.get("idlead") is None or row.get("idlead_conversao") is None:
            raise RuntimeError("Conversão sem vínculo completo")
        event_id = str(row["idlead_conversao"])
        if event_id in seen_events:
            continue
        seen_events.add(event_id)
        lead = str(row["idlead"])
        day = to_date(row.get("referencia_data"))
        associates = row.get("empreendimentos_conversao")
        if (not day or not begin <= day <= today or not isinstance(associates, list)
                or len(associates) != 1 or not conversion_channel(row)):
            continue
        project = possible.get(str(associates[0]))
        first = original.get(lead)
        if (project not in PROJECTS or not first or lead in conflicts or first[0] >= day):
            continue
        key = (project, lead)
        entry[key] = min(day, entry.get(key, day))
        if entry[key] == day:
            entry_origins[key] = "Retorno"
    # IDs de fontes comerciais nunca vão para o arquivo de saída.
    visits = paged(base, email, token, "/api/v1/cvdw/leads/visitas",
                   begin, today, collection=("dados", "data", "visitas"))
    tasks = paged(base, email, token, "/api/v1/cvdw/leads/tarefas",
                  begin, today, collection=("dados", "data", "tarefas"))
    precad = paged(base, email, token, "/api/v1/comercial/precadastro",
                   begin, today, collection=("precadastros",), precadastro=True)
    # O endpoint de pré-cadastro usa pagina/limite e campo total.
    reservations = paged(base, email, token, "/api/v1/cvdw/reservas",
                         begin, today, collection=("dados",))
    # Nunca interpretar alteração inesperada no esquema como zero conversões.
    for label, records in (("visitas", visits), ("tarefas", tasks)):
        if records and not any(r.get("idlead") is not None for r in records):
            raise RuntimeError("API de " + label + " não retornou ID Lead")
    if precad and not any(lead_ids(r) for r in precad):
        raise RuntimeError("Pré-cadastros sem vínculos de leads reconhecíveis")
    if reservations and not any("situacao" in r for r in reservations):
        raise RuntimeError("Reservas sem situação reconhecível")
    stage_by_lead = collections.defaultdict(list)
    for row in visits:
        lead = row.get("idlead")
        day = event_day(row)
        if lead is None or day is None:
            continue
        state = norm(row.get("situacao") or "").upper()
        if state in ("C", "CONCLUIDA", "CONCLUIDO", "REALIZADA", "REALIZADO"):
            level = 2  # visita concluída
        elif state in ("CA", "CANCELADA", "CANCELADO"):
            continue
        else:
            level = 1  # visita agendada
        stage_by_lead[str(lead)].append((day, level))
    # Tarefas só contam como agendamento se explicitamente classificadas como tal.
    for row in tasks:
        lead = row.get("idlead")
        day = event_day(row)
        title = norm(" ".join(str(row.get(k) or "") for k in
                              ("descricao", "nome", "tipo", "tipo_tarefa")))
        state = norm(row.get("situacao") or "").upper()
        if lead is not None and day and "agend" in title and state not in ("CA", "CANCELADA"):
            stage_by_lead[str(lead)].append((day, 1))
    precad_by_lead = {}
    for row in precad:
        day = event_day(row)
        # data_cad is the creation of the pre-registration (not the original lead).
        if day is None:
            raise RuntimeError("Pré-cadastro sem data")
        for lead in lead_ids(row):
            stage_by_lead[lead].append((day, 3))
            current = precad_by_lead.get(lead)
            if current is None or day >= current[0]:
                precad_by_lead[lead] = (day, row)
    sale_by_lead = {}
    reservation_by_lead = {}
    sales_audit = collections.Counter()
    # O vínculo é puramente por ID. Filtros comerciais e datas são verificados
    # somente depois de confirmar que a reserva encontrou um lead do funil.
    prospective_ids = {lead for _, lead in entry}
    original_ids = set(original)
    # CVDW pode devolver múltiplas referências da mesma reserva.
    # Considerar a versão mais recente de cada idreserva, sem somar snapshots.
    latest_reservations={}
    for row in reservations:
        rid=row.get("idreserva")
        if rid is None:
            continue
        key=str(rid)
        reference=str(row.get("referencia_data") or "")
        if key not in latest_reservations or reference>str(latest_reservations[key].get("referencia_data") or ""):
            latest_reservations[key]=row
    sales_audit["snapshots_consultados"]=len(reservations)
    for row in latest_reservations.values():
        sales_audit["reservas_consultadas"] += 1
        ids = lead_ids(row)
        for lead in ids:
            current = reservation_by_lead.get(lead)
            reference = str(row.get("referencia_data") or "")
            if current is None or reference >= current[0]:
                reservation_by_lead[lead] = (reference, row)
        linked_original = ids & original_ids
        linked_cohort = ids & prospective_ids
        if not ids:
            sales_audit["reservas_sem_idlead"] += 1
        if linked_original:
            sales_audit["reservas_com_lead_identificado"] += 1
        if linked_cohort:
            sales_audit["reservas_com_prospect_na_safra"] += 1
        elif linked_original:
            sales_audit["reservas_lead_fora_da_safra"] += 1
        elif ids:
            sales_audit["reservas_id_nao_encontrado"] += 1
        # Não bloquear o vínculo de IDs por data, cancelamento ou status.
        if norm(row.get("ativo")) == "n":
            sales_audit["reservas_inativas"] += 1
            continue
        if row.get("data_cancelamento") or row.get("data_distrato"):
            sales_audit["reservas_canceladas"] += 1
            continue
        if not sold(row):
            continue
        sales_audit["reservas_classificadas_venda"] += 1
        if not ids:
            sales_audit["vendas_sem_idlead"] += 1
            continue
        sales_audit["vendas_com_idlead"] += 1
        day = to_date(row.get("data_venda") or row.get("data_contrato") or row.get("data"))
        if day is None:
            sales_audit["vendas_sem_data"] += 1
            continue
        if linked_cohort:
            sales_audit["vendas_com_prospect_na_safra"] += 1
        else:
            sales_audit["vendas_sem_prospect_na_safra"] += 1
        for lead in ids:
            stage_by_lead[lead].append((day, 4))
            current = sale_by_lead.get(lead)
            if current is None or day >= current[0]:
                sale_by_lead[lead] = (day, row)
    sale_ids = {lead for lead, events in stage_by_lead.items()
                if any(level == 4 for _, level in events)}
    matched_sales = sum(1 for (project, lead), first in entry.items()
                        if any(day >= first and level == 4
                               for day, level in stage_by_lead.get(lead, ())))
    sales_audit["prospects_com_venda_validada"] = matched_sales
    print("Auditoria vendas CV (somente contagens): " +
          json.dumps(dict(sales_audit), sort_keys=True), flush=True)
    # Um mesmo cliente pode entrar por cadastro novo e depois retornar:
    # usar a primeira entrada elegível por empreendimento; não somar eventos.
    dates = [begin + dt.timedelta(days=i) for i in range(DAYS)]
    cohorts = []
    for project in PROJECTS:
        per_day = collections.defaultdict(list)
        for (p, lead), first in entry.items():
            if p != project:
                continue
            # Só eventos após entrada do prospect podem fazê-lo avançar.
            level = max((stage for day, stage in stage_by_lead.get(lead, ())
                         if day >= first), default=0)
            per_day[first].append(level)
        for i, first in enumerate(dates):
            levels = []
            for last in dates[i:]:
                levels.extend(per_day[last])
                counts = {key: sum(level >= n for level in levels)
                          for n, key in enumerate((
                              "prospect", "agendamento", "visita",
                              "analise_credito", "venda_realizada"))}
                cohorts.append({"project": project, "since": first.isoformat(),
                                "until": last.isoformat(), "as_of": today.isoformat(),
                                "validated": True, "counts": counts})
    if not cohorts:
        raise RuntimeError("Coortes não produzidas")
    # Sem vínculo confiável de vendas, não publicar um zero como resultado definitivo.
    sales_link_validated = bool(sales_audit["reservas_classificadas_venda"]
                                and sales_audit["vendas_com_idlead"]
                                and matched_sales)
    if not sales_link_validated:
        print("ATENÇÃO: venda da safra não confirmada; indicador de vendas permanece em auditoria.", flush=True)
    report = {"schema_version": 1, "validated": True,
              "sales_link_validated": sales_link_validated,
              "cohort_mode": "prospect_date", "as_of": today.isoformat(),
              "period": {"since": begin.isoformat(), "until": today.isoformat()},
              "cohorts": cohorts,
              # Somente totais não identificáveis. Nunca publicar idlead,
              # cliente, telefone, e-mail, CPF ou linhas individuais.
              "reservation_link_audit": {
                  key: int(sales_audit[key])
                  for key in (
                      "snapshots_consultados", "reservas_consultadas",
                      "reservas_sem_idlead", "reservas_com_lead_identificado",
                      "reservas_com_prospect_na_safra",
                      "reservas_lead_fora_da_safra",
                      "reservas_id_nao_encontrado",
                      "reservas_inativas", "reservas_canceladas",
                      "reservas_classificadas_venda",
                      "vendas_sem_idlead", "vendas_com_idlead",
                      "vendas_sem_data", "vendas_sem_prospect_na_safra",
                      "vendas_com_prospect_na_safra",
                      "prospects_com_venda_validada"
                  )
              },
              "method": "IDs de prospects por empreendimento e período de entrada. Etapa máxima alcançada após a entrada, contabilizada cumulativamente nas anteriores.",
              "source": "CV CRM v1; contagens agregadas sem IDs ou PII"}
    # Arquivo individual LOCAL: jamais comitar em data/ ou publicar no Pages.
    # É possível importá-lo no dashboard diretamente do computador autorizado.
    project_titles = {
        "residencial flores do cerrado jacaranda": "Jacarandá",
        "residencial village lagoas": "Village Lagoas",
        "spe arraial costa verde club": "Arraial Costa Verde",
        "residencial jatoba": "Jatobá"
    }
    def situation(value):
        if isinstance(value, dict):
            return str(value.get("situacao") or value.get("nome") or value.get("status") or "Não informado")
        return str(value) if value is not None and str(value).strip() else "Não informado"

    detail_rows = []
    for (project, lead), first in sorted(entry.items(), key=lambda kv: (kv[0][0], kv[1], kv[0][1])):
        detail = original_details.get(lead, {})
        precad_record = precad_by_lead.get(lead)
        sale_record = sale_by_lead.get(lead)
        precad_value = precad_record[1] if precad_record else {}
        reservation_record = reservation_by_lead.get(lead)
        reservation_value = reservation_record[1] if reservation_record else {}
        # Situação Reserva reflete a última referência da reserva encontrada por ID,
        # mesmo que não tenha sido classificada como venda.
        reservation_status = situation(reservation_value.get("situacao") or reservation_value.get("status_reserva"))
        detail_rows.append({
            "idlead": lead,
            "cliente": detail.get("cliente", "Não informado"),
            "empreendimento": project_titles.get(project, project),
            "project": project,
            "origem": detail.get("origem", "Não informado"),
            "tipo_entrada": entry_origins.get((project, lead), "Novo cadastro"),
            "data_entrada": first.isoformat(),
            "data_venda": sale_record[0].isoformat() if sale_record and sale_record[0] >= first else "",
            "situacao_lead": situation(detail.get("situacao_lead")),
            "situacao_precadastro": situation(precad_value.get("situacao") or precad_value.get("status")),
            "situacao_reserva": reservation_status
        })
    audit_path = os.getenv("CV_AUDIT_PRIVATE_PATH", "").strip()
    if audit_path:
        directory = os.path.dirname(os.path.abspath(audit_path))
        os.makedirs(directory, exist_ok=True)
        with open(audit_path, "w", encoding="utf-8") as private_file:
            json.dump({
                "schema_version": 1, "source": "CV CRM - dados individuais privados",
                "period": {"since": begin.isoformat(), "until": today.isoformat()},
                "rows": detail_rows
            }, private_file, ensure_ascii=False)
        print("Auditoria individual privada gerada: " + str(len(detail_rows)) +
              " linhas; caminho definido por CV_AUDIT_PRIVATE_PATH.", flush=True)
    else:
        print("Auditoria individual preparada em memória; exportação privada desabilitada.", flush=True)
    target = "data/cv-funnel.json"
    os.makedirs("data", exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, separators=(",", ":"))
    print("Funil agregado validado: " + str(len(cohorts)) + " recortes publicados; nenhum ID exportado.")

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
        print("Funil CV não publicado: " + str(exc), file=sys.stderr)
        sys.exit(1)
