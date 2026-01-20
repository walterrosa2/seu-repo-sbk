
import re
from report_parser import parse_unified_report, sanitize_report_text

# Sample content from relatorio_unificado.md
sample_md = """
### 03702433660-IRPF-A-2025-2024-REC

**<bloco>="1_IRPF - Delcio Vieira Tannus Filho"**

**<cor_card>="amarelo"**

**1_1_IRPF - Informações Pessoais e Patrimoniais**

- **Nome completo do declarante:** Delcio Vieira Tannus Filho
- **CPF do declarante:** 037.024.336-60
- **Endereço:** Rua João Severiano Rodrigues da Cunha, 879, Jardim Karaiba, Uberlândia, MG, CEP 38411-178

**1_2_IRPF - Renda e Capacidade de Pagamento**

- **Total de rendimentos tributáveis:** R$ 105.964,67
- **Imposto devido:** R$ 10.855,27
- **Imposto a restituir:** R$ 0,00
- **Saldo do imposto a pagar:** R$ 10.855,27

---

**<bloco>="2_VADU - AGRO TANNUS LTDA"**

**<cor_card>="amarelo"**

**2_1_VADU - Content Here**
- Details
"""

print(f"--- Raw MD Length: {len(sample_md)} ---")

# 1. Parse Blocks
blocks = parse_unified_report(sample_md)
print(f"Blocks Found: {len(blocks)}")

for i, b in enumerate(blocks):
    print(f"\n=== BLOCK {i+1} ===")
    print(f"Raw Name: {b['raw_name']}")
    print(f"\n-- Clean Content (First 200 chars) --")
    print(b['content_clean'][:200])
    print(f"\n-- Clean Content (Last 50 chars) --")
    print(b['content_clean'][-50:])
    print("\n------------------------------")
