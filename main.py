# main.py
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
RUNNING_ON_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None



def _print(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def resolve_host_port() -> tuple[str, int]:
    """
    Ordem de resolução (o primeiro que existir vence):
      1) config_localhost.py -> ADDRESS/PORT
      2) Variáveis de ambiente STREAMLIT_SERVER_ADDRESS / STREAMLIT_SERVER_PORT
      3) Variáveis API_HOST / API_PORT (se já configuradas no .env)
      4) Defaults: 0.0.0.0:8502
    """
    host = os.getenv("STREAMLIT_SERVER_ADDRESS") or os.getenv("API_HOST") or "0.0.0.0"
    port = int(os.getenv("STREAMLIT_SERVER_PORT") or os.getenv("API_PORT") or 8502)

    try:
        # Opcional: arquivo local para padronizar o endpoint LAN
        # Exemplo de conteúdo:
        # ADDRESS = "0.0.0.0"
        # PORT = 8502
        import config_localhost  # type: ignore
        host = os.getenv("STREAMLIT_SERVER_ADDRESS", getattr(config_localhost, "ADDRESS", host))
        port = int(os.getenv("STREAMLIT_SERVER_PORT", getattr(config_localhost, "PORT", port)))
    except Exception:
        pass

    return host, port


def ensure_project_dirs() -> None:
    """
    Garante a existência do diretório base de execuções.
    """
    base = Path("execuções")
    base.mkdir(parents=True, exist_ok=True)


def main() -> int:
    ensure_project_dirs()

    host, port = resolve_host_port()

    use_ngrok = os.getenv("USE_NGROK", "0") in {"1", "true", "yes"}
    public_url = None

    if use_ngrok:
        try:
            from start_ngrok import iniciar_ngrok
            public_url = iniciar_ngrok(port)
            host = "127.0.0.1"  # Streamlit continua local, mas ngrok aponta pra ele
        except Exception as e:
            print("⚠️ Erro ao iniciar Ngrok:", e)

    os.environ.setdefault("STREAMLIT_SERVER_ADDRESS", host)
    os.environ.setdefault("STREAMLIT_SERVER_PORT", str(port))
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    print("✅ Frontend iniciado")
    if public_url:
        print(f"🌐 Acesse externamente via: {public_url}")
    else:
        print(f"📍 Acesse local: http://{host}:{port}")
        print("🌐 Para acesso remoto, configure .env com USE_NGROK=1 e NGROK_AUTHTOKEN")

    cmd = [
        sys.executable, "-m", "streamlit", "run", "interface_frontend.py",
        "--server.address", host,
        "--server.port", str(port),
    ]

    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        _print("❌ Streamlit não encontrado. Instale com:  pip install streamlit")
        return 1
    except KeyboardInterrupt:
        _print("⛔ Encerrado pelo usuário.")
        return 0


if __name__ == "__main__":
    if RUNNING_ON_RAILWAY:
        print("Rodando no Railway — Streamlit será iniciado pelo Dockerfile.")
    else:
        raise SystemExit(main())
