# PRD: Cadastro Dinâmico de Tipos de Documentos

## 1. Contexto e Objetivo
Atualmente, no módulo de Configurações de Mapeamento, o usuário deve selecionar o tipo de documento a partir de uma lista pré-definida. A funcionalidade existente apenas permite a adição de um nome "cru" do tipo, sem configurar heurísticas necessárias para que o robô faça a correspondência correta de arquivos (via fallback em `classificador_ia.py` e `report_parser.py`).
**Objetivo:** Elaborar uma interface (aba) dedicada para o cadastro completo e dinâmico de novos Tipos Documentais, garantindo que o sistema reconheça, extraia e processe as evidências de forma consistente em todo o pipeline, eliminando regras *hardcoded*.

## 2. Utilizadores
- **Administrador/Gestor da IA:** Que irá parametrizar novos produtos ou novos tipos de documentos aceitos pelo banco/instituição.
- **Analista de Crédito:** Que irá consumir a geração da apresentação com os novos slides mapeados.

## 3. Análise do Fluxo Atual vs. Impacto no Pipeline
**Como é hoje (Fluxo Atual):**
- A inserção ocorre de forma manual (via selectbox "Adicionar Novo Tipo") salvando a chave no `config_evidencias.json`.
- A classificação visual/texto no `classificador_ia.py` conta com a inserção da chave no prompt, mas **a heurística de fallback por nome de arquivo** (`inferir_tipo_por_nome_arquivo`) possui dados fixados no código (ex: "serasa", "irpf").
- No `report_parser.py`, o método `_heuristica_tipo_doc` também possui tipos chumbados.
- Ao classificar incorretamente, a apresentação final (PPTX) não encontra o mapa de slides correspondente no `config_evidencias.json`.

**Impacto (O que precisa ser adaptado):**
1. O `config_evidencias.json` precisará suportar um campo `"palavras_chave": ["termo1", "termo2"]` para injeção dinâmica nas regras de heurística.
2. O `classificador_ia.py` e o `report_parser.py` deverão carregar estas palavras-chave dinamicamente do JSON de configuração em vez de usarem *Ifs* fixos.

## 4. Requisitos para a Nova Interface (Prevenção de Retrabalho)
Para garantir que a aba de cadastro atenda a 100% dos cenários sem necessidade de ajustes futuros no código fonte:
1. **Nome do Tipo de Documento:** Campo de texto único (Chave no JSON).
2. **Palavras-chave (Aliases/Gatilhos):** Campo de tags (texto separado por vírgula) para inserir trechos que possam vir no nome do arquivo (ex: "serasa", "relatorio_risco").
3. **Visibilidade na Apresentação:** Toggle (Chave on/off) para decidir se esse tipo de documento gera Slide automaticamente (`exibir_usuario`).
4. **Categoria:** (Opcional) Classificar se é Risco, Impostos, Contrato, etc.
5. **Ações CRUD:** Listar tipos customizados vs. Tipos de sistema; Editar palavras-chave; Excluir tipo de documento de forma segura.

## 5. Novo Fluxo Principal
1. Usuário acessa aba "Apresentação & Evidências" -> Nova subseção/modal "Gestão de Tipos Documentais" (ou substituição da lógica de Tipos).
2. Define o Nome e as Palavras-chave ("Aliases") do tipo a cadastrar.
3. Backend salva em `config_evidencias.json` com essa nova estrutura.
4. Próxima execução: ao fazer o upload (`pre_processamento` e `classificador_ia`), o Python fará varredura dinâmica cruzando o nome do arquivo contra as "palavras_chave" de todos os documentos cadastrados.
5. Em "Configurações de Mapeamento", o usuário só precisa definir as âncoras/imagens de recorte para o novo Tipo.

## 6. Limitações e Regras de Negócio
- Validar palavras-chave conflitantes (ex: cadastrar "relatorio" para Serasa e para SCR).
- Retrocompatibilidade: Se o JSON atual não tiver `palavras_chave`, o sistema fará migrate ou assumirá o próprio nome como chave principal.
