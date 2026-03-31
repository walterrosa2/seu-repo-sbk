# Checklist de Testes Automatizados - Gerador de Apresentações v2

## 1. Configuração do Ambiente de Testes
- [ ] Criar arquivo `pytest.ini` e configuração base do conftest (`tests/conftest.py`).
- [ ] Configurar fixtures com PDFs e Imagens "dummy" (sem dados reais) para validação.
- [ ] Criar mocks globais para AWS Boto3 (S3/Textract) usando `moto` ou `unittest.mock`.
- [ ] Criar mocks globais ou específicos para a API da OpenAI.

## 2. Testes - Entrada de Dados e Reuso
- [ ] `test_validar_cnpj`: Testar validação e formatação correta do CNPJ na tela inicial.
- [ ] `test_fluxo_reuso_dados`: Simular diretório local/s3 populado com arquivos `.txt` e validar se o sistema detecta e pula a chamada do Textract.
- [ ] `test_fluxo_novo_extracao`: Simular CNPJ inédito e validar se o fluxo invoca corretamente a extração (mockada) via boto3/Textract.
- [ ] `test_envio_multiplos_arquivos`: Validar comportamento ao subir múltiplos PDFs e Imagens simultaneamente.

## 3. Testes - Tipificação de Documentos via IA
- [ ] `test_extracao_paginas_iniciais`: Validar a função que recorta apenas as N primeiras páginas do PDF original para envio (economizando tokens LLM).
- [ ] `test_ia_classificacao_sucesso`: Mockar resposta esperada JSON da OpenAI e checar se o tipo de documento retornado é associado aos tipos conhecidos.
- [ ] `test_ia_classificacao_desconhecido`: Mockar resposta para um tipo não mapeado e verificar se a rotina salva um registro de "Status Pendente" no DB para curadoria.

## 4. Testes - Mapeamento Automático e Fallback
- [ ] `test_map_ancora_textual_encontrada`: Validar a localização do texto principal e extração de coordenadas baseadas no dicionário do Tipo Doc.
- [ ] `test_map_fallback_coordenadas`: Simular falha na busca da âncora textual e certificar-se de que o fallback para as coordenadas fixas (cadastradas) entra em ação.
- [ ] `test_map_falha_total_slide_branco`: Testar cenário extremo onde tanto a âncora quanto as coordenadas falham, devendo retornar slide vazio sem quebrar a execução.
- [ ] `test_auditoria_logs_gerados`: Certificar que o `audit.jsonl` está recebendo o histórico da decisão de busca (resultados Textract, LLM Classifier, âncoras/fallback).

## 5. Testes - Edição de Slides e Ferramenta Visual de Recorte
- [ ] `test_substituir_texto_slide`: Testar função capaz de sobrescrever blocos de texto especificos na estrutura de slide em memória.
- [ ] `test_substituir_imagem_slide`: Validar inserção direta de file image na estrutura do Pptx, mantendo dimensões no slide.
- [ ] `test_cropper_persistencia_upload`: Subir arquivo (PDF/Imagem) e checar a gravação correta no pacote/pasta de cache do respectivo CNPJ, permitindo re-uso e sub-crops no frontend.
- [ ] `test_regerar_slide_acao`: Acionar endpoint simulado que envia as novas coordenadas X, Y, W, H, executando o recorte do arquivo do cache temporário e substituindo a imagem de preview.
- [ ] `test_ui_streamlit_gerador` (Opcional): Usar `AppTest` para navegar entre páginas, checar renderização de inputs no carrossel de previews e botões `.pdf` / `.pptx`.
