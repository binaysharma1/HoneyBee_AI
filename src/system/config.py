from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import os


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


DATABASE_URL = _env(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:funk@127.0.0.1:5432/HoneyBee_ai",
)

JWT_SECRET = _env("JWT_SECRET", "honeybee-dev-secret-change-me")
JWT_ALGORITHM = _env("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_DAYS = int(_env("JWT_EXPIRE_DAYS", "7"))

MODEL = _env("HONEYBEE_MODEL", "phi-3.5-mini-instruct")
MODEL_URL = _env("HONEYBEE_MODEL_URL", "http://127.0.0.1:1234/v1")
API_KEY = _env("HONEYBEE_API_KEY", "lm-studio")

EMBEDDING_MODEL = _env("HONEYBEE_EMBEDDING_MODEL", "text-embedding-embeddinggemma-300m-qat")
EMBEDDING_DIMS = int(_env("HONEYBEE_EMBEDDING_DIMS", "768"))
