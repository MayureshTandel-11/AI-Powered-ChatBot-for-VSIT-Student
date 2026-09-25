"""LLM provider integration for grounded answer generation."""

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are the AI Student Assistant for the college.

Your job is to help students understand college-related information using the provided knowledge context.

Students may ask questions in many different ways. Interpret their intent and wording naturally.

The question may be:
- direct
- conversational
- vague
- broad
- paraphrased
- informal
- a follow-up question

Use the retrieved college context to answer.

For broad questions, summarize the most relevant information instead of requiring an exact matching sentence.

For follow-up questions, use recent conversation context when provided.

Do not invent college-specific facts.

If the provided context does not contain enough information, say that the information is not available in the college knowledge base.

Do not pretend to know official college information that was not provided.

Keep responses concise and student-friendly."""


NO_CONTEXT_ANSWER = (
    "I couldn't find this information in the college knowledge base. "
    "Please contact the relevant college department for the latest information."
)


class LLMServiceError(Exception):
    def __init__(self, message: str, status_code: int = 503) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def build_rag_user_prompt(
    question: str,
    context: str,
    *,
    conversation_context: str = "",
    is_broad: bool = False,
) -> str:
    sections = [f"College knowledge context:\n{context}"]

    if conversation_context.strip():
        sections.append(f"Recent conversation:\n{conversation_context.strip()}")

    sections.append(f"Student question:\n{question.strip()}")

    instruction = "Provide a grounded answer using only the college knowledge context above."
    if is_broad:
        instruction += " Summarize the most relevant aspects as a concise overview."
    if conversation_context.strip():
        instruction += " Treat follow-up questions in light of the recent conversation."

    sections.append(instruction)
    return "\n\n".join(sections)


def generate_completion(system_prompt: str, user_prompt: str) -> str:
    """Generate a completion using the configured LLM provider."""
    if not settings.llm_api_key:
        raise LLMServiceError(
            "LLM service is not configured. Set LLM_API_KEY in your backend .env file.",
            status_code=503,
        )

    provider = settings.llm_provider.lower()
    if provider in {"openai", "groq"}:
        return _generate_openai_compatible(system_prompt, user_prompt)

    if settings.llm_api_key.startswith("gsk_"):
        raise LLMServiceError(
            "LLM API key appears to be a Groq key. Set LLM_PROVIDER=groq and "
            "LLM_BASE_URL=https://api.groq.com/openai/v1 in backend/.env.",
            status_code=503,
        )

    raise LLMServiceError(
        f"Unsupported LLM provider: {settings.llm_provider}. Supported providers: openai, groq.",
        status_code=503,
    )


def _generate_openai_compatible(system_prompt: str, user_prompt: str) -> str:
    try:
        url = settings.llm_chat_completions_url
    except ValueError as exc:
        raise LLMServiceError(str(exc), status_code=503) from exc
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
        status_code = exc.response.status_code
        logger.error(
            "LLM API HTTP error | provider=%s model=%s status=%s",
            settings.llm_provider,
            settings.llm_model,
            status_code,
        )
        if status_code in {401, 403}:
            raise LLMServiceError(
                "LLM API authentication failed. Verify LLM_API_KEY, LLM_PROVIDER, and LLM_BASE_URL.",
                status_code=503,
            ) from exc
        if status_code == 404:
            raise LLMServiceError(
                f"LLM model '{settings.llm_model}' was not found for provider '{settings.llm_provider}'.",
                status_code=503,
            ) from exc
        raise LLMServiceError("LLM API request failed", status_code=502) from exc
    except httpx.RequestError as exc:
        logger.error("LLM API connection error: %s", exc)
        raise LLMServiceError("Unable to reach LLM API", status_code=503) from exc
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Unexpected LLM response format: %s", exc)
        raise LLMServiceError("Invalid response from LLM API", status_code=502) from exc
