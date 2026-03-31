from __future__ import annotations
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=True)

class Settings(BaseSettings):
    """
    Carrega as configs a partir de .env (ou variáveis de ambiente).
    """

    # --- Modelo de carregamento ---
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # --- API / LAN ---
    API_HOST: str = Field("0.0.0.0", description="Bind da FastAPI na LAN")
    API_PORT: int = Field(8000, ge=1, le=65535)

    # --- Redis / Celery ---
    REDIS_URL: str = Field("redis://localhost:6379/0", description="URL do Redis (broker)")
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_BACKEND_URL: Optional[str] = None

    # --- OpenAI ---
    OPENAI_API_KEY: str = Field(..., min_length=10)
    OPENAI_ORG: Optional[str] = None
    OPENAI_MODEL_IA1: str = Field("gpt-4o", description="Modelo para IA1")
    OPENAI_MODEL_IA2: str = Field("gpt-4o", description="Modelo para IA2")

    # --- SMTP / e-mail ---
    SMTP_HOST: str = Field("smtp.gmail.com")
    SMTP_PORT: int = Field(587)
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    SMTP_TLS: bool = Field(True)

    # --- Ngrok / túnel ---
    USE_NGROK: bool = Field(False, description="Habilita túnel ngrok")
    NGROK_AUTHTOKEN: Optional[str] = None
    NGROK_DOMAIN: Optional[str] = None   # 👈 ADICIONE ESTA LINHA

    # --- Chunking / limites ---
    MAX_CHARS_LOTE_IA2: int = Field(120_000, ge=10_000)

    # --- Diretórios base ---
    DATA_DIR: Path = Field(default=Path("execuções"))
    CONFIG_DIR: Path = Field(default=Path("."), description="Pasta para arquivos de config persistentes")
    RETAIN_DAYS: int = Field(30, ge=1)
    MASK_LOGS: bool = Field(True, description="Mascarar CNPJ/E-mail nos logs")

        # === AWS Textract (novos; opcionais para não quebrar nada) ===
    aws_access_key_id: Optional[str] = Field(default=None, validation_alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, validation_alias="AWS_SECRET_ACCESS_KEY")
    aws_default_region: Optional[str] = Field(default=None, validation_alias="AWS_DEFAULT_REGION")
    aws_textract_s3_bucket: Optional[str] = Field(default=None, validation_alias="AWS_TEXTRACT_S3_BUCKET")
    aws_textract_s3_prefix: Optional[str] = Field(default="uploads", validation_alias="AWS_TEXTRACT_S3_PREFIX")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # evita falha se surgir algo novo no .env
    )

    # --- Helpers de diretórios por execução ---
    def job_dir(self, cnpj: str, date: Optional[datetime] = None) -> Path:
        d = (date or datetime.now()).strftime("%d%m%Y")
        return Path(self.DATA_DIR) / f"{cnpj}_{d}"

    def ensure_job_dirs(self, cnpj: str, date: Optional[datetime] = None) -> dict[str, Path]:
        root = self.job_dir(cnpj, date)
        dirs = {
            "root": root,
            "entrada": root / "entrada",
            "saida": root / "saida",
            "pre": root / "Pre_processamento",
            "retorno": root / "Retorno_IA",
            "logs": root / "logs",
        }
        for p in dirs.values():
            p.mkdir(parents=True, exist_ok=True)
        return dirs

@lru_cache
def get_settings() -> Settings:
    return Settings()
