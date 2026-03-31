# Walkthrough: Editor de Apresentações & Mapeamento Dinâmico (Branch analise-apresentacao)

## O que foi feito
1. **Branch analise-apresentacao**: Criada nova branch de staging no GitHub para isolar o desenvolvimento de análise e apresentação.
2. **Mapeamento Dinâmico**: Implementado sistema de CRUD para tipos de documentos em `config_evidencias.json`, permitindo adicionar novos tipos e definir regras de recorte de slides globalmente.
3. **Editor de Slides Premium**: Refatoração do seletor de slides (substituindo abas por um `selectbox` centralizado) para maior escalabilidade e performance.
4. **Substituição Direta de Imagem**: Adicionado botão de confirmação imediata para upload de imagens substitutas nos slides, regerando o PPTX/PDF instantaneamente.
5. **Estabilização de QA**: Correção de dependências (`fpdf2`, `python-pptx`) e ajustes de robustez no `interface_frontend.py` para lidar com desempacotamento de abas dinâmicas.

## Onde no código
- `interface_frontend.py`: Lógica de abas dinâmicas, seletor de slides e botões de ação rápida.
- `config_evidencias_service.py`: Serviço de persistência para as configurações globais de mapeamento.
- `presentation_service.py` & `pdf_presentation_service.py`: Motores de geração de PPTX e PDF.
- `_start.ps1`: Script de inicialização atualizado com validação de módulos críticos.

## Como Validar
1. **Ambiente**: Execute `.\_start.ps1` para validar as dependências.
2. **Mapeamento**: Vá em **🎞️ Apresentação** > **Configurações de Mapeamento** e crie um novo tipo de documento.
3. **Editor**: Localize um slide, altere o título/descrição e clique em "Salvar Ajustes e Regerar".
4. **Imagem**: Suba uma imagem substituta e clique no botão azul correspondente; verifique se o PPTX foi atualizado no diretório de saída.
