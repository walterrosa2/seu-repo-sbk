import socket
import requests
from time import sleep

def verificar_socket(host='127.0.0.1', port=8501):
    print(f"🔍 Testando conexão socket com {host}:{port}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        try:
            s.connect((host, port))
            print("✅ Socket conectado com sucesso.")
            return True
        except Exception as e:
            print(f"❌ Erro de socket: {e}")
            return False

def verificar_http(url='http://127.0.0.1:8501'):
    print(f"🔍 Testando requisição HTTP para {url}...")
    try:
        r = requests.get(url, timeout=3)
        print(f"✅ Resposta HTTP {r.status_code} — {r.reason}")
        print("↪ Conteúdo da resposta (primeiras linhas):")
        print("\n".join(r.text.splitlines()[:15]))
        return True
    except Exception as e:
        print(f"❌ Erro HTTP: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando verificação de Streamlit local...")
    ok_socket = verificar_socket()
    sleep(1)
    ok_http = verificar_http()
    if ok_socket and ok_http:
        print("🎯 Tudo indica que o Streamlit está funcionando corretamente.")
    elif ok_socket and not ok_http:
        print("⚠️ Socket OK, mas a aplicação não está respondendo HTTP. Pode haver erro interno no front.")
    elif not ok_socket:
        print("❌ Porta não está aberta. Streamlit provavelmente não está rodando.")