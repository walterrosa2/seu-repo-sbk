from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List
import os

from openai import OpenAI
from log_service import init_logger, log_step
from progress_tracker import ProgressTracker
from report_service import gerar_relatorio_final
from utils.naming import nome_resumo_ia, nome_analise_final, date_ddmmyyyy

# --- Normalização do Markdown do IA2 ---
import re

def _posprocessar_md_ia2(texto: str) -> str:
    """
    - Remove prefixos 'Dados_0X:'.
    - Converte bullets '•' para '- ' (markdown).
    - Garante quebra de linha antes de cada bullet.
    - Mantém títulos numerados do IA2 como headings markdown.
    - Mantém tags especiais <relatorio_risco> ... </relatorio_risco>.
    """
    if not texto:
        return texto

    # 1) remover prefixos 'Dados_0X:'
    texto = re.sub(r"Dados_\d+\s*:\s*", "", texto)

    # 2) normalizar bullets: '•' -> '- '
    #    (garante que cada bullet comece em nova linha)
    #    substitui variações com tab/espacos
    texto = re.sub(r"[ \t]*•[ \t]*", r"\n- ", texto)

    # 3) se houver linhas iniciando com números seguidos de ponto (ex: "1. CARTÃO CNPJ"),
    #    converte para heading nível 2 "## "
    def _num_to_h2(m):
        return f"\n## {m.group(1).strip()}"
    texto = re.sub(r"(?m)^\s*\d+\.\s+(.*)$", _num_to_h2, texto)

    # 4) remover múltiplas quebras em excesso
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()

    return texto



def load_prompt_agente2() -> str:
    base = Path(__file__).parent
    for p in [base / "prompts" / "agente2.txt", base / "agente2.txt"]:
        if p.exists():
            return p.read_text(encoding="utf-8")
    return "⚠️ ERRO: Prompt 'agente2.txt' não encontrado."


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


from config import get_settings

settings = get_settings()

def run_openai_agente2(system_prompt: str, user_prompt: str, model: str, api_key: str, org: str | None) -> str:
    client = OpenAI(api_key=api_key, organization=org)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=8000,
    )
    return resp.choices[0].message.content.strip()


def process_manifest_ia2(cnpj: str, exec_root: Path = Path("execuções")) -> dict:
    OPENAI_API_KEY = settings.OPENAI_API_KEY
    OPENAI_ORG = settings.OPENAI_ORG
    OPENAI_MODEL_IA2 = settings.OPENAI_MODEL_IA2

    logger = init_logger(cnpj)
    tracker = ProgressTracker(cnpj)

    with log_step(logger, "ia2", {"cnpj": cnpj}):
        job_dir = exec_root / f"{cnpj}_{datetime.now().strftime('%d%m%Y')}"
        saida_dir = job_dir / "saida"
        retorno_dir = job_dir / "Retorno_IA"
        retorno_dir.mkdir(parents=True, exist_ok=True)

        ia1_txt_list = retorno_dir / "resultado_IA1.txt"
        if not ia1_txt_list.exists():
            raise FileNotFoundError("resultado_IA1.txt não encontrado.")

        blocos_ia1 = []
        for path_str in ia1_txt_list.read_text(encoding="utf-8").strip().splitlines():
            p = Path(path_str.strip())
            if p.exists():
                blocos_ia1.append(f"### {p.name}\n{read(p)}")

        manifest_path = saida_dir / "manifest_ia2.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifesto IA2 não encontrado: {manifest_path}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        arquivos_ia2: List[str] = manifest.get("arquivos", [])

        blocos_ia2 = []
        for fname in arquivos_ia2:
            path = saida_dir / fname
            if path.exists():
                blocos_ia2.append(f"### {fname}\n{read(path)}")

        system_prompt = "Você é um analista de crédito. Siga rigorosamente as instruções do usuário."
        instrucao_do_usuario = load_prompt_agente2()

        user_prompt = (
            instrucao_do_usuario
            + "\n\n==== RETORNOS DO AGENTE IA1 ===="            + "\n\n".join(blocos_ia1)
            + "\n\n==== DOCUMENTOS ORIGINAIS SEM RESUMO DA IA1===="            + "\n\n".join(blocos_ia2)
        )

        # Salvar prompt para depuração
        debug_prompt_path = retorno_dir / "prompt_enviado_openai.txt"
        debug_prompt_path.write_text(user_prompt, encoding="utf-8")

        logger.info("📤 Enviando prompt IA2 com %d blocos IA1 + %d IA2...", len(blocos_ia1), len(blocos_ia2))
        resposta = run_openai_agente2(system_prompt, user_prompt, model=OPENAI_MODEL_IA2, api_key=OPENAI_API_KEY, org=OPENAI_ORG)

        # ✅ PÓS-PROCESSAMENTO para aplicar melhorias (M1 e M2)
        resposta = _posprocessar_md_ia2(resposta)

        resposta_path = retorno_dir / "relatorio_final.md"
        resposta_path.write_text(resposta, encoding="utf-8")

        try:
            from report_service import gerar_relatorio_final
            # OBS: geração final de HTML/PDF será feita a partir do MD unificado no frontend.
            # Este gerar_relatorio_final aqui pode ser mantido como fallback (opcional)
            # gerar_relatorio_final(cnpj, datetime.now(), resposta, saida_dir)
            pass
        except Exception as e:
            logger.warning("Falha ao gerar Relatório Final: %s", e)


        resultado_json = {
            "cnpj": cnpj,
            "modelo": OPENAI_MODEL_IA2,
            "arquivos_ia1": len(blocos_ia1),
            "arquivos_ia2": len(blocos_ia2),
            "saida": str(resposta_path),
            "prompt_salvo_em": str(debug_prompt_path)
        }

        (retorno_dir / "resultado_IA2.json").write_text(json.dumps(resultado_json, ensure_ascii=False, indent=2), encoding="utf-8")
        (retorno_dir / ".ia2.DONE").write_text("ok", encoding="utf-8")
        tracker.set_etapa_status("ia2", "concluido", 100)

        return resultado_json