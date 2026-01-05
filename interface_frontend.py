import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))



import streamlit as st
from pathlib import Path
from datetime import datetime
import os
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
import json

# =========================
# Constantes & Helpers
# =========================
EXEC_ROOT = Path("execuções")

def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

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
# Estado da UI
# =========================
if "run_full" not in st.session_state:
    st.session_state.run_full = False
if "cnpj" not in st.session_state:
    st.session_state.cnpj = ""
if "usar_antigo" not in st.session_state:
    st.session_state.usar_antigo = None

# =========================
# Sidebar (Parâmetros)
# =========================
with st.sidebar:
    st.header("Dados da Execução")
    cnpj_raw = st.text_input("CNPJ (somente números)", value=st.session_state.cnpj or "")
    cnpj = "".join(filter(str.isdigit, cnpj_raw))
    st.session_state.cnpj = cnpj

    if len(cnpj) != 14 and cnpj:
        st.warning("⚠️ CNPJ inválido. Certifique-se de digitar os 14 dígitos.")

    empresa = st.text_input("Nome da Empresa")
    email = st.text_input("E-mail para envio do relatório")
    arquivos = st.file_uploader("Selecione os PDFs", type=["pdf"], accept_multiple_files=True)

# Aviso de execução anterior e opção de reuso
usar_antigo = None
ult = ultima_execucao(cnpj) if cnpj else None
if not cnpj:
    st.warning("Informe o CNPJ para iniciar.")
elif ult:
    dias = (datetime.now() - ult).days
    if dias < 90:
        st.warning(f"⚠️ Já existe uma execução de {dias} dias atrás.")
        usar_antigo = st.radio("Deseja reutilizar os dados anteriores?", ["Sim", "Não"])
        st.session_state.usar_antigo = usar_antigo
    else:
        st.session_state.usar_antigo = None

st.title("SBK — Pipeline de Análise de Crédito")

# Habilitação do botão
tem_inputs_basicos = bool(cnpj) and bool(email)
tem_arquivos_ou_reuso = (st.session_state.usar_antigo == "Sim") or (arquivos and len(arquivos) > 0)
habilita_botao = tem_inputs_basicos and (not ult or st.session_state.usar_antigo in ["Sim", "Não"]) and tem_arquivos_ou_reuso

# Clique do botão apenas liga o flag e força rerun
if st.button("🚀 Processamento Completo", type="primary", disabled=not habilita_botao):
    st.session_state.run_full = True
    _safe_rerun()

