import os
from dotenv import load_dotenv


# ---------------------------------------------------------
# Load environment variables from .env
# ---------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


class Settings:
    """
    Centralized global configuration loader.

    - Loads environment variables
    - Provides unified LLM model selection
    - Stores file paths, constants, and limits
    - Maintains compatibility across all modules
    """

    # -----------------------------------------------------
    # PATH SETTINGS
    # -----------------------------------------------------
    PROJECT_ROOT = PROJECT_ROOT
    DATA_RAW = os.path.join(PROJECT_ROOT, "data", "raw")
    DATA_PROCESSED = os.path.join(PROJECT_ROOT, "data", "processed")
    DATA_METADATA = os.path.join(PROJECT_ROOT, "data", "metadata")
    DUCKDB_PATH = os.path.join(PROJECT_ROOT, "data", "retail.duckdb")

    # -----------------------------------------------------
    # API KEYS
    # -----------------------------------------------------
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # -----------------------------------------------------
    # LLM SETTINGS
    # -----------------------------------------------------
    # Provider → openai / gemini / ollama
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

    # Model names
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    # Unified model name resolution
    LLM_MODEL_NAME = (
        os.getenv("OPENAI_MODEL")
        or os.getenv("GEMINI_MODEL")
        or os.getenv("OLLAMA_MODEL")
        or GEMINI_MODEL
    )

    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.3))

    # Token limits
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 1024))
    LLM_HARD_TOKEN_CAP = int(os.getenv("LLM_HARD_TOKEN_CAP", 2048))

    # -----------------------------------------------------
    # FAISS VECTOR SETTINGS
    # -----------------------------------------------------
    VECTOR_DIM = 768  # sentence-transformers / all-mpnet-base-v2
    INDEX_PATH = os.path.join(DATA_METADATA, "faiss_index.bin")

    # -----------------------------------------------------
    # LOGGING SETTINGS
    # -----------------------------------------------------
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()  # DEBUG | INFO | WARNING | ERROR
    LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "logs", "app.log")

    # -----------------------------------------------------
    # SQL EXECUTOR SETTINGS
    # -----------------------------------------------------
    MAX_RESULT_ROWS = int(os.getenv("MAX_RESULT_ROWS", 100))

    # -----------------------------------------------------
    # FASTAPI SETTINGS
    # -----------------------------------------------------
    FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")  # must be string
    FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))

    # -----------------------------------------------------
    # GRADIO SETTINGS
    # -----------------------------------------------------
    GRADIO_HOST = os.getenv("GRADIO_HOST", "0.0.0.0")
    GRADIO_PORT = int(os.getenv("GRADIO_PORT", "7860"))

    # -----------------------------------------------------
    # LLM PROVIDER SELECTION
    # -----------------------------------------------------
    def get_llm_type(self) -> str:
        """
        Returns validated LLM provider name.
        Raises ValueError if provider is invalid.
        """
        provider = self.LLM_PROVIDER

        if provider not in ["openai", "gemini", "ollama"]:
            raise ValueError(
                f"Invalid LLM provider: {provider}. Must be: openai | gemini | ollama"
            )

        return provider


settings = Settings()
