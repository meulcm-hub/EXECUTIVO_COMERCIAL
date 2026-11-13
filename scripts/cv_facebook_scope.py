"""Regra de escopo comercial LCM para o funil Meta/Facebook.

Entram:
- origem de cadastro Facebook/FB (declarada no CV);
- origem Painel Gestor/GE COM mídia WhatsApp Facebook, em conjunto;
- conversão com origem/mídia Facebook explicitamente atribuída no próprio evento.
Não entram Busca Compartilhada (BC), Google, Social genérico, ou Painel Gestor
sem WhatsApp Facebook. Facebook declarado não prova anúncio pago.
"""
import re
import unicodedata

def normalize(value):
    s=unicodedata.normalize("NFKD",str(value or "")).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+"," ","".join(c for c in s if not unicodedata.combining(c))).split())

def origin(row):
    for key in ("origem_original","origem","origem_nome","origem_cadastro"):
        value=row.get(key)
        if value is not None and str(value).strip():return normalize(value)
    return ""

def media(row):
    for key in ("midia_original","midia","midia_nome","midia_ultimo"):
        value=row.get(key)
        if value is not None and str(value).strip():return normalize(value)
    return ""

def facebook_media(value):
    return value in {"whatsapp facebook","facebook whatsapp","wpp facebook","facebook wpp"}

def facebook_origin(value):
    return value in {"fb","facebook","facebook ads","anuncio facebook","anuncios facebook","meta facebook"}

def manager_origin(value):
    return value in {"ge","painel gestor","gestor","painel do gestor"}

def classify(row):
    o,m=origin(row),media(row)
    if facebook_origin(o):return "facebook_origin_cv"
    if manager_origin(o) and facebook_media(m):return "manager_whatsapp_facebook_cv"
    return None

def conversion_classify(row):
    """Somente os atributos da conversão, nunca herdar origem do cadastro."""
    event={"origem":row.get("origem_conversao") or row.get("origem"),
           "midia":row.get("midia_conversao") or row.get("midia")}
    return classify(event)

def attributed_campaign(row):
    """Indicador de ligação confirmada: IDs de anúncio/campanha associados.
    Não converte 'FB' ou mídia em prova de campanha.
    """
    return bool(str(row.get("idcampanha") or row.get("campaign_id") or "").strip()
                and str(row.get("idad") or row.get("ad_id") or "").strip())
