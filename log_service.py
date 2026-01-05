# log_service.py
from __future__ import annotations

import json
import logging
import re
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


# -----------------------------
# Paths por execução
# -----------------------------
def job_root(cnpj: str) -> Path:
    return Path("execuções") / f"{cnpj}_{datetime.now().strftime('%d%m%Y')}"


def ensure_log_dir(cnpj: str) -> Path:
    root = job_root(cnpj)
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


# -----------------------------
# Máscara de dados sensíveis
# -----------------------------
RE_EMAIL = re.compile(r"([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
RE_CNPJ = re.compile(r"\b(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})\b")  # 14 dígitos
RE_CPF  = re.compile(r"\b(\d{3})(\d{3})(\d{3})(\d{2})\b")        # 11 dígitos


def mask_text(text: str, enable: bool = True) -> str:
    if not enable or not text:
        return text

    def _m_email(m: re.Match) -> str:
        user, dom = m.group(1), m.group(2)
        if len(user) <= 2:
            return "***@" + dom
        return user[0] + "***@" + dom

    def _m_cnpj(m: re.Match) -> str:
        return f"{m.group(1)}.***.***/*{m.group(4)[-2:]}-**"

    def _m_cpf(m: re.Match) -> str:
        return f"{m.group(1)}.***.***-**"

    t = RE_EMAIL.sub(_m_email, text)
    t = RE_CNPJ.sub(_m_cnpj, t)
    t = RE_CPF.sub(_m_cpf, t)
    return t


# -----------------------------
# Estruturas e formato JSONL
# -----------------------------
@dataclass
class AuditEvent:
    ts: str
    level: str
    step: str
    message: str
    elapsed_ms: Optional[int] = None
    extra: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "ts": self.ts,
                "level": self.level,
                "step": self.step,
                "message": self.message,
                "elapsed_ms": self.elapsed_ms,
                "extra": self.extra or {},
            },
            ensure_ascii=False,
        )


# -----------------------------
# Inicialização de logger
# -----------------------------
def init_logger(cnpj: str, level: int = logging.INFO, mask: bool = True) -> logging.Logger:
    """
    Cria um logger por execução:
      - logs/app.log (rotativo 5x1MB)
      - logs/audit.jsonl (eventos estruturados)
    """
    log_dir = ensure_log_dir(cnpj)
    logger_name = f"sbk.{cnpj}"
    logger = logging.getLogger(logger_name)
    if logger.handlers:
        # já inicializado
        logger.setLevel(level)
        return logger

    logger.setLevel(level)
    logger.propagate = False

    # Handler texto (rotativo)
    text_path = log_dir / "app.log"
    text_handler = RotatingFileHandler(text_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    text_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    text_handler.setFormatter(text_formatter)

    # Handler console (útil p/ debug local)
    console = logging.StreamHandler()
    console.setFormatter(text_formatter)

    # Wrapper para aplicar máscara antes de escrever
    class MaskingFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if mask and isinstance(record.msg, str):
                record.msg = mask_text(record.msg, enable=True)
            return True

    text_handler.addFilter(MaskingFilter())
    console.addFilter(MaskingFilter())

    logger.addHandler(text_handler)
    logger.addHandler(console)

    # Guarda caminho de audit.jsonl no objeto (para uso no decorator)
    logger.audit_jsonl_path = str(log_dir / "audit.jsonl")  # type: ignore[attr-defined]

    logger.info("Logger inicializado | app.log=%s | audit.jsonl=%s", text_path, logger.audit_jsonl_path)
    return logger


# -----------------------------
# Escrita em audit.jsonl
# -----------------------------
def _audit_write(logger: logging.Logger, event: AuditEvent, mask: bool = True) -> None:
    path = getattr(logger, "audit_jsonl_path", None)
    if not path:
        return
    line = event.to_json()
    if mask:
        line = mask_text(line, enable=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# -----------------------------
# Decorator / Context Manager
# -----------------------------
@contextmanager
def log_step(logger: logging.Logger, step: str, extra: Optional[Dict[str, Any]] = None, mask: bool = True):
    """
    Uso:
        with log_step(logger, "extracao", {"arquivo": "x.pdf"}):
            ... trabalho ...
    Registra início, fim e exceções, com tempo decorrido (ms).
    """
    t0 = time.perf_counter()
    logger.info("[STEP:%s] Início | extra=%s", step, extra or {})
    _audit_write(logger, AuditEvent(
        ts=datetime.now().isoformat(timespec="seconds"),
        level="INFO",
        step=step,
        message="start",
        extra=extra or {},
    ), mask=mask)

    try:
        yield
        elapsed = int((time.perf_counter() - t0) * 1000)
        logger.info("[STEP:%s] Concluído | %d ms", step, elapsed)
        _audit_write(logger, AuditEvent(
            ts=datetime.now().isoformat(timespec="seconds"),
            level="INFO",
            step=step,
            message="done",
            elapsed_ms=elapsed,
            extra=extra or {},
        ), mask=mask)
    except Exception as e:
        elapsed = int((time.perf_counter() - t0) * 1000)
        logger.exception("[STEP:%s] ERRO após %d ms: %s", step, elapsed, e)
        _audit_write(logger, AuditEvent(
            ts=datetime.now().isoformat(timespec="seconds"),
            level="ERROR",
            step=step,
            message=f"error: {type(e).__name__}: {e}",
            elapsed_ms=elapsed,
            extra=extra or {},
        ), mask=mask)
        raise


def logged_call(cnpj: str, step: str, level: int = logging.INFO, mask: bool = True):
    """
    Decorator de alto nível para funções que recebem `cnpj` como 1º arg ou kwarg.
    Ex.:
        @logged_call("extracao")
        def minha_func(cnpj: str, ...):
            ...
    """
    def _decorator(func):
        def _wrapped(*args, **kwargs):
            # descobrir cnpj real
            _cnpj = kwargs.get("cnpj")
            if _cnpj is None and len(args) >= 1:
                _cnpj = args[0]
            logger = init_logger(_cnpj, level=level, mask=mask)
            with log_step(logger, step, extra={"func": func.__name__}, mask=mask):
                return func(*args, **kwargs)
        return _wrapped
    return _decorator


# -----------------------------
# Utilidades
# -----------------------------
def tail_log(cnpj: str, bytes_back: int = 4000) -> str:
    """
    Retorna os últimos `bytes_back` do app.log (para exibir no front).
    """
    log_dir = ensure_log_dir(cnpj)
    path = log_dir / "app.log"
    if not path.exists():
        return ""
    data = path.read_bytes()
    return data[-bytes_back:].decode("utf-8", errors="ignore")


def read_audit(cnpj: str, max_lines: int = 200) -> list[dict]:
    """
    Lê as últimas `max_lines` entradas do audit.jsonl.
    """
    log_dir = ensure_log_dir(cnpj)
    path = log_dir / "audit.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
    out = []
    for ln in lines[-max_lines:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out
