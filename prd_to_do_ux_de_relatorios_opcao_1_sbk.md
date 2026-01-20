# PRD — Reestruturação de UX/Arquitetura Visual dos Relatórios (Opção 1)

## 1) Contexto

A aplicação SBK (Streamlit + pipeline Docling → IA1 → IA2 → geração HTML/PDF → envio por e‑mail) já está funcional, mas o consumo do resultado pelo **gestor** (tomador de decisão de crédito) ainda exige muito “scroll”, leitura técnica extensa e navegação pouco amigável.

**Premissas de escopo deste PRD**

- **Manter o conteúdo** que já é gerado pelos agentes (IA1 e IA2). O foco é **experiência de uso + arquitetura de apresentação**.
- Melhorias de prompt só entram como **opcionais** (fase 2), para reduzir ruído e aumentar consistência de seções.
- Consumo principal em **PC**, com entrega final também em **PDF** e envio por **e‑mail**.

## 2) Objetivo do produto

Transformar o relatório final em um **“Painel de Decisão”**:

- O gestor encontra **em 10–20 segundos**: risco, limite sugerido, alertas e o “porquê”.
- O gestor consegue **drill‑down** para ver evidências por **Agente** e por **Tipo de Documento**.
- O relatório mantém rastreabilidade (evidências + logs), mas **não polui** a área de decisão.

## 3) Público‑alvo e cenários

### Persona principal

**Gestor/Analista de Crédito (tomador de decisão)**

- Quer objetividade: *“aprova ou não? qual limite? quais travas/covenants?”*
- Confere evidências apenas quando algo chama atenção.

### Cenários (User Stories)

1. **Como gestor**, quero abrir o resultado e enxergar um **resumo executivo** (risco + limite + motivos) sem rolar a página.
2. **Como gestor**, quero navegar por **SERASA / VADU / IRPF / Contratos / Outros** para validar a origem de cada alerta.
3. **Como gestor**, quero baixar o **PDF final** e/ou reenviar por e‑mail para outra pessoa.
4. **Como analista operacional**, quero acompanhar andamento (etapas + por arquivo) e ver erros sem ler JSON.

## 4) Diagnóstico da versão atual (o que estamos mantendo e o que dói)

### Conteúdo que está bom e deve ser mantido

- Estrutura macro do unificado: **Identificação → Resumo IA1 → Resumo IA2 → Relatório Quantitativo de Risco → Avisos**.
- Indicadores e recomendações já aparecem no texto (ex.: **RAROC/PD/LGD, limite sugerido, justificativa técnica, alertas**).

### Dores principais observadas nos relatórios atuais

- **Sumário lateral lista tudo** (nomes longos como `ia1_Serasa - OTMA..._resposta`), sem agrupamento por tipo.
- A seção “Arquivos processados” aparece como **uma linha enorme**, difícil de ler.
- Existem **duplicidades** (ex.: “Relatório de Risco – RAROC, PD, LGD” e depois “Relatório Quantitativo de Risco”).
- Pequenos **artefatos de formatação** (tags soltas como `</relatório>`), que prejudicam o acabamento.
- No Streamlit, o progresso é exibido como **JSON/LOG bruto**, o que não é “modo gestor”.

## 5) Solução proposta (Opção 1) — Arquitetura em 2 camadas: RESUMO + AGENTE

A estrutura visual será baseada em dois blocos principais (conforme sugestão):

1. **RESUMO (Executivo)**

- Identificação
- Decisão Recomendada
- Indicadores‑chave
- Alertas & Recomendações
- Documentos Recebidos (tabela)

2. **AGENTE (Drill‑down / Evidências)**

- IA2 (Consolidação)
  - Seções do IA2 (padronizadas por headings)
  - Relatório Quantitativo (RAROC/PD/LGD)
- IA1 (Pré‑processamento / docs grandes)
  - **Agrupado por tipo de documento** (SERASA / VADU / IRPF / Contratos / Outros)
  - Dentro de cada tipo: lista de documentos (com metadados + texto)

### 5.1) Layout de página (PC)

**Top (fixo)**

