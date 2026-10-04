"""mem0-powered long-term memory on PostgreSQL (pgvector).

Degrades gracefully: if mem0 or the vector extension is unavailable,
the chat still works — memories are simply skipped.
"""

import logging

from . import config

logger = logging.getLogger("honeybee.memory")

_memory = None
_init_failed = False


def _get_memory():
    global _memory, _init_failed
    if _memory is not None or _init_failed:
        return _memory
    try:
        from mem0 import Memory

        _memory = Memory.from_config({
            "llm": {
                "provider": "lmstudio",
                "config": {
                    "model": config.MODEL,
                    "lmstudio_base_url": config.MODEL_URL,
                    "api_key": config.API_KEY,
                    "lmstudio_response_format": {"type": "text"},
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": config.EMBEDDING_MODEL,
                    "openai_base_url": config.MODEL_URL,
                    "api_key": config.API_KEY,
                },
            },
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "connection_string": config.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://"),
                    "collection_name": "honeybee_memories",
                    "embedding_model_dims": config.EMBEDDING_DIMS,
                },
            },
            "history_db_path": ":memory:",
        })
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning("mem0 unavailable, memory disabled: %s", exc)
        _init_failed = True
    return _memory


def add_memory(user_id: str, text: str) -> None:
    mem = _get_memory()
    if mem is None:
        return
    try:
        # infer=False: store the exchange verbatim — the local phi-3.5 model
        # can't handle mem0's JSON fact-extraction prompt within an 8k context.
        mem.add(text, user_id=user_id, infer=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mem0 add failed: %s", exc)


def search_memory(user_id: str, query: str, limit: int = 5) -> list[str]:
    mem = _get_memory()
    if mem is None:
        return []
    try:
        results = mem.search(query, filters={"user_id": user_id}, top_k=limit)
        items = results.get("results", results) if isinstance(results, dict) else results
        return [item["memory"] for item in items if isinstance(item, dict) and item.get("memory")]
    except Exception as exc:  # noqa: BLE001
        logger.warning("mem0 search failed: %s", exc)
        return []
