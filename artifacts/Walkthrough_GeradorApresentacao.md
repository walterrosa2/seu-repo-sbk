# Walkthrough do Desenvolvimento: Gerador de Apresentações v2 (Acelerador PPTX)

Este documento atua como o **Handoff Package** das alterações realizadas na Etapa de Apresentação de Crédito, com foco no Acelerador de PPTX, Classificador Inteligente e UI de edição baseada na revisão do PRD.

## 1. O que foi feito e Onde no Código?

Todas as 5 etapas centrais descritas no PRD foram implementadas, resultando em:

- **Seletor CNPJ e Pipeline Dinâmicos** (`interface_frontend.py` aba `Execução`):
  - Inclusão do campo numérico *CNPJ* direto na home, sincronizado com a _sidebar_.
  - Separação da lógica de extração: O usuário agora conta com check *"Deseja fazer a extração (AWS)?"*, útil para gerar os slides diretamente do arquivo original (PDF puro) que pulam as chamadas severas do AWS se ele for reutilizar os dados analíticos mas criar PPTX customizado.
  - Bloqueio de e-mail e botão apenas se estritamente necessários. A pasta temporária de origem (`/entrada`) foi **parada de sofrer purge** quando a execução acontece, garantindo o Requisito 7.1 de reter PDFs para futuro recorte visual.

- **Classificador de Tipos via LLM** (`classificador_ia.py` (NOVO) e `interface_frontend.py`):
  - Foi criado o módulo `classificador_ia.py` importando `fitz` (PyMuPDF).
  - Ele abre silenciosamente as 2 primeiras páginas do PDF e interpela ao ChatGPT-4o qual o tipo do arquivo enviado, casando ou criando (no JSON) a categorização.
  - Adicionado log profundo de auditoria (`audit.jsonl`) registrando o "recorte" de 4 mil caracteres que foi visto pela LLM em todos os uploads.

- **Fallback Automático: Âncora ➡️ Coordenadas** (`interface_frontend.py` linha de geração de Crop):
  - Adicionada regra sequencial: O sistema lê a âncora e, se retornar `success = False` e existirem "coordenadas", ele automaticamente desce pra buscar por crop hardcoded sem estourar o slide, registrando a descida na auditoria do Cockpit.

- **Editor e Carrossel Individual de Slides** (`interface_frontend.py` Aba de Apresentações):
  - Antes havia apenas o "Baixar PPTX".
  - Agora usamos o estado iterativo `slides_config.json`, de modo que a tela de Apresentação renderiza `st.tabs` isolados para **cada um** dos N slides gerados no ciclo.
  - Para cada aba criamos um formulário isolado onde você pode: Alterar o Título do slide; Alterar a descrição; Subir uma imagem limpa (Upload de PNG/JPG) substituta de crop.

- **Ferramenta de Recorte Integrada ao Slider** (`interface_frontend.py` expansor "✂️ Ferramenta"):
  - Integrado o `st_cropper` logo abaixo dos metadados de slide individual.
  - Permite passear pelas N páginas limitadas ao comprimento do próprio PDF (Req 7.4).
  - Gera botões de `Salvar Ajustes e Regerar`. Quando isso acontece, ele invoca a biblioteca nativa, tritura um frame do Pixmap, substitui a foto no `slides_config.json`, chama as funções `criar_apresentacao_evidencias` no ar e dá um recarregamento reativo da página (Req 7.5).

## 2. Como Validar as Alterações no Pipeline Locamente?

1. Certifique-se de que seu `.env` tem `OPENAI_API_KEY` válida (O Classificador de IA depende desse modelo estritamente para não taxar os tipos falhosos).
2. Como se trata de modificações na tela, por gentileza reinicie o seu processo Streamlit (`CTRL+C` -> `py run_app.py`) caso ele trave no hot-reload.
3. No Frontend:
    - Digite um novo CNPJ.
    - Na aba *Apresentação de Crédito + Mapeamento*, insira um PDF com CNPJ "12345" inédito.
    - Se a barra rodar verde, inspecione seus `logs/audit.jsonl`. Devem haver inserções apontando para `classificacao_ia` listando o palpite da OpenAI.
    - Clique na 4ª Aba: *Apresentação*.
    - Selecione um slide dos que aparecerão tabulares (como `Slide 1: Destaque x...`).
    - Altere textualmente algo da área "Descrição" e clique no Disquete. Valide instantes depois subindo e clicando em "Baixar PowerPoint". O título deve vir grafado exato.
    - Na mesma aba, puxe a `Ferramenta Visual de Recorte`, jogue o slide pra "Página 2" (se tiver múltiplas) e rasure a seleção do quadro vermelho. Feche o formulário salvando. O download virá com a nova imagem preenchida no slide.
    
> Risco Observável: Como a IA está solta para categorizar por _Página 1 e 2_, documentos como "Faturamento Assinado Muito Genérico" podem gerar tipos duplicados ("Faturamento 2023", "Faturamento Geral"). A validação humana posterior no "Configurações de Mapeamento" para unir as tags continuará valendo na regra de uso.
