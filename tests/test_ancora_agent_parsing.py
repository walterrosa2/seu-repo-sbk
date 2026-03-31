import pytest

from utils.ancora_agent import _extract_json_object


def test_extract_json_object_from_plain_json():
    payload = '{"ymin": 100, "xmin": 0, "ymax": 900, "xmax": 1000}'
    parsed = _extract_json_object(payload)
    assert parsed == {"ymin": 100, "xmin": 0, "ymax": 900, "xmax": 1000}


def test_extract_json_object_from_markdown_block():
    payload = "```json\n{\"ymin\": 1, \"xmin\": 2, \"ymax\": 3, \"xmax\": 4}\n```"
    parsed = _extract_json_object(payload)
    assert parsed == {"ymin": 1, "xmin": 2, "ymax": 3, "xmax": 4}


def test_extract_json_object_from_text_wrapped_payload():
    payload = (
        "Achei a area. Coordenadas abaixo:\n"
        "{\"ymin\": 150, \"xmin\": 50, \"ymax\": 600, \"xmax\": 950}\n"
        "Fim."
    )
    parsed = _extract_json_object(payload)
    assert parsed["ymin"] == 150
    assert parsed["xmax"] == 950


def test_extract_json_object_raises_for_empty_response():
    with pytest.raises(ValueError, match="Resposta vazia da IA"):
        _extract_json_object("   ")
