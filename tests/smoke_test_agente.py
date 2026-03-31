import os
import sys
import json
from pathlib import Path

# Adicionar raiz ao path
sys.path.append(str(Path(__file__).parent.parent))

from utils.ancora_agent import detectar_coordenadas_ancora

def test_smoke_agente_ia():
    pdf_path = "tests/fixtures/dummy_document_multipage.pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ PDF de teste não encontrado: {pdf_path}")
        return

    print(f"🚀 Iniciando detecção IA no arquivo: {pdf_path}")
    instrucao = "Localize a área que contém o título 'SERASA' ou informações de crédito principal."
    
    resultado = detectar_coordenadas_ancora(pdf_path, instrucao, page_num=1)
    
    print("--- RESULTADO IA ---")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    
    if resultado.get("success"):
        print("✅ Sucesso: Coordenadas detectadas!")
    else:
        print(f"⚠️ Falha ou trecho não localizado: {resultado.get('error')}")

if __name__ == "__main__":
    test_smoke_agente_ia()
