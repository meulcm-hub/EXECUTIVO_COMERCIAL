#!/usr/bin/env python3
"""Anúncios, mídias e métricas diárias Meta para o painel público LCM.

Somente leitura. A publicação usa uma projeção explícita dos anúncios; nunca
salva o token, a resposta bruta, dados de leads ou parâmetros de autenticação.
"""
import datetime as dt
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

import meta_ads_collector as meta
from marketing_campaigns import FORM_ACTION, MESSAGE_ACTION, actions, number

HISTORY_START = dt.date(2026, 1, 1)
OUTPUT = Path("data/marketing-creatives.json")
PROJECTS = {
    "347253318197280": "residencial flores do cerrado jacaranda",
    "626593228944023": "residencial village lagoas",
    "332967835423799": "spe arraial costa verde club",
    "1183301460107081": "residencial jatoba",
}
CATALOG_STATUSES = ["ACTIVE", "PAUSED", "CAMPAIGN_PAUSED", "ADSET_PAUSED",
                    "ARCHIVED", "DELETED", "PENDING_REVIEW", "DISAPPROVED",
                    "PREAPPROVED", "PENDING_BILLING_INFO", "IN_PROCESS", "WITH_ISSUES"]
CREATIVE_FIELDS = ("id,name,title,body,image_url,thumbnail_url,video_id,"
                   "object_story_spec,asset_feed_spec,effective_object_story_id,object_story_id")
AD_FIELDS = ("id,name,campaign_id,effective_status,campaign{id,name,effective_status},"
             "creative{" + CREATIVE_FIELDS + "}")
NUMERIC_ID = re.compile(r"\d{5,30}\Z")


def identifier(value):
    value = str(value or "")
    if not NUMERIC_ID.fullmatch(value):
        raise RuntimeError("Identificador Meta inválido")
    return value


def clean_text(value, maximum=240):
    # Não transformar objetos em texto nem transportar valores secretos vindos
    # da API para um arquivo público, inclusive em nomes de anúncios.
    if not isinstance(value, (str, int)):
        return ""
    value = str(value)
    if meta.TOKEN and meta.TOKEN in value:
        return ""
    return "".join(c for c in value if c >= " " or c in "\n\t")[:maximum]


def safe_url(value):
    """Somente HTTPS Meta/CDN; rejeita credenciais e mantém assinatura CDN."""
    if not isinstance(value, str) or len(value) > 8192:
        return ""
    try:
        parsed = urllib.parse.urlsplit(value)
        host = (parsed.hostname or "").lower()
        allowed = any(host == name or host.endswith("." + name)
                      for name in ("facebook.com", "fbcdn.net", "fbsbx.com", "fb.watch"))
        if (parsed.scheme != "https" or not allowed or parsed.username or
                parsed.password or parsed.port not in (None, 443) or
                any(c.isspace() for c in value)):
            return ""
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if any(re.search(r"token|auth|secret|password", key, re.I) for key, _ in query):
            return ""
        if meta.TOKEN and meta.TOKEN in urllib.parse.unquote(value):
            return ""
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                                       parsed.query, ""))
    except (ValueError, TypeError):
        return ""


class NoGraphRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Redirecionamento de metadados recusado")


GRAPH_OPENER = urllib.request.build_opener(NoGraphRedirect())


