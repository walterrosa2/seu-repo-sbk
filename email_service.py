# email_service.py
from __future__ import annotations

import smtplib
import mimetypes
from pathlib import Path
from email.message import EmailMessage
from email.utils import make_msgid
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

# Integra com Settings (.env)
from config import get_settings  # usa SMTP_HOST/PORT/USER/PASS/TLS do .env
from utils.naming import nome_resumo_ia, nome_analise_final, date_ddmmyyyy


# ---------------------------
# Helpers
# ---------------------------
def _env(templates_dir: str = "templates"):
    return Environment(loader=FileSystemLoader(templates_dir))


def build_email_html(
    cnpj: str,
    data_proc: datetime,
    nome_resumo_pdf: str,
    nome_analise_pdf: str,
    arquivos_processados: list[str],
    observacoes: str = "",
) -> tuple[str, str]:
    """
    Renderiza corpo do email em HTML com logo inline (cid).
    Retorna (html, logo_cid).
    """
    env = _env()
    tpl = env.get_template("email_body.html.j2")

    logo_cid = make_msgid(domain="sbk.local")[1:-1]  # remove <>
    html = tpl.render(
        cnpj=cnpj,
        data_proc=date_ddmmyyyy(data_proc),
        nome_resumo_pdf=nome_resumo_pdf,
        nome_analise_pdf=nome_analise_pdf,
        arquivos_processados=arquivos_processados,
        observacoes=observacoes,
    )
    # Injeta a tag <img src="cid:...">
    html = html.replace("cid:sbk_logo", f"cid:{logo_cid}")
    return html, logo_cid


def _attach_file(msg: EmailMessage, path: Path, as_name: str):
    ctype, _ = mimetypes.guess_type(str(path))
    maintype, subtype = (ctype.split("/", 1) if ctype else ("application", "octet-stream"))
    with open(path, "rb") as f:
        msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=as_name)


def _smtp_send(msg: EmailMessage) -> dict:
    """
    Envia a mensagem usando as configs do .env (SMTP_HOST/PORT/USER/PASS/TLS).
    - SMTP_TLS=True  -> conecta em host/port e faz STARTTLS (típico porta 587)
    - SMTP_TLS=False -> usa SMTP_SSL (típico porta 465)
    """
    s = get_settings()
    host = s.SMTP_HOST
    port = s.SMTP_PORT
    user = s.SMTP_USER
    pwd  = s.SMTP_PASS
    use_tls = bool(s.SMTP_TLS)

    if not user or not pwd:
        return {"ok": False, "detail": "SMTP_USER/SMTP_PASS não configurados no .env."}

    try:
        if use_tls:
            # STARTTLS (porta 587 na maioria dos provedores)
            smtp = smtplib.SMTP(host, port, timeout=20)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
        else:
            # SSL direto (porta 465 na maioria dos provedores)
            smtp = smtplib.SMTP_SSL(host, port, timeout=20)

        smtp.login(user, pwd)
        smtp.send_message(msg)
        smtp.quit()
        return {"ok": True, "detail": "Email enviado com sucesso"}
    except smtplib.SMTPAuthenticationError as e:
        # Caso clássico do Gmail (precisa App Password)
        dica = (
            "Falha de autenticação SMTP.\n"
            "- Se for Gmail com 2FA: gere um App Password em https://myaccount.google.com/apppasswords\n"
            "- Confirme SMTP_HOST/PORT/TLS conforme seu provedor.\n"
            "- O campo 'From' deve ser a mesma conta autenticada."
        )
        return {"ok": False, "detail": f"SMTPAuthenticationError: {e}\n{dica}"}
    except Exception as e:
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}


# ---------------------------
# Função principal de envio
# ---------------------------
def enviar_relatorio_final(cnpj: str, destinatario: str, exec_root: Path) -> dict:
    """
    Monta e envia o e-mail com anexos:
    - ResumoIA_...pdf / html
    - AnaliseIA_...pdf / html
    Ignora arquivos técnicos (.DONE, .txt de IA1, prompts etc).
    """
    data_proc = datetime.now()
    retorno_dir = exec_root / "Retorno_IA"

    # Sempre localizar os finais (Resumo e Analise)
    resumo_pdf = next(retorno_dir.glob("ResumoIA_*.pdf"), None)
    analise_pdf = next(retorno_dir.glob("AnaliseIA_*.pdf"), None)

    if not resumo_pdf or not analise_pdf:
        return {"ok": False, "detail": "Arquivos PDF finais não encontrados."}

    # Renderizar corpo HTML
    arquivos_processados = [p.stem for p in (exec_root / "saida").glob("**/*.txt")]
    html, logo_cid = build_email_html(
        cnpj,
        data_proc,
        resumo_pdf.name,
        analise_pdf.name,
        arquivos_processados
    )

    msg = EmailMessage()
    msg["Subject"] = f"SBK - Análise de Crédito ({cnpj}) - {date_ddmmyyyy(data_proc)}"
    msg["To"] = destinatario
    msg["From"] = "seu.email@gmail.com"

    msg.set_content("Seu cliente de e-mail não suporta HTML.")
    msg.add_alternative(html, subtype="html")

    # Anexar logo inline
    logo_path = Path("templates") / "sbk.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            msg.get_payload()[1].add_related(f.read(),
                                             maintype="image", subtype="png",
                                             cid=f"<{logo_cid}>")

    # ---------------------------
    # Lista de EXCLUSÃO (NÃO ENVIAR)
    # ---------------------------
    NAO_ENVIAR = {
        ".ia1.DONE",
        ".ia2.DONE",
        "resultado_IA1.txt",
        "prompt_enviado_openai.txt"
    }
    # também não enviar nenhum arquivo que comece com "ia1_"
    def deve_enviar(p: Path) -> bool:
        if p.name in NAO_ENVIAR:
            return False
        if p.name.startswith("ia1_"):
            return False
        return True

    # ---------------------------
    # ANEXOS
    # ---------------------------
    # Anexar os finais obrigatórios
    _attach_file(msg, resumo_pdf, resumo_pdf.name)
    _attach_file(msg, analise_pdf, analise_pdf.name)

    resumo_html = next(retorno_dir.glob("ResumoIA_*.html"), None)
    analise_html = next(retorno_dir.glob("AnaliseIA_*.html"), None)
    if resumo_html:
        _attach_file(msg, resumo_html, resumo_html.name)
    if analise_html:
        _attach_file(msg, analise_html, analise_html.name)

    # Qualquer outro arquivo será ignorado por padrão
    for p in retorno_dir.rglob("*"):
        if not p.is_file():
            continue
        if not deve_enviar(p):
            continue
        if p in [resumo_pdf, analise_pdf, resumo_html, analise_html]:
            continue
        # Se quiser anexar mais tipos no futuro, pode liberar aqui

    # Envio real (usando configs do .env via _smtp_send)
    return _smtp_send(msg)

