from __future__ import annotations

import base64
import os
import re
import site
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

def _register_shared_site_packages() -> None:
    app_data = os.getenv("APPDATA") or os.path.expandvars(r"%APPDATA%")
    if not app_data or app_data == r"%APPDATA%":
        app_data = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")

    if not app_data:
        return

    python_root = Path(app_data) / "Python"
    if not python_root.exists():
        return

    for site_packages in python_root.glob("Python*/site-packages"):
        if site_packages.exists():
            site.addsitedir(str(site_packages))


_register_shared_site_packages()

from openai import OpenAI

from config_evidencias_service import load_config, save_config, get_all_aliases
from log_service import AuditEvent, _audit_write

try:
    import fitz  # type: ignore
except Exception:
    fitz = None

try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None


# --- Carregamento de Configurações ---
from config import get_settings
settings = get_settings()

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)

OPENAI_MODEL = settings.OPENAI_MODEL_IA1

TEXT_PREVIEW_LIMIT = 4000
OCR_PAGE_LIMIT = 2
VISION_PAGE_LIMIT = 2
MIN_TEXT_CHARS = 40
MIN_TEXT_ALNUM = 20
TESSERACT_CANDIDATES = (
    os.getenv("TESSERACT_CMD"),
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def texto_tem_conteudo_util(texto: str) -> bool:
    if not texto:
        return False

    if len(re.sub(r"\s+", "", texto)) < MIN_TEXT_CHARS:
        return False

    return sum(1 for ch in texto if ch.isalnum()) >= MIN_TEXT_ALNUM


def _match_known_type(tipos_conhecidos: list[str], *aliases: str) -> Optional[str]:
    aliases_norm = {_normalize_text(alias) for alias in aliases}
    for tipo in tipos_conhecidos:
        if _normalize_text(tipo) in aliases_norm:
            return tipo
    return None


def inferir_tipo_por_nome_arquivo(nome_arquivo: str, tipos_conhecidos: list[str]) -> Optional[str]:
    nome_norm = _normalize_text(nome_arquivo)
    
    # Nova lógica guiada pelo `config_evidencias_service`
    # Carrega o mapeamento do JSON -> dict: { "Tipo Documento": ["alias1", "alias2"] }
    mapeamento_dinamico = get_all_aliases()
    
    # 1. Verifica se existe pelo mapeamento de palavras-chave (dinâmico)
    for tipo_doc, aliases in mapeamento_dinamico.items():
        if tipo_doc in tipos_conhecidos:
            # Checa se algum dos aliases está contido no nome do arquivo
            gatilhos = [_normalize_text(a) for a in aliases]
            if any(gatilho and gatilho in nome_norm for gatilho in gatilhos):
                return tipo_doc

    # 2. Se falhar, faz um fallback exato baseado apenas nos tipos conhecidos
    for tipo in tipos_conhecidos:
        if _normalize_text(tipo) in nome_norm:
            return tipo

    return None


def montar_prompt_classificacao(tipos_conhecidos: list[str], usar_visao: bool = False) -> str:
    tipos_formatados = ", ".join(tipos_conhecidos) if tipos_conhecidos else "Nenhum tipo conhecido cadastrado"
    bloco_visao = ""
    if usar_visao:
        bloco_visao = (
            "\nAlém do texto disponível, avalie visualmente as imagens das primeiras páginas. "
            "Use títulos, cabeçalhos, formulários, selos e o layout como evidência adicional."
        )

    return f"""
Você é um classificador de documentos financeiros/empresariais.
Seu objetivo é identificar o tipo do documento usando duas fontes de evidência:
1. o nome original do arquivo PDF;
2. o texto extraído das primeiras páginas.{bloco_visao}

O nome do arquivo é uma fonte relevante e pode conter siglas, nomes de relatórios, produto, órgão emissor ou categoria documental que não aparecem com clareza no texto.
Use o nome do arquivo como sinal auxiliar para desempate e para melhorar a precisão da classificação, mas sem ignorar o conteúdo extraído quando houver conflito evidente.

Exemplos de tipos conhecidos atualmente: {tipos_formatados}.

Responda APENAS com o nome do Tipo de Documento, sem pontos, sem explicações.
Tente classificar como um dos tipos conhecidos se houver correspondência clara (ex: "Serasa PJ", "IRPF Sócio", "VADU").
Se for um documento diferente dos conhecidos, sugira um nome curto, claro e padronizado, de preferência o nome principal do relatório ou documento.
""".strip()


def montar_contexto_classificacao(
    pdf_path: str,
    texto_extraido: str,
    fonte_texto: str = "texto_nativo",
    tipo_sugerido_nome: Optional[str] = None,
) -> str:
    nome_arquivo = Path(pdf_path).name
    contexto = [
        f"Nome original do arquivo PDF: {nome_arquivo}",
        "",
        "Considere o nome do arquivo como uma pista relevante para identificar o tipo documental.",
        f"Fonte do texto para classificação: {fonte_texto}.",
    ]

    if tipo_sugerido_nome:
        contexto.extend([
            "",
            f"Sugestão preliminar baseada no nome do arquivo: {tipo_sugerido_nome}.",
        ])

    contexto.extend([
        "",
        "Texto das primeiras páginas:",
        "",
        texto_extraido[:TEXT_PREVIEW_LIMIT],
    ])
    return "\n".join(contexto)


def _audit_event(audit_logger, level: str, step: str, message: str, extra: Optional[dict] = None) -> None:
    if not audit_logger:
        return

    _audit_write(audit_logger, AuditEvent(
        ts=datetime.now().isoformat(timespec="seconds"),
        level=level,
        step=step,
        message=message,
        extra=extra or {},
    ))


def _configure_tesseract() -> bool:
    if pytesseract is None:
        return False

    for candidate in TESSERACT_CANDIDATES:
        if candidate and Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return True
    return False


def extrair_texto_paginas_iniciais(pdf_path: str, num_paginas: int = 2) -> str:
    if fitz is None:
        return ""

    texto = ""
    try:
        doc = fitz.open(pdf_path)
        for i in range(min(num_paginas, len(doc))):
            texto += doc[i].get_text("text") + "\n"
        doc.close()
    except Exception as e:
        print(f"Erro ao extrair texto de {pdf_path}: {e}")
    return texto.strip()


def _render_page_as_image(pdf_path: str, page_num: int, dpi: int = 200):
    if fitz is None or Image is None:
        return None

    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return image


def extrair_texto_ocr_paginas_iniciais(pdf_path: str, num_paginas: int = OCR_PAGE_LIMIT) -> str:
    if fitz is None or Image is None or ImageOps is None or pytesseract is None:
        return ""
    if not _configure_tesseract():
        return ""

    textos = []
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(num_paginas, len(doc))
        doc.close()
    except Exception:
        return ""

    for page_num in range(total_pages):
        image = _render_page_as_image(pdf_path, page_num)
        if image is None:
            continue

        prepared = ImageOps.grayscale(image)
        prepared = ImageOps.autocontrast(prepared)
        prepared = prepared.resize((prepared.width * 2, prepared.height * 2))

        best_text = ""
        for lang in ("por+eng", "por", "eng", None):
            try:
                if lang:
                    candidate = pytesseract.image_to_string(prepared, lang=lang)
                else:
                    candidate = pytesseract.image_to_string(prepared)
            except Exception:
                continue

            if len(candidate) > len(best_text):
                best_text = candidate
            if texto_tem_conteudo_util(candidate):
                best_text = candidate
                break

        if best_text:
            textos.append(best_text)

    return "\n".join(textos).strip()


def _encode_image_to_data_url(image) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")


def _registrar_tipo_novo(tipo_identificado: str, config_atual: dict, tipos_conhecidos: list[str]) -> None:
    if not tipo_identificado or tipo_identificado == "Desconhecido" or tipo_identificado in tipos_conhecidos:
        return

    config_atual[tipo_identificado] = {
        "exibir_usuario": False,
        "palavras_chave": [],
        "slides": [
            {
                "id": f"{tipo_identificado.lower().replace(' ', '_')}_auto",
                "modo": "ancora",
                "ancora": "Localize o trecho principal",
                "cabecalho": f"Documento: {tipo_identificado} - " + "{nome_empresa}",
                "descricao": "Slide gerado automaticamente para curadoria."
            }
        ]
    }
    save_config(config_atual)
    print(f"Novo tipo de documento cadastrado para curadoria: {tipo_identificado}")


def _classificar_via_texto(
    pdf_path: str,
    system_prompt: str,
    texto_contexto: str,
    tipos_conhecidos: list[str],
    config_atual: dict,
    estrategia: str,
    audit_logger=None,
) -> Tuple[str, str]:
    _audit_event(
        audit_logger,
        "INFO",
        "classificacao_ia.request",
        f"Classificação iniciada: {Path(pdf_path).name}",
        {
            "arquivo": Path(pdf_path).name,
            "estrategia": estrategia,
            "tipos_conhecidos": tipos_conhecidos,
            "prompt_system": system_prompt.strip(),
            "texto_contexto_preview": texto_contexto[:1500],
        },
    )

    resp = get_openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texto_contexto}
        ],
        temperature=0.0,
        max_tokens=20
    )
    raw_response = resp.choices[0].message.content
    tipo_identificado = raw_response.strip('."\'').strip()

    _registrar_tipo_novo(tipo_identificado, config_atual, tipos_conhecidos)

    _audit_event(
        audit_logger,
        "INFO",
        "classificacao_ia.response",
        f"Classificação concluída: {Path(pdf_path).name}",
        {
            "arquivo": Path(pdf_path).name,
            "estrategia": estrategia,
            "tipo_identificado": tipo_identificado,
            "raw_response": raw_response,
            "novo_tipo_cadastrado": tipo_identificado not in tipos_conhecidos and tipo_identificado != "Desconhecido",
        },
    )
    return tipo_identificado, texto_contexto


