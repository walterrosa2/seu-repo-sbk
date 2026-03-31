import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from config_evidencias_service import get_all_aliases

logger = logging.getLogger(__name__)

# ==========================================
# CONSTANTS
# ==========================================
# ==========================================
# CONSTANTS
# ==========================================
TAG_PATTERNS = {
    "risco": r"<risco>(.*?)</risco>",
    "conclusao": r"<conclus[aã]o>(.*?)</conclus[aã]o>",
    "limite": r"<limite>(.*?)</limite>",
    "raroc": r"<raroc>(.*?)</raroc>",
    "cor_card": r"<cor_card>(.*?)</cor_card>",
    "tipo_arquivo": r"<tipo_arquivo>(.*?)</tipo_arquivo>",
    # New Tags
    "documentos_ausentes": r"<documentos_ausentes>(.*?)</documentos_ausentes>",
    "alerta_docs_antigos": r"<alerta_docs_antigos>(.*?)</alerta_docs_antigos>",
    # Catch-all for other xml-like tags we might want to strip but not necessarily extract distinctively
    "generic_tag": r"</?[a-zA-Z0-9_]+>" 
}

# ==========================================
# PARSING CORE
# ==========================================

def clean_filename(filename: str) -> str:
    """
    User Rule: 'remover no nome dos arquivos os trechos do inicio "ia1" "ia2", e no final o trecho "_resposta.txt"'
    Also removes extension if present.
    """
    if not filename: return ""
    
    # Remove extension first
    stem = Path(filename).stem
    
    # Remove prefixes
    stem = re.sub(r"^(ia\d+_|IA\d+_)", "", stem, flags=re.IGNORECASE)
    
    # Remove suffixes
    stem = re.sub(r"(_resposta|_resumo)$", "", stem, flags=re.IGNORECASE)
    
    # Replace underscores with spaces
    stem = stem.replace("_", " ")
    
    return stem.strip()

# =========================
# HELPER PARSING
# =========================

def _extract_tag_value(tag_name: str, text: str, multi_line: bool = True) -> Optional[str]:
    """
    Robust tag extraction supporting:
    1. XML: <tag>value</tag> or <tag>"value"</tag>
    2. Assignment/Hybrid: <tag>="value", <tag>:"value", or <tag>"value"
    Supports multi-line content via DOTALL if multi_line=True.
    """
    # 1. Try XML first (stricter and more modern)
    p_xml = fr"<{tag_name}>(.*?)</{tag_name}>"
    m_xml = re.search(p_xml, text, re.IGNORECASE | re.DOTALL)
    if m_xml:
        val = m_xml.group(1).strip()
        # Remove leading assignment artifacts inside XML if present (e.g. <tag>="Value"</tag>)
        if val.startswith('=') or val.startswith(':'):
            val = val[1:].strip()
        # Remove quotes inside XML if present (e.g. <bloco>"Value"</bloco>)
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1].strip()
        return val

    # 2. Assignment / Hybrid
    # Look for <tag> separator? content quote?
    # Supports optional = or : and optional quotes
    if not multi_line:
        # Stop at newline or next tag start
        p_assign = fr"<{tag_name}>\s*[:=]?\s*[\"']?([^\"'\n<]+)[\"']?"
    else:
        # Greedy until next tag start of same type or end
        p_assign = fr"<{tag_name}>\s*[:=]?\s*[\"']?((?:(?!</?{tag_name}|<[a-zA-Z]).)*)[\"']?"
    
    m_assign = re.search(p_assign, text, re.IGNORECASE | re.DOTALL)
    if m_assign:
        val = m_assign.group(1).strip()
        # Strip leading = or : again just in case regex captured it
        if val.startswith('=') or val.startswith(':'):
            val = val[1:].strip()
        if val.endswith('"') or val.endswith("'"): val = val[:-1]
        return val
    
    return None

