"""Regra de não-repetição: sugere a melhor foto ainda não usada de cada
pessoa para um evento, sem repetir ninguém na mesma leva. Não marca nada
como usado -- isso só acontece depois, via mark_used.py, quando o
conteúdo final já tiver sido produzido de verdade.

Uso:
    python -m src.select_for_content --evento "Nome do evento" --quantidade 5 \\
        --out data/selection_pending.csv
"""

import argparse
import csv

from . import config
from .drive_client import autenticar, sheets_service


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evento", required=True)
    parser.add_argument("--quantidade", type=int, default=5)
    parser.add_argument("--out", default="data/selection_pending.csv")
    args = parser.parse_args()

    creds = autenticar()
    sheets = sheets_service(creds)

    resposta = sheets.spreadsheets().values().get(
        spreadsheetId=config.TRACKING_SPREADSHEET_ID, range=f"{config.TRACKING_SHEET_NAME}!A2:H",
    ).execute()
    linhas = resposta.get("values", [])

    candidatas = []
    for linha in linhas:
        linha += [""] * (8 - len(linha))
        _, evento, nome_foto, link_foto, pessoa_id, confianca, usada, _ = linha
        if evento != args.evento or usada.strip().upper() == "TRUE":
            continue
        try:
            confianca_num = float(confianca)
        except ValueError:
            confianca_num = 0
        candidatas.append({"nome_foto": nome_foto, "link_foto": link_foto, "pessoa_id": pessoa_id, "confianca": confianca_num})

    melhor_por_pessoa = {}
    for c in candidatas:
        atual = melhor_por_pessoa.get(c["pessoa_id"])
        if not atual or c["confianca"] > atual["confianca"]:
            melhor_por_pessoa[c["pessoa_id"]] = c

    selecionadas = sorted(melhor_por_pessoa.values(), key=lambda c: c["confianca"], reverse=True)[: args.quantidade]

    if not selecionadas:
        print(f"Nenhuma foto disponível para '{args.evento}'.")
        return

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["nome_foto", "link_foto", "pessoa_id", "confianca"])
        writer.writeheader()
        writer.writerows(selecionadas)

    print(f"{len(selecionadas)} foto(s) sugerida(s):\n")
    for c in selecionadas:
        print(f"- {c['pessoa_id']} ({c['confianca']}%) — {c['link_foto']}")
    print(f"\nSalvo em {args.out}. Remova linhas que não forem usadas antes de rodar mark_used.py.")


if __name__ == "__main__":
    main()
