# pre_processamento.py
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyPDF2 import PdfReader


# ----------------------------
# Configurações do heurístico
# ----------------------------
KEYWORDS_ESTRATEGICAS = [
    r"\bSERASA\b",
    r"\bVADU\b",
    r"\bIRPF\b",
    r"Declara(ç|c)ão\s+de\s+Imposto\s+de\s+Renda",
    r"Receita\s+Federal",
]

# Limiares de tamanho (ajuste conforme necessário)
MIN_PAGINAS_ESTRATEGICO = 15         # PDFs com >=15 páginas já suspeitamos ser "grandes"
MIN_CHARS_TXT_ESTRATEGICO = 120_000  # Texto extraído muito volumoso tende a exigir IA1 antes


@dataclass
class DocInfo:
    base: str
    pdf_path: Optional[str]
    txt_path: Optional[str]
    paginas: int
    chars: int
    estrategico: bool
    razoes: List[str]


# ----------------------------
# Funções utilitárias
# ----------------------------
def _contar_paginas(pdf_path: Path) -> int:
    if not pdf_path.exists():
        return 0
    try:
        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        return 0


def _contar_chars(txt_path: Path) -> int:
    if not txt_path.exists():
        return 0
    try:
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            return len(f.read())
    except Exception:
        return 0


def _has_keywords(txt_path: Path) -> Tuple[bool, List[str]]:
    """Verifica ocorrência de palavras-chave estratégicas."""
    if not txt_path.exists():
        return (False, [])
    try:
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        return (False, [])

    hits = []
    for pat in KEYWORDS_ESTRATEGICAS:
        if re.search(pat, content, flags=re.IGNORECASE):
            hits.append(pat)
    return (len(hits) > 0, hits)


def _mapear_arquivos(dirs: Dict[str, Path]) -> Dict[str, Dict[str, Optional[Path]]]:
    """
    Retorna um dicionário base_name -> { 'pdf': Path|None, 'txt': Path|None }
    cruzando entrada/*.pdf e saida/*.txt
    """
    mapa: Dict[str, Dict[str, Optional[Path]]] = {}

    for p in dirs["entrada"].glob("*.pdf"):
        base = p.stem
        mapa.setdefault(base, {"pdf": None, "txt": None})
        mapa[base]["pdf"] = p

    for t in dirs["saida"].glob("*.txt"):
        base = t.stem
        mapa.setdefault(base, {"pdf": None, "txt": None})
        mapa[base]["txt"] = t

    return mapa


def _classificar_doc(base: str, pdf: Optional[Path], txt: Optional[Path], n_pages_override: int = 0) -> DocInfo:
    paginas = n_pages_override
    if paginas == 0 and pdf:
        paginas = _contar_paginas(pdf)
    chars = _contar_chars(txt) if txt else 0

    razoes: List[str] = []

    # Critério 1: Keywords
    kw_hit = False
    kw_list: List[str] = []
    if txt:
        kw_hit, kw_list = _has_keywords(txt)
        if kw_hit:
            razoes.append("palavras‑chave: " + ", ".join(kw_list))

    # Critério 2: Tamanho
    if paginas >= MIN_PAGINAS_ESTRATEGICO:
        razoes.append(f"{paginas} páginas (>= {MIN_PAGINAS_ESTRATEGICO})")
    if chars >= MIN_CHARS_TXT_ESTRATEGICO:
        razoes.append(f"{chars} chars (>= {MIN_CHARS_TXT_ESTRATEGICO})")

    estrategico = bool(razoes)

    return DocInfo(
        base=base,
        pdf_path=str(pdf) if pdf else None,
        txt_path=str(txt) if txt else None,
        paginas=paginas,
        chars=chars,
        estrategico=estrategico,
        razoes=razoes,
    )


def _copiar_para_pre(doc: DocInfo, dirs: Dict[str, Path]) -> Optional[Path]:
    """
    Copia o TXT estratégico para Pre_processamento mantendo o nome base.
    """
    if not doc.txt_path:
        return None
    src = Path(doc.txt_path)
    dst = dirs["pre"] / src.name
    try:
        shutil.copy2(src, dst)
        return dst
    except Exception:
        return None


