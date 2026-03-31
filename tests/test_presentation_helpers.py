import pytest
import os
import json
from pathlib import Path
from utils.presentation_helpers import extract_dynamic_blocks_from_report, inject_variables

def test_extract_dynamic_blocks_from_report_basic():
    mock_md = """
    Alguns textos irrelevantes...
    <bloco>"1_SERASA"
    **Score de Crédito**
    - Score: 750
    - Probabilidade de Inadimplência: Baixa
    
    **Restrições**
    - Nada consta
    </bloco>
    """
    
    result = extract_dynamic_blocks_from_report(mock_md)
    print("Extract result:", result)
    
    # A função mantém o prefixo numérico do bloco e normaliza o nome da seção
    # O bloco "1_SERASA" gera chaves com prefixo "1_serasa."
    score_key = next((k for k in result if "score" in k.lower()), None)
    restricoes_key = next((k for k in result if "restri" in k.lower()), None)
    
    assert score_key is not None, f"Chave de score não encontrada em: {list(result.keys())}"
    assert "750" in result[score_key]
    
    assert restricoes_key is not None, f"Chave de restrições não encontrada em: {list(result.keys())}"
    assert "Nada consta" in result[restricoes_key]


def test_extract_dynamic_blocks_from_report_subitem_format():
    mock_md = """
    <bloco>"VADU_123"
    Subitem => v_socios
    O sócio principal possui 90% das cotas.
    Subitem => v_fiscal
    Regularidade fiscal atestada.
    </bloco>
    """
    
    result = extract_dynamic_blocks_from_report(mock_md)
    
    assert "vadu_123.v_socios" in result
    assert "90% das cotas" in result["vadu_123.v_socios"]
    
    assert "vadu_123.v_fiscal" in result
    assert "Regularidade fiscal" in result["vadu_123.v_fiscal"]


def test_extract_dynamic_blocks_from_report_resilience():
    # Test block without closing tag, or broken formatting
    mock_md_broken = """
    <bloco>"RELATORIO_FINAL"
    **Conclusao**
    Média
    """
    
    result = extract_dynamic_blocks_from_report(mock_md_broken)
    
    assert "relatorio_final.conclusao" in result
    assert "Média" in result["relatorio_final.conclusao"]

    
def test_inject_variables_success():
    text = "O score do cliente é {serasa.score} e a situação é {vadu.fiscal}."
    variables = {
        "serasa.score": "800",
        "vadu.fiscal": "Regular"
    }
    
    result = inject_variables(text, variables)
    assert result == "O score do cliente é 800 e a situação é Regular."


def test_inject_variables_missing_keys():
    text = "Risco: {risco}, Limite: {limite_aprovado}"
    variables = {
        "risco": "Baixo"
        # limite_aprovado is missing
    }
    
    result = inject_variables(text, variables)
    assert result == "Risco: Baixo, Limite: "

def test_inject_variables_none_values():
    text = "O score é {score}."
    variables = {
        "score": None
    }
    
    result = inject_variables(text, variables)
    assert result == "O score é ."

