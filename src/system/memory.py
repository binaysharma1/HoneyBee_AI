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
            "llm": (
                {
                    "provider": "openai",
                    "config": {
                        "model": config.NVIDIA_MODEL,
                        "openai_base_url": config.NVIDIA_BASE_URL,
                        "api_key": config.NVIDIA_API_KEY,
                    },
                }
                if config.PROVIDER == "nvidia"
                else (
                    {
                        "provider": "openai",
                        "config": {
                            "model": config.GROQ_MODEL,
                            "openai_base_url": config.GROQ_BASE_URL,
                            "api_key": config.GROQ_API_KEY,
                        },
                    }
                    if config.PROVIDER == "groq"
                    else {
                        "provider": "lmstudio",
                        "config": {
                            "model": config.MODEL,
                            "lmstudio_base_url": config.MODEL_URL,
                            "api_key": config.API_KEY,
                            "lmstudio_response_format": {"type": "text"},
                        },
                    }
                )
            ),
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": config.EMBEDDING_MODEL,
                    "openai_base_url": config.EMBEDDING_BASE_URL,
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


_NON_PERSONAL = ("no demographic", "query timestamped", "no information", "no specific", "no personal", "no factual")

def search_memory(user_id: str, query: str, limit: int = 10) -> list[str]:
    mem = _get_memory()
    if mem is None:
        return []
    try:
        results = mem.search(query, filters={"user_id": user_id}, top_k=20)
        items = results.get("results", results) if isinstance(results, dict) else results

        query_words = set(query.lower().split())
        ranked: list[tuple[float, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            text = item.get("memory") or item.get("data")
            if not text or any(bad in text.lower() for bad in _NON_PERSONAL):
                continue
            boost = 0.0
            fact_words = set(text.lower().split())
            boost += 0.2 * len(query_words & fact_words)
            ranked.append((float(item.get("score", 0)) + boost, text))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in ranked[:limit]]
    except Exception as exc:  # noqa: BLE001
        logger.warning("mem0 search failed: %s", exc)
        return []


async def extract_facts(user_text: str) -> list[str]:
    from langchain_core.messages import HumanMessage

    from .model import _client

    prompt = (
        "List ONLY concrete facts about the user from this message. "
        "One short fact per line. No explanations, no meta-commentary, no explanations like 'The user...'. "
        "If there are no personal facts, reply with exactly one word: NONE\n\n"
        f"Message:\n{user_text}"
    )
    try:
        result = await _client().ainvoke([HumanMessage(content=prompt)])
        text = result.content if isinstance(result.content, str) else ""
        if not text.strip():
            return []
        meta_noise = (
            "output", "this communication", "the message", "indicate", "implies",
            "seeks information", "initiates interaction", "personal fact", "no specific",
            "no personal", "does not provide", "no factual", "no information", "nothing",
        )
        facts = []
        for line in text.splitlines():
            line = line.strip().lstrip("-•* ").strip()
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("none") or any(bad in lowered for bad in meta_noise):
                continue
            if len(line) > 80:  # real facts are short; explanations are not
                continue
            facts.append(line)
        return facts[:10]
    except Exception as exc:  # noqa: BLE001
        logger.warning("fact extraction failed: %s", exc)
        return []


MAX_FACTS_PER_USER = 500


def _user_facts(user_id: str) -> list[dict]:
    """Read this user's stored facts straight from Postgres."""
    try:
        from sqlalchemy import text

        from .database import SessionLocal

        with SessionLocal() as db:
            rows = db.execute(
                text("SELECT id, payload->>'data' AS data, payload->>'created_at' AS created_at FROM honeybee_memories WHERE payload->>'user_id' = :uid ORDER BY payload->>'created_at' DESC"),
                {"uid": user_id},
            ).fetchall()
            return [{"id": r.id, "data": r.data, "created_at": r.created_at} for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("mem0 table read failed: %s", exc)
        return []


def _delete_fact_ids(ids: list) -> None:
    if not ids:
        return
    try:
        from sqlalchemy import text

        from .database import SessionLocal

        with SessionLocal() as db:
            db.execute(text("DELETE FROM honeybee_memories WHERE id = ANY(:ids)"), {"ids": ids})
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("mem0 delete failed: %s", exc)


async def add_memory(user_id: str, text: str) -> None:
    mem = _get_memory()
    if mem is None:
        return

    # extract only facts — raw conversation dumps would bloat the vector index
    facts = await extract_facts(text)
    if not facts:
        return

    existing = _user_facts(user_id)

    existing_norms = [e["data"].strip().lower() for e in existing if e["data"]]

    from difflib import SequenceMatcher

    def _similar(norm: str, e: str) -> bool:
        norm_words = set(norm.replace(":", " ").split())
        e_words = set(e.replace(":", " ").split())
        if norm in e or e in norm:
            return True
        if norm_words and e_words:
            overlap = len(norm_words & e_words) / max(len(norm_words | e_words), 1)
            if overlap >= 0.5:
                return True
        return SequenceMatcher(None, norm, e).ratio() >= 0.72

    for fact in facts:
        norm = fact.strip().lower()
        if any(_similar(norm, e) for e in existing_norms):
            continue
        try:
            mem.add(fact, user_id=user_id, infer=False)
            existing_norms.append(norm)
        except Exception as exc:  # noqa: BLE001
            logger.warning("mem0 add failed: %s", exc)

    # cap table noise: drop the oldest beyond MAX_FACTS_PER_USER
    fresh = _user_facts(user_id)
    if len(fresh) > MAX_FACTS_PER_USER:
        _delete_fact_ids([f["id"] for f in fresh[MAX_FACTS_PER_USER:]])


def list_memories(user_id: str) -> list[dict]:
    return _user_facts(user_id)


def delete_memory(user_id: str, memory_id: str) -> bool:
    from sqlalchemy import text

    from .database import SessionLocal

    with SessionLocal() as db:
        res = db.execute(
            text("DELETE FROM honeybee_memories WHERE id = :id AND payload->>'user_id' = :uid"),
            {"id": memory_id, "uid": user_id},
        )
        db.commit()
        return res.rowcount > 0


def clear_memories(user_id: str) -> None:
    from sqlalchemy import text

    from .database import SessionLocal

    with SessionLocal() as db:
        db.execute(text("DELETE FROM honeybee_memories WHERE payload->>'user_id' = :uid"), {"uid": user_id})
        db.commit()
