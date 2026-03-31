# progress_tracker.py
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyPDF2 import PdfReader


# -----------------------------
# Utilidades de caminho/execução
# -----------------------------
def job_root(cnpj: str, when: Optional[datetime] = None) -> Path:
    when = when or datetime.now()
    return Path("execuções") / f"{cnpj}_{when.strftime('%d%m%Y')}"


def ensure_job_dirs(cnpj: str) -> Dict[str, Path]:
    root = job_root(cnpj)
    d = {
        "root": root,
        "entrada": root / "entrada",
        "saida": root / "saida",
        "pre": root / "Pre_processamento",
        "retorno": root / "Retorno_IA",
        "logs": root / "logs",
    }
    for p in d.values():
        p.mkdir(parents=True, exist_ok=True)
    return d


def _pdf_pages(path: Path) -> int:
    try:
        return len(PdfReader(str(path)).pages)
    except Exception:
        return 0


# -----------------------------
# Modelo de dados do progresso
# -----------------------------
ETAPAS = ["extracao", "preprocesso", "ia1", "ia2", "apresentacao", "envio"]


@dataclass
class ArquivoStatus:
    nome: str
    paginas_total: int = 0
    paginas_feitas: int = 0
    status: str = "pendente"  # pendente|processando|concluido|erro
    erro: Optional[str] = None

    @property
    def percent(self) -> int:
        if self.paginas_total <= 0:
            # se não sabemos o total, assume 0 ou 100 dependendo do status
            return 100 if self.status == "concluido" else 0
        v = int(round((self.paginas_feitas / max(1, self.paginas_total)) * 100))
        return max(0, min(100, v))


@dataclass
class EtapaStatus:
    nome: str
    percent: int = 0
    status: str = "pendente"  # pendente|processando|concluido|erro
    detalhe: Optional[str] = None


@dataclass
class TrackerState:
    cnpj: str
    created_at: str
    updated_at: str
    arquivos: Dict[str, ArquivoStatus] = field(default_factory=dict)
    etapas: Dict[str, EtapaStatus] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "cnpj": self.cnpj,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "arquivos": {k: {**asdict(v), "percent": v.percent} for k, v in self.arquivos.items()},
            "etapas": {k: asdict(v) for k, v in self.etapas.items()},
            "overall_percent": self.overall_percent(),
        }

    def overall_percent(self) -> int:
        # Média simples das etapas existentes; se não houver, média por arquivos.
        if self.etapas:
            vals = [e.percent for e in self.etapas.values()]
            return int(round(sum(vals) / max(1, len(vals))))
        if self.arquivos:
            vals = [a.percent for a in self.arquivos.values()]
            return int(round(sum(vals) / max(1, len(vals))))
        return 0


