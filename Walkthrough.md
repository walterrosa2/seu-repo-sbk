# Walkthrough

## O que foi feito

Em 10/03/2026 foi reproduzida a falha de inicialização a partir do `_start.ps1`. O erro observado foi `No module named streamlit`, indicando que o `venv` existente estava sendo encontrado, mas sem as dependências mínimas para subir a aplicação.

Na sequência, foi validado que a aplicação sobe corretamente quando acessada por `http://localhost:8502/`. Também foi investigada a falha da suíte de testes: o problema não estava no projeto, mas no runtime Python/Windows, já que `import asyncio` falhava em múltiplos interpretadores com `WinError 10106`.

## Onde foi alterado

- `_start.ps1`: adicionado bootstrap para localizar o Python correto, validar o módulo `streamlit`, preparar `pip`, reaproveitar `site-packages` compartilhado quando necessário e iniciar a aplicação com mais robustez.
- `_start.bat`: alinhado com a mesma estratégia de bootstrap e fallback.
- `main.py` e `streamlit_bootstrap.py`: separação do bootstrap do Streamlit para preservar o runtime durante a inicialização.
- `_pytest.ps1`: agora detecta runtimes quebrados em `asyncio`, tenta usar `venv312` quando saudável e exibe instruções objetivas quando o problema é do Windows/Winsock.
- `_repair_winsock.ps1`: helper para executar o reset do Winsock em PowerShell elevado.

## Como validar

1. Executar `.\_start.ps1`.
2. Acessar `http://localhost:8502/`.
3. Executar `.\_pytest.ps1`.
4. Se o script indicar falha do Winsock, abrir PowerShell como administrador, rodar `.\_repair_winsock.ps1`, reiniciar o Windows e repetir `.\_pytest.ps1`.

## Riscos conhecidos

- A instalação automática de dependências continua dependendo de conectividade quando o ambiente local não possui os pacotes necessários.
- O `WinError 10106` é sistêmico: enquanto o stack Winsock do Windows continuar inconsistente, qualquer Python que precise de `asyncio` pode falhar, inclusive fora deste projeto.

## Atualização 10/03/2026 - Recorte IA deslocado para baixo

### O que foi feito

Foi implementada uma compensação de margem superior no recorte via Agente de IA para reduzir o efeito observado de corte iniciando algumas linhas abaixo do esperado. O ajuste agora expande o topo do retângulo convertido (`y0`) em 3% da altura da página por padrão.

Também foi adicionado suporte de ajuste fino por slide com a chave `ia_top_margin_ratio` no mapeamento de slides.

### Onde foi alterado

- `utils/pdf_cropper.py`: `crop_pdf_by_ia_agent(...)` agora aplica margem superior configurável antes do `clip`.
- `interface_frontend.py`: passagem de `ia_top_margin_ratio` do `slides_config` para o crop do modo IA.
- `tests/test_edicao_slides.py`: novo teste unitário `test_crop_pdf_by_ia_agent_aplica_margem_superior`.

### Como validar

1. Executar a geração de apresentação em um caso com `modo: "ancora"` (Vision).
2. Comparar o recorte antes/depois no mesmo slide.
3. Verificar no `audit.jsonl` em `apresentacao.crop.detalhes` os campos:
   - `rect_convertido`
   - `ia_top_margin_ratio`
4. Opcional: ajustar por slide no JSON de configuração, por exemplo:
   - `ia_top_margin_ratio: 0.02` (mais conservador)
   - `ia_top_margin_ratio: 0.05` (mais agressivo)

### Limitações

- Sem execução de testes automatizados neste terminal devido indisponibilidade do runtime Python no ambiente (`python`/`py` não executáveis aqui).
