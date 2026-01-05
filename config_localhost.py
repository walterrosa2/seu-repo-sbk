# config_localhost.py
import os
import socket
import subprocess
import sys
from pathlib import Path

PORT = 8502  # Porta padrão (altere se quiser outra fixa)

def detectar_ip_lan():
    """Tenta descobrir o IP local da máquina na rede (ex.: 192.168.x.x)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # qualquer IP válido externo — não será enviado, só usado para bind
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def atualizar_streamlit_config(ip: str, porta: int):
    """Gera o arquivo ~/.streamlit/config.toml com host e porta fixos."""
    config_dir = Path.home() / ".streamlit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"

    conteudo = f"""
[server]
address = "{ip}"
port = {porta}
enableCORS = false
headless = true
"""
    config_file.write_text(conteudo.strip(), encoding="utf-8")
    return config_file

def iniciar_streamlit(ip: str, porta: int):
    """Inicia o Streamlit com o IP e porta definidos."""
    print(f"[→] Iniciando: streamlit run interface_frontend.py --server.address {ip} --server.port {porta}")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "interface_frontend.py",
        "--server.address", ip,
        "--server.port", str(porta),
    ])

if __name__ == "__main__":
    ip = detectar_ip_lan()
    print(f"[i] IP detectado: {ip}")

    cfg_path = atualizar_streamlit_config(ip, PORT)
    print(f"[✓] config.toml atualizado em: {cfg_path}")

    iniciar_streamlit(ip, PORT)
