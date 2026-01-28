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
from dotenv import load_dotenv

load_dotenv(override=True)

from extrator_aws import extract_one
from pre_processamento import preparar_pre_processamento
from agente_ia1 import process_manifest_ia1
from agente_ia2 import process_manifest_ia2
from email_service import enviar_relatorio_final
from progress_tracker import ProgressTracker
from log_service import init_logger, log_step, tail_log, read_audit
from report_service import unificar_txt_em_html, gerar_relatorio_final
from utils.naming import nome_resumo_ia, nome_analise_final, date_ddmmyyyy
from report_parser import generate_docs_index, extract_executive_summary, sanitize_report_text, parse_ia_output, clean_filename, parse_unified_report
from auth_service import authenticate, create_user, list_users, delete_user

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
    
    # State Management for Paths
    # If "Nova Execução", use default logic (current date).
    # If History, use that path.
    
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
    "🛠️ Detalhes Técnicos"
]

is_admin = st.session_state.user_info.get("is_admin", False)
if is_admin:
    tabs_list.append("👥 Usuários")

all_tabs = st.tabs(tabs_list)

# Unpack simple tabs first, admin tab handled dynamically
tab_exec = all_tabs[0]
tab_prog = all_tabs[1]
tab_res = all_tabs[2]
tab_tec = all_tabs[3]
tab_users = all_tabs[4] if is_admin else None

# ------------------------------------------------------------------
# ABA 1: EXECUÇÃO
# ------------------------------------------------------------------
with tab_exec:
    st.header("Nova Análise de Crédito")
    
    col1, col2 = st.columns(2)
    with col1:
        empresa = st.text_input("Razão Social (Opcional)")
    with col2:
        email = st.text_input("E-mail para envio do relatório")
    
    arquivos = st.file_uploader("Selecione os documentos (PDFs)", type=["pdf"], accept_multiple_files=True)
    
    # Verificação de reuso
    usar_antigo = None
    ultimo_job = ultima_execucao(cnpj) if cnpj and len(cnpj) == 14 else None
    
    if cnpj and ultimo_job:
        dias = (datetime.now() - ultimo_job).days
        st.success(f"📅 Última execução encontrada: {ultimo_job.strftime('%d/%m/%Y')} ({dias} dias atrás)")
        usar_antigo = st.radio("Deseja reutilizar os dados anteriores?", ["Não", "Sim"], index=1 if dias < 30 else 0)
        st.session_state.usar_antigo = usar_antigo
    
    habilita_botao = (bool(cnpj) and len(cnpj)==14 and bool(email)) and \
                     ( (arquivos and len(arquivos) > 0) or (usar_antigo == "Sim") )

    if st.button("🚀 Iniciar Análise", type="primary", disabled=not habilita_botao, use_container_width=True):
        st.session_state.run_full = True
        _safe_rerun()

