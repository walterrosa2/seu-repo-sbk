import socket
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

def get_local_ip(default="127.0.0.1") -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return default

def iniciar_ngrok(porta=8502) -> str | None:
    try:
        from pyngrok import ngrok
        token = os.getenv("NGROK_AUTHTOKEN")
        if token:
            ngrok.set_auth_token(token)

        # Túnel HTTP apontando para o loopback (ok porque o Streamlit vai bindar em 0.0.0.0)
        url = ngrok.connect(addr=f"http://127.0.0.1:{porta}", bind_tls=True)
        print(f"🌍 URL pública (Ngrok): {url}")
        return str(url)
    except Exception as e:
        print(f"⚠️ Erro ao iniciar Ngrok: {e}")
        return None

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8502"))
    use_ngrok = os.getenv("USE_NGROK", "0").lower() in {"1", "true", "yes"}

    # Detecta o IP da LAN apenas para exibição
    ip_lan = get_local_ip()

    if use_ngrok:
        public_url = iniciar_ngrok(port)
        if public_url:
            print(f"✅ Aplicação exposta remotamente via: {public_url}")
        else:
            print("⚠️ Rodando apenas na rede local devido a erro no Ngrok.")

    # Bind em todas as interfaces para atender LAN e loopback
    print(f"🚀 Iniciando Streamlit (LAN):   http://{ip_lan}:{port}")
    print(f"🚀 Iniciando Streamlit (local): http://127.0.0.1:{port}")
    subprocess.run([
        "streamlit", "run", "interface_frontend.py",
        "--server.address", "0.0.0.0",
        "--server.port", str(port),
        # Opcionalmente reduzir ruído de CORS se for acessar pelo túnel:
        # "--server.enableCORS=false", "--server.enableXsrfProtection=false"
    ])
