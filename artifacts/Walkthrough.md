# Walkthrough: Correção da Substituição de Imagem no Editor de Slides

## O que foi feito
1. Inserido um botão de confirmação `🖼️ Confirmar e Substituir Imagem` logo abaixo do uploader de arquivos na aba **Editor de Slides**.
2. Implementada a lógica de "early return" e "auto-save" para este botão:
   - Salva a imagem no diretório de saída correspondente.
   - Atualiza a referência da imagem no objeto `slide`.
   - Persiste as mudanças no arquivo `slides_config.json`.
   - Regera automaticamente os arquivos PowerPoint (`.pptx`) e PDF (`.pdf`) da apresentação.
   - Realiza o `st.rerun()` para refletir as mudanças na interface.

## Onde no código
As mudanças foram concentradas no ficheiro `interface_frontend.py`, especificamente entre as linhas 1608 e 1635:
- Adição da lógica de persistência para o `nova_img` logo após o `st.file_uploader`.
- Manutenção da lógica original dentro do formulário principal para compatibilidade caso o utilizador prefira "Salvar Tudo" (texto e imagem) de uma vez.

## Como Validar
1. Inicie a aplicação: `.\_start.ps1`
2. Navegue até a aba **🎞️ Apresentação**.
3. Selecione um slide no **Editor de Slides**.
4. Faça o upload de uma nova imagem na área de **Subir Imagem Substituta (Opcional)**.
5. Verifique que agora aparece o botão **🖼️ Confirmar e Substituir Imagem**.
6. Clique no botão e valide que a prévia da imagem é atualizada e o PPTX/PDF são regerados (receberá um toast de sucesso).
