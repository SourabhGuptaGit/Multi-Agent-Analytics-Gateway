import os
from dotenv import load_dotenv

# Load .env file (optional)
load_dotenv()

class Settings:
    """
    Global configuration object.
    - Handles environment variables
    - Provides LLM selection logic
    - Stores global constants + paths
    """

    # -----------------------
    # PATH SETTINGS
    # -----------------------
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    DATA_RAW = os.path.join(PROJECT_ROOT, "data", "raw")
    DATA_PROCESSED = os.path.join(PROJECT_ROOT, "data", "processed")
    DATA_METADATA = os.path.join(PROJECT_ROOT, "data", "metadata")
    DUCKDB_PATH = os.path.join(PROJECT_ROOT, "data", "retail.duckdb")

    # -----------------------
    # API KEYS
    # -----------------------
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Future support (local LLM)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # -----------------------
    # DEFAULT LLM PROVIDER
    # -----------------------
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  
    # Can be: openai | gemini | ollama

    # -----------------------
    # MODELS
    # -----------------------
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    # -----------------------
    # FAISS VECTOR SETTINGS
    # -----------------------
    VECTOR_DIM = 768  # sentence-transformers default
    INDEX_PATH = os.path.join(DATA_METADATA, "faiss_index.bin")

    def get_llm_type(self):
        """
        Returns a string representing the selected LLM provider.
        """
        provider = self.LLM_PROVIDER.lower()

        if provider not in ["openai", "gemini", "ollama"]:
            raise ValueError(f"Invalid LLM provider: {provider}")

        return provider
    
    # -----------------------
    # LOGGING SETTINGS
    # -----------------------
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")  # DEBUG | INFO | WARNING | ERROR
    LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "logs", "app.log")



# Create a global settings instance to import anywhere
settings = Settings()
