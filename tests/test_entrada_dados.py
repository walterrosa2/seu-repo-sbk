import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime

# Imports de interface_frontend serão movidos para as funções para evitar quebra no import

class ObjDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


@pytest.fixture
def setup_dirs(tmp_path, monkeypatch):
    """Muda o EXEC_ROOT para garantir testes limpos."""
    monkeypatch.setattr("interface_frontend.EXEC_ROOT", tmp_path)
    return tmp_path

def test_ultima_execucao(setup_dirs):
    """Testa se a leitura da última execução para um CNPJ funciona baseando-se no diretório."""
    from interface_frontend import ultima_execucao
    
    cnpj = "12345678000195"
    hoje_str = datetime.now().strftime('%d%m%Y')
    
    # Diretório fictício passado
    dir_antigo = setup_dirs / f"{cnpj}_01012024"
    dir_antigo.mkdir()
    
    ultima = ultima_execucao(cnpj)
    assert ultima is not None
    assert ultima.strftime('%d%m%Y') == "01012024"

@patch("interface_frontend.classificar_documento")
@patch("interface_frontend.extract_one")
@patch("interface_frontend.preparar_pre_processamento")
@patch("interface_frontend.process_manifest_ia1")
@patch("interface_frontend.process_manifest_ia2")
@patch("interface_frontend.gerar_relatorio_final")
@patch("interface_frontend.enviar_relatorio_final")
@patch("interface_frontend.criar_apresentacao_evidencias")
@patch("interface_frontend.criar_apresentacao_pdf")
def test_executar_pipeline_novo_fluxo_completo(mock_pdf, mock_pptx, mock_envio, mock_relatorio, mock_ia2, mock_ia1, mock_pre, mock_extract, mock_classificar, setup_dirs):
    """Simula um CNPJ inédito e submissão completa (Análise + Apresentação)."""
    mock_classificar.return_value = ("Outro", "Texto fictício")
    
    import streamlit as st
    st.session_state["fazer_extracao"] = "Sim"
    mock_envio.return_value = {"ok": True}
    
    # Fake uploaded file
    class FakeFile:
        def __init__(self, name):
            self.name = name
        def getbuffer(self):
            return b"dummy content"
            
    arquivos = [FakeFile("doc1.pdf")]
    
    from interface_frontend import executar_pipeline
    executar_pipeline("12345678000195", "teste@sbk.com", arquivos, "Análise de crédito + Geração de apresentação")
    
    # Assertivas para garantir que o Textract (extract_one) foi chamado porque usar_antigo=Não
    mock_extract.assert_called()
    mock_pre.assert_called()
    mock_ia1.assert_called()
    mock_ia2.assert_called()
    # mock_pptx mock_pdf etc should have been called
    mock_pptx.assert_called()
    mock_envio.assert_called()

@patch("interface_frontend.extract_one")
@patch("interface_frontend.preparar_pre_processamento")
def test_executar_pipeline_reuso_dados(mock_pre, mock_extract, setup_dirs):
    """Testa se usar_antigo = 'Sim' previne a chamada de extração."""
    
    import streamlit as st
    # Ajusta o state para "usar_antigo": "Sim"
    st.session_state["usar_antigo"] = "Sim"
    st.session_state["fazer_extracao"] = "Não" # Forçado logicamente no if
    
    class FakeFile:
        def __init__(self, name):
            self.name = name
        def getbuffer(self):
            return b"dummy"
            
    from interface_frontend import executar_pipeline
    executar_pipeline("12345678000195", "teste@sbk.com", [FakeFile("doc2.pdf")], "Somente geração de apresentação")
    
    # Não deve ter chamado o extrator (Textract) pois o usuário optou por reusar
    # Como fazer_extracao == "Não", mock_extract não deve ser chamado
    mock_extract.assert_not_called()
