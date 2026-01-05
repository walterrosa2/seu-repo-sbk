import socket
import subprocess
import os

from dotenv import load_dotenv
load_dotenv()


def iniciar_ngrok(porta=8501) -> str | None:
    try:
        from pyngrok import ngrok

        token = os.getenv("NGROK_AUTHTOKEN")
        if token:
            ngrok.set_auth_token(token)

        url = ngrok.connect(porta, bind_tls=True)
        print(f"🌍 URL pública (Ngrok): {url}")
        return str(url)
    except Exception as e:
        print(f"⚠️ Erro ao iniciar Ngrok: {e}")
        return None

if __name__ == "__main__":
    port = 8501
    use_ngrok = os.getenv("USE_NGROK", "0").lower() in {"1", "true", "yes"}

    ip_local = "127.0.0.1"


    if use_ngrok:
        public_url = iniciar_ngrok(port)
        if public_url:
            print(f"✅ Aplicação exposta remotamente via: {public_url}")
        else:
            print("⚠️ Rodando apenas na rede local devido a erro no Ngrok.")

    print(f"🚀 Iniciando Streamlit com IP local: http://{ip_local}:{port}")
    subprocess.run(["streamlit", "run", "interface_frontend.py", "--server.address", ip_local])
