import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import os
import json
import time # Added for unique JS injection
import shutil
import re
from unittest.mock import MagicMock
from dotenv import load_dotenv

load_dotenv(override=True)

from extrator_aws import extract_one
from pre_processamento import preparar_pre_processamento
from agente_ia1 import process_manifest_ia1
from agente_ia2 import process_manifest_ia2
from email_service import enviar_relatorio_final
from progress_tracker import ProgressTracker
from log_service import init_logger, log_step, tail_log, read_audit, AuditEvent, _audit_write
from report_service import unificar_txt_em_html, gerar_relatorio_final
from utils.naming import nome_resumo_ia, nome_analise_final, date_ddmmyyyy
from report_parser import generate_docs_index, extract_executive_summary, sanitize_report_text, parse_ia_output, clean_filename, parse_unified_report, _heuristica_tipo_doc
from auth_service import authenticate, create_user, list_users, delete_user
from presentation_service import criar_apresentacao_evidencias
from pdf_presentation_service import criar_apresentacao_pdf
from config_evidencias_service import load_config, save_config, get_config_for_type
from utils.pdf_cropper import crop_pdf_by_text, crop_pdf_to_image, crop_pdf_by_text_range
from utils.presentation_helpers import get_presentation_variables, inject_variables
from utils.ui_premium import (
    apply_presentation_premium_css,
    section_header,
    slide_card_header,
    crop_tool_header,
    coords_display,
    instruction_banner,
    ai_card_open,
    ai_card_close,
    glass_card_open,
    glass_card_close,
)
st_cropper_error = None
try:
    from streamlit_cropper import st_cropper
except Exception as e:
    st_cropper = None
    st_cropper_error = str(e)

# =========================
# Constantes & Helpers
# =========================
EXEC_ROOT = Path("execuções")

# Configuração da página para usar layout wide por padrão (melhor para o dashboard)
st.set_page_config(page_title="SBK Capital - Análise de Crédito", layout="wide")

def _safe_rerun():
    time.sleep(0.1)
    st.rerun()

def job_root(cnpj: str, when: datetime | None = None) -> Path:
    when = when or datetime.now()
    return EXEC_ROOT / f"{cnpj}_{when.strftime('%d%m%Y')}"

def ensure_job_dirs(cnpj: str) -> dict:
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

def limpar_entrada(cnpj: str):
    """Remove PDFs da pasta entrada após a extração para não persistir dados sensíveis."""
    dirs = ensure_job_dirs(cnpj)
    entrada = dirs["entrada"]
    if entrada.exists():
        for p in entrada.glob("*.pdf"):
            try:
                p.unlink()
            except Exception as e:
                print(f"⚠️ Erro ao remover {p.name}: {e}")

def ultima_execucao(cnpj: str) -> datetime | None:
    base = EXEC_ROOT
    cand = []
    for d in base.glob(f"{cnpj}_*"):
        try:
            data = datetime.strptime(d.name.split("_")[-1], "%d%m%Y")
            cand.append(data)
        except Exception:
            pass
    return max(cand) if cand else None

# =========================
# Helper de Paths (Adjusted) - Moved to top
# =========================
def get_current_job_dirs(input_cnpj: str):
    """
    Returns the directory structure based on session state (History or New).
    """
    if st.session_state.get("history_mode") and st.session_state.get("selected_job_path"):
        root = st.session_state["selected_job_path"]
    else:
        root = job_root(input_cnpj) # Default to today
        
    return {
        "root": root,
        "entrada": root / "entrada",
        "saida": root / "saida",
        "pre": root / "Pre_processamento",
        "retorno": root / "Retorno_IA",
        "logs": root / "logs",
    }

def resolve_presentation_pdf_sources(cnpj: str, dirs: dict, ultimo_job: datetime | None = None) -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add_from_dir(base_dir: Path | None):
        if not base_dir or not base_dir.exists():
            return
        for pdf in base_dir.glob("*.pdf"):
            key = str(pdf.resolve())
            if key not in seen:
                seen.add(key)
                candidates.append(pdf)

    _add_from_dir(dirs.get("entrada"))

    selected_job = st.session_state.get("selected_job_path")
    if selected_job:
        _add_from_dir(Path(selected_job) / "entrada")

    if ultimo_job:
        _add_from_dir(EXEC_ROOT / f"{cnpj}_{ultimo_job.strftime('%d%m%Y')}" / "entrada")

    for root in sorted(EXEC_ROOT.glob(f"{cnpj}_*"), reverse=True):
        _add_from_dir(root / "entrada")

    _add_from_dir(Path("tmp") / "desenv_pres")
    return candidates