def _classificar_via_vision(
    pdf_path: str,
    tipos_conhecidos: list[str],
    config_atual: dict,
    tipo_sugerido_nome: Optional[str],
    texto_ocr: str,
    audit_logger=None,
) -> Optional[Tuple[str, str]]:
    if not OPENAI_API_KEY or fitz is None or Image is None:
        return None

    try:
        doc = fitz.open(pdf_path)
        total_pages = min(VISION_PAGE_LIMIT, len(doc))
        doc.close()
    except Exception:
        return None

    image_parts = []
    for page_num in range(total_pages):
        image = _render_page_as_image(pdf_path, page_num)
        if image is None:
            continue
        image_parts.append({
            "type": "image_url",
            "image_url": {"url": _encode_image_to_data_url(image)},
        })

    if not image_parts:
        return None

    system_prompt = montar_prompt_classificacao(tipos_conhecidos, usar_visao=True)
    context_lines = [
        f"Nome original do arquivo PDF: {Path(pdf_path).name}",
        "Analise visualmente as primeiras páginas anexadas.",
        "Use o nome do arquivo como pista relevante.",
    ]
    if tipo_sugerido_nome:
        context_lines.append(f"Sugestão preliminar baseada no nome do arquivo: {tipo_sugerido_nome}.")
    if texto_ocr:
        context_lines.extend(["", "Texto OCR disponível:", texto_ocr[:2000]])

    user_text = "\n".join(context_lines)

    _audit_event(
        audit_logger,
        "INFO",
        "classificacao_ia.vision.request",
        f"Classificação Vision iniciada: {Path(pdf_path).name}",
        {
            "arquivo": Path(pdf_path).name,
            "tipos_conhecidos": tipos_conhecidos,
            "prompt_system": system_prompt,
            "texto_contexto_preview": user_text[:1500],
            "imagens_enviadas": len(image_parts),
        },
    )

    response = get_openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{system_prompt}\n\n{user_text}"},
                    *image_parts,
                ],
            }
        ],
        temperature=0.0,
        max_tokens=30,
    )

    raw_response = response.choices[0].message.content.strip()
    tipo_identificado = raw_response.strip('."\'').strip()

    _registrar_tipo_novo(tipo_identificado, config_atual, tipos_conhecidos)

    _audit_event(
        audit_logger,
        "INFO",
        "classificacao_ia.vision.response",
        f"Classificação Vision concluída: {Path(pdf_path).name}",
        {
            "arquivo": Path(pdf_path).name,
            "tipo_identificado": tipo_identificado,
            "raw_response": raw_response,
            "novo_tipo_cadastrado": tipo_identificado not in tipos_conhecidos and tipo_identificado != "Desconhecido",
        },
    )
    return tipo_identificado, user_text


