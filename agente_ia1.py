# agente_ia1.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List
from datetime import datetime

from openai import OpenAI
from report_parser import clean_filename
from utils.naming import nome_resumo_ia

# =============================
# Configs do ambiente / OpenAI
# =============================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG = os.getenv("OPENAI_ORG", None)
OPENAI_MODEL_IA1 = os.getenv("OPENAI_MODEL_IA1", "gpt-4o")

client = OpenAI(api_key=OPENAI_API_KEY, organization=OPENAI_ORG)


# =============================
# Helpers de I/O
# =============================
def load_prompt_agente1() -> str:
    for p in [Path("prompts") / "agente1.txt", Path("agente1.txt")]:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return "Você é o Agente IA1. Analise o conteúdo do documento conforme instruções definidas."  # fallback


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_openai_agente1(system_prompt: str, user_prompt: str) -> str:
    resp = client.responses.create(
        model=OPENAI_MODEL_IA1,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
        max_output_tokens=8000,
    )
    return resp.output_text.strip()


# =============================
# Core IA1
# =============================
def process_manifest_ia1(cnpj: str, exec_root: Path = Path("execuções")) -> dict:
    """
    Lê o manifesto IA1 e processa cada TXT estratégico,
    salvando 'ia1_<base>_resposta.txt' em Retorno_IA/.

    Ao final, consolida TODOS os 'ia1_*.txt' encontrados no disco
    em 'relatorio_IA1.md' e, se possível, gera 'relatorio_IA1.pdf'.
    """
    job_dir = exec_root / f"{cnpj}_{datetime.now().strftime('%d%m%Y')}"
    pre_dir = job_dir / "Pre_processamento"
    saida_dir = job_dir / "saida"
    ret_dir = job_dir / "Retorno_IA"
    ret_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = pre_dir / "manifest_ia1.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifesto IA1 não encontrado: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    arquivos: List[str] = manifest.get("arquivos", [])

    system_prompt = load_prompt_agente1()
    erros, resultado_paths = [], []

    # ---- Processa cada arquivo listado no manifesto ----
    for fname in arquivos:
        base = Path(fname).stem
        txt_path = pre_dir / fname
        if not txt_path.exists():
            # fallback: alguns fluxos podem ter mantido o txt em 'saida/'
            alt = saida_dir / fname
            txt_path = alt if alt.exists() else txt_path
        if not txt_path.exists():
            erros.append({"arquivo": fname, "erro": "Arquivo .txt não encontrado"})
            continue

        try:
            texto = read_text(txt_path)
            resposta = run_openai_agente1(system_prompt, texto)
            out_path = ret_dir / f"ia1_{base}_resposta.txt"
            write_text(out_path, resposta)
            resultado_paths.append(str(out_path))
        except Exception as e:
            erros.append({"arquivo": fname, "erro": str(e)})

    # ---- Artefatos de status da execução IA1 ----
    consolidado = {
        "cnpj": cnpj,
        "modelo": OPENAI_MODEL_IA1,
        "respostas_txt": resultado_paths,
        "erros": erros
    }
    write_text(ret_dir / "resultado_IA1.txt", "\n".join(resultado_paths))
    write_text(ret_dir / ".ia1.DONE", "ok")

    # =====================================================
    # CONSOLIDAÇÃO ROBUSTA: varre o disco por ia1_*.txt
    # (não depende da lista em memória 'resultado_paths')
    # =====================================================
    md_consolidado_path = ret_dir / "relatorio_IA1.md"
    pdf_consolidado_path = ret_dir / "relatorio_IA1.pdf"

    ia1_txts = sorted(ret_dir.glob("ia1_*.txt"))
    blocos = []
    for p in ia1_txts:
        try:
            if p.exists() and p.stat().st_size > 0:
                # Use clean filename for the header
                titulo = f"### {clean_filename(p.name)}"
                conteudo = read_text(p)
                blocos.append(f"{titulo}\n\n{conteudo}")
        except Exception as e:
            # não interrompe a execução por falha em um arquivo
            print(f"[IA1] Aviso: falha ao ler {p.name}: {e}")

    conteudo_md = "\n\n---\n\n".join(blocos)

    if conteudo_md.strip():
        # grava o .md somente se houver conteúdo
        md_consolidado_path.write_text(conteudo_md, encoding="utf-8")
        # tenta gerar PDF (usa seu report_service.py com pdfkit/wkhtmltopdf)
        try:
            from report_service import gerar_relatorio_final
            conteudo_html = md_consolidado_path.read_text(encoding="utf-8", errors="ignore")
            # [FIX] Aponta para a pasta correta (saida_dir) e define NOME Explicito (ResumoIA)
            resumo_name = nome_resumo_ia("DocumentosUnificados", datetime.now())
            gerar_relatorio_final(cnpj, datetime.now(), conteudo_html, saida_dir, output_filename=resumo_name)

        except Exception as e:
            print(f"⚠️ Erro ao gerar PDF IA1 formatado: {e}")
    else:
        print("[IA1] Nenhum conteúdo válido encontrado p/ consolidação; .md/.pdf não foram criados.")

    return consolidado


# =============================
# Execução via CLI
# =============================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agente IA1 — reestruturado (com consolidação robusta)")
    parser.add_argument("--cnpj", required=True, help="CNPJ (somente números)")
    parser.add_argument("--execucoes", default="execuções", help="Diretório raiz das execuções")
    args = parser.parse_args()

    out = process_manifest_ia1(args.cnpj, Path(args.execucoes))
    print(json.dumps(out, ensure_ascii=False, indent=2))
