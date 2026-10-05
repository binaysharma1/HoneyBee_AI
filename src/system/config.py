from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import os


def _env(key: str, default: str | None = None) -> str:
    value = os.getenv(key, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {key} (set it in .env)")
    return value


# All sensitive values come from .env — no secrets in this file.
PROVIDER = _env("HONEYBEE_PROVIDER", "local")

DATABASE_URL = _env("DATABASE_URL")

JWT_SECRET = _env("JWT_SECRET")
JWT_ALGORITHM = _env("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_DAYS = int(_env("JWT_EXPIRE_DAYS", "7"))

MODEL = _env("HONEYBEE_MODEL")
MODEL_URL = _env("HONEYBEE_MODEL_URL")
API_KEY = _env("HONEYBEE_API_KEY")

GROQ_BASE_URL = _env("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_API_KEY = _env("GROQ_API_KEY", "")
GROQ_MODEL = _env("GROQ_MODEL", "openai/gpt-oss-20b")

EMBEDDING_MODEL = _env("HONEYBEE_EMBEDDING_MODEL")
EMBEDDING_DIMS = int(_env("HONEYBEE_EMBEDDING_DIMS", "768"))
EMBEDDING_BASE_URL = _env("HONEYBEE_EMBEDDING_BASE_URL", MODEL_URL)

NVIDIA_BASE_URL = _env("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = _env("NVIDIA_API_KEY", "")
NVIDIA_MODEL = _env("NVIDIA_MODEL", "deepseek-ai/deepseek-v4.1-flash")