- Título (CNPJ + Razão Social)
- Chips de status: `Extracao`, `IA1`, `IA2`, `PDF`, `Email`
- Ações: **Baixar PDF**, **Abrir HTML**, **Reenviar e‑mail**, **Compartilhar link interno (LAN)**

**Coluna esquerda (Navegação)**

- Grupo **RESUMO** (colapsável)
- Grupo **AGENTE** (colapsável)
  - IA2
  - IA1
    - SERASA (CNPJ/CPF)
    - VADU
    - IRPF
    - Contratos
    - Outros

**Área principal (conteúdo)**

- Cards com informações-chave + seções colapsáveis (accordion).

### 5.2) Wireframe textual

- **Card 1 — Decisão Recomendada**

  - Risco: Alto/Médio/Baixo
  - Limite sugerido: R\$ xxx
  - Condições: garantias/covenants
  - 3–5 motivos (bullets)

- **Card 2 — Indicadores**

  - RAROC | PD | LGD
  - Faturamento médio | Endividamento | Restrições

- **Card 3 — Alertas**

  - Top alertas (com severidade)

- **Card 4 — Documentos Recebidos**

  - Tabela: Documento | Tipo | Páginas | Estratégico? | Motivo | Status extração

- **Seção AGENTE → IA2**

  - Render do conteúdo mantendo a íntegra, mas com:
    - headings consistentes
    - callouts (ex.: “Recomendação”, “Risco”, “Garantias”)

- **Seção AGENTE → IA1**

  - Accordion por tipo (SERASA/VADU/IRPF/Contrato/Outros)
  - Dentro do accordion: lista de documentos com:
    - nome amigável
    - metadados (páginas/chars/por que foi estratégico)
    - texto original (mantido)

## 6) Requisitos Funcionais (FR)

### FR‑01 — Página “Resultados” no front (Streamlit)

- Exibir **painel executivo** (RESUMO) + navegação de drill‑down (AGENTE).
- Botões de ação: Baixar PDF, Abrir HTML, Reenviar email.

### FR‑02 — Navegação por “RESUMO” e “AGENTE”