# ------------------------------------------------------------------
# LÓGICA DE EXECUÇÃO (Background)
# ------------------------------------------------------------------
def executar_pipeline(cnpj: str, email: str, arquivos):
    # Force new job path logic for execution
    # Ensure raw ensure_job_dirs (original) creates new folder based on NOW
    # We can use get_current_job_dirs but logically if we are running NEW, it should be NOW.
    # So we trust job_root(cnpj) inside get_current_job_dirs when history_mode is False.
    
    dirs = get_current_job_dirs(cnpj)
    # Ensure they exist
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
        
    tracker = ProgressTracker(cnpj)
    logger = init_logger(cnpj)

    # ... Lógica de REUSO (similar ao original) ...
    # (Rest of logic remains mostly same but using 'dirs' which is correct)
    
    if st.session_state.usar_antigo == "Sim" and ultimo_job:
        job_antigo = EXEC_ROOT / f"{cnpj}_{ultimo_job.strftime('%d%m%Y')}"
        retorno_antigo = job_antigo / "Retorno_IA"
        retorno_atual = dirs["retorno"]
        if retorno_antigo.exists():
             for item in retorno_antigo.glob("*"):
                if item.is_file():
                    import shutil
                    shutil.copy2(item, retorno_atual / item.name)

    # ... Lógica de EXECUÇÃO NOVA ...
    if st.session_state.run_full and (arquivos or st.session_state.usar_antigo == "Sim"):
        # Se for novo processamento
        if st.session_state.usar_antigo != "Sim":
            # 0. Upload
            for arq in arquivos:
                with open(dirs["entrada"] / arq.name, "wb") as f:
                    f.write(arq.getbuffer())
            
            # 1. Extração
            tracker.set_etapa_status("extracao", "processando", 0)
            for arq in arquivos:
                try:
                    p = dirs["entrada"] / arq.name
                    extract_one(str(p), str(dirs["saida"]))
                    tracker.mark_file_done(arq.name)
                except Exception as e:
                    tracker.mark_file_error(arq.name, str(e))
            limpar_entrada(cnpj)
            tracker.set_etapa_status("extracao", "concluido", 100)
            
            # 2. Pre
            tracker.set_etapa_status("preprocesso", "processando", 0)
            preparar_pre_processamento(cnpj)
            tracker.set_etapa_status("preprocesso", "concluido", 100)
            
            # 3. IA1
            tracker.set_etapa_status("ia1", "processando", 0)
            process_manifest_ia1(cnpj)
            tracker.set_etapa_status("ia1", "concluido", 100)
            
            # 4. IA2
            tracker.set_etapa_status("ia2", "processando", 0)
            process_manifest_ia2(cnpj)
            
            # Geração UNIFICADO
            retorno_dir = dirs["retorno"]
            saida_dir = dirs["saida"]
            ia1_md_path = retorno_dir / "relatorio_IA1.md"
            ia2_md_path = retorno_dir / "relatorio_final.md"
            unificado_md_path = retorno_dir / "relatorio_unificado.md"
            
            if ia2_md_path.exists():
                ia1_md = ia1_md_path.read_text(encoding="utf-8", errors="ignore") if ia1_md_path.exists() else ""
                ia2_md = ia2_md_path.read_text(encoding="utf-8", errors="ignore")
                
                # Unificação simples
                import re
                ia2_sem_risco = re.sub(r"(?s)<relatorio_risco>.*?</relatorio_risco>", "", ia2_md).strip()
                risco_m = re.search(r"(?s)<relatorio_risco>(.*?)</relatorio_risco>", ia2_md)
                bloco_risco = risco_m.group(1).strip() if risco_m else ""
                
                unificado_md = f"CNPJ: {cnpj}\n\n{ia2_sem_risco}\n\n"
                if bloco_risco:
                    unificado_md += f"\n{bloco_risco}"
                
                unificado_md_path.write_text(unificado_md, encoding="utf-8")
                
                # Geração PDF removida; apenas HTML gerado por gerar_relatorio_final
                gerar_relatorio_final(cnpj, datetime.now(), unificado_md, saida_dir)

            tracker.set_etapa_status("ia2", "concluido", 100)
            
        
        # Envio (sempre tenta enviar/reenviar)
        tracker.set_etapa_status("envio", "processando", 0)
        res = enviar_relatorio_final(cnpj, email, exec_root=dirs["root"])
        tracker.set_etapa_status("envio", "concluido" if res["ok"] else "erro", 100)
        
        if res["ok"]:
            st.toast("Relatório enviado por e-mail!", icon="📧")
        else:
            st.error(f"Erro no envio: {res['detail']}")


if st.session_state.run_full:
    with st.spinner("Processando... Acompanhe na aba Progresso."):
        executar_pipeline(cnpj, email, arquivos)
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
                    stages = ["extracao", "preprocesso", "ia1", "ia2", "envio"]
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
# ABA 4: DETALHES TÉCNICOS
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
