import sys
from pathlib import Path
from markdown2 import markdown

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



# report_service.py
from datetime import datetime
from pathlib import Path
import pdfkit
from jinja2 import Environment, FileSystemLoader, select_autoescape

from utils.naming import nome_resumo_ia, nome_analise_final, date_ddmmyyyy

config = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')

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

def html_to_pdf(html_path: Path, pdf_path: Path):
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdfkit.from_file(str(html_path), str(pdf_path), configuration=config)
    return pdf_path

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
            raw = p.read_text(encoding="utf-8", errors="ignore")
            conteudos.append({"titulo": p.stem, "texto": raw})
        except Exception as e:
            conteudos.append({"titulo": p.stem, "texto": f"[ERRO ao ler {p.name}: {e}]"})

    payload = {
        "cnpj": cnpj,
        "data_proc": date_ddmmyyyy(data_proc),
        "arquivos_processados": [p.name for p in entrada_txt],
        "blocos": conteudos,
        "parecer_final": "Parecer será consolidado na análise IA2.",
        "chart": {"labels": ["RAROC", "PD", "LGD"], "data": [0, 0, 0]},  # placeholder
    }

    # Caminhos
    base_nome = "DocumentosUnificados"
    # Garantir subpastas dentro de Retorno_IA
    retorno_dir = saida_dir.parent / "Retorno_IA"
    html_path = retorno_dir / f"{Path(nome_resumo_ia(base_nome, data_proc)).stem}.html"
    pdf_path = retorno_dir / nome_resumo_ia(base_nome, data_proc)


    # Renderizar
    render_template_to_html("interactive_report.html.j2", payload, html_path)
    html_to_pdf(html_path, pdf_path)

    return html_path, pdf_path

# ---------------------------
# Relatório Final IA2
# ---------------------------


def gerar_relatorio_final(cnpj: str, data_proc: datetime, conteudo_md: str, saida_dir: Path):
    """
    Converte conteúdo em Markdown para HTML estilizado + PDF.
    """
    html_body = markdown(
        conteudo_md,
        extras=[
            "tables",
            "fenced-code-blocks",
            "break-on-newline",   # ✅ respeita \n como <br/>, mantendo bullets e listas
            "code-friendly",
            "footnotes",
        ],
    )


    env = _env()
    tpl = env.get_template("interactive_report.html.j2")  # ou criar um template exclusivo
    payload = {
        "cnpj": cnpj,
        "data_proc": date_ddmmyyyy(data_proc),
        "arquivos_processados": [],
        "blocos": [],
        "parecer_final": "",
        "chart": {"labels": [], "data": []},
        "conteudo": html_body
    }

    retorno_dir = saida_dir.parent / "Retorno_IA"
    html_path = retorno_dir / f"{Path(nome_analise_final(cnpj, data_proc)).stem}.html"
    pdf_path = retorno_dir / nome_analise_final(cnpj, data_proc)


    html_renderizado = tpl.render(**payload)
    html_path.write_text(html_renderizado, encoding="utf-8")
    html_to_pdf(html_path, pdf_path)

    return html_path, pdf_path

