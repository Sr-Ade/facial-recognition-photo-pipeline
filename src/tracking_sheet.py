"""Cria a planilha de rastreamento (uma vez) e registra novos resultados de
reconhecimento nela (a cada rodada), sem duplicar entradas já existentes.

Uso (criar a planilha, uma vez):
    python -m src.tracking_sheet create

Uso (registrar um resultado de reconhecimento):
    python -m src.tracking_sheet log data/recognition_result.csv --evento "Nome do evento"
"""

import argparse
import csv
from datetime import datetime

from . import config
from .drive_client import autenticar, sheets_service

COLUNAS = ["data_processamento", "evento", "nome_foto", "link_foto", "pessoa_id", "confianca", "usada", "data_uso"]


def criar_planilha(args):
    creds = autenticar()
    sheets = sheets_service(creds)

    corpo = {
        "properties": {"title": args.titulo},
        "sheets": [{"properties": {"title": config.TRACKING_SHEET_NAME}}],
    }
    resultado = sheets.spreadsheets().create(body=corpo, fields="spreadsheetId").execute()
    spreadsheet_id = resultado["spreadsheetId"]

    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{config.TRACKING_SHEET_NAME}!A1",
        valueInputOption="RAW",
        body={"values": [COLUNAS]},
    ).execute()

    print("Planilha criada.")
    print(f"ID: {spreadsheet_id}")
    print(f"Link: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit")
    print("\nSalve esse ID em TRACKING_SPREADSHEET_ID no seu .env.")


def registrar(args):
    creds = autenticar()
    sheets = sheets_service(creds)

    with open(args.csv, encoding="utf-8") as f:
        linhas = [r for r in csv.DictReader(f) if r.get("pessoa_id")]

    resposta = sheets.spreadsheets().values().get(
        spreadsheetId=config.TRACKING_SPREADSHEET_ID, range=f"{config.TRACKING_SHEET_NAME}!A2:H",
    ).execute()
    ja_registrado = {(r[2], r[4]) for r in resposta.get("values", []) if len(r) >= 5}

    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    novas = []
    for row in linhas:
        chave = (row["foto"], row["pessoa_id"])
        if chave in ja_registrado:
            continue
        novas.append([agora, args.evento, row["foto"], row.get("link_foto", ""), row["pessoa_id"], row.get("confianca", ""), "FALSE", ""])
        ja_registrado.add(chave)

    if not novas:
        print("Nenhuma linha nova.")
        return

    sheets.spreadsheets().values().append(
        spreadsheetId=config.TRACKING_SPREADSHEET_ID,
        range=f"{config.TRACKING_SHEET_NAME}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": novas},
    ).execute()

    print(f"{len(novas)} linha(s) adicionada(s).")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="comando", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--titulo", default="Photo Tracking")

    p_log = sub.add_parser("log")
    p_log.add_argument("csv")
    p_log.add_argument("--evento", required=True)

    args = parser.parse_args()
    if args.comando == "create":
        criar_planilha(args)
    else:
        registrar(args)


if __name__ == "__main__":
    main()
