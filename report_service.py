import sys
from pathlib import Path
from markdown2 import markdown

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# report_service.py
from datetime import datetime
# report_service.py
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

from utils.naming import nome_resumo_ia, nome_analise_final, date_ddmmyyyy
from report_parser import sanitize_report_text, parse_unified_report, extract_executive_summary

# pdfkit removido conforme solicitação de desuso de PDF
# config variable deprecated


# ---------------------------
# Helpers
# ---------------------------
def _env(templates_dir: str = "templates"):
    return Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "xml"])
    )

def render_template_to_html(template_name: str, context: dict, output_path: Path):
    env = _env()
    tpl = env.get_template(template_name)
    html = tpl.render(**context)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path

# html_to_pdf function deprecated/removed


# ---------------------------
# Unificação de TXT IA1
# ---------------------------
def unificar_txt_em_html(cnpj: str, data_proc: datetime, entrada_txt: list[Path], saida_dir: Path):
    """
    Unifica todos os .txt do IA1 em um único ResumoIA.
    Gera HTML interativo + PDF.
    """
    conteudos = []
    for p in entrada_txt:
        try:
            # Sanitize each block content
            raw = p.read_text(encoding="utf-8", errors="ignore")
            clean = sanitize_report_text(raw)
            conteudos.append({"titulo": p.stem, "texto": clean})
        except Exception as e:
            conteudos.append({"titulo": p.stem, "texto": f"[ERRO ao ler {p.name}: {e}]"})

    payload = {
        "cnpj": cnpj,
        "data_proc": date_ddmmyyyy(data_proc),
        "arquivos_processados": [p.name for p in entrada_txt],
        "blocos": conteudos,
        "parecer_final": "Parecer será consolidado na análise IA2.",
        "chart": {"labels": ["RAROC", "PD", "LGD"], "data": [0, 0, 0]},
    }

    # Caminhos
    base_nome = "DocumentosUnificados"
    retorno_dir = saida_dir.parent / "Retorno_IA"
    html_path = retorno_dir / f"{Path(nome_resumo_ia(base_nome, data_proc)).stem}.html"
    pdf_path = retorno_dir / nome_resumo_ia(base_nome, data_proc)


    # Usar template V2 (HTML Interativo apenas)
    render_template_to_html("interactive_report_v2.html.j2", {**payload, "conteudo": ""}, html_path)
    
    # PDF generation removed
    pdf_path = None

    return html_path, pdf_path

# ---------------------------
# Relatório Final IA2
# ---------------------------
def gerar_relatorio_final(cnpj: str, data_proc: datetime, conteudo_md: str, saida_dir: Path, output_filename: str = None):
    """
    Converte conteúdo em Markdown para HTML estilizado, espelhando a lógica do Frontend (Streamlit).
    """
    import re
    
    # 1. Extração de Dados (Igual ao Frontend)
    texto_relatorio = conteudo_md
    resumo = extract_executive_summary(texto_relatorio)
    document_blocks = parse_unified_report(texto_relatorio)
    
    # 2. Integração de Métricas (Override com dados dos blocos)
    for doc in document_blocks:
        m = doc.get("meta", {})
        if m.get("risco"): resumo["risco"] = m["risco"]
        if m.get("raroc"): resumo["raroc"] = m["raroc"]
        if m.get("limite"): resumo["limite"] = m["limite"]
        if m.get("conclusao"): resumo["decisao"] = m["conclusao"]
        
        # Justificativas
        if m.get("calculo_raroc"): resumo["calculo_raroc"] = m["calculo_raroc"]
        if m.get("justificativa_risco"): resumo["justificativa_risco"] = m["justificativa_risco"]
        if m.get("justificativa_limite"): resumo["justificativa_limite"] = m["justificativa_limite"]

    # 3. Injeção do Bloco Conclusão (Se existir decisão)
    if resumo.get("decisao"):
        bloco_conclusao = {
            "raw_name": "bloco_conclusao_final",
            "clean_name": "CONCLUSÃO FINAL",
            "meta": {
                "tipo_arquivo": "DESTAQUE",
                "cor_card": "azul"
            },
            "content_clean": resumo["decisao"]
        }
        document_blocks.insert(0, bloco_conclusao)

    # 4. Pré-processamento de Subitens para Renderização (Igual frontend split)
    # Transforma 'content_clean' em uma lista de sub-seções estruturadas
    
    # Extras para o markdown2, para espelhar o comportamento do Streamlit (Standard MD)
    markdown_extras = [
        "tables",
        "fenced-code-blocks",
        "break-on-newline",
        "code-friendly",
        "footnotes",
    ]

    for doc in document_blocks:
        full_text = doc["content_clean"]
        parts = re.split(r"(Subitem\s*=>\s*[^\n]+)", full_text, flags=re.IGNORECASE)
        
        processed_parts = []
        
        # Header do bloco (Pre-content)
        if parts:
            pre_content = parts[0].strip()
            if pre_content:
                processed_parts.append({"type": "info", "header": "", "content": markdown(pre_content, extras=markdown_extras)})
        
        # Pares Header/Content
        for i in range(1, len(parts), 2):
            sub_header = parts[i].strip()
            sub_content = parts[i+1].strip() if i+1 < len(parts) else ""
            # Prepend blank line to content to help markdown2 recognize lists if they start immediately
            md_content = f"\n{sub_content}"
            
            processed_parts.append({
                "type": "subitem",
                "header": sub_header,
                "content": markdown(md_content, extras=markdown_extras),
                "id": re.sub(r"[^a-zA-Z0-9]", "_", re.sub(r"Subitem\s*=>\s*", "", sub_header, flags=re.IGNORECASE).strip()).lower()
            })
            
        doc["render_parts"] = processed_parts
        
        # Mapeamento de cor para CSS
        cor_map = {
            "azul": "#007bff", "blue": "#007bff",
            "verde": "#28a745", "green": "#28a745",
            "vermelho": "#dc3545", "red": "#dc3545",
            "amarelo": "#ffc107", "yellow": "#ffc107",
            "laranja": "#fd7e14", "orange": "#fd7e14",
            "roxo": "#6f42c1", "purple": "#6f42c1",
            "cinza": "#6c757d", "grey": "#6c757d"
        }
        bg = doc["meta"].get("cor_card", "cinza").lower()
        doc["style_color"] = cor_map.get(bg, "#6c757d")

    
    # 5. Payload Final
    env = _env()
    
    payload = {
        "cnpj": cnpj,
        "data_proc": date_ddmmyyyy(data_proc),
        "resumo": resumo,
        "document_blocks": document_blocks,
        # Helper to convert loguru/frontend colors to bootstrap classes or hex? Using inline styles.
    }

    retorno_dir = saida_dir.parent / "Retorno_IA"
    
    if not output_filename:
        output_filename = nome_analise_final(cnpj, data_proc)
        
    html_path = retorno_dir / f"{Path(output_filename).stem}.html"
    pdf_path = retorno_dir / output_filename # Mantemos caminho mesmo sem gerar

    # Renderiza Template V2 Atualizado
    tpl_interactive = env.get_template("interactive_report_v2.html.j2")
    html_interativo = tpl_interactive.render(**payload)
    html_path.write_text(html_interativo, encoding="utf-8")

    return html_path, None
