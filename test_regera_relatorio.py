import sys
from pathlib import Path
from datetime import datetime

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from report_service import gerar_relatorio_final
from report_parser import sanitize_report_text

def run_test():
    # Configurar caminhos
    base_dir = PROJECT_ROOT / "execuções" / "32765305000180_06012026" / "Retorno_IA"
    input_md = base_dir / "relatorio_unificado.md"
    
    if not input_md.exists():
        print(f"❌ Arquivo não encontrado: {input_md}")
        return

    print(f"📂 Lendo: {input_md.name}")
    conteudo_md = input_md.read_text(encoding="utf-8")
    
    # Nome de saída para teste
    output_name = "Teste_Regerado_AnaliseIA_V2.html"
    
    print("🚀 Iniciando geração do relatório...")
    html_path, pdf_path = gerar_relatorio_final(
        cnpj="32.765.305/0001-80",
        data_proc=datetime.now(),
        conteudo_md=conteudo_md,
        saida_dir=base_dir, # Usa o proprio diretorio de retorno como saida simulada
        output_filename=output_name
    )
    
    print("-" * 30)
    print("RESULTADO:")
    
    # 1. Verificar HTML
    if html_path and html_path.exists():
        print(f"✅ HTML Gerado: {html_path}")
        print(f"   Tamanho: {html_path.stat().st_size} bytes")
        
        # Verificar conteúdo basico
        html_content = html_path.read_text(encoding="utf-8")
        if 'id="menu-container"' in html_content:
             print("   ✅ Estrutura de Menu V2 detectada.")
        else:
             print("   ❌ Estrutura de Menu V2 NÃO detectada.")
             
        if '="amarelo"' not in html_content:
             print("   ✅ Limpeza de artefatos ('=\"amarelo\"') feita.")
        else:
             print("   ⚠️ Artefatos de texto ainda presentes.")
             
    else:
        print("❌ Falha na geração do HTML.")

    # 2. Verificar PDF
    if pdf_path is None:
        print("✅ PDF corretamente ignorado (Retorno None).")
    else:
        print(f"❌ PDF foi gerado ou retornado: {pdf_path}")

    print("-" * 30)

if __name__ == "__main__":
    run_test()
