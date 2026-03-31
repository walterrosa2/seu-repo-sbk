# Estratégia de Execução - Desenvolvimento Modular com IA

Para maximizar a precisão, eficiência e controle do agente IA no projeto "Gerador de Apresentações", garantindo que a janela de contexto não seja saturada e evitando alucinações de código, seguem as regras de execução recomendadas:

## 1. Escopo Delimitado por Sessão (Microsteps)
- **Não implemente múltiplas features ao mesmo tempo.** As etapas do `Task_GeradorApresentacao_v2.md` devem ser tratadas como sessões de código independentes.
- Exemplo: Numa sessão, construir apenas o fluxo de "Verificação de CNPJ e extração AWS". Em outra, focar apenas na "Edição de Textos via Streamlit".
- O Agente deve realizar `task_boundary` a cada mudança de escopo.

## 2. Gestão Rígida de Contexto
- **Leia estritamente o necessário.** Evite comandos iterativos como ler grandes diretórios de log ou dar `cat`/`view_file` em arquivos Python de +800 linhas se o defeito estiver claramente numa classe menor.
- **Feche as abas mentais.** Quando uma tarefa for dada como concluída (`[x]`), atualize o markdown e purgue as partes do código que não são mais o foco da análise imediata. Para facilitar, extraia a lógica de UI complexa (ex: `st_cropper`) para um único módulo componentizado.

## 3. Versionamento Contínuo e Testes Intermediários
- Antes de saltar para a próxima fase da task, execute "Smoke Tests" locais ou valide no browser a rota Streamlit correspondente.
- Aja alinhado às diretrizes do Handoff Package / `/versionamento` global do `GEMINI.md`.
- Se a complexidade disparar ou algo parar de funcionar, reverta o passo de imediato. Não empilhe modificações corretivas adivinhadas.

## 4. Trato Seguro com Uploads, Diretórios Temporários e PII
- Como lidamos com IRPF/Serasa, todos arquivos originais/PDFs e renderizações de preview exigidos pelo Requisito 7.1 deverão residir em quarentena de sessão ou na pasta física estruturada `saida/{CNPJ}/`. 
- Implementar política agressiva de exclusão pós-geração do PPTX (ou no `cleanup` event do Streamlit session state) para evitar vazamento ou consumo massivo de disco de múltiplos uploads de PDFs originais.

## 5. Re-leitura Reversa do PRD (Quality Gate Final)
- Para toda sub-entrega, o agente validará os critérios estritos daquele respectivo Requisito anotado no PRD antes de declarar `[x]`. 
- Ex: Terminou ferramenta de recorte? Foi validado o _Req 7.4 da Navegação multi-páginas_ sem atritos? A geração bateu com o _Req 7.6 de correspondência PPTX -> PDF_?
