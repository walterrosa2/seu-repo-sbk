# PRD - Plano de Testes Automatizados (Gerador de Apresentação v2)

## 1. Objetivo
Garantir a qualidade, estabilidade e regressão contínua das novas funcionalidades introduzidas no módulo "Gerador de Apresentações v2", cobrindo desde a entrada de dados (CNPJ e Arquivos), tipificação via IA, até a edição interativa de slides e geração do documento final (PPTX/PDF).

## 2. Usuários
- **Analistas de QA / Engenheiros de Software:** Responsáveis por manter e expandir a suite de testes.
- **Sistema de CI/CD:** Executor automatizado que validará os testes a cada novo Pull Request ou commit na branch principal.

## 3. Requisitos de Testes (Escopo)
O escopo baseia-se nas 5 épicos da V2:
1. **Entrada de Dados e Reuso:** Testar validação de CNPJ, detecção de arquivos em cache local/S3, e roteamento correto (Reuso vs Textract). O Textract deve ser mockado.
2. **Tipificação de Documentos via IA:** Testar a lógica de envio (apenas páginas iniciais), os prompts e o processamento da resposta da OpenAI (via `unittest.mock`). Validar a inclusão de documentos desconhecidos na fila de curadoria.
3. **Mapeamento Automático e Fallback:** Testar a hierarquia de extração: Busca por Âncora Textual -> Coordenadas Fixas -> Slide em Branco. Verificar a geração correta dos logs de auditoria.
4. **Visualização e Edição de Slides:** Validar a estrutura de dados que alimenta o carrossel/grid. Testar as funções de atualização de conteúdo de texto e de substituição de imagem de um slide específico na memória estruturada do PPTX.
5. **Ferramenta de Recorte Visual:** Testar a lógica de persistência dos arquivos originais (cache temporário) e o endpoint/função de `Regerar Slide` recebendo novas coordenadas de crop gerando uma nova imagem.

## 4. Estratégia e Ferramentas
- **Framework Base:** `pytest`
- **Mocks & Stubs:** `unittest.mock` para serviços externos (AWS S3, AWS Textract, OpenAI API).
- **Testes de UI (Streamlit):** Utilizar `AppTest` (do próprio Streamlit) para o comportamento das páginas.
- **Cobertura Mínima Exigida:** 80% das funções do core e services afetados pela V2.

## 5. Limitações e Restrições
- Não deve haver chamadas reais para AWS Textract ou OpenAI durante a execução padrão dos CI tests para evitar custos financeiros e lentidão. O modo de teste deve usar Mocks estritos.
- Os testes de geração de PPTX devem gerar arquivos temporários no diretório de testes (`pytest_tempdir`) e devem ser limpos após a execução.

## 6. Dados Sensíveis e PII
- Os testes devem utilizar **CNPJs e CPFs fictícios** (gerados para fins de teste).
- **Documentos de amostra (Fixtures):** Os PDFs e imagens usados como massa de teste não podem conter dados reais de clientes ou documentos verídicos. Usar layouts falsos (ex. Lorem Ipsum).
- Chaves de API (`AWS_ACCESS_KEY_ID`, `OPENAI_API_KEY`, etc.) nunca devem estar hardcoded nos testes. Utilizar o `.env.test` com credenciais dummy.
