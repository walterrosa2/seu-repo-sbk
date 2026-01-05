# start_ngrok.py
import os
from pyngrok import ngrok

def iniciar_ngrok(porta=8501) -> str:
    token = os.getenv("NGROK_AUTHTOKEN")
    if token:
        ngrok.set_auth_token(token)

    public_url = ngrok.connect(addr=porta, bind_tls=True)
    print(f"🌍 URL pública (Ngrok): {public_url}")
    return public_url