def parse_ia_output(text: str) -> Dict[str, Any]:
    """
    Parses the raw text output from IA.
    Extracts tags defined in TAG_PATTERNS keys using robust extraction.
    Returns a dict with extracted metadata and the 'clean_text' (without tags).
    """
    if not text:
        return {"clean_text": "", "meta": {}}

    meta = {}
    clean_text = text

    # Extract Tags using robust helper
    for key in TAG_PATTERNS.keys():
        if key == "generic_tag": 
            continue
            
        multi_tags = ["calculo_raroc", "justificativa_risco", "justificativa_limite", "conclusao", "conclusão", "documentos_ausentes", "alerta_docs_antigos"]
        is_multi = key in multi_tags
        
        val = _extract_tag_value(key, text, multi_line=is_multi)
        if val:
            meta[key] = val
            
            # Remove the tag from text
            # For specific "content" tags (Justificativas, Raroc Calculation), we want to KEEP the content in the text 
            # but remove the tag wrapper <tag>= to clean it up.
            # For others (like <risco>=Alto), we usually want to remove it entirely as it's metadata.
            
            keep_content_keys = ["calculo_raroc", "justificativa_risco", "justificativa_limite", "conclusao", "conclusão"]
            
            if key in keep_content_keys:
                 # Remove only the tag identifier part: <tag>=" or <tag>=
                 # And the closing quote if it exists? Hard to know where it ends without matching.
                 # Strategy: Replace the WHOLE match with the CAPTURED VALUE (group 1).
                 # Regex matches: <tag>=" (VALUE) "
                 # We replace with \1 (Value).
                 
                 # XML cleanup
                 clean_text = re.sub(fr"<{key}>(.*?)</{key}>", r"\1", clean_text, flags=re.IGNORECASE | re.DOTALL)
                 # Assignment cleanup (greedy but stops at next tag or newline)
                 clean_text = re.sub(fr"<{key}>\s*[:=]?\s*[\"']?((?:(?!</?{key}|<[a-zA-Z]).)*?)[\"']?(?=\s*(?:\n|<|$))", r"\1", clean_text, flags=re.IGNORECASE | re.DOTALL)
                 
            else:
                # Remove entirely (Metadata tags)
                # XML cleanup
                clean_text = re.sub(fr"<{key}>(.*?)</{key}>", "", clean_text, flags=re.IGNORECASE | re.DOTALL)
                # Assignment cleanup: Safer non-greedy match respecting quotes or newline
                # Matches: key="value" OR key='value' OR key=value_until_newline
                clean_text = re.sub(fr"<{key}>\s*[:=]?\s*(?:([\"'])(.*?)\1|((?:(?!</?{key}|<[a-zA-Z]).)*))", "", clean_text, flags=re.IGNORECASE | re.DOTALL)

    # 3.2 Post-Processing Cleanups
    
    # Remove Variable Placeholders like <relatorio_final_IRPF_resumo.txt>
    # Logic: Remove <...txt> if it looks like a filename variable
    clean_text = re.sub(r"<[\w\-\.]+\.txt>", "", clean_text, flags=re.IGNORECASE)
    
    # Remove generic tags if any left
    # clean_text = re.sub(r"</?[a-zA-Z0-9_]{3,}>", "", clean_text) 
    
    # Fix Markdown Issues
    # "** text **" -> "**text**"
    clean_text = re.sub(r"\*\*\s+(.*?)\s+\*\*", r"**\1**", clean_text)

    # [NEW] Remove residual empty bold markers (common artifact after tag removal)
    # E.g. **<tag>** -> ****
    clean_text = re.sub(r"\*\*\s*\*\*", "", clean_text)
    
    # Fix Specific User formatting issues caused by LLM output
    # "Perdaesperada" -> "Perda esperada"
    clean_text = re.sub(r"Perdaesperada", "Perda esperada", clean_text, flags=re.IGNORECASE)
    
    # [NEW] Remove artifact assignments like ="IRPF" or ="amarelo"
    # Matches ="Value" or ="Value" usually at end of lines or loosely
    clean_text = re.sub(r'="[^"]+"', '', clean_text)
    clean_text = re.sub(r"='[^']+'", '', clean_text)
    
    # [NEW] Boldify Bullets: "- Key: Value" -> "- **Key**: Value"
    # Look for lines starting with "- " followed by some text and a colon
    clean_text = re.sub(r'^-\s+([^:\n]+):', r'- **\1**:', clean_text, flags=re.MULTILINE)

    
    # Escape $ to avoid Latex rendering issues in Streamlit
    # Uses \$ to escape.
    clean_text = clean_text.replace("$", "\\$")
    
    # Normalize Whitespace
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)

    return {
        "meta": meta,
        "clean_text": clean_text.strip()
    }

def generate_docs_index(execution_path: Path) -> List[Dict[str, Any]]:
    """
    Scans contents of 'entrada' and 'saida' to index documents with metadata
    (pages, chars, type, strategic status).
    """
    entrada_dir = execution_path / "entrada"
    saida_dir = execution_path / "saida"
    pre_dir = execution_path / "Pre_processamento"
    
    docs_index = []
    
    # Load manifest if available
    manifest_path = pre_dir / "manifest_ia1.json"
    manifest_data = {}
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Error reading manifest: {e}")

    def get_manifest_info(filename):
        if "arquivos" in manifest_data:
            for f in manifest_data["arquivos"]:
                if isinstance(f, str):
                    if f == filename:
                         return {"estrategico": True, "motivo": "Listado no manifesto IA1"}
                elif isinstance(f, dict):
                    if f.get("nome_original") == filename or f.get("arquivo") == filename:
                        return f
        return {}

    if saida_dir.exists():
        for txt_file in saida_dir.glob("*.txt"):
            original_pdf_name = txt_file.stem + ".pdf"
            
            chars = len(txt_file.read_text(encoding="utf-8", errors="ignore"))
            
            meta_path = saida_dir / f"{txt_file.stem}.meta.json"
            pages = 0
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    pages = meta.get("pages", 0)
                    if "original_name" in meta:
                        original_pdf_name = meta["original_name"]
                except:
                    pass
            
            # Classification (Legacy Heuristic as backup)
            doc_type = _heuristica_tipo_doc(original_pdf_name, txt_file)
            
            # Strategic info
            m_info = get_manifest_info(original_pdf_name)
            if not m_info:
                m_info = get_manifest_info(txt_file.name)
                
            estrategico = m_info.get("estrategico", False)
            razao = m_info.get("motivo", "")
            status = "Processado"

            docs_index.append({
                "filename": original_pdf_name,
                "filename_txt": txt_file.name,
                "pages": pages,
                "chars": chars,
                "type": doc_type,
                "strategic": estrategico,
                "reason": razao,
                "status": status
            })

    return docs_index

