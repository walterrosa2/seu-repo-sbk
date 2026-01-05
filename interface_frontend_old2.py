import streamlit as st
from pathlib import Path
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv(override=True)

from extrator_docling import extract_one
from pre_processamento import preparar_pre_processamento
from agente_ia1 import process_manifest_ia1
from agente_ia2 import process_manifest_ia2
from email_service import enviar_relatorio_final
from progress_tracker import ProgressTracker
from log_service import init_logger, log_step, tail_log, read_audit

EXEC_ROOT = Path("execuções")

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

# Sidebar
with st.sidebar:
    st.header("Dados da Execução")
    cnpj_raw = st.text_input("CNPJ (somente números)")
    cnpj = "".join(filter(str.isdigit, cnpj_raw))  # CNPJ limpo para uso em pastas
    if len(cnpj) != 14:
        st.warning("⚠️ CNPJ inválido. Certifique-se de digitar os 14 dígitos.")
    empresa = st.text_input("Nome da Empresa")
    email = st.text_input("E-mail para envio do relatório")
    arquivos = st.file_uploader("Selecione os PDFs", type=["pdf"], accept_multiple_files=True)

usar_antigo = None
ult = ultima_execucao(cnpj)
if not cnpj:
    st.warning("Informe o CNPJ para iniciar.")
elif ult:
    dias = (datetime.now() - ult).days
    if dias < 90:
        st.warning(f"⚠️ Já existe uma execução de {dias} dias atrás.")
        usar_antigo = st.radio("Deseja reutilizar os dados anteriores?", ["Sim", "Não"])

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

st.title("SBK — Pipeline de Análise de Crédito")

habilita_botao = cnpj and email and (not ult or usar_antigo in ["Sim", "Não"])

if st.button("🚀 Processamento Completo", type="primary", disabled=not habilita_botao):
    try:
        dirs = ensure_job_dirs(cnpj)
        tracker = ProgressTracker(cnpj)
        logger = init_logger(cnpj)

        if usar_antigo == "Sim" and ult:
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
                st.error(f"❌ Não foi possível reutilizar: os seguintes arquivos estão ausentes em {retorno_antigo}:\n- {lista}")
                st.stop()
            for nome in arquivos_esperados:
                origem = retorno_antigo / nome
                destino = retorno_atual / nome
                with open(origem, "rb") as src, open(destino, "wb") as dst:
                    dst.write(src.read())
                st.success(f"✅ Copiado: {nome}")

            with log_step(logger, "envio", {"destinatario": email}):
                tracker.set_etapa_status("envio", "processando", 0)
                res = enviar_relatorio_final(cnpj, email, exec_root=dirs["root"])
                tracker.set_etapa_status("envio", "concluido" if res.ok else "erro", 100 if res.ok else 0, detalhe=res.detail)
                if res.ok:
                    st.success(f"📬 Relatório reenviado com base na execução de {ult.strftime('%d/%m/%Y')}.")
                else:
                    st.error(f"❌ Erro no envio: {res.detail}")
        else:
            st.info("🔄 Iniciando processamento completo...")
            for arq in arquivos:
                caminho_pdf = dirs["entrada"] / arq.name
                with open(caminho_pdf, "wb") as f:
                    f.write(arq.getbuffer())

            st.info("📄 Etapa 1: Extração de texto com Docling")
            tracker.set_etapa_status("extracao", "processando", 0)
            for arq in arquivos:
                try:
                    caminho_pdf = dirs["entrada"] / arq.name
                    txt_path, _ = extract_one(str(caminho_pdf), str(dirs["saida"]))
                    tracker.mark_file_done(arq.name)
                except Exception as e:
                    tracker.mark_file_error(arq.name, str(e))
            tracker.set_etapa_status("extracao", "concluido", 100)
            st.success("✅ Etapa 1 concluída")

            st.info("🧠 Etapa 2: Classificação de documentos estratégicos")
            tracker.set_etapa_status("preprocesso", "processando", 0)
            preparar_pre_processamento(cnpj)
            tracker.set_etapa_status("preprocesso", "concluido", 100)
            st.success("✅ Etapa 2 concluída")

            st.info("🤖 Etapa 3: Processamento com Agente IA1")
            tracker.set_etapa_status("ia1", "processando", 0)
            process_manifest_ia1(cnpj)
            tracker.set_etapa_status("ia1", "concluido", 100)
            st.success("✅ Etapa 3 concluída")

            st.info("🧠 Etapa 4: Consolidação com Agente IA2")
            tracker.set_etapa_status("ia2", "processando", 0)
            process_manifest_ia2(cnpj)
            tracker.set_etapa_status("ia2", "concluido", 100)
            st.success("✅ Etapa 4 concluída")

            st.info("📤 Etapa 5: Enviando relatório final por e-mail...")
            with log_step(logger, "envio", {"destinatario": email}):
                tracker.set_etapa_status("envio", "processando", 0)
                res = enviar_relatorio_final(cnpj, email, exec_root=dirs["root"])
                tracker.set_etapa_status("envio", "concluido" if res.ok else "erro", 100 if res.ok else 0, detalhe=res.detail)
                if res.ok:
                    st.success("📬 Relatório enviado com sucesso.")
                else:
                    st.error(f"❌ Erro no envio: {res.detail}")
    except Exception as e:
        st.error(f"⚠️ Erro durante a execução completa: {e}")

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
