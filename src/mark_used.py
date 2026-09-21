"""Marca como usadas (na planilha de rastreamento) as fotos que constam num
arquivo de seleção -- rodar só depois que o conteúdo final já tiver sido
produzido de verdade. Linhas removidas do CSV antes de rodar não são
marcadas.

Uso:
    python -m src.mark_used data/selection_pending.csv
"""

import sys
import csv
from datetime import datetime

from . import config
from .drive_client import autenticar, sheets_service


def main():
    if len(sys.argv) < 2:
        print("Uso: python -m src.mark_used <selection.csv>")
        return

    with open(sys.argv[1], encoding="utf-8") as f:
        confirmadas = {(r["nome_foto"], r["pessoa_id"]) for r in csv.DictReader(f)}

    if not confirmadas:
        print("Nenhuma linha a marcar.")
        return

    creds = autenticar()
    sheets = sheets_service(creds)

    resposta = sheets.spreadsheets().values().get(
        spreadsheetId=config.TRACKING_SPREADSHEET_ID, range=f"{config.TRACKING_SHEET_NAME}!A2:H",
    ).execute()
    linhas = resposta.get("values", [])

    hoje = datetime.now().strftime("%Y-%m-%d")
    atualizacoes = []
    for i, linha in enumerate(linhas, start=2):
        linha += [""] * (8 - len(linha))
        if (linha[2], linha[4]) in confirmadas:
            atualizacoes.append({"range": f"{config.TRACKING_SHEET_NAME}!G{i}:H{i}", "values": [["TRUE", hoje]]})

    if not atualizacoes:
        print("Nenhuma correspondência encontrada.")
        return

    sheets.spreadsheets().values().batchUpdate(
        spreadsheetId=config.TRACKING_SPREADSHEET_ID,
        body={"valueInputOption": "RAW", "data": atualizacoes},
    ).execute()

    print(f"{len(atualizacoes)} linha(s) marcada(s) como usada(s) em {hoje}.")


if __name__ == "__main__":
    main()
