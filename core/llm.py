from core.config import settings
from core.utils import logger


# -------------------------------
# SELECT WHICH LLM TO USE
# -------------------------------

def _select_llm_client():
    """
    Returns an LLM client (OpenAI or Gemini) depending on settings.LLM_PROVIDER.
    This allows switching between providers without code changes.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        from openai import OpenAI
        return OpenAI(api_key=settings.OPENAI_API_KEY)

    # elif provider == "gemini":
    #     # Using Google Generative AI client
    #     from google import generativeai as genai
    #     genai.configure(api_key=settings.GEMINI_API_KEY)
    #     return genai

    else:
        raise ValueError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")

# -------------------------------
# EXECUTE MODEL CALL
# -------------------------------

def call_llm(prompt: str) -> str:
    llm = _select_llm_client()
    provider = settings.LLM_PROVIDER.lower()
    logger.info(f"Calling LLM provider: {provider}")

    if provider == "openai":
        response = llm.chat.completions.create(
            model=settings.LLM_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS
        )
        logger.info(f"Token usage: prompt={response.usage.prompt_tokens}, "
                    f"completion={response.usage.completion_tokens}, "
                    f"total={response.usage.total_tokens}")

        return response.choices[0].message.content.strip()

    elif provider == "gemini":
        model = llm.GenerativeModel(settings.LLM_MODEL_NAME)
        response = model.generate_content(prompt)

        # Gemini token usage
        usage = response.usage_metadata
        logger.info(f"Token usage: input={usage.prompt_token_count}, "
                    f"output={usage.candidates_token_count}, "
                    f"total={usage.total_token_count}")

        return response.text.strip()
