import os
import pytest
from unittest.mock import patch, MagicMock

class ObjDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

import sys
mock_st = MagicMock()
mock_st.session_state = ObjDict({
    "authenticated": True,
    "user_info": {"username": "testuser"},
    "usar_antigo": "Não",
    "fazer_extracao": "Não",
    "run_full": True,
    "cnpj": "12345678000195",
    "cfg_tipo": "Serasa PJ"
})
def mock_columns(args, *pargs, **kwargs):
    if isinstance(args, int):
        return [MagicMock() for _ in range(args)]
    elif isinstance(args, list) or isinstance(args, tuple):
        return [MagicMock() for _ in range(len(args))]
    return [MagicMock()]

mock_st.columns.side_effect = mock_columns

def mock_selectbox(label, options, *args, **kwargs):
    if options and hasattr(options, "__iter__") and not isinstance(options, str):
        return options[0]
    return "Serasa PJ"

mock_st.selectbox.side_effect = mock_selectbox
mock_st.radio.return_value = "Detalhamento IA (Full)"
sys.modules["streamlit"] = mock_st

@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Ensure no real API keys are used during testing."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "dummy_access_key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "dummy_secret_key")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy_openai_key")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "postgres")
    monkeypatch.setenv("POSTGRES_DB", "postgres")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")

@pytest.fixture
def mock_s3_client():
    """Mock boto3 S3 client."""
    with patch("boto3.client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_textract_client():
    """Mock boto3 Textract client."""
    with patch("boto3.client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    with patch("openai.OpenAI") as mock_openai:
        mock_instance = MagicMock()
        mock_openai.return_value = mock_instance
        yield mock_instance
