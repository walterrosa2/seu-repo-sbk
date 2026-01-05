# test_email_send.py
from pathlib import Path
from email_service import enviar_relatorio_final
from config import get_settings

if __name__ == "__main__":
    CNPJ = "21878984000188"            # <- ajuste aqui
    DEST = "ia@enthusconsulting.com.br"  # <- ajuste aqui

    s = get_settings()
    exec_root = s.job_dir(CNPJ)        # execuções/{CNPJ}_{DDMMAAAA}

    result = enviar_relatorio_final(CNPJ, DEST, exec_root)
    print(result)