def graph_object(node_id, fields):
    """Objetos de mídia individuais; a requisição compartilhada lê listas."""
    node_id = identifier(node_id)
    if not meta.TOKEN:
        raise RuntimeError("META_ACCESS_TOKEN ausente")
    if not re.fullmatch(r"v\d+\.\d+", meta.API_VERSION):
        raise RuntimeError("META_API_VERSION inválida")
    url = meta.BASE + "/" + node_id + "?" + urllib.parse.urlencode({"fields": fields})
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": "Bearer " + meta.TOKEN,
                "Accept": "application/json",
                "User-Agent": "LCM-Creatives-Collector/1.0",
            })
            with GRAPH_OPENER.open(req, timeout=40) as response:
                payload = json.load(response)
            if not isinstance(payload, dict) or "error" in payload:
                raise RuntimeError("Metadados de mídia indisponíveis")
            if str(payload.get("id", "")) != node_id:
                raise RuntimeError("Metadados de mídia sem identificador correspondente")
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError("Metadados de mídia indisponíveis") from None
        except (urllib.error.URLError, TimeoutError, http.client.IncompleteRead,
                ConnectionResetError, ValueError):
            if attempt == 2:
                raise RuntimeError("Metadados de mídia indisponíveis") from None
        time.sleep(2 ** attempt)
    raise RuntimeError("Metadados de mídia indisponíveis")


