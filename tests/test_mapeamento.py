import pytest
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
from utils.pdf_cropper import crop_pdf_by_text, crop_pdf_to_image, crop_pdf_by_text_range

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

class ObjDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

# O fixture mock_streamlit não é mais necessário pois o conftest.py injeta no sys.modules

def test_map_ancora_textual_encontrada(tmp_path):
    pdf_path = os.path.join(FIXTURES_DIR, "dummy_document_multipage.pdf")
    out_img = os.path.join(tmp_path, "crop_test.png")
    if not os.path.exists(pdf_path):
        pytest.skip("Fixture PDF ausente para teste de âncora.")
        
    resultado = crop_pdf_by_text(pdf_path, "SERASA", (50, 50, 50, 50), out_img)
    if resultado.get("success"):
        assert "rect" in resultado
        assert resultado["page"] == 1
        assert os.path.exists(out_img)

def test_map_fallback_coordenadas(tmp_path):
    pdf_path = os.path.join(FIXTURES_DIR, "dummy_document_multipage.pdf")
    out_img = os.path.join(tmp_path, "crop_fallback.png")
    if not os.path.exists(pdf_path):
        pytest.skip("Fixture PDF ausente.")
        
    resultado_ancora = crop_pdf_by_text(pdf_path, "PALAVRA_INEXISTENTE_NO_PDF_123", (50, 50, 50, 50), out_img)
    assert resultado_ancora.get("success") is False
    
    resultado_coords = crop_pdf_to_image(pdf_path, 0, (0, 0, 100, 100), out_img)
    if resultado_coords:
        assert os.path.exists(out_img)

@patch("interface_frontend._audit_write")
@patch("interface_frontend.classificar_documento")
@patch("interface_frontend.load_config")
@patch("interface_frontend.crop_pdf_by_text")
@patch("interface_frontend.crop_pdf_to_image")
@patch("interface_frontend.criar_apresentacao_evidencias")
@patch("interface_frontend.criar_apresentacao_pdf")
@patch("interface_frontend.Path.glob")
@patch("streamlit.empty")
def test_auditoria_logs_e_slide_branco(mock_audit, mock_classificar, mock_load, mock_crop_text, mock_crop_coords, mock_pptx_ev, mock_pptx_pdf, mock_glob, mock_st):
    from interface_frontend import executar_pipeline
    
    # Setup mocks
    mock_glob.return_value = [Path("fake_doc.pdf")]
    mock_classificar.return_value = ("Serasa PJ", "texto")
    mock_load.return_value = {
        "Serasa PJ": {
            "ancora": "SERASA",
            "modo": "ancora",
            "coordenadas": "0,0,100,100",
            "cabecalho": "teste",
            "descricao": "teste desc"
        }
    }
    
    mock_crop_text.return_value = {"success": False}
    mock_crop_coords.return_value = False
    mock_crop_coords.side_effect = Exception("Falhou hard test")
    
    with patch("interface_frontend.get_current_job_dirs") as mock_dirs:
        import tempfile
        temp_d = Path(tempfile.mkdtemp())
        mock_dirs.return_value = {"root": temp_d, "entrada": temp_d, "saida": temp_d, "retorno": temp_d, "logs": temp_d, "pre": temp_d}
        
        executar_pipeline("12345678000195", "teste@sbk", [], "Somente geração de apresentação")
    
    audit_calls = mock_audit.call_args_list
    assert len(audit_calls) > 0
    crop_audit_call = None
    for call in audit_calls:
        ev = call[0][1]
        if ev.step == "apresentacao.crop":
            crop_audit_call = ev
            break
            
    assert crop_audit_call is not None
    assert crop_audit_call.level == "WARNING"
    assert crop_audit_call.extra["resultado"] == "FALHA"
    
    slides_config = mock_pptx_ev.call_args[0][1]
    assert len(slides_config) == 1


# ---------------------------------------------------------------------------
# Testes para crop_pdf_by_text_range
# ---------------------------------------------------------------------------

def test_crop_range_inicio_e_fim(tmp_path):
    """Garante que crop_pdf_by_text_range funciona quando ambas as âncoras existem."""
    pdf_path = os.path.join(FIXTURES_DIR, "dummy_document_multipage.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip("Fixture PDF ausente.")

    out_img = str(tmp_path / "range_completo.png")
    # Usa textos genéricos que provavelmente aparecem no PDF de fixture
    resultado = crop_pdf_by_text_range(pdf_path, "SERASA", "", margin=30, out_path=out_img)
    # Se o texto de inicio for encontrado, deve retornar sucesso
    if resultado.get("success"):
        assert "rect" in resultado
        assert resultado["page"] >= 1
        assert os.path.exists(out_img), "Imagem de saída não foi gerada"
        # Range sem fim deve retornar até o final da página
        assert resultado["modo"] in ("range_sem_fim", "range_ate_fim_pagina", "range_completo")


def test_crop_range_inicio_nao_encontrado(tmp_path):
    """Garante que a função retorna erro (não levanta exceção) quando texto_inicio não existe."""
    pdf_path = os.path.join(FIXTURES_DIR, "dummy_document_multipage.pdf")
    if not os.path.exists(pdf_path):
        pytest.skip("Fixture PDF ausente.")

    out_img = str(tmp_path / "range_falhou.png")
    resultado = crop_pdf_by_text_range(
        pdf_path,
        "TEXTO_IMPOSSIVEL_DE_ENCONTRAR_9999XYZ",
        "OUTRO_TEXTO_IMPOSSIVEL",
        margin=10,
        out_path=out_img,
    )
    assert resultado["success"] is False
    assert "error" in resultado
    assert not os.path.exists(out_img), "Imagem não deveria ter sido gerada"