# =========================
# CSS Customizado (Ajustes finos para o Dashboard)
# =========================
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #dcdcdc;
        text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #0f54c9;
    }
    .metric-label {
        font-size: 14px;
        color: #555;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# =========================
# Estado da UI
# =========================
# ==========================================
# AUTH CHECK
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_info" not in st.session_state:
    st.session_state.user_info = {}

def login_form():
    st.title("🔐 Login - SBK Capital")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit:
                user = authenticate(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user_info = user
                    st.success("Login realizado com sucesso!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

if not st.session_state.authenticated:
    login_form()
    st.stop() # Stop execution here if not authenticated

# =========================
# Estado da UI
# =========================
if "run_full" not in st.session_state:
    st.session_state.run_full = False
if "cnpj" not in st.session_state:
    st.session_state.cnpj = ""
if "usar_antigo" not in st.session_state:
    st.session_state.usar_antigo = None

# =========================
# Sidebar (Navegação Global)
# =========================
with st.sidebar:
    st.title("SBK Capital")
    
    # User Info / Logout
    st.markdown(f"**👤 Usuário:** {st.session_state.user_info.get('username', 'N/A')}")
    if st.button("Sair / Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_info = {}
        st.rerun()
    
    st.markdown("---")
    
    st.markdown("### Seleção do Cliente")
    cnpj_raw = st.text_input("CNPJ (somente números)", value=st.session_state.cnpj or "")
    cnpj = "".join(filter(str.isdigit, cnpj_raw))
    st.session_state.cnpj = cnpj

    if len(cnpj) != 14 and cnpj:
        st.warning("⚠️ CNPJ inválido. Digite 14 dígitos.")
    
    st.markdown("---")
    st.markdown("### Histórico de Execuções")
    
    # Listar pastas de execução
    history_options = ["Nova Execução"]
    job_map = {}
    
    if EXEC_ROOT.exists():
        # List all directories, sort by date desc
        # Format: CNPJ_DDMMYYYY
        all_jobs = []
        for p in EXEC_ROOT.iterdir():
             if p.is_dir() and "_" in p.name:
                 try:
                     # Validate date part
                     parts = p.name.split("_")
                     cnpj_part = parts[0]
                     date_str = parts[-1]
                     dt = datetime.strptime(date_str, "%d%m%Y")
                     label = f"{dt.strftime('%d/%m/%Y')} - {cnpj_part}"
                     all_jobs.append({"path": p, "date": dt, "label": label, "cnpj": cnpj_part})
                 except:
                     pass
        
        # Sort desc
        all_jobs.sort(key=lambda x: x["date"], reverse=True)
        
        # Filter by CNPJ if typed? Or show all?
        # Let's show all but maybe filter if CNPJ is typed
        filtered_jobs = [j for j in all_jobs if (not cnpj or j["cnpj"] == cnpj)] if cnpj and len(cnpj) == 14 else all_jobs
        
        for j in filtered_jobs:
            history_options.append(j["label"])
            job_map[j["label"]] = j

    selected_history = st.selectbox("Selecione:", history_options)
    
    if selected_history != "Nova Execução":
        st.session_state["history_mode"] = True
        st.session_state["selected_job_path"] = job_map[selected_history]["path"]
        # Auto-fill CNPJ if missing
        if not cnpj:
            st.session_state.cnpj = job_map[selected_history]["cnpj"]
            st.rerun()
    else:
        st.session_state["history_mode"] = False
        st.session_state["selected_job_path"] = None

    st.markdown("---")
    st.markdown("### 🛠️ Opções do Desenvolvedor")
    st.checkbox("Ativar Modo Desenv", key="modo_desenv", help="Habilita a aba de testes modulares e ferramentas de depuração.")

    st.info("Utilize as abas superiores para navegar entre Execução, Progresso e Resultados.")
    
    # ------------------------------------------------------------------
    # MENU LATERAL - ÍNDICE DO RELATÓRIO
    # ------------------------------------------------------------------
    st.markdown("---")
    if st.session_state.get("run_full") is False: # Only show if not running
        # Try to find current report blocks to build menu
        # Reuse logic from Results tab
        current_dirs = get_current_job_dirs(st.session_state.cnpj) if st.session_state.cnpj else None
        if current_dirs and (current_dirs["retorno"] / "relatorio_unificado.md").exists():
            st.markdown("### 📑 Índice do Relatório")
            try:
                txt_rep = (current_dirs["retorno"] / "relatorio_unificado.md").read_text(encoding="utf-8", errors="ignore")
                menu_blocks = parse_unified_report(txt_rep)
                
                if menu_blocks:
                    for b_idx, block in enumerate(menu_blocks):
                        b_name = block['clean_name']
                        # Unique key for block expander
                        with st.expander(f"{b_name}", expanded=False):
                            # Click block title to go there? 
                            # Or just list subitems.
                            
                            # Button for the main block
                            blk_id_clean = re.sub(r"[^a-zA-Z0-9]", "_", b_name).lower()
                            if st.button(f"Ir para {b_name}", key=f"nav_blk_{b_idx}"):
                                st.session_state["selected_doc"] = block["raw_name"]
                                st.session_state["viz_section"] = "Detalhamento IA (Full)" # Force tab
                                st.session_state["scroll_target_id"] = f"blk_{blk_id_clean}"
                                st.session_state["do_scroll"] = True
                                st.rerun()
                                
                            # Subitems list
                            subs = block["meta"].get("subitems", [])
                            for s_idx, sub in enumerate(subs):
                                # Clean subitem name (remove 1_1_ etc if needed, but user wants to see it)
                                # Extract just the name part usually Subitem => 1_1_NAME
                                # We treat the whole string as the label but ID needs to be clean.
                                raw_sub_name = re.sub(r"Subitem\s*=>\s*", "", sub, flags=re.IGNORECASE).strip()
                                sub_id_clean = re.sub(r"[^a-zA-Z0-9]", "_", raw_sub_name).lower()
                                
                                if st.button(f"🔸 {sub}", key=f"nav_sub_{b_idx}_{s_idx}"):
                                    st.session_state["selected_doc"] = block["raw_name"]
                                    st.session_state["viz_section"] = "Detalhamento IA (Full)"
                                    # Set TARGET ID for scrolling
                                    st.session_state["scroll_target_id"] = f"sub_{sub_id_clean}"
                                    st.session_state["do_scroll"] = True
                                    st.rerun()

            except Exception:
                pass



# =========================
# Lógica Principal (Abas)
# =========================

tabs_list = [
    "🚀 Execução", 
    "⏳ Progresso", 
    "📊 Resultados (Painel)", 
    "🎞️ Apresentação", 
    "🛠️ Detalhes Técnicos"
]

is_admin = st.session_state.user_info.get("is_admin", False)
if is_admin:
    tabs_list.append("👥 Usuários")

if st.session_state.get("modo_desenv"):
    tabs_list.append("🧪 Modo Desenv")

all_tabs = st.tabs(tabs_list)

# Unpack simple tabs safely (important for headless tests)
if len(all_tabs) >= 5:
    tab_exec = all_tabs[0]
    tab_prog = all_tabs[1]
    tab_res = all_tabs[2]
    tab_pres = all_tabs[3]
    tab_tec = all_tabs[4]
else:
    # Em ambiente de teste streamlit.tabs pode retornar lista vazia
    tab_exec = tab_prog = tab_res = tab_pres = tab_tec = MagicMock()

idx_next = 5
tab_users = None
if is_admin:
    tab_users = all_tabs[idx_next]
    idx_next += 1

tab_desenv = None
if st.session_state.get("modo_desenv"):
    tab_desenv = all_tabs[idx_next]

# ------------------------------------------------------------------
# ABA 1: EXECUÇÃO
# ------------------------------------------------------------------
with tab_exec:
    st.header("Nova Análise / Apresentação de Crédito")
    
    # Garantir que o CNPJ esteja sincronizado com a sidebar
    if "cnpj_input" not in st.session_state:
        st.session_state.cnpj_input = st.session_state.cnpj or ""
    
    def on_cnpj_change():
        st.session_state.cnpj = "".join(filter(str.isdigit, st.session_state.cnpj_input))
    
    col_cnpj, col_empresa = st.columns(2)
    with col_cnpj:
        st.text_input("CNPJ (somente números)", key="cnpj_input", on_change=on_cnpj_change)
        # O CNPJ real usado pelo sistema será o da session_state.cnpj
        cnpj = st.session_state.cnpj
        if len(cnpj) > 0 and len(cnpj) != 14:
            st.warning("⚠️ CNPJ inválido. Digite 14 dígitos.")
    
    with col_empresa:
        empresa = st.text_input("Razão Social (Opcional)")
        
    tipo_execucao = st.selectbox(
        "Modalidade de Execução",
        [
            "Análise de crédito + Geração de apresentação",
            "Somente análise de crédito",
            "Somente geração de apresentação"
        ]
    )
    
    is_only_presentation = tipo_execucao == "Somente geração de apresentação"
    
    email = st.text_input("E-mail para envio do relatório" + (" (Opcional)" if is_only_presentation else " (Obrigatório)"))
    
    # Verificação de reuso
    usar_antigo = "Não"
    fazer_extracao = "Sim"
    ultimo_job = ultima_execucao(cnpj) if cnpj and len(cnpj) == 14 else None
    
    if cnpj and len(cnpj) == 14:
        if ultimo_job:
            dias = (datetime.now() - ultimo_job).days
            st.success(f"📅 Execução anterior encontrada na base: {ultimo_job.strftime('%d/%m/%Y')} ({dias} dias atrás)")
            usar_antigo = st.radio("Deseja reutilizar os dados anteriores? (Usará os textos já extraídos na execução anterior)", ["Sim", "Não"], index=0 if dias < 30 else 1)
            st.session_state.usar_antigo = usar_antigo
        else:
            st.info("CNPJ não encontrado na base de execuções locais.")
            fazer_extracao = st.radio("Deseja fazer a extração (AWS Textract) dos documentos enviados?", ["Sim", "Não"], index=0)
            
    st.session_state.fazer_extracao = fazer_extracao
    
    # Se optou por reutilizar e não quiser submeter arquivos novos, o upload vira opcional
    arquivos = st.file_uploader("Selecione os documentos (PDF e Imagens)", type=["pdf", "png", "jpg", "jpeg"], accept_multiple_files=True)
    
    # Lógica de validação do botão
    habilita_botao = True
    if not cnpj or len(cnpj) != 14:
        habilita_botao = False
    
    if not is_only_presentation and not email:
        habilita_botao = False
        
    if (not arquivos or len(arquivos) == 0) and usar_antigo == "Não":
        habilita_botao = False

    if st.button("🚀 Iniciar Processamento", type="primary", disabled=not habilita_botao, use_container_width=True):
        st.session_state.run_full = True
        st.session_state.tipo_execucao = tipo_execucao
        _safe_rerun()

# ------------------------------------------------------------------
# LÓGICA DE EXECUÇÃO (Background)
# ------------------------------------------------------------------
# -------------------------------------------------------------------------
# Helper de log visual no terminal (sem depender de Loguru ou Streamlit)
# -------------------------------------------------------------------------
def _tlog(nivel: str, msg: str) -> None:
    """Emite linha de log formatada no stdout (terminal onde o Streamlit roda)."""
    import sys
    now = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️ ", "OK": "✅ ", "ERR": "❌ ", "WARN": "⚠️ ", "STEP": "▶️ ", "DONE": "🏁 ", "SUB": "   └─ "}
    prefix = icons.get(nivel, "   ")
    line = f"[{now}] {prefix}{msg}"
    print(line, flush=True, file=sys.stdout)

def _tlog_sep(titulo: str = "") -> None:
    """Imprime separador visual de etapa."""
    import sys
    bar = "─" * 60
    if titulo:
        print(f"\n{bar}", flush=True, file=sys.stdout)
        print(f"  {titulo}", flush=True, file=sys.stdout)
        print(bar, flush=True, file=sys.stdout)
    else:
        print(bar, flush=True, file=sys.stdout)


def executar_pipeline(cnpj: str, email: str, arquivos, tipo_execucao: str):
    # Force new job path logic for execution
    # Ensure raw ensure_job_dirs (original) creates new folder based on NOW
    # We can use get_current_job_dirs but logically if we are running NEW, it should be NOW.
    # So we trust job_root(cnpj) inside get_current_job_dirs when history_mode is False.
    
    _pasta_exec = Path("execuções") / f"{cnpj}_{datetime.now().strftime('%d%m%Y')}"
    _tlog_sep(f"🚀 PIPELINE INICIADO | CNPJ: {cnpj} | Modalidade: {tipo_execucao}")
    _tlog("INFO", f"Pasta de execução: {_pasta_exec}")

    dirs = get_current_job_dirs(cnpj)
    # Ensure they exist
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)

    _tlog("OK", f"Diretórios criados: {dirs['root']}")
    tracker = ProgressTracker(cnpj)
    logger = init_logger(cnpj)

    # ... Lógica de REUSO (similar ao original) ...
    # (Rest of logic remains mostly same but using 'dirs' which is correct)
    
    if st.session_state.usar_antigo == "Sim" and ultimo_job:
        import shutil
        job_antigo = EXEC_ROOT / f"{cnpj}_{ultimo_job.strftime('%d%m%Y')}"
        _tlog_sep("♻️  REUSO DE DADOS ANTERIORES")
        _tlog("INFO", f"Copiando dados de execução anterior: {job_antigo.name}")

        # 1. Copia Retorno IA (Resultados)
        retorno_antigo = job_antigo / "Retorno_IA"
        retorno_atual = dirs["retorno"]
        if retorno_antigo.exists() and retorno_antigo.resolve() != retorno_atual.resolve():
            _tlog("STEP", "Copiando Retorno_IA (resultados anteriores)...")
            copiados, ignorados = 0, 0
            for item in retorno_antigo.glob("*"):
                if item.is_file():
                    dest = retorno_atual / item.name
                    try:
                        shutil.copy2(item, dest)
                        copiados += 1
                        _tlog("SUB", f"{item.name}")
                    except PermissionError:
                        ignorados += 1
                        _tlog("WARN", f"Arquivo bloqueado, ignorado: {item.name}")
                    except shutil.SameFileError:
                        pass
            _tlog("OK", f"Retorno_IA: {copiados} arquivos copiados, {ignorados} ignorados (bloqueados)")
        else:
            _tlog("INFO", "Retorno_IA: mesma pasta ou inexistente, nada a copiar")

        # 2. Copia Entrada (PDFs para recorte se necessário)
        entrada_antigo = job_antigo / "entrada"
        entrada_atual = dirs["entrada"]
        if entrada_antigo.exists() and entrada_antigo.resolve() != entrada_atual.resolve():
            _tlog("STEP", "Copiando PDFs de entrada anteriores...")
            copiados, ignorados = 0, 0
            for item in entrada_antigo.glob("*.*"):
                if item.is_file() and item.suffix.lower() in [".pdf", ".png", ".jpg", ".jpeg"]:
                    dest = entrada_atual / item.name
                    try:
                        shutil.copy2(item, dest)
                        copiados += 1
                        _tlog("SUB", f"{item.name}")
                    except PermissionError:
                        ignorados += 1
                        _tlog("WARN", f"Arquivo bloqueado, ignorado: {item.name}")
                    except shutil.SameFileError:
                        pass
            _tlog("OK", f"Entrada: {copiados} arquivos copiados, {ignorados} ignorados")
        else:
            _tlog("INFO", "Entrada: mesma pasta ou inexistente, nada a copiar")

    # ... Lógica de EXECUÇÃO NOVA ...
    if st.session_state.run_full and (arquivos or st.session_state.usar_antigo == "Sim"):
        # Se for novo processamento
        if st.session_state.usar_antigo != "Sim":

            # ── ETAPA 0: Upload ─────────────────────────────────────────────
            _tlog_sep("📂 ETAPA 0 — Upload de Arquivos")
            _tlog("INFO", f"{len(arquivos)} arquivo(s) recebido(s) para upload")
            for arq in arquivos:
                with open(dirs["entrada"] / arq.name, "wb") as f:
                    f.write(arq.getbuffer())
                _tlog("SUB", f"Salvo: {arq.name} ({arq.size // 1024} KB)")
            _tlog("OK", f"Todos os arquivos salvos em: {dirs['entrada']}")

            fazer_extracao = st.session_state.get("fazer_extracao", "Sim")

            # ── ETAPA 1: Extração AWS Textract ──────────────────────────────
            _tlog_sep("🔍 ETAPA 1 — Extração de Texto (AWS Textract)")
            if fazer_extracao == "Sim":
                tracker.set_etapa_status("extracao", "processando", 0)
                pdfs_extrair = [a for a in arquivos if Path(a.name).suffix.lower() == ".pdf"]
                _tlog("INFO", f"{len(pdfs_extrair)} PDF(s) para extração")
                for arq in pdfs_extrair:
                    _tlog("STEP", f"Extraindo: {arq.name} ...")
                    try:
                        p = dirs["entrada"] / arq.name
                        t0 = datetime.now()
                        extract_one(str(p), str(dirs["saida"]))
                        elapsed = (datetime.now() - t0).seconds
                        tracker.mark_file_done(arq.name)
                        _tlog("OK", f"  {arq.name} → concluído em {elapsed}s")
                    except Exception as e:
                        tracker.mark_file_error(arq.name, str(e))
                        _tlog("ERR", f"  {arq.name} → ERRO: {e}")
                tracker.set_etapa_status("extracao", "concluido", 100)
                _tlog("DONE", "Extração AWS concluída")
            else:
                tracker.set_etapa_status("extracao", "concluido", 100, detalhe="Pulado (Usuário bypassou extração)")
                _tlog("WARN", "Extração PULADA pelo usuário")

            # ── ETAPA 2: Pré-processamento ──────────────────────────────────
            _tlog_sep("⚙️  ETAPA 2 — Pré-processamento")
            _tlog("STEP", "Preparando manifesto e arquivos de texto...")
            tracker.set_etapa_status("preprocesso", "processando", 0)
            preparar_pre_processamento(cnpj)
            tracker.set_etapa_status("preprocesso", "concluido", 100)
            _tlog("DONE", "Pré-processamento concluído")

            # ── ETAPAS 3 e 4: IA1 e IA2 ────────────────────────────────────
            if "análise" in tipo_execucao.lower() or "ambas" in tipo_execucao.lower() or "analise" in tipo_execucao.lower():
                _tlog_sep("🤖 ETAPA 3 — IA1 (Análise Documental)")
                _tlog("STEP", "Enviando documentos para análise IA1 (OpenAI)...")
                tracker.set_etapa_status("ia1", "processando", 0)
                t0 = datetime.now()
                process_manifest_ia1(cnpj)
                tracker.set_etapa_status("ia1", "concluido", 100)
                _tlog("DONE", f"IA1 concluída em {(datetime.now()-t0).seconds}s")

                _tlog_sep("🤖 ETAPA 4 — IA2 (Síntese e Risco)")
                _tlog("STEP", "Enviando análise para síntese IA2 (OpenAI)...")
                tracker.set_etapa_status("ia2", "processando", 0)
                t0 = datetime.now()
                process_manifest_ia2(cnpj)
                tracker.set_etapa_status("ia2", "concluido", 100)
                _tlog("DONE", f"IA2 concluída em {(datetime.now()-t0).seconds}s")
            else:
                tracker.set_etapa_status("ia1", "concluido", 100, detalhe="Pulado (Somente Apresentação)")
                tracker.set_etapa_status("ia2", "concluido", 100, detalhe="Pulado (Somente Apresentação)")
                _tlog("WARN", "Etapas IA1/IA2 PULADAS (modalidade: Somente Apresentação)")
            
        # -- Fim do Bloco de Processamento Pesado --
        
        # Geração UNIFICADO (Sempre tenta gerar o final se houver dados, independente de ser reuso ou novo)
        if "análise" in tipo_execucao.lower() or "analise" in tipo_execucao.lower() or "ambas" in tipo_execucao.lower():
            _tlog_sep("📄 ETAPA 5 — Consolidação do Relatório Unificado")
            retorno_dir = dirs["retorno"]
            saida_dir = dirs["saida"]
            ia2_md_path = retorno_dir / "relatorio_final.md"
            unificado_md_path = retorno_dir / "relatorio_unificado.md"

            if ia2_md_path.exists():
                _tlog("STEP", "Mesclando blocos IA2 + bloco de risco...")
                ia2_md = ia2_md_path.read_text(encoding="utf-8", errors="ignore")

                import re
                ia2_sem_risco = re.sub(r"(?s)<relatorio_risco>.*?</relatorio_risco>", "", ia2_md).strip()
                risco_m = re.search(r"(?s)<relatorio_risco>(.*?)</relatorio_risco>", ia2_md)
                bloco_risco = risco_m.group(1).strip() if risco_m else ""

                unificado_md = f"CNPJ: {cnpj}\n\n{ia2_sem_risco}\n\n"
                if bloco_risco:
                    unificado_md += f"\n{bloco_risco}"
                    _tlog("SUB", "Bloco de risco encontrado e incluído")

                unificado_md_path.write_text(unificado_md, encoding="utf-8")
                _tlog("STEP", "Gerando relatório HTML final...")
                gerar_relatorio_final(cnpj, datetime.now(), unificado_md, saida_dir)
                _tlog("DONE", f"Relatório salvo: {saida_dir}")
            else:
                _tlog("WARN", f"relatorio_final.md não encontrado em {retorno_dir} — relatório unificado pulado")

        # Geração de APRESENTAÇÃO (Sempre tenta se solicitado)
        if "apresentação" in tipo_execucao.lower() or "ambas" in tipo_execucao.lower() or "apresentacao" in tipo_execucao.lower():
            _tlog_sep("🎞️  ETAPA 6 — Geração de Apresentação")
            tracker.set_etapa_status("apresentacao", "processando", 0)

            # 1. Carrega Variáveis da IA
            _tlog("STEP", "Carregando variáveis do relatório IA...")
            vars_ia = get_presentation_variables(cnpj, dirs["root"])
            _tlog("SUB", f"Empresa: {vars_ia.get('nome_empresa','N/D')} | Risco: {vars_ia.get('risco','N/D')} | Limite: {vars_ia.get('limite','N/D')}")

            # 2. Carrega Configurações de Mapeamento
            configs = load_config()
            _tlog("INFO", f"Tipos mapeados no config_evidencias.json: {list(configs.keys())}")

            slides_config = []

            # 3. Varre arquivos para recortes
            pdf_files = resolve_presentation_pdf_sources(cnpj, dirs, ultimo_job)
            _tlog("INFO", f"{len(pdf_files)} PDF(s) encontrado(s) para processamento de slides")
            _audit_write(logger, AuditEvent(
                ts=datetime.now().isoformat(timespec="seconds"),
                level="INFO",
                step="apresentacao.pdf_sources",
                message=f"Fontes de PDF resolvidas para apresentação: {cnpj}",
                extra={
                    "cnpj": cnpj,
                    "dirs_root": str(dirs["root"]),
                    "history_mode": bool(st.session_state.get("history_mode")),
                    "selected_job_path": str(st.session_state.get("selected_job_path") or ""),
                    "pdf_sources": [str(p) for p in pdf_files],
                }
            ))

            if not pdf_files:
                _tlog("WARN", "Nenhum PDF de origem foi localizado para a apresentação.")
                _audit_write(logger, AuditEvent(
                    ts=datetime.now().isoformat(timespec="seconds"),
                    level="WARNING",
                    step="apresentacao.no_pdf_source",
                    message=f"Nenhum PDF encontrado para apresentação: {cnpj}",
                    extra={
                        "cnpj": cnpj,
                        "entrada_dir": str(dirs["entrada"]),
                        "selected_job_path": str(st.session_state.get("selected_job_path") or ""),
                        "tmp_desenv_pres_exists": (Path("tmp") / "desenv_pres").exists(),
                    }
                ))

            # Importa o classificador
            from classificador_ia import classificar_documento

            for idx, pdf_p in enumerate(pdf_files, 1):
                _tlog_sep(f"  📄 [{idx}/{len(pdf_files)}] {pdf_p.name}")

                # Classifica usando a IA e as primeiras páginas
                _tlog("STEP", f"Classificando via IA: {pdf_p.name}...")
                t0 = datetime.now()
                try:
                    tipo_norm, texto_contexto = classificar_documento(str(pdf_p), audit_logger=logger)
                except TypeError as e:
                    if "audit_logger" not in str(e):
                        raise
                    _tlog("WARN", "classificador_ia carregado sem suporte a audit_logger; usando compatibilidade retroativa.")
                    _audit_write(logger, AuditEvent(
                        ts=datetime.now().isoformat(timespec="seconds"),
                        level="WARNING",
                        step="classificacao_ia.compat",
                        message=f"Fallback de compatibilidade aplicado: {pdf_p.name}",
                        extra={
                            "arquivo": pdf_p.name,
                            "erro": str(e),
                        }
                    ))
                    tipo_norm, texto_contexto = classificar_documento(str(pdf_p))
                _tlog("OK", f"Tipo identificado: '{tipo_norm}' ({(datetime.now()-t0).seconds}s)")

                # Recarrega config caso a IA tenha adicionado um tipo pendente
                configs = load_config()

                if tipo_norm not in configs:
                    _tlog("WARN", f"Tipo '{tipo_norm}' NÃO encontrado no config. Slide ignorado para este arquivo.")
                    continue

                cfg = configs[tipo_norm]
                img_name = f"evidencia_{pdf_p.stem}.png"
                img_path = dirs["saida"] / img_name

                # --- NOVO FLUXO: Múltiplos Slides por Documento ---
                slides_do_doc = cfg.get("slides", [])
                if not slides_do_doc:
                    # Fallback para o formato antigo se a migração falhar ou não houver slides
                    slides_do_doc = [{
                        "id": f"{pdf_p.stem}_fallback",
                        "modo": cfg.get("modo", "ancora"),
                        "ancora": cfg.get("ancora", ""),
                        "ancora_inicio": cfg.get("ancora_inicio", ""),
                        "ancora_fim": cfg.get("ancora_fim", ""),
                        "coordenadas": cfg.get("coordenadas", ""),
                        "pagina": cfg.get("pagina", 1),
                        "cabecalho": cfg.get("cabecalho", "Destaque"),
                        "descricao": cfg.get("descricao", "")
                    }]

                for s_idx, s_cfg in enumerate(slides_do_doc):
                    img_name = f"evidencia_{pdf_p.stem}_s{s_idx}.png"
                    img_path = dirs["saida"] / img_name
                    
                    success = False
                    crop_result = {"success": False}
                    modo = s_cfg.get("modo", "ancora")
                    
                    _tlog("STEP", f"Processando Slide {s_idx+1}: {s_cfg.get('cabecalho', 'Sem título')} [Modo: {modo}]")

                    if modo == "ancora":
                        ancora_ins = s_cfg.get("ancora", "")
                        ini_ctx = s_cfg.get("ancora_inicio", "")
                        fim_ctx = s_cfg.get("ancora_fim", "")
                        pag = s_cfg.get("pagina", 1) - 1

                        start_marker = ancora_ins or ini_ctx
                        if start_marker and fim_ctx:
                            _tlog("STEP", f"Recorte determinístico por marcadores: '{start_marker}' até '{fim_ctx}' (pág {pag+1})...")
                            from utils.pdf_cropper import crop_pdf_by_section_markers
                            crop_result = crop_pdf_by_section_markers(
                                str(pdf_p),
                                start_text=start_marker,
                                end_text=fim_ctx,
                                page_num=pag,
                                out_path=str(img_path),
                            )
                            success = crop_result.get("success", False)
                            if success:
                                _tlog("OK", "Recorte por marcadores aplicado com sucesso")
                            else:
                                _tlog("WARN", f"Recorte por marcadores falhou: {crop_result.get('error')}")

                        if not success and ancora_ins:
                            # Fallback para Agente de IA (Vision)
                            instrucao_ia = ancora_ins
                            if ini_ctx or fim_ctx:
                                contexto_extra = f" (Busque o trecho entre '{ini_ctx}' e '{fim_ctx}')"
                                instrucao_ia += contexto_extra

                            _tlog("STEP", f"Agente IA → Buscando: '{instrucao_ia}' (pág {pag+1})...")
                            from utils.pdf_cropper import crop_pdf_by_ia_agent
                            crop_result = crop_pdf_by_ia_agent(str(pdf_p), instrucao_ia, page_num=pag, out_path=str(img_path), audit_logger=logger)
                            success = crop_result.get("success", False)
                            if success:
                                _tlog("OK", f"Agente IA identificou trecho com sucesso")
                            else:
                                _tlog("WARN", f"Agente IA falhou: {crop_result.get('error')}")
                        else:
                            if not start_marker:
                                _tlog("WARN", "Modo 'ancora' selecionado mas sem marcadores textuais ou instrução de âncora")

                    elif modo == "ancora_simples":
                        # RESTAURADO: Âncora textual simples
                        termo = s_cfg.get("ancora", "")
                        if termo:
                            _tlog("STEP", f"Buscando Âncora Simples: '{termo}'...")
                            from utils.pdf_cropper import crop_pdf_by_text
                            # Padding padrão para âncoras simples: (esq, topo, dir, base)
                            crop_result = crop_pdf_by_text(str(pdf_p), termo, padding=(50, 50, 50, 50), out_path=str(img_path))
                            success = crop_result.get("success", False)
                            if success:
                                _tlog("OK", f"Âncora '{termo}' localizada na pág {crop_result.get('page')}")
                            else:
                                _tlog("WARN", f"Âncora '{termo}' não encontrada.")
                        else:
                            _tlog("WARN", "Modo 'ancora_simples' sem termo definido.")

                    elif modo == "ancora_range":
                        inicio = s_cfg.get("ancora_inicio", "")
                        fim    = s_cfg.get("ancora_fim", "")
                        if inicio:
                            from utils.pdf_cropper import crop_pdf_by_text_range
                            crop_result = crop_pdf_by_text_range(str(pdf_p), inicio, fim, margin=20, out_path=str(img_path))
                            success = crop_result.get("success", False)
                            if success:
                                _tlog("OK", f"Âncora range detectada na pág {crop_result.get('page')}")
                            else:
                                _tlog("WARN", f"Range não localizado: {crop_result.get('error')}")
                    
                    elif modo == "coordenadas":
                        pag = s_cfg.get("pagina", 1) - 1
                        rect_str = s_cfg.get("coordenadas", "0,0,595,300")
                        try:
                            from utils.pdf_cropper import crop_pdf_to_image
                            rect_tuple = tuple(map(float, rect_str.replace(" ", "").split(",")))
                            success = crop_pdf_to_image(str(pdf_p), pag, rect_tuple, str(img_path))
                            crop_result = {"success": success, "page": pag+1, "rect": rect_tuple}
                        except Exception as e:
                            _tlog("ERR", f"Erro no crop por coordenadas: {e}")

                    # Fallback para coordenadas fixas se âncoras falharem
                    if not success and s_cfg.get("coordenadas"):
                        pag = s_cfg.get("pagina", 1) - 1
                        rect_str = s_cfg.get("coordenadas")
                        _tlog("STEP", "Aplicando fallback para coordenadas fixas...")
                        try:
                            from utils.pdf_cropper import crop_pdf_to_image
                            rect_tuple = tuple(map(float, rect_str.replace(" ", "").split(",")))
                            success = crop_pdf_to_image(str(pdf_p), pag, rect_tuple, str(img_path))
                            crop_result = {"success": success, "fallback": True, "page": pag+1, "rect": rect_tuple}
                        except: pass

                    # LOG DE AUDITORIA
                    _audit_write(logger, AuditEvent(
                        ts=datetime.now().isoformat(timespec="seconds"),
                        level="INFO" if success else "WARNING",
                        step="apresentacao.crop",
                        message=f"Recorte slide {s_idx}: {pdf_p.name}",
                        extra={"arquivo": pdf_p.name, "modo": modo, "resultado": "SUCESSO" if success else "FALHA", "detalhes": crop_result}
                    ))

                    # Injeção de variáveis (Headers e Descrição)
                    title_final = inject_variables(s_cfg.get("cabecalho", "Destaque"), vars_ia)
                    desc_final = inject_variables(s_cfg.get("descricao", ""), vars_ia)
                    
                    slides_config.append({
                        "id": f"slide_{pdf_p.stem}_{s_idx}",
                        "title": title_final,
                        "description": desc_final,
                        "image_path": str(img_path) if success else "",
                        "pdf_source": str(pdf_p),
                        "page_orig": s_cfg.get("pagina", 1)
                    })
                    _tlog("SUB", f"Slide: '{title_final}' | imagem: {'✅' if success else '❌'}")

            if not slides_config:
                _tlog("WARN", "Nenhum slide configurado. Adicionando slide placeholder.")
                slides_config.append({
                    "id": "slide_vazio",
                    "title": "Apresentação de Evidências",
                    "description": "Nenhuma evidência automática configurada ou nenhum PDF de origem disponível para os documentos enviados.",
                    "image_path": "",
                    "pdf_source": ""
                })

            # Grava estado das páginas em JSON para edição posterior no frontend
            config_slides_path = dirs["saida"] / "slides_config.json"
            import json
            config_slides_path.write_text(json.dumps(slides_config, indent=4, ensure_ascii=False), encoding="utf-8")
            _tlog("SUB", f"slides_config.json gravado com {len(slides_config)} slide(s)")

            out_pptx = dirs["saida"] / f"Apresentacao_{cnpj}.pptx"
            out_pdf  = dirs["saida"] / f"Apresentacao_{cnpj}.pdf"

            _tlog("STEP", "Gerando arquivo PPTX...")
            criar_apresentacao_evidencias(cnpj, slides_config, str(out_pptx))
            _tlog("OK", f"PPTX salvo: {out_pptx.name}")

            _tlog("STEP", "Gerando arquivo PDF da apresentação...")
            criar_apresentacao_pdf(cnpj, slides_config, str(out_pdf))
            _tlog("OK", f"PDF salvo: {out_pdf.name}")

            tracker.set_etapa_status("apresentacao", "concluido", 100)
            _tlog("DONE", "Apresentação gerada com sucesso")

        # Comentado para preservar PDFs originais para etapa futura de recorte (Req 7.1)
        # if st.session_state.usar_antigo != "Sim":
        #     limpar_entrada(cnpj)
            
        
        # ── ETAPA 7: Envio por E-mail ───────────────────────────────────────
        if "análise" in tipo_execucao.lower() or "analise" in tipo_execucao.lower() or "ambas" in tipo_execucao.lower():
            _tlog_sep("📧 ETAPA 7 — Envio por E-mail")
            _tlog("STEP", f"Enviando relatório para: {email}")
            tracker.set_etapa_status("envio", "processando", 0)
            res = enviar_relatorio_final(cnpj, email, exec_root=dirs["root"])
            tracker.set_etapa_status("envio", "concluido" if res["ok"] else "erro", 100)
            if res["ok"]:
                _tlog("DONE", f"E-mail enviado com sucesso para {email}")
                st.toast("Relatório enviado por e-mail!", icon="📧")
            else:
                _tlog("ERR", f"Falha no envio: {res.get('detail', 'Desconhecido')}")
                st.error(f"Erro no envio: {res['detail']}")
        else:
            tracker.set_etapa_status("envio", "concluido", 100, detalhe="Pulado (Somente Apresentação)")
            _tlog("WARN", "Envio de e-mail PULADO (modalidade: Somente Apresentação)")

        _tlog_sep("🏆 PIPELINE FINALIZADO")
        _tlog("DONE", f"Execução completa para CNPJ {cnpj} | Saída: {dirs['saida']}")


if st.session_state.run_full:
    tipo_exec = st.session_state.get("tipo_execucao", "Análise de crédito + Geração de apresentação")
    with st.spinner("Processando... Acompanhe na aba Progresso."):
        executar_pipeline(cnpj, email, arquivos, tipo_exec)
    st.session_state.run_full = False
    _safe_rerun()


# ------------------------------------------------------------------
# ABA 2: PROGRESSO
# ------------------------------------------------------------------
with tab_prog:
    st.header("Status do Processamento")
    if cnpj and len(cnpj) == 14:
        # Use get_current_job_dirs to find logs
        dirs = get_current_job_dirs(cnpj)
        
        if dirs["logs"].exists():
            try:
                prog_path = dirs["logs"] / "progress.json"
                if prog_path.exists():
                    prog_data = json.loads(prog_path.read_text(encoding="utf-8"))
                    stages = ["extracao", "preprocesso", "ia1", "ia2", "apresentacao", "envio"]
                    cols = st.columns(len(stages))
                    for i, stage in enumerate(stages):
                        s_info = prog_data.get("etapas", {}).get(stage, {})
                        status = s_info.get("status", "pending")
                        icon = "✅" if status == "concluido" else "⏳" if status == "processando" else "⏹️"
                        cols[i].metric(label=stage.upper(), value=status, delta=icon)
                    
                    st.write("---")
                    st.subheader("Arquivos")
                    if "arquivos" in prog_data:
                        df_prog = prog_data["arquivos"]
                        if isinstance(df_prog, list) and len(df_prog) > 0:
                           st.dataframe(df_prog, use_container_width=True)
                        else:
                            st.write("Nenhum arquivo processado ainda.")
                else:
                    st.info("Arquivo de progresso não encontrado (talvez execução antiga).")

            except Exception as e:
                st.error(f"Erro ao ler progresso: {e}")
        else:
            st.info("Aguardando início do processamento...")
    else:
        st.info("Informe um CNPJ para ver o progresso.")


# ------------------------------------------------------------------
# ABA 3: RESULTADOS (PAINEL DE DECISÃO) - UPDATED!
# ------------------------------------------------------------------
with tab_res:
    if not cnpj or len(cnpj) != 14:
        st.warning("Selecione um cliente para visualizar os resultados.")
    else:
        dirs = get_current_job_dirs(cnpj)
        
        if st.session_state.get("history_mode"):
            st.markdown(f"**📂 Visualizando Histórico:** `{dirs['root'].name}`")
        
        # Caminhos principais
        unificado_path = dirs["retorno"] / "relatorio_unificado.md"
        # Agora buscamos o HTML principal gerado
        html_final_path = None
        # Tenta achar o HTML gerado com nome padronizado (AnaliseIA...)
        for f in dirs["retorno"].glob("AnaliseIA_*.html"):
            html_final_path = f
            break
        
        # Fallback se não achou com pattern, tenta relatorio_final.html se existir (legado ou fallback)
        if not html_final_path:
             if (dirs["retorno"] / "relatorio_final.html").exists():
                 html_final_path = dirs["retorno"] / "relatorio_final.html"

        retorno_dir = dirs["retorno"]
        
        # Tenta carregar dados processados (Resumo e Arquivos)
        if unificado_path.exists():
            # 1. Carrega dados do Relatório Final (Unificado)
            texto_relatorio = unificado_path.read_text(encoding="utf-8", errors="ignore")
            resumo = extract_executive_summary(texto_relatorio)
            
            # 2. Parse Blocs for Cards (NEW LOGIC)
            document_blocks = parse_unified_report(texto_relatorio)
            
            # Fallback: if 0 blocks found (maybe parsing failed), check file dump (Legacy)
            if not document_blocks and retorno_dir.exists():
                 # ... (Legacy logic for compatibility if needed, but let's trust unified md first)
                 pass

            # Ordena por nome limpo
            # document_blocks.sort(key=lambda x: x["clean_name"]) # Keep order found in file usually better? NO, existing code sorted.
            # Let's keep original file order for story telling, or sort alphabetically? 
            # Report usually has logical order (1, 2, 3...). Let's keep file order!

            # ---------------------------------------------------------------------
            # INTEGRAÇÃO DE MÉTRICAS (OVERRIDE)
            # Procura nos blocos se existem tags de <risco>, <raroc>, etc.
            # Se encontrar, atualiza o dicionário 'resumo' que alimenta o Cockpit.
            # ---------------------------------------------------------------------
            for doc in document_blocks:
                m = doc.get("meta", {})
                if m.get("risco") or m.get("raroc") or m.get("limite"):
                    if m.get("risco"): resumo["risco"] = m["risco"]
                    if m.get("raroc"): resumo["raroc"] = m["raroc"]
                    if m.get("limite"): resumo["limite"] = m["limite"]
                    if m.get("conclusao"): resumo["decisao"] = m["conclusao"]
                    
                    # Justificativas
                    if m.get("calculo_raroc"): resumo["calculo_raroc"] = m["calculo_raroc"]
                    if m.get("justificativa_risco"): resumo["justificativa_risco"] = m["justificativa_risco"]
                    if m.get("justificativa_limite"): resumo["justificativa_limite"] = m["justificativa_limite"]
                    
                    # Assume que o último bloco com essas infos é o valedor (ou o único)


            # ---------------------------------------------------------------------
            # INJEÇÃO CARD CONCLUSÃO
            # O usuário pediu para que a conclusão saísse do cockpit e virasse um card.
            # ---------------------------------------------------------------------
            if resumo.get("decisao"):
                # Cria um bloco sintético para a conclusão ser renderizada junto com os outros
                bloco_conclusao = {
                    "raw_name": "bloco_conclusao_final",
                    "clean_name": "CONCLUSÃO FINAL",
                    "meta": {
                        "tipo_arquivo": "DESTAQUE",
                        "cor_card": "azul" # Cor de destaque
                    },
                    "content_clean": resumo["decisao"]
                }
                # Adiciona no início ou fim? Vamos colocar no início pata destaque ou fim?
                # Usuário disse "dentro do bloco Blocos Analisados". Vou inserir na primeira posição.
                document_blocks.insert(0, bloco_conclusao)


            # ==========================================
            # HEADER DE AÇÕES
            # ==========================================
            col_actions = st.columns([6, 2, 2, 2])
            with col_actions[0]:
                st.subheader(f"Analise de Crédito: {empresa if empresa else cnpj}")
            with col_actions[1]:
                if html_final_path and html_final_path.exists():
                    with open(html_final_path, "rb") as f:
                        st.download_button("📥 Baixar Relatório", f, file_name=html_final_path.name, mime="text/html")
            with col_actions[2]:
                if st.button("📧 Reenviar E-mail"):
                   # Força regeneração do HTML para garantir que correções do parser sejam aplicadas
                   st.toast("Regerando relatório HTML...", icon="⚙️")
                   gerar_relatorio_final(cnpj, datetime.now(), texto_relatorio, dirs["retorno"])
                   
                   res = enviar_relatorio_final(cnpj, email, exec_root=dirs["root"])
                   if res["ok"]: st.toast("Reenviado!", icon="✅")
                   else: st.toast(f"Erro: {res.get('detail', 'Desconhecido')}", icon="❌")
            
            st.divider()

            # ==========================================
            # 1. COCKPIT VISUAL (MÉTRICAS) - REFACTORED (3 COLS)
            # ==========================================
            c1, c2, c3 = st.columns(3)
            # Risco
            risco_val = resumo.get("risco", "N/D")
            color_risco = "red" if risco_val == "Alto" else "orange" if risco_val == "Médio" else "green"
            
            with c1:
                st.markdown(f"<div class='metric-card'><div class='metric-label'>RISCO</div><div class='metric-value' style='color:{color_risco}'>{risco_val}</div></div>", unsafe_allow_html=True)
                if st.button("Ver Detalhe", key="btn_risco", use_container_width=True):
                    st.session_state["viz_section"] = "Resumo Executivo"
                    st.session_state["resumo_focus"] = "justificativa_risco"
                    st.session_state["scroll_target_id"] = "anchor_risco"
                    st.session_state["do_scroll"] = True
                    st.rerun()

            # Limite (Agora na C2)
            with c2:
                st.markdown(f"<div class='metric-card'><div class='metric-label'>LIMITE SUGERIDO</div><div class='metric-value'>{resumo.get('limite', 'N/D')}</div></div>", unsafe_allow_html=True)
                if st.button("Ver Detalhe", key="btn_limite", use_container_width=True):
                    st.session_state["viz_section"] = "Resumo Executivo"
                    st.session_state["resumo_focus"] = "justificativa_limite"
                    st.session_state["scroll_target_id"] = "anchor_limite"
                    st.session_state["do_scroll"] = True
                    st.rerun()

            # KPI (RAROC) - Agora na C3
            with c3:
                st.markdown(f"<div class='metric-card'><div class='metric-label'>RAROC</div><div class='metric-value' style='font-size:18px'>{resumo.get('raroc','-')}</div></div>", unsafe_allow_html=True)
                if st.button("Ver Métricas", key="btn_raroc", use_container_width=True):
                    st.session_state["viz_section"] = "Resumo Executivo"
                    st.session_state["resumo_focus"] = "calculo_raroc"
                    st.session_state["scroll_target_id"] = "anchor_raroc"
                    st.session_state["do_scroll"] = True
                    st.rerun()

            st.write("")
            
            # ==========================================
            # 2. COCKPIT VISUAL (CARDS DE DOCUMENTOS)
            # ==========================================
            if document_blocks:
                st.markdown("### 📂 Blocos Analisados")
                
                # ... CSS ...
                st.markdown("""
                <style>
                .doc-card {
                    padding: 15px;
                    border-radius: 8px;
                    color: white;
                    margin-bottom: 10px;
                    text-align: center;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    transition: transform 0.2s;
                    min-height: 80px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                }
                .doc-card:hover {
                    transform: translateY(-2px);
                }
                .doc-type {
                    font-size: 0.75rem;
                    text-transform: uppercase;
                    opacity: 0.9;
                    margin-bottom: 4px;
                }
                .doc-name {
                    font-size: 0.95rem;
                    font-weight: bold;
                    line-height: 1.2;
                }
                </style>
                """, unsafe_allow_html=True)

                # Grid Layout Customizado
                # Vamos renderizar 4 cards por linha
                cols_per_row = 4
                rows = [document_blocks[i:i + cols_per_row] for i in range(0, len(document_blocks), cols_per_row)]
                
                for row_docs in rows:
                    cols = st.columns(cols_per_row)
                    for idx, doc in enumerate(row_docs):
                        # Pega cor do card
                        bg_color = doc["meta"].get("cor_card", "#6c757d") 
                        
                        # Mapping de cores básicas
                        color_map = {
                            "azul": "#007bff", "blue": "#007bff",
                            "verde": "#28a745", "green": "#28a745",
                            "vermelho": "#dc3545", "red": "#dc3545",
                            "amarelo": "#ffc107", "yellow": "#ffc107",
                            "laranja": "#fd7e14", "orange": "#fd7e14",
                            "roxo": "#6f42c1", "purple": "#6f42c1",
                            "cinza": "#6c757d", "grey": "#6c757d"
                        }
                        final_color = color_map.get(bg_color.lower(), bg_color)
                        
                        nome_doc = doc['clean_name']
                        tipo_doc = doc["meta"].get("tipo_arquivo", "BLOCO")

                        with cols[idx]:
                            # Renderiza visual do card
                            st.markdown(f"""
                            <div class='doc-card' style='background-color: {final_color};'>
                                <div class='doc-type'>{tipo_doc}</div>
                                <div class='doc-name' title='{nome_doc}'>{nome_doc}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Botão para selecionar
                            # Adding idx to key to ensure uniqueness even if raw_name is duplicated (though it shouldn't be ideally)
                            if st.button(f"Ver Detalhes", key=f"btn_{doc['raw_name']}_{idx}", use_container_width=True):
                                st.session_state["selected_doc"] = doc["raw_name"]
                                st.session_state["viz_section"] = "Detalhamento IA (Full)"
                                # Define target ID for block
                                blk_id_clean = re.sub(r"[^a-zA-Z0-9]", "_", doc['clean_name']).lower()
                                st.session_state["scroll_target_id"] = f"blk_{blk_id_clean}"
                                st.session_state["do_scroll"] = True
                                st.rerun()

            st.divider()

            # ==========================================
            # 3. NAVEGAÇÃO E DETALHAMENTO
            # ==========================================
            # Anchor tag for scrolling
            st.markdown("<div id='start_details'></div>", unsafe_allow_html=True)
            

            
            # Check scroll request
            if st.session_state.get("do_scroll"):
                target_id = st.session_state.get("scroll_target_id", "start_details")
                # Reset specific target after use, fallback to start_details next time
                st.session_state["scroll_target_id"] = None
                st.session_state["do_scroll"] = False # Consume flag
                
                timestamp = int(time.time() * 1000)
                st.components.v1.html(
                    f"""
                    <script>
                        // {timestamp}
                        setTimeout(function() {{
                            var target = window.parent.document.getElementById('{target_id}');
                            if (!target) {{
                                target = window.parent.document.getElementById('start_details');
                            }}
                            
                            if (target) {{
                                var headerOffset = 150;
                                var elementPosition = target.getBoundingClientRect().top;
                                var offsetPosition = elementPosition + window.parent.scrollY - headerOffset;
                                
                                window.parent.scrollTo({{
                                    top: offsetPosition,
                                    behavior: "smooth"
                                }});
                            }}
                        }}, 800);
                    </script>
                    """,
                    height=0,
                    width=0
                )

            col_nav, col_content = st.columns([1, 3])
            
            with col_nav:
                st.markdown("### Navegação")
                
                
                # Mapa de Seções para Index
                sections = ["Detalhamento IA (Full)", "Resumo Executivo"]
                
                # Tenta recuperar o alvo do drill-down
                default_idx = 0
                target = st.session_state.get("viz_section", None)
                if target in sections:
                    default_idx = sections.index(target)
                    # Não limpa viz_section aqui pois o script roda top-down e o radio usa o index.
                    # Mas se o radio mudar, o session_state atualiza.
                    # Se limpamos aqui, o rerun funciona?
                    # Melhor só usar setando o index e deixar o radio controlar o state.
                
                # Se clicou no radio manualmente, limpa o foco!
                antigo_vis = st.session_state.get("last_viz_mode")
                modo_vis = st.radio("Seção:", sections, index=default_idx)
                
                # Detecta mudança manual de aba para limpar foco
                if modo_vis != antigo_vis:
                     st.session_state["resumo_focus"] = None
                     st.session_state["last_viz_mode"] = modo_vis
                
                if modo_vis == "Detalhamento IA (Full)":
                    st.markdown("---")
                    st.markdown("**Filtro por Tipo**")
                    all_types = sorted(list(set(d["meta"].get("tipo_arquivo", "Geral") for d in document_blocks))) or ["Todos"]
                    filtro_tipo = st.selectbox("Selecione:", ["Todos"] + all_types)

            with col_content:
                if modo_vis == "Resumo Executivo":
                    st.markdown("### 📊 Relatório de Risco Quantitativo")
                    
                    # Checa se existe foco específico
                    foco = st.session_state.get("resumo_focus")
                    
                    # Botão para limpar foco se houver algum
                    if foco:
                        if st.button("Mostrar Todos"):
                            st.session_state["resumo_focus"] = None
                            st.rerun()

                    # Show specific justifications if available, otherwise fallback to Regex
                    has_details = False
                    
                    # SECTION: RISCO
                    if (not foco or foco == "justificativa_risco") and resumo.get("justificativa_risco"):
                        st.markdown("<div id='anchor_risco'></div>", unsafe_allow_html=True)
                        st.markdown(f"#### Risco: {resumo.get('risco', 'N/D')}")
                        st.write(sanitize_report_text(resumo["justificativa_risco"]))
                        has_details = True
                        st.divider()

                    # SECTION: LIMITE
                    if (not foco or foco == "justificativa_limite") and resumo.get("justificativa_limite"):
                        st.markdown("<div id='anchor_limite'></div>", unsafe_allow_html=True)
                        st.markdown(f"#### Limite Sugerido: {resumo.get('limite', 'N/D')}")
                        st.write(sanitize_report_text(resumo["justificativa_limite"]))
                        has_details = True
                        st.divider()

                    # SECTION: RAROC
                    if (not foco or foco == "calculo_raroc") and resumo.get("calculo_raroc"):
                        st.markdown("<div id='anchor_raroc'></div>", unsafe_allow_html=True)
                        st.markdown(f"#### Memória de Cálculo RAROC")
                        st.info(sanitize_report_text(resumo["calculo_raroc"]))
                        has_details = True
                        st.divider()
                        
                    # SECTION: DECISAO (Sempre mostra se não tiver foco OU se foco for geral?)
                    # Usuário não especificou, mas geralmente decisão é bom ver sempre. 
                    # Mas "Restringir bloco" implica esconder o resto.
                    # Se foco definido, esconder Decisão Final? 
                    # O usuário disse: "use o detalhe somente o conteudo da variavel vinculada somente"
                    # Então se tiver foco, não mostra decisão final a não ser que o foco SEJA decisão.
                    
                    if (not foco or foco == "decisao") and resumo.get("decisao"):
                        st.markdown("<div id='anchor_decisao'></div>", unsafe_allow_html=True)
                        st.markdown("#### Conclusão Final")
                        st.success(resumo["decisao"])
                        has_details = True
                    
                    if not has_details and not foco:
                         st.info("Este painel foca nos indicadores de Risco (RAROC, PD, LGD) e Conclusão.")
                         # Tenta extrair apenas a seção de Risco do unificado (Legacy Fallback)
                         import re
                         m_risco = re.search(r"(?i)# Relatório Quantitativo de Risco(.*?)(?:$|#)", texto_relatorio, re.DOTALL)
                         if m_risco:
                            st.markdown(sanitize_report_text(m_risco.group(1)))
                         else:
                            st.markdown(sanitize_report_text(texto_relatorio[:2000])) # Fallback

                elif modo_vis == "Detalhamento IA (Full)":
                    st.markdown("### 🤖 Detalhamento por Bloco")
                    
                    # Filtra blocos
                    blocos_visiveis = document_blocks
                    if filtro_tipo != "Todos":
                        blocos_visiveis = [b for b in document_blocks if b["meta"].get("tipo_arquivo") == filtro_tipo]
                    
                    if not blocos_visiveis:
                        st.info("Nenhum bloco encontrado com este filtro.")
                    
                    for doc in blocos_visiveis:
                        # Auto-expandir se foi selecionado no card
                        sel_doc = st.session_state.get("selected_doc", "")
                        is_expanded = (sel_doc == doc["raw_name"])
                        
                        icone = "📄"
                        doc_type = doc["meta"].get("tipo_arquivo", "DOC")
                        titulo_exp = f"{icone} {doc['clean_name']}  [{doc_type}]"
                        
                        # INJECT ANCHOR FOR BLOCK
                        blk_id_clean = re.sub(r"[^a-zA-Z0-9]", "_", doc['clean_name']).lower()
                        st.markdown(f"<div id='blk_{blk_id_clean}'></div>", unsafe_allow_html=True)

                        with st.expander(titulo_exp, expanded=is_expanded):
                            # CUSTOM RENDERING FOR HIGHLIGHTS & SUBITEMS
                            
                            full_text = doc["content_clean"]
                            
                            # Split by "Subitem =>"
                            # Pattern: (Subitem => .*?)(?=\nSubitem =>|\Z)
                            # But we also have content BEFORE the first subitem.
                            
                            parts = re.split(r"(Subitem\s*=>\s*[^\n]+)", full_text, flags=re.IGNORECASE)
                            # Result: [Pre-content, Header1, Content1, Header2, Content2...]
                            
                            # Render Pre-content (Header of the block)
                            if parts:
                                pre_content = parts[0].strip()
                                if pre_content:
                                    st.info(pre_content)

                            # Iterate pairs (Header, Content)
                            # We start from index 1.
                            for i in range(1, len(parts), 2):
                                sub_header = parts[i].strip() # "Subitem => 1_1_Name"
                                sub_content = parts[i+1].strip() if i+1 < len(parts) else ""
                                
                                # Extract pure name for ID generation
                                # Remove "Subitem =>" prefix matches
                                raw_name = re.sub(r"Subitem\s*=>\s*", "", sub_header, flags=re.IGNORECASE).strip()
                                
                                # Generate ID
                                # Use simple regex to match sidebar logic
                                sub_id_clean = re.sub(r"[^a-zA-Z0-9]", "_", raw_name).lower()
                                anchor_id = f"sub_{sub_id_clean}"

                                # Inject Anchor
                                st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
                                
                                # Render Header & Content in specific color card
                                # Use st.info (blue) as requested for "highlight"
                                # We combine header and content for a unified look
                                st.info(f"**{sub_header}**\n\n{sub_content}")
                                st.divider()
                            
        else:
             st.info("ℹ️ Nenhum relatório processado encontrado nesta execução.")


# ------------------------------------------------------------------
# ABA 4 (NOVA): APRESENTAÇÃO
# ------------------------------------------------------------------
with tab_pres:
    st.header("🎞️ Evidências e Apresentações")
    st.markdown("Interface para geração, mapeamento manual e download das apresentações geradas (.pptx e .pdf).")
    if st.session_state.pop("presentation_generated_notice", False):
        st.success("Apresentação gerada nesta execução. Valide os slides abaixo e ajuste se necessário.")
    
    if cnpj:
        dirs = get_current_job_dirs(cnpj)
        out_pptx = dirs["saida"] / f"Apresentacao_{cnpj}.pptx"
        out_pdf = dirs["saida"] / f"Apresentacao_{cnpj}.pdf"
        
        if out_pptx.exists() or out_pdf.exists():
            st.success("Apresentações disponíveis para download!")
            col1, col2 = st.columns(2)
            
            with col1:
                if out_pptx.exists():
                    with open(out_pptx, "rb") as f:
                        st.download_button(
                            label="📥 Baixar PowerPoint (PPTX)",
                            data=f,
                            file_name=out_pptx.name,
                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            use_container_width=True
                        )
            
            with col2:
                if out_pdf.exists():
                    with open(out_pdf, "rb") as f:
                        st.download_button(
                            label="📥 Baixar Documento (PDF)",
                            data=f,
                            file_name=out_pdf.name,
                            mime="application/pdf",
                            use_container_width=True
                        )
        else:
            st.info("Apresentação ainda não foi gerada para este cliente/execução.")
            
        config_slides_path = dirs["saida"] / "slides_config.json"
        
        if config_slides_path.exists():
            apply_presentation_premium_css()
            st.divider()
            section_header("Editor de Slides", tag="APRESENTAÇÃO", icon="🎨")
            instruction_banner("Abaixo estão os slides gerados. Edite o cabeçalho, a descrição ou realize o upload de uma nova imagem. As alterações regerarão o PPTX final.")
            
            try:
                import json
                slides = json.loads(config_slides_path.read_text(encoding="utf-8"))
                
                if not slides:
                    st.warning("Nenhum slide foi listado nesta execução.")
                else:
                    # Seletor Central de Slides
                    col_sel, col_del_btn = st.columns([4, 1])
                    with col_sel:
                        i = st.selectbox(
                            "Selecione um Slide para Editar / Pré-visualizar",
                            range(len(slides)),
                            format_func=lambda x: f"Slide {x+1}: {slides[x].get('title', 'Sem título')[:60]}"
                        )
                    with col_del_btn:
                        st.write("") # alinhamento visual com selectbox
                        st.write("")
                        if st.button("🗑️ Excluir", key="btn_del_slide_gerado", use_container_width=True, type="secondary", help="Exclui o slide atual e regera a apresentação"):
                            slides.pop(i)
                            config_slides_path.write_text(json.dumps(slides, indent=4, ensure_ascii=False), encoding="utf-8")
                            with st.spinner("Regerando PPTX sem este slide..."):
                                criar_apresentacao_evidencias(cnpj, slides, str(out_pptx))
                                criar_apresentacao_pdf(cnpj, slides, str(out_pdf))
                            st.success("Slide Excluído!")
                            time.sleep(1)
                            st.rerun()

                    if slides:
                        slide = slides[i]
                        st.markdown("---")
                        
                        with st.container():
                            has_img = bool(slide.get("image_path") and Path(slide["image_path"]).exists())
                            slide_card_header(i + 1, slide.get("title", "Sem título"), has_img)
                            c_img, c_form = st.columns([1, 1])
                            
                            with c_img:
                                st.markdown("**🖼️ Prévia da Imagem da Evidência**")
                                if slide.get("image_path") and Path(slide["image_path"]).exists():
                                    st.image(slide["image_path"], use_container_width=True)
                                else:
                                    st.warning("Nenhuma imagem de evidência atrelada a este slide.")
                                
                                # Fonte do PDF (para Recorte Futuro)
                                src = slide.get("pdf_source")
                                if src and Path(src).exists():
                                    st.caption(f"Trilho de origem: `{Path(src).name}`")
                                    
                                    with st.expander("✂️ Ferramenta Visual de Recorte (PDF Original)"):
                                        crop_tool_header()
                                        try:
                                            import fitz
                                            from PIL import Image
                                            doc_slide = fitz.open(src)
                                            tot_pags = len(doc_slide)
                                            st.caption(f"📄 O PDF possui **{tot_pags} página(s)**.")
                                            
                                            pag_sel = st.number_input("Página para recorte", min_value=1, max_value=tot_pags, value=1, key=f"pag_crop_{i}")
                                            
                                            page_slide = doc_slide[pag_sel - 1]
                                            pix_slide = page_slide.get_pixmap(dpi=72)
                                            img_slide = Image.frombytes("RGB", [pix_slide.width, pix_slide.height], pix_slide.samples)
                                            
                                            if st_cropper:
                                                st.caption("🖱️ Clique e arraste para definir a área de evidência:")
                                                rect_slide = st_cropper(img_slide, realtime_update=True, box_color='#00D1FF', aspect_ratio=None, return_type='box', key=f"crop_slide_ui_{i}_{pag_sel}")
                                                if rect_slide:
                                                    x0_c, y0_c = int(rect_slide['left']), int(rect_slide['top'])
                                                    x1_c, y1_c = x0_c + int(rect_slide['width']), y0_c + int(rect_slide['height'])
                                                    coords_display(x0_c, y0_c, x1_c, y1_c)
                                                    
                                                    if st.button("✂️ Confirmar e Salvar Recorte", key=f"btn_crop_slide_{i}", type="primary", use_container_width=True):
                                                        from utils.pdf_cropper import crop_pdf_to_image
                                                        img_path_novo = dirs["saida"] / f"crop_custom_{i}_{Path(src).stem}.png"
                                                        if crop_pdf_to_image(src, pag_sel - 1, (x0_c, y0_c, x1_c, y1_c), str(img_path_novo)):
                                                            slide["image_path"] = str(img_path_novo)
                                                            slides[i] = slide
                                                            config_slides_path.write_text(json.dumps(slides, indent=4, ensure_ascii=False), encoding="utf-8")
                                                            
                                                            with st.spinner("Regerando PPTX com novo recorte..."):
                                                                criar_apresentacao_evidencias(cnpj, slides, str(out_pptx))
                                                                criar_apresentacao_pdf(cnpj, slides, str(out_pdf))
                                                            st.toast("✅ Recorte aplicado e PPTX regerado!", icon="✂️")
                                                            time.sleep(1)
                                                            st.rerun()
                                                        else:
                                                            st.toast("❌ Falha ao salvar o recorte da imagem.", icon="⚠️")
                                            else:
                                                st.warning(f"⚠️ Módulo `st_cropper` não carregado: {st_cropper_error}")
                                        except Exception as ec:
                                            st.error(f"Erro ao abrir Cropper: {ec}")
                                            
                                st.markdown("**📤 Subir Imagem Substituta (Opcional)**")
                                nova_img = st.file_uploader(f"Substituir evidência (Slide {i+1})", type=["png", "jpg", "jpeg"], key=f"up_img_{i}")
                                if nova_img:
                                    if st.button("🖼️ Confirmar e Substituir Imagem", key=f"btn_up_confirm_{i}", type="primary", use_container_width=True):
                                        img_path = dirs["saida"] / f"custom_{i}_{nova_img.name}"
                                        img_path.write_bytes(nova_img.getbuffer())
                                        slide["image_path"] = str(img_path)
                                        slides[i] = slide
                                        import json
                                        config_slides_path.write_text(json.dumps(slides, indent=4, ensure_ascii=False), encoding="utf-8")
                                        from presentation_service import criar_apresentacao_evidencias
                                        from pdf_presentation_service import criar_apresentacao_pdf
                                        criar_apresentacao_evidencias(cnpj, slides, str(out_pptx))
                                        criar_apresentacao_pdf(cnpj, slides, str(out_pdf))
                                        st.toast("✅ Imagem substituída!", icon="🖼️")
                                        import time; time.sleep(1); st.rerun()
                            
                            with c_form:
                                with st.form(key=f"form_slide_{i}"):
                                    novo_tit = st.text_input("Cabeçalho do Slide", value=slide.get("title", ""))
                                    nova_desc = st.text_area("Descrição", value=slide.get("description", ""), height=150)
                                    
                                    submitted = st.form_submit_button("💾 Salvar Ajustes e Regerar")
                                    if submitted:
                                        slide["title"] = novo_tit
                                        slide["description"] = nova_desc
                                        
                                        if nova_img:
                                            img_path = dirs["saida"] / f"custom_{i}_{nova_img.name}"
                                            img_path.write_bytes(nova_img.getbuffer())
                                            slide["image_path"] = str(img_path)
                                        
                                        slides[i] = slide
                                        config_slides_path.write_text(json.dumps(slides, indent=4, ensure_ascii=False), encoding="utf-8")
                                        
                                        with st.spinner("Regerando apresentação com novos dados..."):
                                            criar_apresentacao_evidencias(cnpj, slides, str(out_pptx))
                                            criar_apresentacao_pdf(cnpj, slides, str(out_pdf))
                                            
                                        st.toast("✅ Slide atualizado! PPTX e PDF regerados.", icon="🎞️")
                                        time.sleep(1)
                                        st.rerun()
            except Exception as e:
                st.error(f"Erro ao carregar editor de slides: {e}")

        st.divider()
    else:
        st.info("💡 Informe um CNPJ na aba Execução para visualizar e editar os slides gerados para um cliente específico.")

    # ------------------------------------------------------------------
    # SEÇÃO: CONFIGURAÇÕES DE MAPEAMENTO (Sempre visível)
    # ------------------------------------------------------------------
    st.divider()
    apply_presentation_premium_css()
    section_header("Configurações de Mapeamento", tag="POR TIPO DE DOC", icon="⚙️")
    instruction_banner("Defina as configurações padrão para recortes dinâmicos por tipo de documento. Estas regras servem para todas as próximas execuções.")
    
    # --- O bloco de variáveis dinâmicas foi movido para dentro da tab_mapeamento para melhor UX ---

    
    # --- Sub-Abas de Configuração (com controle de estado) ---
    config_tab_options = ["✂️ Mapeamento de Recortes", "📄 Gestão de Tipos", "📋 Visão Geral"]
    if "active_config_tab_idx" not in st.session_state:
        st.session_state.active_config_tab_idx = 0
        
    # Usando o parâmetro de index do st.tabs (disponível em versões recentes)
    # Caso sua versão não suporte, o sistema ainda trocará o valor do selectbox interno.
    try:
        t_tabs = st.tabs(config_tab_options)
    except:
        t_tabs = st.tabs(config_tab_options)

    if len(t_tabs) == 3:
        tab_mapeamento, tab_gestao, tab_resumo = t_tabs
    else:
        from unittest.mock import MagicMock
        tab_mapeamento = tab_gestao = tab_resumo = MagicMock()

    with tab_resumo:
        st.subheader("📋 Conferência de Mapeamentos")
        st.caption("Visão geral de todos os slides configurados por tipo de documento.")
        cfg_view = load_config()
        
        if not cfg_view:
            st.info("Nenhum mapeamento customizado encontrado.")
        else:
            # Converte dict para list para facilitar manipulação
            tipos_lista = list(cfg_view.keys())
            
            with st.form("form_reordenacao_global"):
                st.markdown("**Defina a Sequência de Apresentação:**")
                nova_ordem_map = {}
                
                for idx, t_name in enumerate(tipos_lista):
                    t_data = cfg_view[t_name]
                    slides_count = len(t_data.get("slides", []))
                    
                    c_label, c_order = st.columns([4, 1])
                    c_label.markdown(f"📁 **{t_name}** ({slides_count} slides)")
                    # O usuário escolhe o número da posição (Ex: 1, 2, 3...)
                    pos = c_order.number_input(f"Ordem", min_value=1, max_value=len(tipos_lista), value=idx+1, key=f"ordem_{t_name}")
                    nova_ordem_map[t_name] = pos
                
                if st.form_submit_button("✅ Aplicar e Salvar Nova Sequência"):
                    # Ordena a lista de chaves baseada nos valores numéricos escolhidos
                    # Proteção: Verifica se os valores não são mocks antes de ordenar
                    tipos_ordenados = sorted(tipos_lista, key=lambda x: nova_ordem_map[x] if not isinstance(nova_ordem_map[x], MagicMock) else 0)
                    
                    # Reconstrói o dicionário de configuração na nova ordem
                    new_cfg = {k: cfg_view[k] for k in tipos_ordenados}
                    if save_config(new_cfg):
                        st.success("Nova sequência de apresentação aplicada com sucesso!")
                        time.sleep(1)
                        st.rerun()

            st.divider()
            st.markdown("**Resumo dos Slides por Tipo:**")
            for idx, t_name in enumerate(tipos_lista):
                t_data = cfg_view[t_name]
                with st.expander(f"🔍 Detalhes: {t_name}"):
                    c_edit_btn = st.columns([4, 1])[1]
                    if c_edit_btn.button("✏️ Editar", key=f"btn_edit_res_{t_name}"):
                        st.session_state["target_edit_type"] = t_name
                        st.rerun()
                        
                    if not t_data.get("slides"):
                        st.warning("Sem slides.")
                    else:
                        st.table([{
                            "Slide": i+1, 
                            "Cabeçalho": s.get("cabecalho", ""), 
                            "Mapeamento": s.get("modo", "")
                        } for i, s in enumerate(t_data["slides"])])

    with tab_gestao:
        st.subheader("Gestão Dinâmica de Tipos")
        cfg_edit = load_config()
        with st.form("form_novo_tipo_aba"):
            st.markdown("**Cadastrar Novo Tipo de Documento**")
            novo_tipo_nome = st.text_input("Nome", placeholder="Ex: Extrato Bancário Santander")
            aliases_input = st.text_input("Palavras-chave (Aliases)", help="Textos que se contidos no nome do arquivo identificam este tipo. Separe por vírgula.")
            if st.form_submit_button("✅ Salvar Tipo"):
                novo_tipo_nome = novo_tipo_nome.strip()
                if novo_tipo_nome and novo_tipo_nome not in cfg_edit:
                    aliases = [a.strip() for a in aliases_input.split(",") if a.strip()]
                    cfg_edit[novo_tipo_nome] = {
                        "exibir_usuario": True, 
                        "palavras_chave": aliases, 
                        "slides": [{
                            "modo": "ancora",
                            "ancora": "",
                            "pagina": 1,
                            "cabecalho": f"{novo_tipo_nome}",
                            "descricao": ""
                        }]
                    }
                    save_config(cfg_edit)
                    st.success(f"Tipo '{novo_tipo_nome}' cadastrado com sucesso!")
                    import time; time.sleep(0.5); st.rerun()
                elif not novo_tipo_nome: st.error("O nome não pode estar vazio.")
                else: st.error("Este tipo já existe.")

        st.markdown("**Tipos Customizados**")
        for t_name, t_data in cfg_edit.items():
            with st.expander(f"📁 {t_name}"):
                palavras = ", ".join(t_data.get("palavras_chave", []))
                new_aliases = st.text_input("Palavras-chave (Aliases)", value=palavras, key=f"aliases_{t_name}")
                c1, c2 = st.columns([1, 1])
                if c1.button("💾 Salvar Alterações", key=f"upd_{t_name}"):
                    t_data["palavras_chave"] = [x.strip() for x in new_aliases.split(",") if x.strip()]
                    cfg_edit[t_name] = t_data
                    save_config(cfg_edit)
                    st.success("Salvo!"); st.rerun()
                if c2.button("🗑️ Remover Tipo", key=f"rm_{t_name}"):
                    del cfg_edit[t_name]
                    save_config(cfg_edit)
                    st.success("Removido!"); st.rerun()

    with tab_mapeamento:
        cfg_all = load_config()
        # Usa estritamente os tipos carregados do JSON
        tipos_disponiveis = list(cfg_all.keys())
        if not tipos_disponiveis:
            tipos_disponiveis = ["SEM CONFIGURAÇÃO"]
        
        if st.session_state.get("target_edit_type"):
            st.session_state.cfg_tipo = st.session_state.pop("target_edit_type")
        
        if "cfg_tipo" not in st.session_state or st.session_state.cfg_tipo not in tipos_disponiveis:
            st.session_state.cfg_tipo = tipos_disponiveis[0]
            
        selecao_doc = st.selectbox("Selecionar Tipo Documento", tipos_disponiveis, key="cfg_tipo")
        atual = cfg_all.get(selecao_doc, {})
        
        # Busca PDF de exemplo para o auxiliar visual
        pdf_exemplo = None
        search_dirs = []
        if cnpj:
            dirs_tmp = get_current_job_dirs(cnpj)
            search_dirs = [dirs_tmp["entrada"], dirs_tmp["pre"]]
        
        # Adiciona diretórios de execuções passadas para busca de amostra
        for d in list(EXEC_ROOT.glob("*"))[:10]:
            if d.is_dir():
                search_dirs.append(d / "entrada")
                search_dirs.append(d / "Pre_processamento")

        all_pdfs = []
        seen_paths = set()
        for d in search_dirs:
            if d.exists():
                for pf in d.glob("*.pdf"):
                    if pf.name not in seen_paths:
                        all_pdfs.append(pf)
                        seen_paths.add(pf.name)
        
        for pf in all_pdfs:
            # Import dinâmico necessário para evitar circular dependência no boot
            from report_parser import _heuristica_tipo_doc
            if _heuristica_tipo_doc(pf.name, pf).upper() in selecao_doc.upper():
                pdf_exemplo = pf
                break
        
        if not pdf_exemplo and all_pdfs:
            pdf_exemplo = all_pdfs[0]

        # Gestão de Múltiplos Slides para o Tipo Selecionado
        slides_mapeados = atual.get("slides", [])
        if not slides_mapeados:
             slides_mapeados = [{
                "modo": "ancora",
                "ancora": "",
                "pagina": 1,
                "cabecalho": selecao_doc,
                "descricao": ""
             }]

        st.markdown(f"### Slides Configuradores para: **{selecao_doc}**")
        st.caption("Você pode configurar múltiplos recortes/slides para este mesmo tipo de documento.")
        
        slide_idx_edit = st.selectbox("Selecionar Slide para Editar", range(len(slides_mapeados)), format_func=lambda x: f"Slide {x+1}: {slides_mapeados[x].get('cabecalho', 'Novo')}")
        s_atual = slides_mapeados[slide_idx_edit]
        
        col_reorder, col_del = st.columns([4, 1])
        
        with col_reorder:
            # Botões de reordenação (somente se houver mais de 1 slide)
            if len(slides_mapeados) > 1:
                c_up, c_down, c_spacer = st.columns([1, 1, 2])
                if slide_idx_edit > 0:
                    if c_up.button("⬆️ Subir", help="Mover slide para cima na ordem", use_container_width=True):
                        # Troca de posição
                        slides_mapeados[slide_idx_edit], slides_mapeados[slide_idx_edit-1] = slides_mapeados[slide_idx_edit-1], slides_mapeados[slide_idx_edit]
                        cfg_all[selecao_doc]["slides"] = slides_mapeados
                        save_config(cfg_all)
                        st.toast("Slide movido para cima!")
                        time.sleep(0.3)
                        st.rerun()
                
                if slide_idx_edit < len(slides_mapeados) - 1:
                    if c_down.button("⬇️ Baixar", help="Mover slide para baixo na ordem", use_container_width=True):
                        # Troca de posição
                        slides_mapeados[slide_idx_edit], slides_mapeados[slide_idx_edit+1] = slides_mapeados[slide_idx_edit+1], slides_mapeados[slide_idx_edit]
                        cfg_all[selecao_doc]["slides"] = slides_mapeados
                        save_config(cfg_all)
                        st.toast("Slide movido para baixo!")
                        time.sleep(0.3)
                        st.rerun()

        with col_del:
            if st.button("🗑️ Excluir", key=f"del_slide_map_{slide_idx_edit}", use_container_width=True, type="secondary"):
                slides_mapeados.pop(slide_idx_edit)
                if not slides_mapeados:
                    cfg_all[selecao_doc]["slides"] = [{
                        "modo": "ancora", "cabecalho": selecao_doc, "pagina": 1, "ancora": "", "descricao": ""
                    }]
                else:
                    cfg_all[selecao_doc]["slides"] = slides_mapeados
                save_config(cfg_all)
                st.success("Removido!"); time.sleep(0.5); st.rerun()

        modo_s = st.radio(
            "Modo de Recorte do Slide",
            ["Agente de IA (Vision)", "Âncora Textual (simples)", "Âncora Início+Fim (Range)", "Coordenadas Fixas"],
            index=(
                0 if s_atual.get("modo") == "ancora"
                else 1 if s_atual.get("modo") == "ancora_simples"
                else 2 if s_atual.get("modo") == "ancora_range"
                else 3
            ),
            key=f"modo_slide_{slide_idx_edit}",
            horizontal=True
        )

        with st.expander("📌 Variáveis Dinâmicas & Lista de Apoio"):
            st.markdown("Use as abas abaixo para copiar as variáveis disponíveis:")
            vt1, vt2, vt3 = st.tabs(["📋 Cadastro", "📈 Financeiro", "⚖️ Risco"])
            with vt1: st.code("{nome_empresa} {cnpj} {data_fundacao} {capital_social} {porte_empresa} {situacao_cadastral} {nire} {socios}", language=None)
            with vt2: st.code("{faturamento_mensal} {sazonalidade} {principais_clientes} {principais_fornecedores} {endividamento_bancario}", language=None)
            with vt3: st.code("{risco} {limite} {raroc} {score_serasa} {decisao} {justificativa_risco} {justificativa_limite} {total_protestos} {pefin_refin}", language=None)
            
            st.divider()
            from utils.presentation_helpers import STATIC_AGENT_VARIABLES
            base_vars = ["{nome_empresa}", "{cnpj}", "{data_fundacao}", "{capital_social}", "{porte_empresa}", "{situacao_cadastral}", "{nire}", "{socios}", "{patrimonio_socios}", "{renda_declarada}", "{risco}", "{limite}", "{raroc}", "{score_serasa}", "{decisao}", "{justificativa_risco}", "{justificativa_limite}", "{alerta_docs_antigos}", "{total_protestos}", "{quantidade_processos}", "{pefin_refin}"]
            agent_vars = [f"{{{v}}}" for v in STATIC_AGENT_VARIABLES]
            vars_all = base_vars + agent_vars
            v_sel = st.selectbox("🔍 Copiar para Cabeçalho/Descrição:", [""] + vars_all, key=f"var_sel_{slide_idx_edit}")
            if v_sel: st.info(f"Clique para copiar: `{v_sel}`")


    with st.form("form_mapping"):
        st.markdown(f"**Configurações do Slide {slide_idx_edit + 1}**")
        
        # Unificação de inputs: Usamos as variáveis locais para coletar o estado final
        if modo_s == "Coordenadas Fixas":
            st.markdown("**Ajuste Fino das Coordenadas**")
            cp1, cp2 = st.columns([1, 3])
            pagina_final = cp1.number_input("Página", min_value=1, value=s_atual.get("pagina", 1), key=f"pag_s_{slide_idx_edit}")
            coords_final = cp2.text_input("Coordenadas (x0, y0, x1, y1)", value=s_atual.get("coordenadas", ""), key=f"coords_s_{slide_idx_edit}")
            ancora_final = ancora_ini_final = ancora_fim_final = ""

        elif modo_s == "Âncora Início+Fim (Range)":
            c1, c2 = st.columns(2)
            ancora_ini_final = c1.text_input("Texto de Início", value=s_atual.get("ancora_inicio", ""), key=f"ini_s_{slide_idx_edit}")
            ancora_fim_final = c2.text_input("Texto de Fim", value=s_atual.get("ancora_fim", ""), key=f"fim_s_{slide_idx_edit}")
            ancora_final = st.text_input("Âncora Fallback", value=s_atual.get("ancora", ""), key=f"anc_fall_s_{slide_idx_edit}")
            pagina_final = st.number_input("Página Provável", min_value=1, value=s_atual.get("pagina", 1), key=f"pag_range_{slide_idx_edit}")
            coords_final = ""

        elif modo_s == "Agente de IA (Vision)":
            st.info("🤖 **Modo Inteligente**: O Agente tentará localizar a área baseando-se nos termos abaixo.")
            ancora_final = st.text_input("Termo/Âncora Principal", value=s_atual.get("ancora", ""), key=f"anc_ia_{slide_idx_edit}")
            c1, c2 = st.columns(2)
            ancora_ini_final = c1.text_input("Trecho Início (Opcional)", value=s_atual.get("ancora_inicio", ""), key=f"ini_ia_{slide_idx_edit}")
            ancora_fim_final = c2.text_input("Trecho Fim (Opcional)", value=s_atual.get("ancora_fim", ""), key=f"fim_ia_{slide_idx_edit}")
            pagina_final = st.number_input("Página Provável", min_value=1, value=s_atual.get("pagina", 1), key=f"pag_ia_{slide_idx_edit}")
            coords_final = ""

        else: # Âncora Textual (simples)
            ancora_final = st.text_input("Texto a ser encontrado (Âncora)", value=s_atual.get("ancora", ""), key=f"anc_s_{slide_idx_edit}")
            pagina_final = st.number_input("Página Provável", min_value=1, value=s_atual.get("pagina", 1), key=f"pag_simples_{slide_idx_edit}")
            ancora_ini_final = ancora_fim_final = ""
            coords_final = ""

        st.markdown("**Conteúdo do Slide**")
        cabecalho = st.text_input("Cabeçalho do Slide", value=s_atual.get("cabecalho", ""), key=f"tit_s_{slide_idx_edit}")
        descricao = st.text_area("Descrição", value=s_atual.get("descricao", ""), key=f"desc_s_{slide_idx_edit}")
        
        c_save, c_add = st.columns(2)
        if c_save.form_submit_button("💾 Salvar Alterações no Slide"):
            _modo_salvo = (
                "ancora" if modo_s == "Agente de IA (Vision)"
                else "ancora_simples" if modo_s == "Âncora Textual (simples)"
                else "ancora_range" if modo_s == "Âncora Início+Fim (Range)"
                else "coordenadas"
            )
            slides_mapeados[slide_idx_edit] = {
                "modo":         _modo_salvo,
                "ancora":       ancora_final,
                "ancora_inicio": ancora_ini_final,
                "ancora_fim":    ancora_fim_final,
                "pagina":       pagina_final,
                "coordenadas":  coords_final,
                "cabecalho":    cabecalho,
                "descricao":    descricao,
            }
            cfg_all[selecao_doc] = {"exibir_usuario": atual.get("exibir_usuario", True), "slides": slides_mapeados}
            if save_config(cfg_all): st.success("✅ Configurações salvas!")
            st.rerun()

        if c_add.form_submit_button("➕ Adicionar Novo Slide para este Tipo"):
            slides_mapeados.append({"modo": "ancora", "cabecalho": "Novo Slide", "pagina": 1})
            cfg_all[selecao_doc] = {"exibir_usuario": atual.get("exibir_usuario", True), "slides": slides_mapeados}
            save_config(cfg_all)
            st.rerun()

    with st.expander("🖼️ Abrir Auxiliar Visual de Recorte / Preview"):
        if not pdf_exemplo:
            st.warning("Nenhum arquivo PDF encontrado para preview. Você pode subir um arquivo de referência:")
            ref_upload = st.file_uploader("Upload de PDF Referência", type=["pdf"], key=f"ref_up_{selecao_doc}")
            if ref_upload:
                pdf_exemplo = Path("tmp") / f"ref_{selecao_doc}.pdf"
                pdf_exemplo.parent.mkdir(exist_ok=True)
                pdf_exemplo.write_bytes(ref_upload.read())
        
        if pdf_exemplo:
            try:
                import fitz
                from PIL import Image
                doc = fitz.open(str(pdf_exemplo))
                tot_pags = len(doc)
                st.caption(f"Exemplo: `{pdf_exemplo.name}` ({tot_pags} páginas)")
                
                # --- NOVO: MODO ROLLOUT (SCROLL) ---
                st.markdown("### Navegação por Scroll (Rollout)")
                st.info("💡 Role para baixo para visualizar todas as páginas. Clique em 'Recortar esta Página' para definir as coordenadas.")
                
                # Estado para saber qual página está sendo "croppada"
                if f"active_crop_pag_{selecao_doc}" not in st.session_state:
                    st.session_state[f"active_crop_pag_{selecao_doc}"] = 1
                
                # Container com Scroll para visualização rápida
                with st.container(height=500):
                    for p_num in range(tot_pags):
                        page_obj = doc[p_num]
                        # Renderização leve para o scroll (baixo DPI)
                        pix = page_obj.get_pixmap(matrix=fitz.Matrix(0.5, 0.5)) # 50% scale
                        img_v = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        
                        st.image(img_v, caption=f"Página {p_num + 1}", use_container_width=False)
                        if st.button(f"✂️ Selecionar Página {p_num + 1}", key=f"btn_sel_pag_{selecao_doc}_{p_num}"):
                            st.session_state[f"active_crop_pag_{selecao_doc}"] = p_num + 1
                        st.markdown("---")
                
                # --- ÁREA DE RECORTE (APENAS PÁGINA ATIVA) ---
                active_p = st.session_state[f"active_crop_pag_{selecao_doc}"]
                st.markdown(f"#### ✂️ Recortando Página: **{active_p}**")
                
                page_active = doc[active_p - 1]
                pix_high = page_active.get_pixmap(dpi=72)
                img_crop = Image.frombytes("RGB", [pix_high.width, pix_high.height], pix_high.samples)
                
                if st_cropper:
                    rect = st_cropper(img_crop, realtime_update=True, box_color='#00D1FF', aspect_ratio=None, return_type='box', key=f"crop_ui_v2_{selecao_doc}")
                    if rect:
                        x0, y0, x1, y1 = int(rect['left']), int(rect['top']), int(rect['left']+rect['width']), int(rect['top']+rect['height'])
                        coords_str = f"{x0}, {y0}, {x1}, {y1}"
                        st.code(f"Coordenadas: {coords_str} | Página: {active_p}")
                        
                        if st.button("📥 Aplicar no Formulário Acima", key=f"apply_coords_{selecao_doc}"):
                            # Injeta no session state do widget de coordenadas
                            st.session_state[f"coords_s_{slide_idx_edit}"] = coords_str
                            st.session_state[f"pag_s_{slide_idx_edit}"] = active_p
                            # Força o modo para Coordenadas Fixas se não estiver
                            st.session_state[f"modo_slide_{slide_idx_edit}"] = "Coordenadas Fixas"
                            st.rerun()
                else:
                    st.image(img_crop, use_container_width=True)
                    st.warning("Módulo st_cropper não disponível.")
                
                doc.close()
            except Exception as e:
                st.error(f"Erro no preview visual: {e}")

# ------------------------------------------------------------------
# ABA 5: DETALHES TÉCNICOS
# ------------------------------------------------------------------
with tab_tec:
    st.header("Logs e Auditoria do Sistema")
    if cnpj:
        dirs = get_current_job_dirs(cnpj)
        st.subheader(f"Console Log (Tail) - {dirs['root'].name}")
        st.code(tail_log(cnpj), language="text") # Note: tail_log needs path awareness if reading file.
        # tail_log reads global? or by cnpj? log_service probably reads specific user log.
        # Let's inspect log_service in next turn if needed, but usually it finds via CNPJ.
        
        st.subheader("Audit Trail JSON")
        st.json(read_audit(cnpj))
    else:
        st.write("Sem logs disponíveis.")

# ------------------------------------------------------------------
# ABA 5: GESTÃO DE USUÁRIOS (ADMIN ONLY)
# ------------------------------------------------------------------
if is_admin and tab_users:
    with tab_users:
        st.header("Gestão de Usuários")
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.subheader("Cadastrar Novo Usuário")
            with st.form("new_user"):
                new_user = st.text_input("Novo Usuário")
                new_pass = st.text_input("Senha", type="password")
                new_is_admin = st.checkbox("É Admin?")
                
                if st.form_submit_button("Cadastrar"):
                    if len(new_user) < 3 or len(new_pass) < 3:
                        st.error("Usuário e senha devem ter min. 3 caracteres.")
                    else:
                        ok = create_user(new_user, new_pass, new_is_admin)
                        if ok:
                            st.success(f"Usuário {new_user} criado!")
                            time.sleep(1) 
                            st.rerun()
                        else:
                            st.error("Usuário já existe.")

        with c2:
            st.subheader("Usuários Existentes")
            users = list_users()
            if users:
                for u in users:
                    with st.container():
                        cU, cA, cD = st.columns([3, 2, 1])
                        cU.write(f"**{u['username']}**")
                        cA.write("Admin" if u['is_admin'] else "User")
                        if st.button("🗑️", key=f"del_{u['username']}"):
                             if u['username'] == "admin":
                                 st.error("Não é possível remover o super-admin.")
                             elif u['username'] == st.session_state.user_info.get("username"):
                                 st.error("Não é possível remover a si mesmo.")
                             else:
                                 delete_user(u['username'])
                                 st.success("Removido.")
                                 time.sleep(0.5)
                                 st.rerun()
            else:
                st.info("Nenhum usuário encontrado.")

# ------------------------------------------------------------------
# ABA: MODO DESENV (Modular Testing)
# ------------------------------------------------------------------
if tab_desenv:
    with tab_desenv:
        st.header("🧪 Modo Desenvolvedor: Testes Modulares")
        st.info("Este ambiente permite executar partes da pipeline de forma isolada para depuração e testes rápidos.")
        dev_upload = st.file_uploader("Upload de PDFs para Testes (Modo Desenv)", type=["pdf"], accept_multiple_files=True, key="dev_mode_upload")
        
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            st.subheader("Frente 1: Análise de Crédito")
            st.markdown("Executa a extração, tipificação e análise (IA1/IA2) sem gerar apresentações.")
            
            with st.form("form_desenv_analise"):
                d_cnpj = st.text_input("CNPJ de Teste", value=st.session_state.cnpj or "12345678000195")
                d_email = st.text_input("E-mail para Relatório", value=st.session_state.user_info.get("email", "teste@sbk.com"))
                d_files = st.file_uploader("Upload de PDFs (Volume de Teste)", type=["pdf"], accept_multiple_files=True, key="dev_analysis_upload")
                
                if st.form_submit_button("🚀 Iniciar Somente Análise"):
                    if not d_cnpj or len(d_cnpj) != 14:
                        st.error("CNPJ inválido para teste.")
                    elif not d_files:
                        st.error("Suba ao menos um PDF.")
                    else:
                        st.session_state.run_full = True
                        st.session_state.cnpj = d_cnpj
                        # Chamada customizada via session state flags
                        st.session_state["tipo_execucao"] = "Somente análise de crédito"
                        with st.spinner("Executando Análise..."):
                            executar_pipeline(d_cnpj, d_email, d_files, "Somente análise de crédito")
                        st.success("Análise modular concluída!")
                        st.session_state.run_full = False
                        st.rerun()

        with col_f2:
            st.subheader("Frente 2: Geração de Apresentação")
            st.markdown("Testa o motor de recortes e montagem de slides usando PDFs locais.")
            
            d_files_pres = st.file_uploader("Upload de PDFs para Recorte", type=["pdf"], accept_multiple_files=True, key="up_desenv_pres")
            
            if d_files_pres:
                st.session_state["desenv_files"] = d_files_pres
                # Salva temporariamente para permitir processamento local
                d_tmp = Path("tmp") / "desenv_pres"
                d_tmp.mkdir(parents=True, exist_ok=True)
                for f in d_files_pres:
                    (d_tmp / f.name).write_bytes(f.getbuffer())
                
                st.success(f"{len(d_files_pres)} arquivo(s) prontos para teste.")
                
                if st.button("🔍 Mapear via IA (Agente de Visão)"):
                    with st.spinner("Agente de IA analisando documentos..."):
                        from classificador_ia import classificar_documento
                        from config_evidencias_service import load_config
                        
                        cfg_temp = load_config()
                        results = []
                        for f in d_files_pres:
                            p_path = d_tmp / f.name
                            tipo, context = classificar_documento(str(p_path))
                            
                            # Tenta sugerir âncoras se o tipo for novo ou precisar de ajuste
                            status = "Conhecido" if tipo in cfg_temp else "Novo Identificado"
                            results.append({"arquivo": f.name, "tipo": tipo, "status": status})
                            
                        st.write("### Resultados do Agente:")
                        st.table(results)
                        st.info("Os tipos novos foram pré-cadastrados no 'Configurações de Mapeamento' para ajuste fino.")

                if st.button("🎞️ Gerar Apresentação Standalone"):
                    if not st.session_state.cnpj:
                        st.error("Informe um CNPJ no sidebar ou na Frente 1 para vincular os resultados.")
                    else:
                        st.session_state.run_full = True
                        st.session_state["tipo_execucao"] = "Somente geração de apresentação"
                        st.session_state["history_mode"] = False
                        st.session_state["selected_job_path"] = None
                        with st.spinner("Gerando slides e PPTX..."):
                            executar_pipeline(st.session_state.cnpj, "dev@null", d_files_pres, "Somente geração de apresentação")
                        st.session_state.run_full = False
                        st.session_state["presentation_generated_notice"] = True
                        st.rerun()
            else:
                st.info("Suba PDFs para habilitar as ferramentas de teste de apresentação.")
