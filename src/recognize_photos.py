"""Detecta todos os rostos em cada foto de uma pasta (não apenas o maior) e
busca cada um individualmente na coleção -- essencial para fotos de grupo
com vários jogadores no mesmo quadro.

Uso:
    python -m src.recognize_photos --folder-id <id_da_pasta_no_drive> \\
        --out data/recognition_result.csv
"""

import argparse
import csv

import boto3
from PIL import Image
import io

from . import config
from .drive_client import autenticar, drive_service, listar_fotos, baixar_arquivo, redimensionar_se_precisar


def recortar_rosto(imagem_pil: Image.Image, bounding_box: dict, margem: float = 0.15) -> bytes:
    largura, altura = imagem_pil.size
    bw, bh = bounding_box["Width"], bounding_box["Height"]

    left = max(0, bounding_box["Left"] - bw * margem) * largura
    top = max(0, bounding_box["Top"] - bh * margem) * altura
    right = min(1, bounding_box["Left"] + bw * (1 + margem)) * largura
    bottom = min(1, bounding_box["Top"] + bh * (1 + margem)) * altura

    recorte = imagem_pil.crop((left, top, right, bottom)).convert("RGB")
    buffer = io.BytesIO()
    recorte.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder-id", required=True)
    parser.add_argument("--out", default="data/recognition_result.csv")
    args = parser.parse_args()

    creds = autenticar()
    drive = drive_service(creds)
    rekognition = boto3.client("rekognition", region_name=config.AWS_REGION)

    fotos = listar_fotos(drive, args.folder_id)
    print(f"{len(fotos)} foto(s) encontrada(s).")

    linhas = [["foto", "rosto_num", "pessoa_id", "confianca", "link_foto"]]

    for foto in fotos:
        link = f"https://drive.google.com/file/d/{foto['id']}/view"
        try:
            imagem_bytes = redimensionar_se_precisar(baixar_arquivo(drive, foto["id"]))
            deteccao = rekognition.detect_faces(Image={"Bytes": imagem_bytes})
            rostos = deteccao.get("FaceDetails", [])

            if not rostos:
                linhas.append([foto["name"], 0, "", "sem_rosto_na_foto", link])
                continue

            imagem_pil = Image.open(io.BytesIO(imagem_bytes))
            print(f"{foto['name']}: {len(rostos)} rosto(s)")

            for i, rosto in enumerate(rostos, start=1):
                if rosto["BoundingBox"]["Width"] < config.MIN_FACE_WIDTH_RATIO:
                    continue  # rosto pequeno demais (provável fundo/torcida)

                recorte = redimensionar_se_precisar(recortar_rosto(imagem_pil, rosto["BoundingBox"]))
                try:
                    resp = rekognition.search_faces_by_image(
                        CollectionId=config.REKOGNITION_COLLECTION_ID,
                        Image={"Bytes": recorte},
                        MaxFaces=3,
                        FaceMatchThreshold=config.FACE_MATCH_THRESHOLD,
                    )
                    matches = resp.get("FaceMatches", [])
                    if not matches:
                        linhas.append([foto["name"], i, "", "", link])
                    for m in matches:
                        linhas.append([foto["name"], i, m["Face"]["ExternalImageId"], round(m["Similarity"], 1), link])
                except rekognition.exceptions.InvalidParameterException:
                    linhas.append([foto["name"], i, "", "recorte_baixa_qualidade", link])

        except Exception as e:
            linhas.append([foto["name"], 0, "", f"erro: {e}", link])

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(linhas)

    print(f"\nConcluído. Resultado em {args.out}")


if __name__ == "__main__":
    main()
