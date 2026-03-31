import pytest
import os
from unittest.mock import patch, MagicMock
from classificador_ia import (
    extrair_texto_paginas_iniciais,
    classificar_documento,
    texto_tem_conteudo_util,
    inferir_tipo_por_nome_arquivo,
    montar_contexto_classificacao,
    montar_prompt_classificacao,
)

# Path para os fixtures
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def test_extracao_paginas_iniciais():
    """Valida a extração de texto limitando às primeiras N páginas."""
    pdf_path = os.path.join(FIXTURES_DIR, "dummy_document_multipage.pdf")
    
    # Se o fixture não existir, pular ou mockar, mas a gente espera que o script tenha gerado
    if not os.path.exists(pdf_path):
        pytest.skip("Fixture PDF ausente.")
        
    texto = extrair_texto_paginas_iniciais(pdf_path, num_paginas=2)
    # Verifica se extraiu conteúdo
    assert "Dummy PDF Content for Testing - Page 1" in texto
    assert "SERASA" in texto
    # Garante que só extraiu 2 páginas (se existissem 10)
    assert len(texto) > 0

@patch("classificador_ia.extrair_texto_paginas_iniciais")
@patch("classificador_ia.get_openai_client")
def test_ia_classificacao_sucesso(mock_get_client, mock_extracao):
    """Testa a classificação retornando um tipo CONHECIDO."""
    mock_extracao.return_value = "Texto simulado do topo de um documento Serasa PJ."
    
    # Setup mock do cliente e da resposta da IA
    mock_client = MagicMock()
    mock_openai = mock_client.chat.completions.create
    mock_get_client.return_value = mock_client
    
    # Setup mock da resposta da IA
    mock_choice = MagicMock()
    mock_choice.message.content = "Serasa PJ"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_openai.return_value = mock_response
    
    pdf_path = os.path.join(FIXTURES_DIR, "serasa_pj_fake.pdf")
    tipo, contexto = classificar_documento(pdf_path)
    
    assert tipo == "Serasa PJ"
    assert "Nome original do arquivo PDF: serasa_pj_fake.pdf" in contexto
    assert "Texto simulado do topo de um documento Serasa PJ" in contexto
    mock_openai.assert_called_once()
    payload = mock_openai.call_args.kwargs["messages"]
    assert payload[0]["role"] == "system"
    assert "nome original do arquivo pdf" in payload[0]["content"].lower()
    assert payload[1]["content"] == contexto
    assert "serasa_pj_fake.pdf" in payload[1]["content"]


@patch("classificador_ia.extrair_texto_paginas_iniciais")
@patch("classificador_ia.get_openai_client")
@patch("classificador_ia.save_config")
@patch("classificador_ia.load_config")
def test_ia_classificacao_desconhecido(mock_load_config, mock_save_config, mock_get_client, mock_extracao):
    """Testa a classificação de um novo tipo e garante que adicione na base com status pendente."""
    mock_extracao.return_value = "Texto simulado de Relatorio de Credito Personalizado"
    
    # Simular base local sem o novo tipo
    mock_load_config.return_value = {"Serasa PJ": {}}
    
    # Setup mock do cliente e da resposta da IA
    mock_client = MagicMock()
    mock_openai = mock_client.chat.completions.create
    mock_get_client.return_value = mock_client
    
    # Setup mock da resposta da IA (Tipo Novo)
    mock_choice = MagicMock()
    mock_choice.message.content = "Relatório de Crédito Personalizado"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_openai.return_value = mock_response
    
    tipo, contexto = classificar_documento(os.path.join(FIXTURES_DIR, "balanco_personalizado_fake.pdf"))
    
    assert tipo == "Relatório de Crédito Personalizado"
    assert "balanco_personalizado_fake.pdf" in contexto
    
    # Garante que o método save_config foi chamado para salvar esse tipo novo
    mock_save_config.assert_called_once()
    
    # Avalia o JSON/Dictionary gravado
    args, kwargs = mock_save_config.call_args
    config_salva = args[0]
    
    assert "Relatório de Crédito Personalizado" in config_salva
    assert config_salva["Relatório de Crédito Personalizado"]["exibir_usuario"] is False
    assert "relatório_de_crédito_personalizado_auto" in config_salva["Relatório de Crédito Personalizado"]["slides"][0]["id"]


