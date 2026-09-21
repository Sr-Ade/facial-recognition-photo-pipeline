"""Configuração central do pipeline, lida de variáveis de ambiente (.env)."""

import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.environ.get("AWS_REGION", "sa-east-1")
REKOGNITION_COLLECTION_ID = os.environ["REKOGNITION_COLLECTION_ID"]

GOOGLE_CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE = os.environ.get("GOOGLE_TOKEN_FILE", "token.json")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]

TRACKING_SPREADSHEET_ID = os.environ.get("TRACKING_SPREADSHEET_ID", "")
TRACKING_SHEET_NAME = os.environ.get("TRACKING_SHEET_NAME", "Recognitions")

# DRIVE_ROOT_FOLDERS="Category A:id1,Category B:id2" -> {"Category A": "id1", ...}
def _parse_root_folders(raw: str) -> dict:
    pares = [p for p in raw.split(",") if p.strip()]
    return dict(p.split(":", 1) for p in pares)


DRIVE_ROOT_FOLDERS = _parse_root_folders(os.environ.get("DRIVE_ROOT_FOLDERS", ""))

# Limites de segurança de custo/tempo, ajustáveis conforme a escala do projeto
MAX_IMAGE_BYTES = 4_500_000       # margem abaixo do limite de 5 MB do Rekognition
MAX_PHOTOS_PER_ATHLETE_BATCH = 8  # limite ao avaliar em lote (controle de custo)
FACE_MATCH_THRESHOLD = 90         # % mínimo de confiança para considerar um match
MIN_FACE_WIDTH_RATIO = 0.03       # ignora rostos com menos de 3% da largura da foto
