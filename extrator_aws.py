# extrator_aws_textract.py
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Tuple, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from PyPDF2 import PdfReader

from log_service import init_logger, log_step

# Carrega .env (como no exemplo do app.py anexo)
load_dotenv(override=True)

# Cliente Textract (mesmo padrão do app.py anexo)
_TEXTRACT = boto3.client(
    "textract",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_DEFAULT_REGION")
)

# Opcional para fallback assíncrono
_S3 = None
_AWS_BUCKET = os.getenv("AWS_TEXTRACT_S3_BUCKET")
_AWS_PREFIX = os.getenv("AWS_TEXTRACT_S3_PREFIX", "uploads")
if _AWS_BUCKET:
    _S3 = boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_DEFAULT_REGION")
    )


def _pdf_pages(pdf_path: Path) -> int:
    try:
        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        return 0


def _detect_sync(pdf_bytes: bytes) -> str:
    """
    Caminho simples (síncrono), igual ao exemplo do app.py: detect_document_text + join de LINHAS.
    """
    resp = _TEXTRACT.detect_document_text(Document={"Bytes": pdf_bytes})
    lines = [
        b["Text"] for b in resp.get("Blocks", [])
        if b.get("BlockType") == "LINE" and b.get("Text")
    ]
    return "\n".join(lines).strip()


def _detect_async_s3(bucket: str, key: str, poll_sec: float = 2.0, timeout_sec: int = 600) -> str:
    """
    Fallback assíncrono para PDFs grandes: StartDocumentTextDetection + polling de GetDocumentTextDetection.
    Requer S3 (bucket + key).
    """
    start = _TEXTRACT.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    job_id = start["JobId"]

    t0 = time.time()
    status = "IN_PROGRESS"
    next_token = None
    blocks: List[dict] = []

    while time.time() - t0 < timeout_sec:
        args = {"JobId": job_id}
        if next_token:
            args["NextToken"] = next_token

        resp = _TEXTRACT.get_document_text_detection(**args)
        status = resp["JobStatus"]

        if status == "SUCCEEDED":
            blocks.extend(resp.get("Blocks", []))
            next_token = resp.get("NextToken")
            if not next_token:
                break
        elif status in ("FAILED", "PARTIAL_SUCCESS"):
            raise RuntimeError(f"Textract job {job_id} terminou com status {status}")
        else:
            time.sleep(poll_sec)

    if status != "SUCCEEDED":
        raise TimeoutError(f"Textract job {job_id} não concluiu em {timeout_sec}s")

    lines = [b["Text"] for b in blocks if b.get("BlockType") == "LINE" and b.get("Text")]
    return "\n".join(lines).strip()


def _upload_to_s3(local_path: Path, bucket: str, prefix: str) -> str:
    key = f"{prefix.strip('/')}/{local_path.name}"
    assert _S3 is not None
    _S3.upload_file(str(local_path), bucket, key)
    return key


def extract_one(caminho_pdf: str, out_dir: str = "saida") -> Tuple[str, int]:
    """
    Extrai texto de PDF usando AWS Textract:
    - lê PDF local (mantemos a etapa de upload -> entrada/)
    - tenta síncrono detect_document_text
    - se der erro típico de PDF grande, usa caminho assíncrono via S3
    - salva <base>.txt em `out_dir`
    - retorna (caminho_txt, n_paginas)
    """
    pdf_path = Path(caminho_pdf).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / f"{pdf_path.stem}.txt"

    # Evita reprocesso (como no Docling)
    if txt_path.exists() and txt_path.stat().st_size > 30:
        return str(txt_path), _pdf_pages(pdf_path)

    logger = init_logger(pdf_path.stem)  # usa nome base como "cnpj" p/ particionar logs

    with log_step(logger, "extracao.aws", {"arquivo": pdf_path.name}):
        try:
            pdf_bytes = pdf_path.read_bytes()

            try:
                # 1) Tenta síncrono (simples e rápido p/ PDFs menores)
                texto = _detect_sync(pdf_bytes)

            except (ClientError, BotoCoreError) as e:
                # 2) Fallback assíncrono via S3 (para PDFs grandes)
                if not _AWS_BUCKET or _S3 is None:
                    raise RuntimeError(
                        f"Falha no detect_document_text e sem bucket configurado p/ fallback. Erro: {e}"
                    )
                key = _upload_to_s3(pdf_path, _AWS_BUCKET, _AWS_PREFIX)
                texto = _detect_async_s3(_AWS_BUCKET, key)

            # Grava o .txt de saída
            txt_path.write_text(texto or "", encoding="utf-8")

            return str(txt_path), _pdf_pages(pdf_path)

        except Exception as e:
            raise RuntimeError(f"Erro ao extrair {pdf_path.name} via AWS Textract: {e}")
