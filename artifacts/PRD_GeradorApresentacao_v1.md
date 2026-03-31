# PRD - Módulo de Apresentação de Evidências

[Sequencia correta de uso:

1 - Coloca numero do cnpj (caso exista na base vai mostrar a pergunta "Deseja reutilizar os dados anteriores?" vai usar os arquivos txt extraidos pelo serviço AWS na execução anterior, caso não exista na base vai mostrar a pergunta "Deseja fazer a extração dos arquivos pdf?" se sim, vai usar o serviço AWS para extrair os arquivos txt)
2 - Caso a modalidade seja somente geracao de apresentacao, não será obrigatorio o preenchimento do campo email
3 - Usuario vai selecionar um ou mais arquivos para fazer upload
4 - Clica em iniciar o processamento
5 - Clica na aba de apresentacao
6 - Aqui devo mostrar a previa dos slides, ou seja, na tela devemos visualizar os slides gerados, com os textos e imagens recortadas, e devemos ter um botao para fazer o download do arquivo pptx e pdf
6.1 - A visualização previa dos slides deve possibilitar os requisitos 7 a 7.3
7 - Caso os dados e imagens dos slides não estejam corretos, o usuario deve poder editar os textos e imagens dos slides, no caso das imagens, o usuario deve poder fazer o upload de uma nova imagem, ou fazer o recorte da imagem original (usando a ferramenta de recorte de imagem), ou fazer o upload de uma nova imagem/pdf e usar a ferramenta de recorte de imagem para recortar a imagem/pdf e usar no slide. Ou seja, a aplicação será um acelerador de montagem de slides pptx
7.1 - Ao fazer o upload dos arquivos pdfs, precisamos avaliar se sera necessario gerar imagens das paginas para usarmos no recorte, ou se podemos usar o pdf original para fazer o recorte (precisamos confirmar o local onde esta sendo salvo para nao gerar erro no momento de editar os slides gerados com o auxiliar visual de recorte). A logica é usarmos os mesmos arquivos originais para recorte, ou seja, se o usuario fizer o upload de um pdf, ele deve ser salvo em algum lugar para que possamos fazer o recorte dele, e se ele fizer o upload de uma imagem, ela deve ser salva em algum lugar para que possamos fazer o recorte dela. E caso tenhamos feito o upload de mais de um arquivo pdf, todos eles devem ser salvos em algum lugar para que possamos fazer o recorte deles. E caso tenhamos feito o upload de mais de uma imagem, todas elas devem ser salvas em algum lugar para que possamos fazer o recorte delas.
7.2 - A seleção de recorte de imagem deve ser feita de forma visual, ou seja, o usuario deve poder selecionar a area que deseja recortar com o mouse, e o sistema deve fazer o recorte da imagem baseado na seleção do usuario. E caso o usuario nao consiga fazer o recorte da imagem, ele deve poder fazer o upload de uma nova imagem e usar a ferramenta de recorte de imagem para recortar a imagem e usar no slide. Ou seja, a aplicação será um acelerador de montagem de slides pptx
7.3 as possibilidades 7.1 e 7.2 devem estar disponiveis para edição de todos os slides gerados (mesmo que tenhamos mais de um slide por tipo de documento)
7.4 A ferramenta de recorte de imagem será usada em todas as paginas, entao precisamos ter a opção de seleção de todas as paginas, atualmente temos de selecionar a pagina no filtro e somente depois fazer a seleção do recorte e isso pode dificultar para o usuario, avalie a melhor estrategia para resolver isso
7.5 Apos a seleção precisamos que a aplicação tenha a opção de regerar o slide com as novas configurações, ou seja, o usuario deve poder fazer o recorte da imagem e clicar em regerar o slide para que a aplicação gere o slide com a nova configuração
7.6 O arquivo pdf gerado apos a execução e/ou ajustes precisa seguir a formatação dos slides, ou seja, é como se fossemos mandar imprimir o slide e vai sair exatamente como o pptx, ou seja, o pdf deve ser gerado a partir do pptx gerado]









# Estrutura inicial
Na tela inicial de upload dos arquivos, precisaremos deixar para o usuario escolher o tipo de execução:
Somente analise de credito (sem geração de apresentação)
Somente geração de apresentação (sem analise de crédito)
Ambas as opções (Analise de crédito + Geração de apresentação)

## 1. Objetivo
Criar um módulo complementar à análise de crédito atual que permita a geração automática e manual de apresentações (PowerPoint e PDF) contendo partes/recortes (evidências) dos documentos originais enviados (ex: Serasa, IRPF, IRPJ) [avalie a pasta execuções e veja quais tipos de documentos temos, e deixe pre cadastrado no sistema. Precisaremos também de uma tela de cadastro de tipos de documentos]. Será interessante que a cada novo tipo de documento tenhamos a inserção automatica do tipo de documento para depois manualmente finalizar o cadastro. Cada evidência será apresentada em um slide contendo um cabeçalho, uma descrição e a imagem recortada.

## 2. Utilizadores
- **Analistas de Crédito / Operadores:** Usuários que interagem com o frontend (Streamlit) para revisar a análise, configurar recortes manuais ou ajustar textos das apresentações antes de exportar o resultado final.

## 3. Requisitos Funcionais e Técnicos