# =========================
# Execução do Pipeline
# =========================
def executar_pipeline(cnpj: str, email: str, arquivos):
    """
    Executa o fluxo completo (ou reuso) persistindo progresso entre reruns.
    """
    dirs = ensure_job_dirs(cnpj)
    tracker = ProgressTracker(cnpj)
    logger = init_logger(cnpj)

    # REUSO
    if st.session_state.usar_antigo == "Sim" and ult:
        st.info("♻️ Reutilizando dados anteriores. Enviando relatório final...")

        job_antigo = EXEC_ROOT / f"{cnpj}_{ult.strftime('%d%m%Y')}"
        retorno_antigo = job_antigo / "Retorno_IA"
        retorno_atual = dirs["retorno"]

        arquivos_esperados = [
            "relatorio_final.md",
            "relatorio_final.pdf",
            "resultado_IA2.json"
        ]
        faltando = [nome for nome in arquivos_esperados if not (retorno_antigo / nome).exists()]
        if faltando:
            lista = "\n- ".join(faltando)
            st.error(
                "❌ Não foi possível reutilizar: os seguintes arquivos estão ausentes em "
                f"{retorno_antigo}:\n- {lista}"
            )
            return

        for nome in arquivos_esperados:
            origem = retorno_antigo / nome
            destino = retorno_atual / nome
            with open(origem, "rb") as src, open(destino, "wb") as dst:
                dst.write(src.read())
            st.success(f"✅ Copiado: {nome}")

        with log_step(logger, "envio", {"destinatario": email}):
            tracker.set_etapa_status("envio", "processando", 0)
            res = enviar_relatorio_final(cnpj, email, exec_root=dirs["root"])
            tracker.set_etapa_status(
                "envio",
                "concluido" if res["ok"] else "erro",
                100 if res["ok"] else 0,
                detalhe=res["detail"]
            )
            if res["ok"]:
                st.success(f"📬 Relatório reenviado com base na execução de {ult.strftime('%d/%m/%Y')}.")
            else:
                st.error(f"❌ Erro no envio: {res['detail']}")


    # Execução completa (sem reuso)
    if not arquivos or len(arquivos) == 0:
        st.error("❌ Selecione ao menos um PDF ou escolha reutilizar dados anteriores.")
        return

    st.info("🔄 Iniciando processamento completo...")

    # Copia uploads para /entrada
    for arq in arquivos:
        caminho_pdf = dirs["entrada"] / arq.name
        with open(caminho_pdf, "wb") as f:
            f.write(arq.getbuffer())

    # 1) Extração
    st.info("📄 Etapa 1: Extração de texto com AWS Textract")
    tracker.set_etapa_status("extracao", "processando", 0)
    for arq in arquivos:
        try:
            caminho_pdf = dirs["entrada"] / arq.name
            # Se quiser tratar "PDF protegido", pode colocar um try rápido aqui antes.
            txt_path, n_pages = extract_one(str(caminho_pdf), str(dirs["saida"]))
            
            # Salvar metadados (páginas) para uso no pré-processamento, já que PDF será apagado
            meta_path = dirs["saida"] / f"{Path(arq.name).stem}.meta.json"
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({"pages": n_pages, "original_name": arq.name}, f)

            tracker.mark_file_done(arq.name)
        except Exception as e:
            # Marca erro, mas continua o loop
            tracker.mark_file_error(arq.name, str(e))
    
    # Limpeza dos PDFs após extração
    limpar_entrada(cnpj)
    
    tracker.set_etapa_status("extracao", "concluido", 100)
    st.success("✅ Etapa 1 concluída (PDFs removidos)")

    # 2) Pré-processo
    st.info("🧠 Etapa 2: Classificação de documentos estratégicos")
    tracker.set_etapa_status("preprocesso", "processando", 0)
    preparar_pre_processamento(cnpj)
    tracker.set_etapa_status("preprocesso", "concluido", 100)
    st.success("✅ Etapa 2 concluída")

    # 3) IA1
    st.info("🤖 Etapa 3: Processamento com Agente IA1")
    tracker.set_etapa_status("ia1", "processando", 0)
    process_manifest_ia1(cnpj)
    tracker.set_etapa_status("ia1", "concluido", 100)
    st.success("✅ Etapa 3 concluída")

    # 4) IA2
    st.info("🧠 Etapa 4: Consolidação com Agente IA2")
    tracker.set_etapa_status("ia2", "processando", 0)
    process_manifest_ia2(cnpj)
    tracker.set_etapa_status("ia2", "concluido", 100)
    st.success("✅ Etapa 4 concluída")

    # 4.1) Geração dos relatórios finais (UNIFICADO)
    st.info("📝 Gerando relatórios consolidados...")
    tracker.set_etapa_status("ia2", "processando", 50, "Gerando relatórios finais")

    data_proc = datetime.now()
    dirs = ensure_job_dirs(cnpj)
    retorno_dir = dirs["retorno"]     # ✅ use sempre Retorno_IA como base
    saida_dir = dirs["saida"]         # usado apenas para naming no report_service

    # --- (a) Unificar TXT da IA1 em um HTML/PDF auxiliar (opcional para consulta)
    ia1_txt_files = sorted(retorno_dir.glob("ia1_*.txt"))
    if ia1_txt_files:
        html_resumo, pdf_resumo = unificar_txt_em_html(cnpj, data_proc, ia1_txt_files, saida_dir)
        st.success(f"Resumo IA (auxiliar) gerado: {pdf_resumo.name}")
    else:
        st.warning("⚠️ Nenhum TXT ia1_*.txt encontrado para unificação auxiliar do Resumo IA.")

    # --- (b) Construir RELATÓRIO UNIFICADO (MD) = [Identificação] + [IA1] + [IA2] + [<relatorio_risco>] + [Avisos]
    ia1_md_path = retorno_dir / "relatorio_IA1.md"
    ia2_md_path = retorno_dir / "relatorio_final.md"
    unificado_md_path = retorno_dir / "relatorio_unificado.md"

    if not ia2_md_path.exists():
        st.error("❌ Arquivo 'relatorio_final.md' do IA2 não foi encontrado. Interrompendo a unificação.")
        return

    # Carregar conteúdos
    ia1_md = ia1_md_path.read_text(encoding="utf-8", errors="ignore") if ia1_md_path.exists() else ""
    ia2_md = ia2_md_path.read_text(encoding="utf-8", errors="ignore")

    # --- Extração simples para montar 'Identificação' a partir do IA1 (best-effort)
    import re
    razao = re.search(r"(?i)raz[aã]o\s+social[:\s]*([^\n]+)", ia1_md)
    cnpj_encontrado = re.search(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b", ia1_md)
    razao_social = razao.group(1).strip() if razao else "Não informado"
    cnpj_fmt = cnpj_encontrado.group(0) if cnpj_encontrado else cnpj

    # --- Separar o bloco <relatorio_risco> do IA2, se existir
    risco_m = re.search(r"(?s)<relatorio_risco>(.*?)</relatorio_risco>", ia2_md)
    bloco_risco = risco_m.group(1).strip() if risco_m else ""
    ia2_sem_risco = re.sub(r"(?s)<relatorio_risco>.*?</relatorio_risco>", "", ia2_md).strip()

    # --- Montar o MD Unificado na ordem desejada
    partes = []

    # 1) Identificação
    partes.append("# Identificação\n")
    partes.append(f"- **Razão Social:** {razao_social}\n- **CNPJ:** {cnpj_fmt}\n")

    # 2) Resumo IA1 (se houver)
    if ia1_md.strip():
        partes.append("\n# Resumo IA1\n")
        partes.append(ia1_md.strip())

    # 3) Resumo IA2 (sem o bloco de risco)
    partes.append("\n# Resumo IA2\n")
    partes.append(ia2_sem_risco)

    # 4) Relatório Quantitativo de Risco (se houver)
    if bloco_risco:
        partes.append("\n# Relatório Quantitativo de Risco\n")
        partes.append(bloco_risco)

    # 5) Avisos de Documentos Não Recebidos (se estiver ao final do IA2)
    avisos_m = re.search(r"(?si)\*\*AVISOS DE DOCUMENTOS NÃO RECEBIDOS:\*\*(.*)$", ia2_md)
    if avisos_m:
        partes.append("\n# Avisos de Documentos Não Recebidos\n")
        partes.append(avisos_m.group(0))

    unificado_md = "\n\n".join(p.strip() for p in partes if p and p.strip())
    unificado_md_path.write_text(unificado_md, encoding="utf-8")

    # --- (c) Gerar HTML/PDF FINAL a partir do MD Unificado
    html_final, pdf_final = gerar_relatorio_final(cnpj, data_proc, unificado_md, saida_dir)
    st.success(f"Relatório final unificado gerado: {pdf_final.name}")

    tracker.set_etapa_status("ia2", "concluido", 100, "Relatórios prontos")

    # 5) Envio
    st.info("📤 Etapa 5: Enviando relatório final por e-mail...")
    with log_step(logger, "envio", {"destinatario": email}):
        tracker.set_etapa_status("envio", "processando", 0)
        res = enviar_relatorio_final(cnpj, email, exec_root=dirs["root"])
        tracker.set_etapa_status(
            "envio",
            "concluido" if res["ok"] else "erro",
            100 if res["ok"] else 0,
            detalhe=res["detail"]
        )
        if res["ok"]:
            st.success("📬 Relatório enviado com sucesso.")
        else:
            st.error(f"❌ Erro no envio: {res['detail']}")

# Dispara execução se flag estiver ativo
if st.session_state.run_full:
    try:
        executar_pipeline(cnpj, email, arquivos)
    except Exception as e:
        st.error(f"⚠️ Erro durante a execução completa: {e}")
    finally:
        # Garante que não re-executará no próximo rerun
        st.session_state.run_full = False

# =========================
# Logs e Progresso (sempre visível)
# =========================
if cnpj and len(cnpj) == 14:
    dirs = ensure_job_dirs(cnpj)
    tracker = ProgressTracker(cnpj)
    logger = init_logger(cnpj)

    st.divider()
    st.subheader("Logs e Progresso")
    progress_file = dirs["logs"] / "progress.json"
    if progress_file.exists():
        st.code(progress_file.read_text(encoding="utf-8"), language="json")

    st.text("📜 Log (últimos 4000 bytes)")
    st.code(tail_log(cnpj), language="log")

    st.text("📊 Audit Trail (últimos eventos)")
    st.json(read_audit(cnpj))