- Menu lateral com **grupos colapsáveis**.
- Deep links (#anchors) para seções.

### FR‑03 — Tabela de Documentos Recebidos

- Exibir lista de PDFs processados + metadados:
  - nome amigável
  - páginas (via PyPDF2)
  - chars extraídos (tamanho do .txt)
  - classificado como estratégico? + razão (keywords/tamanho)
  - status de extração

### FR‑04 — Agrupamento por Tipo de Documento

- Regra mínima (heurística por nome e/ou keywords no texto):
  - SERASA, VADU, IRPF, Contrato, Proposta, Outros.
- Usar este agrupamento **tanto no HTML final** quanto na visualização do Streamlit.

### FR‑05 — “Sumário Executivo” automático

- Gerar um bloco de resumo executivo **sem alterar o texto original**:
  - Extrair via regex best‑effort: RAROC/PD/LGD, limite sugerido, risco, principais alertas.
  - Se não encontrar algum campo, mostrar “Não identificado automaticamente”.

### FR‑06 — Sanitização de artefatos de formatação

- Remover tags soltas/estranhas e padronizar bullets/linhas para não quebrar HTML/PDF.
- Exemplos:
  - remover `</relatório>` e tags desconhecidas
  - normalizar `** **` em valores

### FR‑07 — Visualização de progresso (modo humano)

- Trocar exibição “progress.json em code” por:
  - stepper de etapas (Extracao/Preprocesso/IA1/IA2/Envio)
  - lista de arquivos com barra de progresso e status
  - área “Detalhes técnicos” colapsável para logs/json

### FR‑08 — Reenvio de e‑mail e download no front

- Campo para e‑mail adicional (opcional) e botão “Reenviar”.
- Download direto do PDF final e do HTML final.

### FR‑09 — Compatibilidade LAN

- Manter execução local + acesso via LAN (host fixo) conforme `main.py`.
- Exibir no topo da UI o endpoint atual (somente leitura), para facilitar suporte.

## 7) Requisitos Não‑Funcionais (NFR)

- **NFR‑01 Performance:** abrir a página de resultados em até 2–4s em PC comum (sem reprocessar IA).
- **NFR‑02 Idempotência:** resultados devem ser reutilizáveis por data/CNPJ sem reprocessar, mantendo “reuso” atual.
- **NFR‑03 Auditoria:** manter logs e evidências; expor somente sob “Detalhes técnicos”.
- **NFR‑04 Print/PDF:** PDF final com layout limpo, cabeçalho/rodapé e sumário (quando possível).
- **NFR‑05 Segurança:** não expor API keys e não exibir dados sensíveis em logs visíveis por padrão.

## 8) Artefatos e dados (como vamos aproveitar o que já existe)

### Pastas atuais (mantidas)

- `execuções/{cnpj_ddmmyyyy}/entrada` (PDFs)
- `.../saida` (TXTs)
- `.../Pre_processamento` (manifest\_ia1.json)
- `.../Retorno_IA` (respostas IA1/IA2 + relatórios)
- `.../logs` (progress.json + audit)

### Novos arquivos propostos

- `Retorno_IA/docs_index.json`
  - índice consolidado de documentos (tipo, páginas, chars, estratégico, razões).
- `Retorno_IA/resumo_executivo.json`
  - extração best‑effort dos campos do resumo.

## 9) Alterações técnicas (arquivos impactados)

### Frontend

- `interface_frontend.py`
  - Criar layout em abas (ex.: **Execução**, **Progresso**, **Resultados**, **Detalhes técnicos**)
  - Renderizar relatórios finais (HTML embutido via `st.components.v1.html`)
  - Download/reenviar

### Tracker / Progresso

- `progress_tracker.py`
  - Usar `plan_extracao()` no início da extração
  - Marcar `mark_file_processing()` antes do processamento

### Relatórios

- `report_service.py`
  - Novo template **print‑friendly** para PDF (ex.: `report_print.html.j2`)
  - Melhorar opções do `pdfkit` (margens, footer/header)

### Novo módulo

- `report_parser.py` (novo)
  - Construir `docs_index.json` a partir de `entrada/*.pdf`, `saida/*.txt`, `Pre_processamento/manifest_ia1.json`
  - Extrair `resumo_executivo.json` do markdown do IA2/unificado.

## 10) Critérios de Aceitação (Definition of Done)

1. **Página Resultados** exibe RESUMO + AGENTE e permite drill‑down por tipo.
2. **Resumo Executivo** mostra (quando disponível) risco, limite, RAROC/PD/LGD e alertas.
3. **Tabela de documentos** aparece legível e pesquisável (filtro por tipo).
4. **PDF final** mantém conteúdo e melhora legibilidade (sem menus laterais quebrados).
5. **Reenvio de e‑mail** e downloads funcionam sem rerodar IA.
6. Logs continuam disponíveis, mas ficam escondidos por padrão.

## 11) Fora de escopo (por enquanto)

- Alterar lógica de concessão/calibração de risco.
- Criar autenticação multiusuário.
- Criar extração “por página” com Docling (pode entrar depois como otimização).

---

# To‑Do (Backlog para o time de desenvolvimento)

> **Regra do projeto:** manter 100% do conteúdo gerado (IA1/IA2), mudando **apenas** apresentação, navegação e “acabamento” (semântica visual).

## EPIC 1 — Nova UX no Streamlit (modo gestor)
**Objetivo:** entregar uma tela “Resultados” com **Painel de Decisão** + drill‑down (RESUMO/AGENTE) e ações (PDF/HTML/e‑mail).

### T1.1 — Criar aba “Resultados” (layout Opção 1)
- Implementar estrutura em `interface_frontend.py`:
  - Abas: **Execução | Progresso | Resultados | Detalhes técnicos**
  - Na aba **Resultados**:
    - Header fixo (CNPJ, empresa, data, status das etapas)
    - Botões: **Baixar PDF**, **Abrir HTML**, **Reenviar e‑mail**
    - Layout em 2 colunas: Sidebar de navegação + Conteúdo

**DoD / Aceite**
- A aba Resultados carrega sem reprocessar nada.
- Ações de PDF/HTML/e‑mail funcionam com arquivos já gerados.

### T1.2 — Implementar “Painel de Decisão” (Resumo Executivo)
- Criar cards (sem mexer no texto original):
  - **Decisão recomendada** (Aprovar/Aprovar com ressalvas/Recusar)
  - **Limite sugerido**
  - **Risco** (alto/médio/baixo)
  - **RAROC/PD/LGD** (quando presente)
  - **Alertas críticos** (chips)
  - **Documentos faltantes / baixa confiabilidade** (chips)

**DoD / Aceite**
- Gestor consegue entender decisão e limite sem rolar a página.

### T1.3 — Criar navegação RESUMO / AGENTE dentro do Streamlit
- Sidebar com grupos colapsáveis:
  - RESUMO: Identificação | Decisão | Indicadores | Alertas | Documentos
  - AGENTE: IA2 | IA1 → SERASA | VADU | IRPF | Contratos | Outros
- Implementar navegação por âncoras (quando renderizando HTML embutido) e/ou scroll para containers.

**DoD / Aceite**
- Clique no item do menu leva o usuário à seção correspondente.

### T1.4 — Melhorar “modo técnico” (logs/JSON) sem poluir o gestor
- Criar um expander/checkbox “Detalhes técnicos” com:
  - logs resumidos (últimas linhas)
  - `progress.json`
  - manifestos (ia1/ia2)

**DoD / Aceite**
- Por padrão, não aparece JSON/log bruto na tela.

---

## EPIC 2 — Índice de documentos e classificação por tipo
**Objetivo:** manter conteúdo, mas tornar **documentos legíveis e navegáveis**.

### T2.1 — Criar `report_parser.py` para gerar `docs_index.json`
Gerar índice consolidado por execução:
- Ler PDFs em `entrada/` → páginas (PyPDF2)
- Ler TXTs em `saida/` → chars e data de geração
- Ler `Pre_processamento/manifest_ia1.json` → estratégico? + razões
- Inferir `doc_tipo` por heurística (nome do arquivo + palavras‑chave):
  - SERASA, VADU, IRPF, Contrato/Proposta, Outros

**Saída (exemplo de campos)**
- `filename_pdf`, `filename_txt`, `pages`, `chars`, `doc_tipo`, `estrategico`, `razoes`, `status`

**DoD / Aceite**
- `docs_index.json` é gerado sem depender de IA.

### T2.2 — Exibir “Documentos Recebidos” como tabela filtrável
- Na aba Resultados → seção RESUMO → “Documentos Recebidos”:
  - tabela com filtro por tipo e por “estratégico/alerta/erro”
  - ações por linha: abrir PDF / abrir TXT (quando existir)

**DoD / Aceite**
- A seção “Arquivos processados” deixa de ser uma linha gigante e vira tabela.

### T2.3 — Padronizar nomes amigáveis
- Criar função de normalização de nomes:
  - remover prefixos `ia1_`, sufixos `_resposta`, timestamps verbosos
  - gerar “Título de Documento” legível

**DoD / Aceite**
- Menu e cards mostram nomes humanos (ex.: “SERASA — Empresa”, “IRPF — Sócia”).

---

## EPIC 3 — Resumo Executivo automático (sem alterar conteúdo)
**Objetivo:** criar uma camada “executiva” por **parsing** do texto atual (best‑effort), sem reescrever IA.

### T3.1 — Implementar extração best‑effort (`resumo_executivo.json`)
- Parser que tenta extrair do relatório IA2/unificado:
  - risco (alto/médio/baixo)
  - limite sugerido (R$)
  - RAROC/PD/LGD
  - principais alertas (lista)
  - recomendações/condições (lista)
- Estratégia:
  - regex + heurística por headings e padrões numéricos
  - fallback: “Não identificado automaticamente”

**DoD / Aceite**
- Sempre gera um `resumo_executivo.json` mesmo que incompleto.

### T3.2 — Renderizar cards do Painel de Decisão a partir do JSON
- UI consome `resumo_executivo.json` para montar cards.

**DoD / Aceite**
- Painel funciona mesmo sem mudar prompt do IA2.

### T3.3 — (Opcional / Fase 2) Header estruturado no IA2
- Atualizar prompt do IA2 para incluir bloco `<json_resumo>...</json_resumo>`.
- Se presente, preferir esse JSON; se não, usar best‑effort parser.

**DoD / Aceite**
- Compatibilidade retroativa garantida.

---

## EPIC 4 — Template HTML com navegação RESUMO/AGENTE
**Objetivo:** manter o HTML/PDF final, mas com **arquitetura visual e navegação**.

### T4.1 — Criar/atualizar template `interactive_report_v2.html.j2`
Requisitos:
- Sidebar com grupos **RESUMO** e **AGENTE** (colapsáveis)
- Seções com âncoras por tipo (SERASA/VADU/IRPF/Contratos/Outros)
- “Documentos Recebidos” em tabela
- Accordion para IA1 por tipo
- Callouts (caixas) para:
  - Decisão
  - Limite
  - Risco
  - Alertas

**DoD / Aceite**
- HTML abre bem no PC e a navegação leva às seções.

### T4.2 — Sanitização de artefatos de formatação (pré-render)
- Implementar `sanitize_report_text()`:
  - remover tags estranhas (ex.: `</relatório>`)
  - normalizar bullets e quebras de linha
  - corrigir trechos com `** **` e espaços quebrados

**DoD / Aceite**
- Relatório não exibe “sujeira” visual.

### T4.3 — Deduplicação visual (sem remover conteúdo)
- Quando houver duplicidade de títulos/trechos, manter ambos, mas:
  - transformar o segundo em “Detalhes técnicos / Repetição do modelo” (expander)

**DoD / Aceite**
- Usuário não sente “texto repetido” ocupando a primeira dobra da página.

---

## EPIC 5 — PDF print‑friendly
**Objetivo:** PDF limpo e executivo, mantendo o conteúdo.

### T5.1 — Criar template `report_print.html.j2`
- Sem sidebar fixa
- Cabeçalho e rodapé
- Estilos de impressão (fontes legíveis, margens, quebra de página por seção)

**DoD / Aceite**
- PDF final fica bom para arquivar e enviar.

### T5.2 — Ajustar opções do `pdfkit`
- A4, margens, encoding, disable-smart-shrinking (se necessário)
- Fallback: se PDF falhar, manter HTML e sinalizar no front.

**DoD / Aceite**
- Erro de PDF não derruba o pipeline.

---

## EPIC 6 — QA, testes e validação com usuários
**Objetivo:** garantir que a mudança é só UX e não quebra o fluxo.

### T6.1 — Checklist de regressão (conteúdo)
- Validar que todas as seções existentes continuam presentes:
  - Identificação
  - Resumo IA1
  - Resumo IA2
  - Relatório Quantitativo
  - Avisos

### T6.2 — Checklist de UX (gestor)
- Decisão e limite visíveis sem scroll
- Alertas em chips
- Documentos em tabela
- Drill-down por tipo funciona

### T6.3 — Testes com 3 execuções reais
- 3 CNPJs/datas diferentes
- pelo menos 1 caso com documento estratégico + 1 caso com falha parcial

**DoD / Aceite**
- Aprovação do usuário final (gestor) em demonstração.

---

## EPIC 7 — Documentação para operação (LAN)
**Objetivo:** facilitar suporte e uso em rede local.

### T7.1 — README de operação LAN
- Como subir (host/port), como acessar na rede
- Como reenviar e-mail e baixar PDF
- Onde ficam as evidências por execução

### T7.2 — “Guia rápido do gestor”
- 1 página: como ler o Painel de Decisão e validar evidências

---

## Observações finais para o time
- **Conteúdo IA1/IA2 é intocável** nesta fase (apenas sanitização visual e reestruturação de UI).
- `docs_index.json` e `resumo_executivo.json` devem ser salvos em `Retorno_IA/` para auditoria.
- Se `templates/` ainda não estiver versionado no repo, priorizar a inclusão para garantir reprodutibilidade.

