"""Autenticação e operações básicas no Google Drive, compartilhadas por todo
o pipeline. Escopo é sempre o mínimo necessário -- leitura no Drive, e
escrita apenas em Sheets quando explicitamente configurado.
"""

import io

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from PIL import Image

from . import config


def autenticar() -> Credentials:
    """Autentica via OAuth (fluxo local, uma vez), reaproveitando o token
    salvo nas execuções seguintes."""
    creds = None
    try:
        creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_FILE, config.GOOGLE_SCOPES)
    except FileNotFoundError:
        pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_FILE, config.GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(config.GOOGLE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)


def sheets_service(creds: Credentials):
    return build("sheets", "v4", credentials=creds)


def listar_filhos(drive, parent_id: str) -> list[dict]:
    """Lista todos os arquivos/pastas dentro de uma pasta, paginando quando
    necessário."""
    query = f"'{parent_id}' in parents and trashed = false"
    resultados, page_token = [], None
    while True:
        resp = drive.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType)",
            pageToken=page_token,
            pageSize=100,
        ).execute()
        resultados.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return resultados


def listar_fotos(drive, parent_id: str) -> list[dict]:
    return [f for f in listar_filhos(drive, parent_id) if f["mimeType"].startswith("image/")]


def baixar_arquivo(drive, file_id: str) -> bytes:
    request = drive.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def redimensionar_se_precisar(imagem_bytes: bytes, limite: int = config.MAX_IMAGE_BYTES) -> bytes:
    """Reduz qualidade/dimensões progressivamente até caber no limite de
    tamanho exigido pela API de reconhecimento."""
    if len(imagem_bytes) <= limite:
        return imagem_bytes

    img = Image.open(io.BytesIO(imagem_bytes)).convert("RGB")
    qualidade, largura = 85, img.width

    while True:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=qualidade)
        dados = buffer.getvalue()
        if len(dados) <= limite:
            return dados
        if qualidade > 40:
            qualidade -= 15
        else:
            largura = int(largura * 0.8)
            img = img.resize((largura, int(img.height * largura / img.width)))


def encontrar_pasta_por_caminho(drive, categoria: str, subpasta: str, nome_final: str, cache: dict) -> dict | None:
    """Localiza uma pasta de atleta pelo caminho categoria/subpasta/nome,
    com cache para evitar relistar a mesma subpasta repetidamente."""
    raiz_id = config.DRIVE_ROOT_FOLDERS[categoria]
    chave_cache = (categoria, subpasta)

    if chave_cache not in cache:
        subpastas = listar_filhos(drive, raiz_id)
        alvo = next((p for p in subpastas if p["name"] == subpasta), None)
        cache[chave_cache] = listar_filhos(drive, alvo["id"]) if alvo else []

    return next((p for p in cache[chave_cache] if p["name"].strip() == nome_final.strip()), None)
