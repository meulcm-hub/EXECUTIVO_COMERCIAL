"""Apresentação de nomes na LCM; não é anonimização e não altera IDs."""
import re
import unicodedata

def display_name(value):
    if not isinstance(value,str):
        return "Não informado"
    clean=unicodedata.normalize("NFC",value)
    clean=re.sub(r"[\x00-\x1f\x7f]+"," ",clean)
    clean=re.sub(r"\s+"," ",clean).strip()
    if not clean:
        return "Não informado"
    parts=clean.split(" ")
    return " ".join(parts[:2])