def test_prompt_classificacao_menciona_nome_do_arquivo():
    prompt = montar_prompt_classificacao(["Serasa PJ", "IRPF Sócio"])

    assert "nome original do arquivo pdf" in prompt.lower()
    assert "fonte relevante" in prompt.lower()
    assert "Serasa PJ" in prompt
    assert "IRPF Sócio" in prompt


def test_contexto_classificacao_inclui_nome_e_texto():
    contexto = montar_contexto_classificacao(
        os.path.join(FIXTURES_DIR, "IRPF_socio_2025.pdf"),
        "Linha 1\nLinha 2"
    )

    assert "Nome original do arquivo PDF: IRPF_socio_2025.pdf" in contexto
    assert "Considere o nome do arquivo como uma pista relevante" in contexto
    assert "Linha 1" in contexto


def test_texto_tem_conteudo_util():
    assert texto_tem_conteudo_util("Relatório de comportamento financeiro do cliente com dados suficientes.")
    assert not texto_tem_conteudo_util("")
    assert not texto_tem_conteudo_util("123")


def test_inferir_tipo_por_nome_arquivo():
    tipos = ["Serasa PJ", "IRPF Sócio", "VADU"]

    assert inferir_tipo_por_nome_arquivo("4 - JULIANE-IRPF-2023-2024-DEC.pdf", tipos) == "IRPF Sócio"
    assert inferir_tipo_por_nome_arquivo("5.1 - SERASA ATHENA.pdf", tipos) == "Serasa PJ"
    assert inferir_tipo_por_nome_arquivo("7 - VADU JS.pdf", tipos) == "VADU"


@patch("classificador_ia._classificar_via_texto")
@patch("classificador_ia.extrair_texto_ocr_paginas_iniciais")
@patch("classificador_ia.extrair_texto_paginas_iniciais")
@patch("classificador_ia.load_config")
def test_classificacao_usa_ocr_quando_texto_nativo_esta_vazio(mock_load_config, mock_texto_nativo, mock_ocr, mock_classifica_texto):
    mock_load_config.return_value = {"Serasa PJ": {}, "IRPF Sócio": {}, "VADU": {}}
    mock_texto_nativo.return_value = ""
    mock_ocr.return_value = "DECLARACAO DE AJUSTE ANUAL IMPOSTO SOBRE A RENDA DA PESSOA FISICA"
    mock_classifica_texto.return_value = ("IRPF Sócio", "contexto ocr")

    tipo, contexto = classificar_documento(os.path.join(FIXTURES_DIR, "4 - JULIANE-IRPF-2023-2024-DEC.pdf"))

    assert tipo == "IRPF Sócio"
    assert contexto == "contexto ocr"
    assert mock_ocr.called
    assert mock_classifica_texto.call_args.kwargs["estrategia"] == "ocr_paginas_iniciais"


@patch("classificador_ia._classificar_via_vision")
@patch("classificador_ia.extrair_texto_ocr_paginas_iniciais")
@patch("classificador_ia.extrair_texto_paginas_iniciais")
@patch("classificador_ia.load_config")
def test_classificacao_usa_vision_como_fallback(mock_load_config, mock_texto_nativo, mock_ocr, mock_vision):
    mock_load_config.return_value = {"Serasa PJ": {}, "IRPF Sócio": {}, "VADU": {}}
    mock_texto_nativo.return_value = ""
    mock_ocr.return_value = ""
    mock_vision.return_value = ("IRPF Sócio", "contexto vision")

    tipo, contexto = classificar_documento(os.path.join(FIXTURES_DIR, "4 - JULIANE-IRPF-2023-2024-DEC.pdf"))

    assert tipo == "IRPF Sócio"
    assert contexto == "contexto vision"
    assert mock_vision.called