# ----------------------------
# API principal do módulo
# ----------------------------
def preparar_pre_processamento(cnpj: str, raiz_execucoes: Path = Path("execuções")) -> Dict:
    """
    Varre a execução do dia para o CNPJ informado:
      execuções/{CNPJ}_{DDMMAAAA}/entrada|saida|Pre_processamento|Retorno_IA|logs

    Identifica documentos 'estratégicos' e gera manifestos para IA1/IA2.
    Cria marcador '.pre.DONE' ao final.

    Retorna um dicionário-resumo, com detalhes por arquivo.
    """
    from datetime import datetime

    # Descobrir diretórios
    job_root = raiz_execucoes / f"{cnpj}_{datetime.now().strftime('%d%m%Y')}"
    dirs = {
        "root": job_root,
        "entrada": job_root / "entrada",
        "saida": job_root / "saida",
        "pre": job_root / "Pre_processamento",
        "retorno": job_root / "Retorno_IA",
        "logs": job_root / "logs",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)

    # Cruzar PDFs e TXTs
    mapa = _mapear_arquivos(dirs)

    # Classificar
    docs: List[DocInfo] = []
    for base, paths in mapa.items():
        # Tenta ler metadados de páginas (gerados na extração)
        meta_path = dirs["saida"] / f"{base}.meta.json"
        n_pages = 0
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                n_pages = meta.get("pages", 0)
            except:
                pass

        info = _classificar_doc(base, paths.get("pdf"), paths.get("txt"), n_pages_override=n_pages)
        docs.append(info)

    # Separar estratégicos (IA1) vs restantes (IA2)
    ia1_files: List[str] = []
    ia2_files: List[str] = []

    detalhes: Dict[str, Dict] = {}

    for d in docs:
        detalhes[d.base] = asdict(d)
        if d.estrategico:
            # Copiar para Pre_processamento
            _copiar_para_pre(d, dirs)
            ia1_files.append(f"{d.base}.txt")
        else:
            if d.txt_path:
                ia2_files.append(f"{d.base}.txt")

    # Manifestos
    manifest_ia1 = {
        "cnpj": cnpj,
        "etapa": "IA1",
        "arquivos": ia1_files,
        "criterios": {
            "keywords": KEYWORDS_ESTRATEGICAS,
            "min_paginas": MIN_PAGINAS_ESTRATEGICO,
            "min_chars": MIN_CHARS_TXT_ESTRATEGICO,
        },
    }
    manifest_ia2 = {
        "cnpj": cnpj,
        "etapa": "IA2",
        "arquivos": ia2_files,
        "dependencias": ["resultado_IA1"],  # IA2 dependerá do retorno do IA1
    }

    with open(dirs["pre"] / "manifest_ia1.json", "w", encoding="utf-8") as f:
        json.dump(manifest_ia1, f, ensure_ascii=False, indent=2)

    with open(dirs["saida"] / "manifest_ia2.json", "w", encoding="utf-8") as f:
        json.dump(manifest_ia2, f, ensure_ascii=False, indent=2)

    # Marcador de etapa concluída
    (dirs["pre"] / ".pre.DONE").write_text("ok", encoding="utf-8")

    # Resumo
    resumo = {
        "status": "concluido",
        "total_docs": len(docs),
        "ia1_count": len(ia1_files),
        "ia2_count": len(ia2_files),
        "detalhes": {k: v for k, v in detalhes.items()},
        "paths": {
            "manifest_ia1": str(dirs["pre"] / "manifest_ia1.json"),
            "manifest_ia2": str(dirs["saida"] / "manifest_ia2.json"),
        },
    }
    return resumo


# Execução manual (opcional)
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pré-processamento e identificação de documentos estratégicos")
    parser.add_argument("--cnpj", required=True, help="CNPJ somente números")
    parser.add_argument("--execucoes", default="execuções", help="Diretório raiz das execuções")
    args = parser.parse_args()

    out = preparar_pre_processamento(args.cnpj, Path(args.execucoes))
    print(json.dumps(out, ensure_ascii=False, indent=2))
