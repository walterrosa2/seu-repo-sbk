import fitz
import os
from pathlib import Path

def _normalize_clip_rect(rect: tuple, page_rect, min_size: float = 4.0):
    x0, y0, x1, y1 = [float(v) for v in rect]

    left = min(x0, x1)
    right = max(x0, x1)
    top = min(y0, y1)
    bottom = max(y0, y1)

    clip = fitz.Rect(
        max(0, left),
        max(0, top),
        min(page_rect.width, right),
        min(page_rect.height, bottom),
    )

    if clip.width < min_size or clip.height < min_size:
        return None
    return clip

def crop_pdf_to_image(pdf_path: str, page_num: int, rect: tuple, out_path: str):
    """
    Recorta uma região (x0, y0, x1, y1) de uma página específica do PDF
    e salva como imagem.
    """
    try:
        doc = fitz.open(pdf_path)
        if page_num < 0 or page_num >= len(doc):
            raise ValueError(f"Página {page_num} inválida para o documento.")
        
        page = doc[page_num]
        fitz_rect = _normalize_clip_rect(rect, page.rect)
        if fitz_rect is None:
            raise ValueError(f"Retângulo de recorte inválido ou muito pequeno: {rect}")
        pix = page.get_pixmap(clip=fitz_rect, dpi=300)
        pix.save(out_path)
        return True
    except Exception as e:
        print(f"Erro ao recortar PDF por coordenadas: {e}")
        return False

