# utils/naming.py
from datetime import datetime
import re

def date_ddmmyyyy(dt: datetime) -> str:
    """Formata a data no padrão DDMMYYYY"""
    return dt.strftime("%d%m%Y")

def sanitize_component(text: str) -> str:
    """Sanitiza nome de arquivo removendo caracteres inválidos"""
    text = re.sub(r"[\\/:*?\"<>|]", "-", text)
    text = re.sub(r"\s+", "_", text).strip("_")
    return text

def nome_resumo_ia(base_nome: str, dt: datetime) -> str:
    """
    Nome do resumo IA consolidado.
    Exemplo: ResumoIA_Documentos_14092025.pdf
    """
    return f"ResumoIA_{sanitize_component(base_nome)}_{date_ddmmyyyy(dt)}.pdf"

def nome_analise_final(cnpj: str, dt: datetime) -> str:
    """
    Nome do relatório final IA2.
    Exemplo: AnaliseIA_21878984000188_14092025.pdf
    """
    cnpj_clean = re.sub(r"\D", "", cnpj)
    return f"AnaliseIA_{cnpj_clean}_{date_ddmmyyyy(dt)}.pdf"