# -----------------------------
# Núcleo do Tracker
# -----------------------------
class ProgressTracker:
    """
    Persistência em logs/progress.json para leitura pelo front.
    - Crie com `ProgressTracker(cnpj)`
    - Chame `plan_extracao()` antes da etapa de extração para definir páginas/arquivos
    - Use `mark_file_done()` ao concluir cada PDF (com páginas estimadas)
    - Para etapas IA1/IA2/Envio, use `set_etapa_status(...)` para refletir o andamento
    """
    def __init__(self, cnpj: str):
        self.cnpj = cnpj
        self.dirs = ensure_job_dirs(cnpj)
        self.path = self.dirs["logs"] / "progress.json"
        self._lock = threading.Lock()
        now = datetime.now().isoformat(timespec="seconds")

        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.state = self._from_dict(data)
            except Exception:
                self.state = TrackerState(cnpj=cnpj, created_at=now, updated_at=now)
        else:
            self.state = TrackerState(cnpj=cnpj, created_at=now, updated_at=now)

        # Garante etapas padrão
        for e in ETAPAS:
            if e not in self.state.etapas:
                self.state.etapas[e] = EtapaStatus(nome=e, percent=0, status="pendente")

        self._persist()

    # ---------- helpers ----------
    def _persist(self) -> None:
        self.state.updated_at = datetime.now().isoformat(timespec="seconds")
        self.path.write_text(json.dumps(self.state.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _from_dict(self, data: dict) -> TrackerState:
        st = TrackerState(
            cnpj=data.get("cnpj", self.cnpj),
            created_at=data.get("created_at", datetime.now().isoformat(timespec="seconds")),
            updated_at=data.get("updated_at", datetime.now().isoformat(timespec="seconds")),
        )
        for k, v in (data.get("arquivos") or {}).items():
            st.arquivos[k] = ArquivoStatus(
                nome=v.get("nome", k),
                paginas_total=int(v.get("paginas_total", 0)),
                paginas_feitas=int(v.get("paginas_feitas", 0)),
                status=v.get("status", "pendente"),
                erro=v.get("erro"),
            )
        for k, v in (data.get("etapas") or {}).items():
            st.etapas[k] = EtapaStatus(
                nome=v.get("nome", k),
                percent=int(v.get("percent", 0)),
                status=v.get("status", "pendente"),
                detalhe=v.get("detalhe"),
            )
        return st

    # ---------- plano e arquivos ----------
    def plan_extracao(self) -> Dict[str, int]:
        """
        Varre entrada/*.pdf e define plano por arquivo com páginas estimadas.
        Retorna dict {nome_arquivo: paginas}
        """
        with self._lock:
            plano: Dict[str, int] = {}
            for pdf in self.dirs["entrada"].glob("*.pdf"):
                pages = _pdf_pages(pdf)
                name = pdf.name
                plano[name] = max(pages, 1)  # evita zero p/ barras
                if name not in self.state.arquivos:
                    self.state.arquivos[name] = ArquivoStatus(nome=name, paginas_total=plano[name], paginas_feitas=0, status="pendente")
                else:
                    a = self.state.arquivos[name]
                    a.paginas_total = plano[name]
                    if a.status == "concluido" and a.paginas_feitas < plano[name]:
                        a.paginas_feitas = plano[name]
                # marca como pendente para a nova execução de extração
                self.state.arquivos[name].status = "pendente"
                self.state.arquivos[name].erro = None

            # Pode haver arquivos que não estão mais na pasta entrada/
            # não removemos histórico; apenas mantemos como estão.

            # Atualiza etapa
            self.state.etapas["extracao"].status = "processando"
            self.state.etapas["extracao"].percent = 0
            self._recalc_extracao_percent()
            self._persist()
            return plano

    def mark_file_processing(self, nome_arquivo: str) -> None:
        with self._lock:
            a = self.state.arquivos.get(nome_arquivo)
            if not a:
                a = self.state.arquivos[nome_arquivo] = ArquivoStatus(nome=nome_arquivo, paginas_total=1, paginas_feitas=0)
            a.status = "processando"
            self._persist()

    def mark_file_done(self, nome_arquivo: str) -> None:
        with self._lock:
            a = self.state.arquivos.get(nome_arquivo)
            if not a:
                a = self.state.arquivos[nome_arquivo] = ArquivoStatus(nome=nome_arquivo, paginas_total=1, paginas_feitas=1)
            # Como nossa extração atual é “tudo de uma vez”, consideramos 100% ao concluir
            a.paginas_feitas = max(a.paginas_total, 1)
            a.status = "concluido"
            self._recalc_extracao_percent()
            self._persist()

    def mark_file_error(self, nome_arquivo: str, erro: str) -> None:
        with self._lock:
            a = self.state.arquivos.get(nome_arquivo)
            if not a:
                a = self.state.arquivos[nome_arquivo] = ArquivoStatus(nome=nome_arquivo, paginas_total=1, paginas_feitas=0)
            a.status = "erro"
            a.erro = erro
            self._recalc_extracao_percent()
            self._persist()

    def _recalc_extracao_percent(self) -> None:
        if not self.state.arquivos:
            self.state.etapas["extracao"].percent = 0
            return
        vals = [a.percent for a in self.state.arquivos.values()]
        self.state.etapas["extracao"].percent = int(round(sum(vals) / max(1, len(vals))))
        # conclui etapa se todos concluídos
        if all(a.status in ("concluido",) for a in self.state.arquivos.values()):
            self.state.etapas["extracao"].status = "concluido"

    # ---------- etapas (preprocesso, ia1, ia2, envio) ----------
    def set_etapa_status(self, etapa: str, status: str, percent: Optional[int] = None, detalhe: Optional[str] = None) -> None:
        if etapa not in ETAPAS:
            raise ValueError(f"Etapa desconhecida: {etapa}. Válidas: {ETAPAS}")
        with self._lock:
            e = self.state.etapas.setdefault(etapa, EtapaStatus(nome=etapa))
            e.status = status  # pendente|processando|concluido|erro
            if percent is not None:
                e.percent = max(0, min(100, int(percent)))
            if detalhe is not None:
                e.detalhe = detalhe
            self._persist()

    # ---------- leitura ----------
    def snapshot(self) -> dict:
        with self._lock:
            return self.state.as_dict()
