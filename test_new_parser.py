import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from report_parser import parse_unified_report, extract_executive_summary

def test_parsing():
    test_text = """
<documentos_ausentes>Balanço 2024</documentos_ausentes>

<bloco>"1_IRPF - Leticia"
<cor_card>"verde"</cor_card>
Subitem => 1_1_Identificação
- CPF: 123
- Nome: Leticia

Subitem => 1_2_Renda
- Renda: R$ 10.000
</bloco>

<bloco>="2_SERASA - Empresa XPTO"
<cor_card>="amarelo"</cor_card>
Subitem => 2_1_Pendências
- Protestos: 1
</bloco>

<bloco>3_VADU - Geral
<cor_card>vermelho
Subitem => 3_1_Processos
- Quantidade: 50
</bloco>

<bloco>"RELATORIO RISCO"
<cor_card>"cinza"</cor_card>
<risco>Alto</risco>
<raroc>15%</raroc>
<limite>R$ 50.000,00</limite>
<conclusao>Reprovar devido alto risco.</conclusao>
<calculo_raroc>Memoria de calculo aqui...</calculo_raroc>
</bloco>
"""

    print("=== TESTANDO PARSE_UNIFIED_REPORT ===")
    blocks = parse_unified_report(test_text)
    
    for i, b in enumerate(blocks):
        print(f"\nBloco {i+1}: {b['clean_name']}")
        print(f"  Cor: {b['meta']['cor_card']}")
        print(f"  Tipo: {b['meta']['tipo_arquivo']}")
        print(f"  Subitens: {b['meta']['subitems']}")
        if b['meta'].get('risco'):
            print(f"  Metadados Extra: Risco={b['meta']['risco']}, Limite={b['meta']['limite']}")

    print("\n=== TESTANDO EXTRACT_EXECUTIVE_SUMMARY ===")
    summary = extract_executive_summary(test_text)
    print(f"Resumo Executivo:")
    print(f"  Risco: {summary['risco']}")
    print(f"  Limite: {summary['limite']}")
    print(f"  RAROC: {summary['raroc']}")
    print(f"  Decisão: {summary['decisao']}")

if __name__ == "__main__":
    test_parsing()
