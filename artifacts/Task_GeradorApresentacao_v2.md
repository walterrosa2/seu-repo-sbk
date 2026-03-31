# Plano de Tarefas (Task.md) - Gerador de Apresentações v2 (Melhorias PRD)

## 1. Entrada de Dados e Reuso (AWS Textract)
- [x] Adicionar campo para entrada de CNPJ na tela inicial.
- [x] Implementar verificação de existência do CNPJ na base de dados (arquivos locais/S3).
- [x] Criar fluxo "Deseja reutilizar os dados anteriores?" (Caso CNPJ exista) -> Reaproveitar arquivos `.txt` extraídos.
- [x] Criar fluxo "Deseja fazer a extração dos arquivos pdf?" (Caso CNPJ não exista) -> Disparar AWS Textract.
- [x] Modificar obrigatoriedade do campo E-mail: Só exigir e-mail se "Módulo de Análise de Crédito" estiver ativo (Opcional se for "Somente Apresentação").
- [x] Suportar upload de múltiplos arquivos (PDF e Imagens) simultaneamente.
- [x] Revisar a estrutura de pastas e arquivos para suportar a geração de apresentações, e reuso dos arquivos

## 2. Tipificação de Documentos via IA
- [x] Implementar agente classificador (IA) para analisar o arquivo original e determinar o "Tipo de Documento".
- [x] Comparar com tipos de documentos pré-cadastrados (ex: IRPF, IRPJ, Serasa) baseados na pasta `execuções`.
- [x] Implentar rotina que cadastra automaticamente documentos não-reconhecidos na base com status pendente (para curadoria humana posterior).
- [x] Como não teremos tipos diferentes de documentos no mesmo arquivo uploaded, então podemos limitar o envio ao agente classificador de tipo as paginas iniciais onde temos o cabeçalho do documento, ou seja, as paginas que temos o tipo de documento


## 3. Mapeamento Automático e Fallback
- [x] Adaptar busca de "Âncora Textual" baseada no Tipo de Documento retornado pela IA.
- [x] Gravar como log de auditoria, o que foi enviado para o agente classificador de tipo, e o resultado retornado, além do resultado dos termos de busca de "Âncora Textual" e coordenadas fixas  
- [x] Implementar fallback: Caso a busca falhe, utilizar "Coordenadas Fixas" cadastradas para o tipo.
- [x] Emitir aviso visual ao usuário e gerar o slide com espaço em branco caso ambas as opções de busca falhem.

## 4. Visualização e Edição de Slides (Acelerador PPTX)
- [x] Construir interface de pré-visualização carrossel ou grid com os slides gerados (`.pptx` / `.pdf`).
- [x] Incluir botões para download em `.pptx` e `.pdf` (O PDF deve ser um reflexo/impresão direta do PPTX final).
- [x] Inserir modo de edição individual por slide (mesmo para N slides do mesmo tipo):
  - [x] Edição de textos (Cabeçalho, Descrição).
  - [x] Upload de imagem substituta direta.
  - [x] Utilizar o arquivo original para recorte, ou seja, se o usuario fizer o upload de um pdf, ele deve ser salvo em algum lugar para que possamos fazer o recorte dele, e se ele fizer o upload de uma imagem, ela deve ser salva em algum lugar para que possamos fazer o recorte dela. E caso tenhamos feito o upload de mais de um arquivo pdf, todos eles devem ser salvos em algum lugar para que possamos fazer o recorte deles. E caso tenhamos feito o upload de mais de uma imagem, todas elas devem ser salvas em algum lugar para que possamos fazer o recorte delas.
  - [x] Ferramenta Visual de Recorte focada no slide atual.

## 5. Ferramenta Visual de Recorte (Cropper Modular)
- [x] Resolver a usabilidade de seleção de páginas (Req 7.4): Permitir navegação por todas as páginas do PDF escolhido *diretamente na interface de recorte*.
- [x] Garantir persistência de todos os uploads originais enviados (PDFs e imagens da Etapa 1) num diretório de cache (`saida/{cnpj}/` ou DB Temporário) para viabilizar edições futuras sem re-upload (Req 7.1).
- [x] Ação "Regerar Slide" (Req 7.5): Submeter novo recorte ou imagem via upload e atualizar o respectivo slide na prévia instantaneamente.