def classificar_documento(pdf_path: str, audit_logger=None) -> Tuple[str, str]:
    """
    Pipeline de classificação:
    1. Texto nativo das primeiras páginas.
    2. OCR local para PDFs imagem/scan.
    3. OpenAI Vision como fallback final.
    """
    config_atual = load_config()
    tipos_conhecidos = list(config_atual.keys())
    nome_arquivo = Path(pdf_path).name
    tipo_sugerido_nome = inferir_tipo_por_nome_arquivo(nome_arquivo, tipos_conhecidos)

    texto_nativo = extrair_texto_paginas_iniciais(pdf_path, num_paginas=OCR_PAGE_LIMIT)
    _audit_event(
        audit_logger,
        "INFO",
        "classificacao_ia.source",
        f"Texto nativo inspecionado: {nome_arquivo}",
        {
            "arquivo": nome_arquivo,
            "estrategia": "texto_nativo",
            "chars_extraidos": len(texto_nativo),
            "texto_util": texto_tem_conteudo_util(texto_nativo),
            "tipo_sugerido_nome": tipo_sugerido_nome,
        },
    )

    try:
        if texto_tem_conteudo_util(texto_nativo):
            system_prompt = montar_prompt_classificacao(tipos_conhecidos)
            texto_contexto = montar_contexto_classificacao(
                pdf_path,
                texto_nativo,
                fonte_texto="texto_nativo",
                tipo_sugerido_nome=tipo_sugerido_nome,
            )
            return _classificar_via_texto(
                pdf_path,
                system_prompt,
                texto_contexto,
                tipos_conhecidos,
                config_atual,
                estrategia="texto_nativo",
                audit_logger=audit_logger,
            )

        texto_ocr = extrair_texto_ocr_paginas_iniciais(pdf_path, num_paginas=OCR_PAGE_LIMIT)
        _audit_event(
            audit_logger,
            "INFO",
            "classificacao_ia.ocr",
            f"OCR executado: {nome_arquivo}",
            {
                "arquivo": nome_arquivo,
                "chars_extraidos": len(texto_ocr),
                "texto_util": texto_tem_conteudo_util(texto_ocr),
                "texto_ocr_preview": texto_ocr[:1500],
            },
        )

        if texto_tem_conteudo_util(texto_ocr):
            system_prompt = montar_prompt_classificacao(tipos_conhecidos)
            texto_contexto = montar_contexto_classificacao(
                pdf_path,
                texto_ocr,
                fonte_texto="ocr_paginas_iniciais",
                tipo_sugerido_nome=tipo_sugerido_nome,
            )
            return _classificar_via_texto(
                pdf_path,
                system_prompt,
                texto_contexto,
                tipos_conhecidos,
                config_atual,
                estrategia="ocr_paginas_iniciais",
                audit_logger=audit_logger,
            )

        resultado_vision = _classificar_via_vision(
            pdf_path,
            tipos_conhecidos,
            config_atual,
            tipo_sugerido_nome=tipo_sugerido_nome,
            texto_ocr=texto_ocr,
            audit_logger=audit_logger,
        )
        if resultado_vision:
            return resultado_vision

        if tipo_sugerido_nome:
            contexto = montar_contexto_classificacao(
                pdf_path,
                "",
                fonte_texto="fallback_nome_arquivo",
                tipo_sugerido_nome=tipo_sugerido_nome,
            )
            _audit_event(
                audit_logger,
                "WARNING",
                "classificacao_ia.filename_fallback",
                f"Fallback por nome do arquivo aplicado: {nome_arquivo}",
                {
                    "arquivo": nome_arquivo,
                    "tipo_identificado": tipo_sugerido_nome,
                },
            )
            return tipo_sugerido_nome, contexto

        _audit_event(
            audit_logger,
            "WARNING",
            "classificacao_ia.no_content",
            f"Documento sem texto útil para classificação: {nome_arquivo}",
            {
                "arquivo": nome_arquivo,
                "texto_nativo_chars": len(texto_nativo),
                "texto_ocr_chars": len(texto_ocr),
            },
        )
        return "Desconhecido", "Documento sem texto útil após extração nativa, OCR e Vision."

    except Exception as e:
        _audit_event(
            audit_logger,
            "ERROR",
            "classificacao_ia.error",
            f"Falha na classificação: {nome_arquivo}",
            {
                "arquivo": nome_arquivo,
                "erro": str(e),
                "tipo_sugerido_nome": tipo_sugerido_nome,
            },
        )
        print(f"Erro ao classificar documento via IA: {e}")

        if tipo_sugerido_nome:
            contexto = montar_contexto_classificacao(
                pdf_path,
                "",
                fonte_texto="fallback_nome_arquivo_apos_erro",
                tipo_sugerido_nome=tipo_sugerido_nome,
            )
            return tipo_sugerido_nome, contexto

        return "Desconhecido", str(e)
