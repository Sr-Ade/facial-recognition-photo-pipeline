"""Substitui a foto de referência de uma pessoa (ou de um lote) na coleção
do Rekognition: remove o vetor de rosto antigo e indexa de novo com uma
foto melhor.

IMPORTANTE: isso NUNCA apaga nada no Google Drive (acesso é somente
leitura). O que é removido é apenas um registro interno de comparação
facial na coleção da AWS -- a foto original permanece intacta.

Uso (uma pessoa):
    python -m src.reindex_athlete --categoria "Category A" --subpasta "2007" \\
        --pessoa "Nome Sobrenome" --arquivo "foto_boa.jpg"

Uso (lote, a partir da saída do evaluate_reference_quality --batch):
    python -m src.reindex_athlete --batch data/reference_priority.csv \\
        --incluir trocar
"""

import argparse
import csv

import boto3

from . import config
from .drive_client import autenticar, drive_service, listar_fotos, baixar_arquivo, redimensionar_se_precisar, encontrar_pasta_por_caminho
from .naming import to_external_id


def apagar_rosto_antigo(rekognition, external_id: str) -> int:
    """Remove o(s) vetor(es) de rosto associado(s) a um external_id na
    coleção da AWS. Não afeta nenhum arquivo no Google Drive."""
    face_ids, token = [], None
    while True:
        kwargs = {"CollectionId": config.REKOGNITION_COLLECTION_ID, "MaxResults": 4096}
        if token:
            kwargs["NextToken"] = token
        resp = rekognition.list_faces(**kwargs)
        face_ids += [f["FaceId"] for f in resp.get("Faces", []) if f["ExternalImageId"] == external_id]
        token = resp.get("NextToken")
        if not token:
            break

    if face_ids:
        rekognition.delete_faces(CollectionId=config.REKOGNITION_COLLECTION_ID, FaceIds=face_ids)
    return len(face_ids)


def reindexar(rekognition, drive, categoria, subpasta, nome_pasta, nome_arquivo, cache):
    external_id = to_external_id(subpasta, nome_pasta)
    pasta = encontrar_pasta_por_caminho(drive, categoria, subpasta, nome_pasta, cache)
    if not pasta:
        return "erro_pasta_nao_encontrada"

    foto = next((f for f in listar_fotos(drive, pasta["id"]) if f["name"] == nome_arquivo), None)
    if not foto:
        return "erro_arquivo_nao_encontrado"

    apagar_rosto_antigo(rekognition, external_id)
    imagem = redimensionar_se_precisar(baixar_arquivo(drive, foto["id"]))

    resp = rekognition.index_faces(
        CollectionId=config.REKOGNITION_COLLECTION_ID,
        ExternalImageId=external_id,
        Image={"Bytes": imagem},
        MaxFaces=1,
        QualityFilter="AUTO",
    )
    return "reindexado" if resp["FaceRecords"] else "erro_sem_rosto_na_foto_nova"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--categoria")
    parser.add_argument("--subpasta")
    parser.add_argument("--pessoa")
    parser.add_argument("--arquivo")
    parser.add_argument("--batch", help="CSV do evaluate_reference_quality --batch")
    parser.add_argument("--incluir", default="trocar", help="valor de 'recomendacao' a processar no modo lote")
    parser.add_argument("--out", default="data/reindex_log.csv")
    args = parser.parse_args()

    creds = autenticar()
    drive = drive_service(creds)
    rekognition = boto3.client("rekognition", region_name=config.AWS_REGION)
    cache = {}

    if args.batch:
        with open(args.batch, encoding="utf-8") as f:
            linhas = [r for r in csv.DictReader(f) if r["recomendacao"] == args.incluir]

        log = [["nome_pasta", "resultado"]]
        for row in linhas:
            resultado = reindexar(rekognition, drive, row["categoria"], row["subpasta"], row["nome_pasta"], row["arquivo_melhor"], cache)
            print(f"[{resultado}] {row['nome_pasta']}")
            log.append([row["nome_pasta"], resultado])

        with open(args.out, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(log)
        print(f"\nConcluído. Log em {args.out}")

    elif args.categoria and args.subpasta and args.pessoa and args.arquivo:
        resultado = reindexar(rekognition, drive, args.categoria, args.subpasta, args.pessoa, args.arquivo, cache)
        print(resultado)
    else:
        parser.error("Use --categoria/--subpasta/--pessoa/--arquivo para uma pessoa, ou --batch para o lote.")


if __name__ == "__main__":
    main()
