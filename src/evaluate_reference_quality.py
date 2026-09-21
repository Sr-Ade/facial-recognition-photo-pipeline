"""Avalia a qualidade de fotos como referência facial (nitidez, frontalidade,
ambiguidade de múltiplos rostos), usando os atributos que o próprio
Rekognition retorna em detect_faces.

NÃO altera nada -- apenas avalia e reporta. É a base para decidir se vale
trocar a referência atual de uma pessoa por uma foto melhor disponível na
mesma pasta.

Uso (uma pessoa, ranking completo da pasta):
    python -m src.evaluate_reference_quality --categoria "Category A" \\
        --subpasta "2006" --pessoa "Nome Sobrenome"

Uso (lote, a partir de um CSV de indexação):
    python -m src.evaluate_reference_quality --batch data/index_result.csv \\
        --out data/reference_priority.csv
"""

import argparse
import csv

import boto3

from . import config
from .drive_client import autenticar, drive_service, listar_fotos, baixar_arquivo, redimensionar_se_precisar, encontrar_pasta_por_caminho


def pontuar(rostos: list[dict]) -> tuple[float, int]:
    if not rostos:
        return -1.0, 0

    rostos_ordenados = sorted(rostos, key=lambda r: r["BoundingBox"]["Width"], reverse=True)
    principal = rostos_ordenados[0]
    largura = principal["BoundingBox"]["Width"]

    penalidade = 0
    if len(rostos_ordenados) > 1 and rostos_ordenados[1]["BoundingBox"]["Width"] > largura * 0.7:
        penalidade = 30  # 2º rosto quase do mesmo tamanho -> foto ambígua

    frontalidade = max(0, 100 - (abs(principal["Pose"]["Yaw"]) + abs(principal["Pose"]["Pitch"])))
    nitidez = principal["Quality"]["Sharpness"]
    brilho = principal["Quality"]["Brightness"]
    tamanho_score = min(largura * 300, 100)

    score = (frontalidade * 0.35) + (nitidez * 0.25) + (brilho * 0.15) + (tamanho_score * 0.25) - penalidade
    return round(score, 1), len(rostos)


def avaliar_pasta(rekognition, drive, pasta_id: str, limite_fotos: int | None = None) -> list[dict]:
    fotos = listar_fotos(drive, pasta_id)
    if limite_fotos:
        fotos = fotos[:limite_fotos]

    resultados = []
    for i, foto in enumerate(fotos):
        try:
            imagem = redimensionar_se_precisar(baixar_arquivo(drive, foto["id"]))
            deteccao = rekognition.detect_faces(Image={"Bytes": imagem}, Attributes=["ALL"])
            score, n_rostos = pontuar(deteccao.get("FaceDetails", []))
        except Exception:
            score, n_rostos = -1.0, 0
        resultados.append({"nome": foto["name"], "score": score, "n_rostos": n_rostos, "ordem": i})

    return resultados


def modo_individual(args):
    creds = autenticar()
    drive = drive_service(creds)
    rekognition = boto3.client("rekognition", region_name=config.AWS_REGION)

    cache = {}
    pasta = encontrar_pasta_por_caminho(drive, args.categoria, args.subpasta, args.pessoa, cache)
    if not pasta:
        print("Pasta não encontrada.")
        return

    resultados = avaliar_pasta(rekognition, drive, pasta["id"])
    resultados.sort(key=lambda r: r["score"], reverse=True)

    print(f"Ranking de {len(resultados)} foto(s):\n")
    for i, r in enumerate(resultados, start=1):
        marcador = "  <- melhor" if i == 1 else ""
        print(f"{i}. [{r['score']}] {r['nome']} ({r['n_rostos']} rosto(s)){marcador}")


def modo_lote(args):
    creds = autenticar()
    drive = drive_service(creds)
    rekognition = boto3.client("rekognition", region_name=config.AWS_REGION)
    cache = {}

    with open(args.batch, encoding="utf-8") as f:
        linhas = [r for r in csv.DictReader(f) if r["status"] == "indexado"]

    saida = []
    for row in linhas:
        pasta = encontrar_pasta_por_caminho(drive, row["categoria"], row["subpasta"], row["nome_pasta"], cache)
        if not pasta:
            continue

        resultados = avaliar_pasta(rekognition, drive, pasta["id"], limite_fotos=config.MAX_PHOTOS_PER_ATHLETE_BATCH)
        if not resultados:
            continue

        atual = next((r for r in resultados if r["ordem"] == 0), resultados[0])
        melhor = max(resultados, key=lambda r: r["score"])
        diferenca = round(melhor["score"] - atual["score"], 1)

        saida.append({
            "categoria": row["categoria"], "subpasta": row["subpasta"], "nome_pasta": row["nome_pasta"],
            "score_atual": atual["score"], "arquivo_atual": atual["nome"],
            "score_melhor": melhor["score"], "arquivo_melhor": melhor["nome"],
            "diferenca": diferenca,
            "recomendacao": "trocar" if diferenca >= 20 else ("avaliar" if diferenca >= 10 else "manter"),
        })
        print(f"{row['nome_pasta']}: atual={atual['score']} melhor={melhor['score']} -> {saida[-1]['recomendacao']}")

    saida.sort(key=lambda r: r["score_atual"])
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(saida[0].keys()))
        writer.writeheader()
        writer.writerows(saida)

    print(f"\nConcluído. Resultado em {args.out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--categoria")
    parser.add_argument("--subpasta")
    parser.add_argument("--pessoa")
    parser.add_argument("--batch", help="CSV de indexação, para avaliar todos em lote")
    parser.add_argument("--out", default="data/reference_priority.csv")
    args = parser.parse_args()

    if args.batch:
        modo_lote(args)
    elif args.categoria and args.subpasta and args.pessoa:
        modo_individual(args)
    else:
        parser.error("Use --categoria/--subpasta/--pessoa para uma pessoa, ou --batch para o lote.")


if __name__ == "__main__":
    main()