def crop_pdf_by_text(pdf_path: str, keyword: str, padding: tuple, out_path: str):
    """
    Busca uma palavra-chave no PDF, localiza a coordenada da primeira ocorrência,
    aplica um padding (esq, topo, dir, base) e salva o recorte como imagem.
    """
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            rl = page.search_for(keyword)
            if rl:
                r = rl[0]
                # padding: (esq, topo, dir, base)
                rect = fitz.Rect(
                    max(0, r.x0 - padding[0]),
                    max(0, r.y0 - padding[1]),
                    r.x1 + padding[2],
                    r.y1 + padding[3]
                )
                
                # Se o rect passar dos limites da página, ajusta
                rect = rect.intersect(page.rect)
                
                pix = page.get_pixmap(clip=rect, dpi=300)
                pix.save(out_path)
                return {
                    "success": True,
                    "page": page_num + 1,
                    "rect": (rect.x0, rect.y0, rect.x1, rect.y1),
                    "text_found": keyword
                }
        return {"success": False, "error": "Âncora não encontrada"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def crop_pdf_by_section_markers(
    pdf_path: str,
    start_text: str,
    end_text: str = "",
    page_num: int | None = None,
    top_margin: int = 18,
    bottom_margin: int = 10,
    out_path: str = "",
) -> dict:
    """
    Recorta uma seção textual usando um marcador inicial e, opcionalmente, um marcador final.
    Estratégia ideal para PDFs textuais estruturados, mantendo o foco da seção.
    """
    try:
        doc = fitz.open(pdf_path)
        page_indexes = [page_num] if page_num is not None else list(range(len(doc)))

        for idx in page_indexes:
            if idx < 0 or idx >= len(doc):
                continue
            page = doc[idx]

            start_rects = page.search_for(start_text) if start_text else []
            if not start_rects:
                continue

            start_rect = start_rects[0]
            end_rect = None
            if end_text:
                for rect in page.search_for(end_text):
                    if rect.y0 > start_rect.y0:
                        end_rect = rect
                        break

            y0 = max(0, start_rect.y0 - top_margin)
            y1 = (end_rect.y0 - bottom_margin) if end_rect else page.rect.height
            crop_rect = _normalize_clip_rect((0, y0, page.rect.width, y1), page.rect)
            if crop_rect is None:
                continue

            if out_path:
                pix = page.get_pixmap(clip=crop_rect, dpi=300)
                pix.save(out_path)

            doc.close()
            return {
                "success": True,
                "page": idx + 1,
                "rect": (crop_rect.x0, crop_rect.y0, crop_rect.x1, crop_rect.y1),
                "modo": "section_markers",
                "start_text": start_text,
                "end_text": end_text if end_rect else None,
            }

        doc.close()
        return {
            "success": False,
            "error": f"Marcadores não localizados para recorte: start='{start_text}' end='{end_text}'",
            "modo": "section_markers",
        }
    except Exception as e:
        return {"success": False, "error": str(e), "modo": "section_markers"}


from utils.ancora_agent import detectar_coordenadas_ancora, normal_to_pdf_coords

def crop_pdf_by_ia_agent(
    pdf_path: str,
    instrucao: str,
    page_num: int = 0,
    out_path: str = "",
    audit_logger=None,
    ia_top_margin_ratio: float = 0.03,
):
    """
    Usa o Agente de IA para localizar um trecho e realiza o recorte.
    """
    try:
        # 1. Chamar o Agente IA
        resultado = detectar_coordenadas_ancora(pdf_path, instrucao, page_num=page_num, audit_logger=audit_logger)
        
        if not resultado.get("success"):
            return {"success": False, "error": resultado.get("error", "Erro desconhecido na IA")}

        coords_0_1000 = resultado.get("coords")
        if not coords_0_1000:
            return {"success": False, "error": "IA não retornou coordenadas válidas"}

        # 2. Abrir PDF para converter coordenadas
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        w, h = page.rect.width, page.rect.height
        
        # 3. Converter 0-1000 para pontos PDF
        x0, y0, x1, y1 = normal_to_pdf_coords(coords_0_1000, w, h)
        # Vision tende a retornar a caixa exata do bloco principal, sem "respiro" superior.
        # Expande um pouco o topo para evitar perda das primeiras linhas/títulos.
        margin_ratio = max(0.0, float(ia_top_margin_ratio))
        y0_adj = max(0.0, y0 - (h * margin_ratio))

        crop_rect = _normalize_clip_rect((x0, y0_adj, x1, y1), page.rect)
        if crop_rect is None:
            doc.close()
            return {
                "success": False,
                "error": "Coordenadas retornadas pela IA geraram um recorte inválido ou muito pequeno",
                "coords_originais": coords_0_1000,
                "rect_convertido": (x0, y0_adj, x1, y1),
                "page": page_num + 1,
                "modo": "agente_ia",
            }
        
        # 4. Salvar Recorte
        if out_path:
            pix = page.get_pixmap(clip=crop_rect, dpi=300)
            pix.save(out_path)
        
        doc.close()
        return {
            "success": True,
            "page": page_num + 1,
            "rect": (crop_rect.x0, crop_rect.y0, crop_rect.x1, crop_rect.y1),
            "modo": "agente_ia",
            "coords_originais": coords_0_1000,
            "rect_convertido": (x0, y0_adj, x1, y1),
            "ia_top_margin_ratio": margin_ratio,
        }
    except Exception as e:
        return {"success": False, "error": f"Erro no crop via IA: {str(e)}"}

def crop_pdf_by_text_range(
    pdf_path: str,
    texto_inicio: str,
    texto_fim: str = "",
    margin: int = 20,
    out_path: str = "",
) -> dict:
    """
    Recorta o trecho do PDF entre `texto_inicio` e `texto_fim`.

    Fluxo:
    1. Busca `texto_inicio` no documento (primeira ocorrência).
    2. Na mesma página, busca `texto_fim` (primeira ocorrência após o início).
    3. O rect do recorte é a união dos dois rects, mais `margin` pixels ao redor.
    4. Se `texto_fim` não for encontrado na página, recorta até o final da página.
    5. Retorna dict de auditoria: {success, page, rect, modo, texto_inicio, texto_fim}
    """
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]

            rects_inicio = page.search_for(texto_inicio)
            if not rects_inicio:
                continue

            r_inicio = rects_inicio[0]

            # Tenta localizar o texto_fim na mesma página
            r_fim = None
            if texto_fim:
                rects_fim = page.search_for(texto_fim)
                # Pega o primeiro rect que esteja ABAIXO (y0 maior) do inicio
                for rf in rects_fim:
                    if rf.y0 >= r_inicio.y0:
                        r_fim = rf
                        break

            # Monta o rect de recorte
            if r_fim:
                # Union entre inicio e fim
                x0 = min(r_inicio.x0, r_fim.x0) - margin
                y0 = r_inicio.y0 - margin
                x1 = max(r_inicio.x1, r_fim.x1) + margin
                y1 = r_fim.y1 + margin
                modo_efetivo = "range_completo"
            else:
                # Sem texto_fim: vai do inicio ate o final da pagina
                x0 = 0 - margin
                y0 = r_inicio.y0 - margin
                x1 = page.rect.width + margin
                y1 = page.rect.height
                modo_efetivo = "range_sem_fim" if texto_fim else "range_ate_fim_pagina"

            # Clip nos limites reais da página
            crop_rect = fitz.Rect(
                max(0, x0),
                max(0, y0),
                min(page.rect.width, x1),
                min(page.rect.height, y1),
            )

            if out_path:
                pix = page.get_pixmap(clip=crop_rect, dpi=300)
                pix.save(out_path)

            doc.close()
            return {
                "success": True,
                "page": page_num + 1,
                "rect": (crop_rect.x0, crop_rect.y0, crop_rect.x1, crop_rect.y1),
                "modo": modo_efetivo,
                "texto_inicio": texto_inicio,
                "texto_fim": texto_fim if r_fim else None,
            }

        doc.close()
        return {"success": False, "error": f"Âncora de início não encontrada: '{texto_inicio}'"}
    except Exception as e:
        return {"success": False, "error": str(e)}
