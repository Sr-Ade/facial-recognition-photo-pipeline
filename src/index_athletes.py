"""Indexa a foto de referência de cada pessoa (a partir de pastas
organizadas por categoria/subpasta/pessoa) na coleção do Rekognition.

Tenta a primeira foto de cada pasta; se falhar (tamanho ou nenhum rosto
detectado), tenta as demais fotos da mesma pasta em ordem, aplicando
redimensionamento quando necessário.

Uso:
    python -m src.index_athletes --out data/index_result.csv
"""

import argparse
import csv

import boto3

from . import config
from .drive_client import autenticar, drive_service, listar_filhos, listar_fotos, baixar_arquivo, redimensionar_se_precisar
from .naming import to_external_id


def indexar_pessoa(rekognition, drive, categoria, subpasta, pasta_pessoa):
    fotos = listar_fotos(drive, pasta_pessoa["id"])
    if not fotos:
        return "sem_foto", None

    external_id = to_external_id(subpasta, pasta_pessoa["name"])

    for foto in fotos:
        try:
            imagem = redimensionar_se_precisar(baixar_arquivo(drive, foto["id"]))
            resp = rekognition.index_faces(
                CollectionId=config.REKOGNITION_COLLECTION_ID,
                ExternalImageId=external_id,
                Image={"Bytes": imagem},
                MaxFaces=1,
                QualityFilter="AUTO",
            )
            if resp["FaceRecords"]:
                return "indexado", resp["FaceRecords"][0]["Face"]["FaceId"]
        except Exception:
            continue

    return "sem_rosto_detectado", None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/index_result.csv")
    args = parser.parse_args()

    creds = autenticar()
    drive = drive_service(creds)
    rekognition = boto3.client("rekognition", region_name=config.AWS_REGION)

    linhas = [["categoria", "subpasta", "nome_pasta", "external_id", "status", "face_id"]]

    for categoria, raiz_id in config.DRIVE_ROOT_FOLDERS.items():
        subpastas = [p for p in listar_filhos(drive, raiz_id) if p["mimeType"] == "application/vnd.google-apps.folder"]

        for subpasta in sorted(subpastas, key=lambda p: p["name"]):
            pessoas = [p for p in listar_filhos(drive, subpasta["id"]) if p["mimeType"] == "application/vnd.google-apps.folder"]

            for pessoa in pessoas:
                status, face_id = indexar_pessoa(rekognition, drive, categoria, subpasta["name"], pessoa)
                external_id = to_external_id(subpasta["name"], pessoa["name"])
                print(f"[{status}] {categoria}/{subpasta['name']}/{pessoa['name']}")
                linhas.append([categoria, subpasta["name"], pessoa["name"], external_id, status, face_id or ""])

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(linhas)

    print(f"\nConcluído. Resultado em {args.out}")


if __name__ == "__main__":
    main()
