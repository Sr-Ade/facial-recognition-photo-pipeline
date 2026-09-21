"""Varre um CSV de reconhecimento e sinaliza rostos que bateram com 2+
identidades diferentes acima do limiar de confiança -- o padrão que indica
uma foto de referência ruim (indexando a pessoa errada). Ver estudo de
caso no README.

Não corrige nada -- apenas aponta os casos para revisão manual com
evaluate_reference_quality + reindex_athlete.

Uso:
    python -m src.detect_confusions data/recognition_result.csv
"""

import sys
import csv
from collections import defaultdict

from . import config


def main():
    if len(sys.argv) < 2:
        print("Uso: python -m src.detect_confusions <arquivo.csv>")
        return

    with open(sys.argv[1], encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    por_rosto = defaultdict(list)
    for row in linhas:
        if not row.get("pessoa_id") or not row.get("confianca"):
            continue
        try:
            confianca = float(row["confianca"])
        except ValueError:
            continue
        if confianca >= config.FACE_MATCH_THRESHOLD:
            por_rosto[(row["foto"], row["rosto_num"])].append((row["pessoa_id"], confianca, row.get("link_foto", "")))

    suspeitos = {k: v for k, v in por_rosto.items() if len(v) > 1}

    if not suspeitos:
        print("Nenhuma confusão detectada.")
        return

    print(f"{len(suspeitos)} rosto(s) suspeito(s) de confusão entre identidades:\n")
    for (foto, rosto_num), matches in suspeitos.items():
        print(f"Foto: {foto} (rosto {rosto_num})")
        for pessoa_id, confianca, link in matches:
            print(f"   - {pessoa_id}: {confianca}%")
        print(f"   {matches[0][2]}\n")

    print("Recomendado: revisar as referências dessas pessoas com evaluate_reference_quality.")


if __name__ == "__main__":
    main()