def _heuristica_tipo_doc(filename: str, txt_filepath: Path) -> str:
    """Classifies document based on filename and content dynamically."""
    name_lower = filename.lower()
    mapeamento_dinamico = get_all_aliases()
    
    for tipo_doc, aliases in mapeamento_dinamico.items():
        if any(a.lower() in name_lower for a in aliases if a):
            return tipo_doc
            
    # Fallback to general generic if no dynamic matched
    if "contrato" in name_lower or "social" in name_lower: return "Contratos"
    if "faturamento" in name_lower or "nota" in name_lower: return "Financeiro"
    return "Outros"

def extract_executive_summary(report_text: str) -> Dict[str, Any]:
    """
    Extraction of executive summary fields.
    Updated to prioritize tags if present, else fallback to regex.
    """
    summary = {
        "risco": "Não identificado",
        "limite": "Não identificado",
        "raroc": "N/D",
        "pd": "N/D",
        "lgd": "N/D",
        "decisao": "Em análise",
        "alertas": []
    }
    
    if not report_text:
        return summary

    # Try Parsing Tags First (if the text is the full unified output containing these tags)
    parsed = parse_ia_output(report_text)
    meta = parsed["meta"]
    
    if "risco" in meta: summary["risco"] = meta["risco"]
    if "limite" in meta: summary["limite"] = meta["limite"]
    if "raroc" in meta: summary["raroc"] = meta["raroc"]
    if "conclusao" in meta: summary["decisao"] = meta["conclusao"]

    # Fallback to Regex if tags missing (Legacy Logic)
    text_clean = report_text.replace("*", "")
    
    if summary["risco"] == "Não identificado":
        m_risco = re.search(r"(?i)(?:nível de )?risco[:\s]+(Alto|Médio|Baixo)", text_clean)
        if m_risco: summary["risco"] = m_risco.group(1).title()

    if summary["decisao"] == "Em análise":
        # Heuristics for conclusion based on keywords if tag missing
        if re.search(r"(?i)aprovado|favorável|recomendação[:\s]+aprovar", text_clean):
            summary["decisao"] = "Aprovar"
        elif re.search(r"(?i)reprovar|não recomendado", text_clean):
            summary["decisao"] = "Reprovar"

    if summary["raroc"] == "N/D":
        m_raroc = re.search(r"(?i)RAROC[:\s]+([\d,]+%)", text_clean)
        if m_raroc: summary["raroc"] = m_raroc.group(1)

    # PD/LGD always Regex as they might be inline
    m_pd = re.search(r"(?i)PD[:\s]+([\d,]+%)", text_clean)
    if m_pd: summary["pd"] = m_pd.group(1)

    m_lgd = re.search(r"(?i)LGD[:\s]+([\d,]+%)", text_clean)
    if m_lgd: summary["lgd"] = m_lgd.group(1)

    # Alertas
    m_alertas_block = re.search(r"(?i)(?:principais )?alertas[:\n](.*?)(?:\n#|\n\n[A-Z])", text_clean, re.DOTALL)
    if m_alertas_block:
        lines = [line.strip("- ").strip() for line in m_alertas_block.group(1).splitlines() if line.strip()]
        summary["alertas"] = lines[:5]

    return summary

def sanitize_report_text(text: str) -> str:
    """
    Cleans up formatting artifacts and removes specific XML-like tags
    so they don't show up in the UI.
    """
    return parse_ia_output(text)["clean_text"]

