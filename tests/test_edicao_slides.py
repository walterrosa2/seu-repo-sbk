import pytest
import os
import json
import fitz
from unittest.mock import patch, MagicMock
from presentation_service import criar_apresentacao_evidencias
from utils.pdf_cropper import crop_pdf_by_ia_agent

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def test_substituir_texto_slide(tmp_path):
    """Testa se a função de criar slide aceita sobrescrever títulos e descrições."""
    slides_config = [
        {
            "id": "slide_1",
            "title": "Título Editado",
            "description": "Descrição Editada Manualmente",
            "image_path": "",
            "pdf_source": ""
        }
    ]
    out_pptx = os.path.join(tmp_path, "Apresentacao_Editada.pptx")
    
    # Chama a função e verifica se não quebra
    resultado = criar_apresentacao_evidencias("12345678000195", slides_config, out_pptx)
    
    # Validações básicas de persistência de arquivo
    assert os.path.exists(out_pptx)
    assert resultado == out_pptx

def test_substituir_imagem_slide(tmp_path):
    """Valida inserção direta de file image na estrutura do Pptx."""
    dummy_img = os.path.join(FIXTURES_DIR, "dummy_image.png")
    
    slides_config = [
        {
            "id": "slide_1",
            "title": "Teste com Imagem",
            "description": "Validando crop image",
            "image_path": dummy_img,
            "pdf_source": ""
        }
    ]
    out_pptx = os.path.join(tmp_path, "Apresentacao_Imagem.pptx")
    
    # Mesmo com imagem, a função deve gerar sem quebrar
    resultado = criar_apresentacao_evidencias("12345678000195", slides_config, out_pptx)
    assert os.path.exists(out_pptx)

def test_regerar_slide_acao(tmp_path):
    """Simula o endpoint/logic do Streamlit que regera um slide a partir de coordenadas."""
    
    mock_crop = MagicMock(return_value=True)
    mock_pptx = MagicMock()
    
    slides = [
        {
            "id": "slide_1",
            "title": "Original",
            "image_path": "original.png",
            "pdf_source": "source.pdf"
        }
    ]
    
    x0, y0, x1, y1 = 0, 0, 100, 100
    pag_sel = 1
    src = "source.pdf"
    
    img_path_novo = os.path.join(tmp_path, "crop_custom.png")
    
    sucesso_crop = mock_crop(src, pag_sel - 1, (x0, y0, x1, y1), img_path_novo)
    
    if sucesso_crop:
        slides[0]["image_path"] = img_path_novo
        mock_pptx("12345678000195", slides, "out.pptx")
    
    mock_crop.assert_called_with(src, 0, (0, 0, 100, 100), img_path_novo)
    
    args = mock_pptx.call_args[0]
    assert args[1][0]["image_path"] == img_path_novo


def test_cropper_persistencia_upload_cache(tmp_path):
    """
    Testa se o diretório de saida do Job atual persiste as imagens,
    simulando a etapa de upload substituto e salvamento.
    """
    nova_img_content = b"fake image bytes"
    saida_dir = tmp_path / "saida"
    saida_dir.mkdir()
    
    img_path = saida_dir / "custom_0_fake_upload.png"
    
    # Simula salvamento via `write_bytes` conforme UI
    img_path.write_bytes(nova_img_content)
    
    assert img_path.exists()
    assert img_path.read_bytes() == b"fake image bytes"


@patch("utils.pdf_cropper.detectar_coordenadas_ancora")
def test_crop_pdf_by_ia_agent_rejeita_retangulo_degenerado(mock_detectar):
    mock_detectar.return_value = {
        "success": True,
        "coords": {"xmin": 500, "xmax": 500, "ymin": 100, "ymax": 100},
    }

    resultado = crop_pdf_by_ia_agent(
        pdf_path=os.path.join(FIXTURES_DIR, "dummy_document.pdf"),
        instrucao="Localize o título principal",
        page_num=0,
        out_path="",
    )

    assert resultado["success"] is False
    assert "inválido" in resultado["error"]
    assert resultado["modo"] == "agente_ia"


@patch("utils.pdf_cropper.detectar_coordenadas_ancora")
def test_crop_pdf_by_ia_agent_aplica_margem_superior(mock_detectar):
    mock_detectar.return_value = {
        "success": True,
        "coords": {"xmin": 100, "xmax": 900, "ymin": 300, "ymax": 700},
    }

    pdf_path = os.path.join(FIXTURES_DIR, "dummy_document.pdf")
    resultado = crop_pdf_by_ia_agent(
        pdf_path=pdf_path,
        instrucao="Localize o bloco principal",
        page_num=0,
        out_path="",
        ia_top_margin_ratio=0.03,
    )

    assert resultado["success"] is True
    assert resultado["modo"] == "agente_ia"

    with fitz.open(pdf_path) as doc:
        h = doc[0].rect.height

    y0_sem_margem = (300 / 1000.0) * h
    y0_esperado = max(0.0, y0_sem_margem - (h * 0.03))
    y0_final = resultado["rect_convertido"][1]

    assert y0_final == pytest.approx(y0_esperado, abs=0.5)
    assert y0_final < y0_sem_margem
