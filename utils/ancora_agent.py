import os
import json
import base64
import fitz # PyMuPDF
from datetime import datetime
from io import BytesIO
from PIL import Image
from openai import OpenAI
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# Carregar chaves
from config import get_settings
from log_service import AuditEvent, _audit_write
settings = get_settings()

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY, organization=settings.OPENAI_ORG)


def _extract_response_text(response: Any) -> str:
    """Extrai texto da resposta do OpenAI ou fallback do Responses API."""
    # 1. Padrao OpenAI Chat Completions
    if hasattr(response, "choices") and len(response.choices) > 0:
        choice = response.choices[0]
        finish_reason = getattr(choice, "finish_reason", "desconhecido")
        content = choice.message.content if choice.message.content else ""
        if not content.strip():
            raise ValueError(
                f"OpenAI retornou conteúdo vazio. finish_reason='{finish_reason}'. "
                "Possíveis causas: content_filter, limit de tokens ou imagem inválida."
            )
        return content.strip()

    # 2. Fallbacks para outros formats (se houver)
    direct_text = getattr(response, "output_text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    raise ValueError("OpenAI retornou resposta sem choices ou output_text.")


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    """Lê um objeto JSON mesmo quando vier cercado por markdown ou texto auxiliar."""
    content = (raw_text or "").strip()
    if not content:
        raise ValueError("Resposta vazia da IA")

    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Resposta JSON não é um objeto")
        return parsed
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = content[start:end + 1]
            parsed = json.loads(snippet)
            if not isinstance(parsed, dict):
                raise ValueError("Resposta JSON extraída não é um objeto")
            return parsed
        raise

def encode_image_to_base64(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_page_as_image(pdf_path: str, page_num: int, dpi: int = 150) -> Image.Image:
    """Converte uma página de PDF em imagem PIL."""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img

def detectar_coordenadas_ancora(pdf_path: str, instrucao: str, page_num: int = 0, audit_logger=None) -> Dict[str, Any]:
    """
    Usa o GPT-4o Vision para encontrar as coordenadas de um trecho no PDF.
    """
    raw_response = ""
    response = None
    try:
        # 1. Preparar imagem
        img = get_page_as_image(pdf_path, page_num)
        base64_image = encode_image_to_base64(img)
        
        # 2. Prompt do Sistema
        system_prompt = """Você é um especialista em análise visual de documentos.
Sua tarefa é localizar a área exata solicitada e retornar as coordenadas normalizadas (0-1000).
Retorne um JSON puro: {"ymin": int, "xmin": int, "ymax": int, "xmax": int}.
"""

        if audit_logger:
            _audit_write(audit_logger, AuditEvent(
                ts=datetime.now().isoformat(timespec="seconds"),
                level="INFO",
                step="apresentacao.mapeamento.request",
                message=f"Mapeamento IA iniciado: {Path(pdf_path).name}",
                extra={
                    "arquivo": Path(pdf_path).name,
                    "page_num": page_num + 1,
                    "instrucao": instrucao,
                    "prompt_system": system_prompt.strip(),
                }
            ))

        # 3. Chamada OpenAI Chat Completions
        response = get_openai_client().chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{system_prompt}\n\nInstrução: {instrucao}"},
                        {
                            "type": "image_url", 
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            temperature=0.0
        )
        
        raw_response = _extract_response_text(response)
        resultado = _extract_json_object(raw_response)
        if audit_logger:
            _audit_write(audit_logger, AuditEvent(
                ts=datetime.now().isoformat(timespec="seconds"),
                level="INFO",
                step="apresentacao.mapeamento.response",
                message=f"Mapeamento IA concluído: {Path(pdf_path).name}",
                extra={
                    "arquivo": Path(pdf_path).name,
                    "page_num": page_num + 1,
                    "instrucao": instrucao,
                    "raw_response": raw_response,
                    "coords": resultado if "error" not in resultado else None,
                    "error": resultado.get("error"),
                }
            ))
        return {
            "success": "error" not in resultado,
            "page": page_num,
            "coords": resultado if "error" not in resultado else None,
            "error": resultado.get("error")
        }

    except Exception as e:
        import traceback
        status = None
        try:
            status = getattr(response, "status", None)
        except Exception:
            status = None

        if raw_response:
            preview = raw_response[:500]
        else:
            preview = "<vazio>"

        err = f"Erro no Agente IA: {str(e)}\n{traceback.format_exc()}"
        if audit_logger:
            _audit_write(audit_logger, AuditEvent(
                ts=datetime.now().isoformat(timespec="seconds"),
                level="ERROR",
                step="apresentacao.mapeamento.error",
                message=f"Falha no mapeamento IA: {Path(pdf_path).name}",
                extra={
                    "arquivo": Path(pdf_path).name,
                    "page_num": page_num + 1,
                    "instrucao": instrucao,
                    "response_status": status,
                    "raw_response_preview": preview,
                    "erro": err,
                }
            ))
        return {"success": False, "error": err}

def normal_to_pdf_coords(coords_0_1000: Dict[str, int], page_width: float, page_height: float) -> Tuple[float, float, float, float]:
    """Converte escala 0-1000 para pontos do PDF (fitz)."""
    # ymin, xmin, ymax, xmax
    y0 = (coords_0_1000['ymin'] / 1000.0) * page_height
    x0 = (coords_0_1000['xmin'] / 1000.0) * page_width
    y1 = (coords_0_1000['ymax'] / 1000.0) * page_height
    x1 = (coords_0_1000['xmax'] / 1000.0) * page_width
    return (x0, y0, x1, y1)
