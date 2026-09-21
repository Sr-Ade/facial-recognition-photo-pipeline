"""Cria a coleção de rostos no AWS Rekognition. Rodar uma vez só -- a
coleção persiste na conta AWS entre execuções.

Uso:
    python -m src.setup_collection
"""

import boto3

from . import config


def main():
    client = boto3.client("rekognition", region_name=config.AWS_REGION)
    try:
        resp = client.create_collection(CollectionId=config.REKOGNITION_COLLECTION_ID)
        print(f"Coleção '{config.REKOGNITION_COLLECTION_ID}' criada.")
        print(f"ARN: {resp['CollectionArn']}")
    except client.exceptions.ResourceAlreadyExistsException:
        print(f"A coleção '{config.REKOGNITION_COLLECTION_ID}' já existe.")


if __name__ == "__main__":
    main()