### 3.1. Geração e Formato
- **Formatos de Saída:** 
O sistema deve permitir visualizar o arquivo pptx gerado e o pdf gerado na própria aplicação.
Possibilitar a edição de qualquer slide manualmente usando o recorte de imagem e texto
O sistema deve exportar a apresentação final nos formatos `.pptx` (para ajustes manuais finais) e `.pdf` (documento estático fechado).
- **Identidade Visual:** A apresentação deve adotar o esquema de cores corporativo da SBK Capital (Azul escuro, Cinza, Branco) e incluir a logo fornecida.
- **Estruturação do Slide:** Cada slide deve conter:
  1. Cabeçalho (Título)
  2. Descrição (Contexto corporativo)
  3. Imagem (Recorte da evidência do PDF original)

### 3.2. Configuração de Recortes (Mapeamento)
O sistema deve suportar duas estratégias de mapeamento de evidências, configuráveis por **Tipo de Documento**:
- **Opção 1 (Automática):** 
[Será necessário termos certeza quanto a esse fluxo:
Upload do arquivo pdf ()
Fazer a extração do documento para texto (aws)
Verificação dos tipos de documentos cadastrados (Essa verificação precisa ser feita via agente de IA, enviando o arquivo original para ele verificar qual é o tipo de documento)
Confrontação entre os arquivos uploaded com os tipos de documentos cadastrados, com retorno apontando qual o tipo de documento
Apos buscar as configurações de mapeamento fazer a busca dos termos (Âncora Textual), caso nao localizado será usado a opção de coordenadas fixas no arquivo (avisar o usuario que nao foi possivel encontrar a âncora textual)]
  - Recorte baseado em coordenadas fixas no arquivo.]
  - Recorte dinâmico baseado em âncoras de texto (ex: buscar palavras-chave). 
  - *Comportamento de Falha:* Se a busca falhar, o slide deve ser gerado contendo o cabeçalho e a descrição preenchidos, deixando um espaço em branco para posterior inserção manual da imagem.
- **Opção 2 (Manual):** Interface no frontend (Streamlit) permitindo que o usuário visualize o PDF original e interaja visualmente para determinar a "caixa delimitadora" (Crop) com o mouse ou definir coordenadas para selecionar a imagem da evidência.

### 3.3. Textos Dinâmicos e Descrições
- **Cabeçalhos e Descrições Dinâmicos:** Os textos dos slides podem ser pré-cadastrados contendo variáveis extraídas pela IA durante o processo principal de análise de crédito (ex: `{nome_empresa}`, `{score_serasa}`). Será importante que façamos o mapeamento de todas as variaveis possiveis, a partir do retorno dos agentes analise de credito, e assim disponibilizar as variaveis para o usuario no frontend.
- **Preenchimento das Descrições:** O preenchimento da descrição se dará de forma 100% manual por configuração prévia ou digitação do usuário. A IA não gerará os textos das descrições de forma generativa.

### 3.4. Fluxo de Trabalho (Pipeline)
1. **Entrada e Cadastro:** O processo inicia-se pelo fluxo atual: cadastro da empresa (Nome, CNPJ) e upload dos arquivos PDF. (apos selecionar o metodo de execução - analise de crédito + geracao de apresentacao, analise de crédito, geracao de apresentacao)
2. **Processamento (Análise IA):** Os agentes executam as análises em background e extraem as variáveis necessárias dos documentos.
3. **Mapeamento e Pré-geração:** O sistema aplica as configurações automáticas de recorte e carrega as variáveis extraídas nos cabeçalhos/descrições configurados. O rascunho dos slides (estado) é salvo de forma persistente atrelado àquela execução. (Caso seja selecionado somente a geração de apresentacao, o sistema ira apenas gerar os slides baseados na configuração prévia)

## 3.5. Visual da apresentação
Precisaremos usar skills, metodos, frameworks e bibliotecas que permitam a geração de apresentações (PowerPoint e PDF) contendo partes/recortes (evidências) dos documentos originais enviados (ex: Serasa, IRPF, IRPJ). Cada evidência será apresentada em um slide contendo um cabeçalho, uma descrição e a imagem recortada. E além disso, será de extrema importancia um visual bonito, elegante e sexy dos slides, que chame a atenção do usuário e faça com que ele queira apresentar para o cliente.

4. **Revisão e Geração Final (Frontend):** O usuário acessa o histórico da execução local, podendo:
   - Validar as evidências e os textos gerados automaticamente.
   - Realizar recortes e upload ou delimitação de imagens em slides pendentes (falhas da Opção 1 ou documentos da Opção 2).
   - Exportar a apresentação final validada em PPTX e PDF.

## 4. Limitações e Premissas
- A geração da apresentação de evidências corre de forma modular e separada ao gerador original do Relatório Executivo consolidado (.pdf) de crédito.
- A interação manual de recorte (bounding box) depende de integração customizada avançada no Streamlit (ex: uso de `streamlit-cropper`, `streamlit-image-coordinates`, ou seleção via ranges de páginas). Caso o uso de bounding box interativo via mouse seja instável, pode-se adotar soluções alternativas como recortes baseados no display lado a lado com sliders dimensionais.

## 5. Dados Sensíveis / PII
- As apresentações conterão recortes de documentos originais (IRPF, Serasa, etc.) que possuem alto volume de PII (Dados Pessoais) e dados sensíveis de empresas e sócios (faturamento, dívidas).
- **Segurança:** Arquivos temporários de imagens gerados para renderizar na tela devem obrigatoriamente ser armazenados no contexto local (pasta `saida/` ou em quarentena) e não ficar expostos. Recomenda-se exclusão das imagens intermediárias após a consolidação do `.pptx` ou controle de acesso estrito se armazenado de acordo com a política atual de persistência.
