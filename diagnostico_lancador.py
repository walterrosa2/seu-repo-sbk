import os
import sys
import socket
import subprocess
import importlib.util
from datetime import datetime
from pathlib import Path

log_path = Path("log_execucao.txt")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

def check_port_available(port=8501):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False

def check_module_installed(module_name):
    spec = importlib.util.find_spec(module_name)
    return spec is not None

def main():
    log_path.unlink(missing_ok=True)
    log("🔍 Iniciando diagnóstico da aplicação Streamlit...")

    log(f"Python: {sys.executable}")
    log(f"Args: {sys.argv}")
    log(f"Platform: {sys.platform}")
    log(f"Current Dir: {os.getcwd()}")

    log("🔍 Checando variáveis de ambiente relevantes...")
    for var in ["OPENAI_API_KEY", "SMTP_USER", "API_PORT", "STREAMLIT_SERVER_ADDRESS"]:
        log(f"ENV {var} = {os.getenv(var, '[não definido]')}")

    log("🔍 Verificando se o módulo 'streamlit' está instalado...")
    if not check_module_installed("streamlit"):
        log("❌ Módulo 'streamlit' NÃO está instalado neste ambiente Python.")
        return

    log("✅ Módulo 'streamlit' está instalado.")

    log("🔍 Verificando se o arquivo interface_frontend.py existe...")
    if not Path("interface_frontend.py").exists():
        log("❌ Arquivo 'interface_frontend.py' NÃO encontrado.")
        return

    log("✅ Arquivo encontrado.")

    log("🔍 Testando se a porta 8501 está disponível...")
    if not check_port_available():
        log("⚠️ Porta 8501 já está em uso. A aplicação pode estar travando por isso.")
    else:
        log("✅ Porta 8501 está livre.")

    log("🔍 Tentando iniciar o Streamlit em modo teste (sem abrir navegador)...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "interface_frontend.py", "--server.headless", "true"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for i in range(20):  # Lê as primeiras ~20 linhas de saída
            line = proc.stdout.readline()
            if not line:
                break
            log(f"[Streamlit] {line.strip()}")
        proc.terminate()
    except Exception as e:
        log(f"❌ Erro ao tentar executar Streamlit: {e}")
        return

    log("✅ Diagnóstico finalizado. Verifique o arquivo log_execucao.txt para detalhes.")

if __name__ == "__main__":
    main()