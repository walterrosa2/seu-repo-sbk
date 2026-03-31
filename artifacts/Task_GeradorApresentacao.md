# Plano de Tarefas (Task.md) - Gerador de Apresentações

## 1. Setup e Estrutura Base (Concluído ✅)
- [x] Adicionar dependências `python-pptx` e `pymupdf` no projeto.
- [x] Criar utilitário de manipulação de PDF (`utils/pdf_cropper.py`):
  - [x] Função de recorte por coordenadas (`crop_pdf_to_image`).
  - [x] Função de recorte por âncora textual (`crop_pdf_by_text`).
- [x] Criar serviço construtor de slide / PPTX (`presentation_service.py`):
  - [x] Definição de layout Widescreen 16:9.
  - [x] Criação de Header/Background com paleta de cores corporativa ativa (Azul, Cinza, Branco).
  - [x] Incorporar logo oficial (`templates/sbk.png`).

## 2. Ajustes de Fluxo e UI Inicial (Concluído ✅)
- [x] Inserir "Seletor de Modalidade" (Tipos de Execução) na tela inicial de disparo do pipeline.
- [x] Modificar o orquestrador `executar_pipeline` para só disparar a(s) etapa(s) desejada(s) (Análise de crédito, PPTX, ou ambos).
- [x] Criar aba de "🎞️ Apresentação" no frontend (Streamlit) para visualização final.
- [x] Configurar endpoint de download/export base para PPTX formatado padrão.

## 3. Parametrização e Configurações de Mapeamento (Concluído ✅)
- [x] Criar controlador para salvar/carregar as configurações no arquivo persistente `config_evidencias.json`.
- [x] Construir a UI completa de Mapeamento dentro da Aba de Apresentação:
  - [x] Formulário para o usuário escolher: Tipo de Documento, Modo de busca (Âncora vs Coordenadas).
  - [x] Inserção de Textos fixos para cabeçalho e descrição atrelados a cada tipo de documento.
- [ ] Interatividade visual/componente para selecionar Bounding Box ("caixa_delimitadora") caso precise testar na tela (Crop Manual). -> *Limitação de Escopo v2.*

## 4. Integração IA e Variáveis Dinâmicas (Concluído ✅)
- [x] Construir rotina para pegar o resultado unificado dos Agentes IA (ex: faturamento, score, raroc, nome_empresa) e montar um dicionário genérico de Variáveis Disponíveis.
- [x] Exibir ao usuário na tela de Mapeamento um quadro com todas as variáveis retornadas.
- [x] Mapear o substituidor (`injector`) de variáveis dinâmicas no momento da compilação do Slide.

## 5. Pipeline de Apresentação e Processamento Final (Concluído ✅)
- [x] Injetar a lógica de busca e recorte real durante o processamento `(executar_pipeline)`
- [x] Falhas da busca da Âncora: Configurar serviço para salvar "slides com imagem pendente" que o usuário preenche na aba da UI.
- [x] Gerar render e consolidar imagens limpas no disco local `(saida/)` antes da montagem e deletar as evidências localmente pós-geração por segurança.
- [x] Gerar versão paralela ou funcionalidade para Exportar em PDF (conversor do slide gerado).
- [x] Implementação de Auditoria de Recorte (Log de regras detectadas).
- [x] Correção de Fluxo de Reuso de Dados (Modo Somente Apresentação).

## 6. Ajustes de Usabilidade e Correções (Em andamento ⏳)
- [x] Refatoração da interface de mapeamento (Seletor externo ao form).
- [x] Busca automática de PDFs de histórico para preview.
- [x] Implementação de Seleção Visual via Mouse (Clica e Arrasta).
- [/] Depuração do carregamento do componente `st_cropper` (Fallback detectado pelo usuário).
- [ ] Verificação de dependências de imagem (OpenCV/PIL) no ambiente do usuário.
