"""Geração de identificadores seguros (ASCII, sem espaços/acentos) a partir
de nomes livres -- exigido pelo campo ExternalImageId do Rekognition."""

import re
import unicodedata


def to_external_id(*partes: str) -> str:
    bruto = "_".join(p.strip() for p in partes if p)
    sem_acento = unicodedata.normalize("NFKD", bruto).encode("ascii", "ignore").decode()
    limpo = re.sub(r"[^a-zA-Z0-9._-]", "_", sem_acento)
    limpo = re.sub(r"_+", "_", limpo).strip("_")
    return limpo[:255]
