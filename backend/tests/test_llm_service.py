"""LLM service tests with mocked HTTP responses."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.llm_service import LLMServiceError, generate_completion


def test_generate_completion_requires_api_key(monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm_service.settings.llm_api_key", "")
    with pytest.raises(LLMServiceError, match="LLM service is not configured"):
        generate_completion("system", "user")


@patch("app.services.llm_service.httpx.Client")
def test_generate_completion_openai_success(mock_client_cls, monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm_service.settings.llm_api_key", "test-key")
    monkeypatch.setattr("app.services.llm_service.settings.llm_provider", "openai")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", "gpt-4o-mini")
    monkeypatch.setattr("app.services.llm_service.settings.llm_base_url", "")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Grounded college answer."}}]
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    answer = generate_completion("system prompt", "user prompt")
    assert answer == "Grounded college answer."


@patch("app.services.llm_service.httpx.Client")
def test_generate_completion_groq_success(mock_client_cls, monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm_service.settings.llm_api_key", "test-key")
    monkeypatch.setattr("app.services.llm_service.settings.llm_provider", "groq")
    monkeypatch.setattr("app.services.llm_service.settings.llm_model", "llama-3.1-8b-instant")
    monkeypatch.setattr("app.services.llm_service.settings.llm_base_url", "")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Groq grounded answer."}}]
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    answer = generate_completion("system prompt", "user prompt")
    assert answer == "Groq grounded answer."
    assert mock_client.post.call_args.args[0] == "https://api.groq.com/openai/v1/chat/completions"


@patch("app.services.llm_service.httpx.Client")
def test_generate_completion_handles_http_error(mock_client_cls, monkeypatch) -> None:
    monkeypatch.setattr("app.services.llm_service.settings.llm_api_key", "test-key")
    monkeypatch.setattr("app.services.llm_service.settings.llm_provider", "openai")

    mock_response = MagicMock()
    mock_response.text = "Unauthorized"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "error",
        request=MagicMock(),
        response=mock_response,
    )

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    with pytest.raises(LLMServiceError, match="LLM API request failed"):
        generate_completion("system", "user")