def parse_unified_report(text: str) -> List[Dict[str, Any]]:
    """
    Parses the unified report looking for <bloco>="NAME" tags.
    Returns a list of dicts representing each block/card.
    """
    if not text:
        return []
    
    blocks = []
    
    # Pattern to find blocks: <bloco>="NAME" ... content ... (until next separator or end)
    # The file uses "----------------------------------------------------------------------------------------------------" as separator
    # We can rely on split by separator or regex.
    # Regex approach:
    # We strip the separator lines first to make it cleaner? No, regex is fine.
    
    # Find all occurrences of <bloco>="NAME"
    # We capture the Name and then the content until the lookahead for the next separator or end of file
    
    # ------------------------------------------------------------------
    # 2. Extract REGULAR BLOCKS (now including RELATORIO RISCO due to prompt change)
    # ------------------------------------------------------------------
    # Updated pattern to capture Name and Content
    # Supports:
    # <bloco>="NAME"
    # <bloco>"NAME"
    # <bloco>NAME
    # Stops at </bloco> OR next <bloco>
    
    pattern = r'<bloco>\s*[:=]?\s*["\']?([^"\'\n>]+)["\']?\s*(.*?)(?:</bloco>|(?=\s*<bloco(?:=|\s|["\'])|\Z))'
    
    matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for m in matches:
        title = m.group(1).strip()
        raw_content = m.group(2).strip()
        
        # Clean up the content
        clean_content = sanitize_report_text(raw_content)
        
        # Try to find card color using robust helper (single line)
        color = _extract_tag_value("cor_card", raw_content, multi_line=False) or "cinza"

        # EXTRACT SUBITEMS
        # Pattern: Subitem => 1_1_IRPF - Info...
        # Returns list of strings
        subitems = re.findall(r"Subitem\s*=>\s*(.*)", raw_content, re.IGNORECASE)
        subitems_clean = [s.strip() for s in subitems if s.strip()]

        # Extract specific risk/limit tags that might be inside the block
        raroc_val = _extract_tag_value("raroc", raw_content, multi_line=False)
        risco_val = _extract_tag_value("risco", raw_content, multi_line=False)
        limite_val = _extract_tag_value("limite", raw_content, multi_line=False)
        conclusao_val = _extract_tag_value("conclusao", raw_content) or _extract_tag_value("conclusão", raw_content)
        
        calculo_raroc_val = _extract_tag_value("calculo_raroc", raw_content)
        justificativa_risco_val = _extract_tag_value("justificativa_risco", raw_content)
        justificativa_limite_val = _extract_tag_value("justificativa_limite", raw_content)

        # [NEW] Classification for type label
        doc_type = _heuristica_tipo_doc(title, Path(title))
        if "RELATORIO RISCO" in title.upper():
            doc_type = "RISCO"
        elif "CONCLUSAO" in title.upper():
            doc_type = "DESTAQUE"

        meta = {
            "tipo_arquivo": doc_type, 
            "cor_card": color,
            "raroc": raroc_val,
            "risco": risco_val,
            "limite": limite_val,
            "conclusao": conclusao_val,
            "calculo_raroc": calculo_raroc_val,
            "justificativa_risco": justificativa_risco_val,
            "justificativa_limite": justificativa_limite_val,
            "subitems": subitems_clean
        }
        
        # If title is RELATORIO RISCO, we can treat it specially or just let it be a block.
        # User wants it as a block.
        
        blocks.append({
            "raw_name": f"bloco_{title}",
            "clean_name": title, # Keep original case (1_IRPF...) usually
            "meta": meta,
            "content_clean": clean_content
        })
    
    # ------------------------------------------------------------------
    # ADD SYNTHETIC BLOCKS FOR ALERTS (Docs Ausentes / Antigos)
    # ------------------------------------------------------------------
    # (Existing logic...)
    
    # 1. Documentos Ausentes
    m_docs_ausentes = re.search(r"<documentos_ausentes>(.*?)</documentos_ausentes>", text, re.DOTALL | re.IGNORECASE)
    if m_docs_ausentes:
        content = m_docs_ausentes.group(1).strip()
        if content and len(content) > 3 and "nenhum" not in content.lower():
             blocks.insert(0, {
                "raw_name": "bloco_docs_ausentes",
                "clean_name": "Documentos Ausentes",
                "meta": {
                    "tipo_arquivo": "ALERTA",
                    "cor_card": "vermelho",
                    "subitems": []
                },
                "content_clean": sanitize_report_text(content)
            })

    # 2. Alerta Documentos Antigos
    m_docs_antigos = re.search(r"<alerta_docs_antigos>(.*?)</alerta_docs_antigos>", text, re.DOTALL | re.IGNORECASE)
    if m_docs_antigos:
        content = m_docs_antigos.group(1).strip()
        if content and len(content) > 3 and "nenhum" not in content.lower():
             blocks.insert(0, {
                "raw_name": "bloco_docs_antigos",
                "clean_name": "Docs Antigos/Vencidos",
                "meta": {
                    "tipo_arquivo": "ALERTA",
                    "cor_card": "vermelho",
                    "subitems": []
                },
                "content_clean": sanitize_report_text(content)
            })

    return blocks
