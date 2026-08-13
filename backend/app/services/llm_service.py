"""LLM provider integration for grounded answer generation."""

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an AI student assistant for a college.

Answer the student's question using only the provided college knowledge context.
Do not invent college policies, dates, faculty names, fees, rules, or other facts.
If the answer cannot be determined from the provided context, clearly say that the information is not available in the college knowledge base.
When appropriate, recommend that the student contact the relevant college department.
Keep answers concise, clear, and student-friendly."""


class LLMServiceError(Exception):
    def __init__(self, message: str, status_code: int = 503) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def generate_completion(system_prompt: str, user_prompt: str) -> str:
    """Generate a completion using the configured LLM provider."""
    if not settings.llm_api_key:
        raise LLMServiceError("LLM API key is not configured. Set LLM_API_KEY in your environment.")

    provider = settings.llm_provider.lower()
    if provider == "openai":
        return _generate_openai_compatible(system_prompt, user_prompt)
    raise LLMServiceError(f"Unsupported LLM provider: {settings.llm_provider}")


def _generate_openai_compatible(system_prompt: str, user_prompt: str) -> str:
    base_url = settings.llm_base_url.rstrip("/") if settings.llm_base_url else "https://api.openai.com/v1"
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as exc:
        logger.error("LLM API HTTP error: %s", exc.response.text)
        raise LLMServiceError("LLM API request failed", status_code=502) from exc
    except httpx.RequestError as exc:
        logger.error("LLM API connection error: %s", exc)
        raise LLMServiceError("Unable to reach LLM API", status_code=503) from exc
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Unexpected LLM response format: %s", exc)
        raise LLMServiceError("Invalid response from LLM API", status_code=502) from exc