def month_ranges(first, last):
    current = first
    while current <= last:
        following = (current.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        end = min(last, following - dt.timedelta(days=1))
        yield current, end
        current = end + dt.timedelta(days=1)


def exact_integer(value):
    result = number(value)
    if result != int(result):
        raise RuntimeError("Quantidade Meta não integral")
    return int(result)


def metric_rows(rows, first, last):
    """Agrupa por anúncio/data sem somar linhas duplicadas ou alcance diário."""
    by_ad = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("Linha de métricas Meta inválida")
        aid = identifier(row.get("ad_id"))
        cid = identifier(row.get("campaign_id"))
        date = str(row.get("date_start") or "")
        try:
            parsed = dt.date.fromisoformat(date)
        except ValueError:
            raise RuntimeError("Data de anúncio inválida") from None
        if parsed.isoformat() != date or not first <= parsed <= last:
            raise RuntimeError("Data de anúncio fora do período")
        item = by_ad.setdefault(aid, {"campaign_id": cid,
                                    "campaign_name": clean_text(row.get("campaign_name"), 180),
                                    "name": clean_text(row.get("ad_name"), 180), "daily": {}})
        if item["campaign_id"] != cid:
            raise RuntimeError("Campanha de anúncio inconsistente")
        if date in item["daily"]:
            raise RuntimeError("Anúncio/data duplicado: publicação recusada")
        item["daily"][date] = {
            "date": date,
            "impressions": exact_integer(row.get("impressions")),
            "clicks": exact_integer(row.get("clicks")),
            "spend": str(number(row.get("spend"))),
            "form_leads": int(actions(row, FORM_ACTION)),
            "messages": int(actions(row, MESSAGE_ACTION)),
        }
        # Conversões são contagens, não valores monetários fracionários.
        if (actions(row, FORM_ACTION) != item["daily"][date]["form_leads"] or
                actions(row, MESSAGE_ACTION) != item["daily"][date]["messages"]):
            raise RuntimeError("Conversão de anúncio não integral")
    return by_ad


def story_url(creative):
    value = creative.get("effective_object_story_id") or creative.get("object_story_id")
    if isinstance(value, str) and re.fullmatch(r"\d+_\d+", value):
        page, post = value.split("_")
        return "https://www.facebook.com/" + page + "/posts/" + post
    return ""


def extract_media(creative, video_lookup):
    """Mídias regulares, carrosséis e variações dinâmicas em formato público."""
    if not isinstance(creative, dict):
        creative = {}
    spec = creative.get("object_story_spec") or {}
    spec = spec if isinstance(spec, dict) else {}
    feed = creative.get("asset_feed_spec") or {}
    feed = feed if isinstance(feed, dict) else {}
    fallback_image = safe_url(creative.get("image_url")) or safe_url(creative.get("thumbnail_url"))
    permalink = story_url(creative)
    found = []
    seen = set()

    def image(url):
        url = safe_url(url)
        if url and ("image", url) not in seen:
            seen.add(("image", url))
            found.append({"type": "image", "image_url": url, "video_url": "", "permalink_url": permalink})

    def video(value, poster=""):
        value = str(value or "")
        if not NUMERIC_ID.fullmatch(value) or ("video", value) in seen:
            return
        seen.add(("video", value))
        detail = video_lookup(value)
        thumbnail = (safe_url(poster) or safe_url(detail.get("picture")) or fallback_image)
        found.append({"type": "video", "image_url": thumbnail,
                      "video_url": safe_url(detail.get("source")),
                      "permalink_url": safe_url(detail.get("permalink_url")) or permalink or
                          "https://www.facebook.com/watch/?v=" + value})

    video_data = spec.get("video_data") or {}
    video_data = video_data if isinstance(video_data, dict) else {}
    video(creative.get("video_id") or video_data.get("video_id"), video_data.get("image_url", ""))
    link_data = spec.get("link_data") or {}
    link_data = link_data if isinstance(link_data, dict) else {}
    attachments = link_data.get("child_attachments") or []
    for child in attachments[:20] if isinstance(attachments, list) else []:
        if not isinstance(child, dict):
            continue
        if child.get("video_id"):
            video(child["video_id"], child.get("picture", ""))
        else:
            image(child.get("picture") or child.get("image_url"))
    feed_videos = feed.get("videos") or []
    for child in feed_videos[:20] if isinstance(feed_videos, list) else []:
        if isinstance(child, dict):
            video(child.get("video_id"), child.get("thumbnail_url", ""))
    feed_images = feed.get("images") or []
    for child in feed_images[:20] if isinstance(feed_images, list) else []:
        if isinstance(child, dict):
            image(child.get("url"))
    if not found:
        image(link_data.get("picture") or fallback_image)
    # image_hash sem URL exige outra permissão; manter a miniatura disponível.
    main = found[0] if found else {"type": "unknown", "image_url": fallback_image,
                                  "video_url": "", "permalink_url": permalink}
    return {"media_type": "carousel" if len(found) > 1 else main["type"],
            "image_url": main["image_url"], "video_url": main["video_url"],
            "permalink_url": main["permalink_url"],
            "body": clean_text(creative.get("body") or link_data.get("message") or video_data.get("message"), 1600),
            "media": found[:20]}


def primary_request(path, params, stage):
    try:
        return meta.request(path, params)
    except RuntimeError as error:
        # request() oferece somente códigos numéricos e categorias fixas.
        raise RuntimeError(stage + ": " + str(error)) from None


def collect_account(account, first, last, video_cache):
    full_id = str(account.get("id") or "")
    if not re.fullmatch(r"act_\d{5,30}", full_id):
        raise RuntimeError("Conta Meta inválida")
    if account.get("currency") != "BRL":
        raise RuntimeError("Conta de anúncio sem moeda BRL confirmada")
    account_id = full_id[4:]
    catalog = primary_request(full_id + "/ads", {
        "fields": AD_FIELDS, "effective_status": json.dumps(CATALOG_STATUSES), "limit": 100,
    }, "Catálogo de anúncios da conta " + account_id)
    metadata = {}
    for ad in catalog:
        if not isinstance(ad, dict):
            raise RuntimeError("Catálogo de anúncios inválido")
        aid = identifier(ad.get("id"))
        if aid in metadata:
            raise RuntimeError("Anúncio duplicado no catálogo")
        metadata[aid] = ad
    metrics = {}
    for since, until in month_ranges(first, last):
        rows = primary_request(full_id + "/insights", {
            "fields": "ad_id,ad_name,campaign_id,campaign_name,date_start,impressions,clicks,spend,actions",
            "level": "ad", "time_increment": 1,
            "action_report_time": "impression", "use_unified_attribution_setting": "true",
            "time_range": json.dumps({"since": since.isoformat(), "until": until.isoformat()}, separators=(",", ":")),
            "limit": 500,
        }, "Métricas da conta " + account_id + " em " + since.isoformat()[:7])
        for aid, item in metric_rows(rows, since, until).items():
            previous = metrics.setdefault(aid, {**item, "daily": {}})
            if previous["campaign_id"] != item["campaign_id"]:
                raise RuntimeError("Campanha de anúncio inconsistente")
            if previous["daily"].keys() & item["daily"].keys():
                raise RuntimeError("Data de anúncio duplicada entre períodos")
            previous["daily"].update(item["daily"])

    def video_lookup(vid):
        if vid not in video_cache:
            try:
                video_cache[vid] = graph_object(vid, "id,source,picture,permalink_url")
            except RuntimeError:
                video_cache[vid] = {}
        return video_cache[vid]

    published = []
    # Não baixar mídias de anúncios antigos pausados sem entrega no ano.
    # Anúncios atuais ativos entram mesmo sem entrega; históricos com insights
    # permanecem disponíveis independentemente do status e da mídia legível.
    eligible = set(metrics) | {aid for aid, ad in metadata.items()
                               if ad.get("effective_status") == "ACTIVE"}
    for aid in sorted(eligible):
        ad = metadata.get(aid, {})
        metric = metrics.get(aid, {})
        campaign = ad.get("campaign") or {}
        campaign = campaign if isinstance(campaign, dict) else {}
        cid = identifier(ad.get("campaign_id") or campaign.get("id") or metric.get("campaign_id"))
        status = clean_text(ad.get("effective_status") or "UNKNOWN", 40).upper()
        if status == "ACTIVE" and campaign.get("effective_status") not in (None, "ACTIVE"):
            status = "CAMPAIGN_PAUSED"
        published.append({
            "ad_id": aid, "name": clean_text(ad.get("name") or metric.get("name") or "Anúncio", 180),
            "account_id": account_id, "account_name": clean_text(account.get("name"), 100),
            "project": PROJECTS.get(account_id),
            "campaign_id": cid,
            "campaign_name": clean_text(campaign.get("name") or metric.get("campaign_name") or "Campanha", 180),
            "status": status, **extract_media(ad.get("creative"), video_lookup),
            "daily": [metric["daily"][date] for date in sorted(metric.get("daily", {}))],
        })
    print("Conta consultada: " + str(len(published)) + " anúncios; " +
          str(sum(len(x["daily"]) for x in published)) + " linhas diárias.", flush=True)
    return published


def collect(first=HISTORY_START, last=None):
    last = last or dt.date.today()
    if last < first:
        raise RuntimeError("Período de criativos inválido")
    catalog = meta.accounts()
    if len(catalog) != 8:
        raise RuntimeError("Esperadas exatamente oito contas de anúncios")
    ads, videos = [], {}
    for account in catalog:
        ads.extend(collect_account(account, first, last, videos))
    if len({ad["ad_id"] for ad in ads}) != len(ads):
        raise RuntimeError("Anúncio repetido entre contas")
    return {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "period": {"since": first.isoformat(), "until": last.isoformat()},
        "currency": "BRL", "ads": ads,
        "action_type": FORM_ACTION,
        "action_report_time": "impression", "attribution": "use_unified_attribution_setting=true",
        "warning": "Status atual do anúncio. Métricas somáveis por dia; CPC = investimento / cliques. Alcance não é somado por dia nem por anúncio. Mídias indisponíveis mantêm miniatura ou link da publicação quando possível; URLs Meta podem expirar e são renovadas a cada coleta.",
    }


def publish(payload, output=OUTPUT):
    # Nada é escrito até todas as contas e métricas terminarem com sucesso.
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    os.replace(temporary, output)


def main():
    payload = collect()
    publish(payload)
    print("Criativos e indicadores diários preparados para publicação automática; sem credenciais.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        print("Coleta de criativos não concluída: " + str(error) + ". Dados anteriores preservados.", file=sys.stderr)
        sys.exit(1)
    except (InvalidOperation, ValueError, OSError):
        # Nenhum traceback/URL/corpo bruto: credenciais ficam no secret do Actions.
        print("Coleta de criativos não concluída. Dados anteriores preservados; consulte acesso Meta e contas vinculadas.", file=sys.stderr)
        sys.exit(1)
