"""Lightweight real-time lookup via a public, open web endpoint.

Uses Wikipedia's opensearch + page summary API so we don't need an API key.
Results are formatted as sources for the LLM to cite.
"""

from __future__ import annotations

import logging
from typing import Any

from ddgs import DDGS

logger = logging.getLogger("honeybee.web")

USER_AGENT = "HoneybeeAI/1.0"


def _fetch(url: str, timeout: int = 8) -> bytes:
    # DuckDuckGo result page URLs are fetched by the ddgs package itself
    return b""


def search_web(query: str, limit: int = 3) -> list[dict[str, Any]]:
    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(query, max_results=limit))
            return [
                {
                    "title": h.get("title", ""),
                    "url": h.get("href", ""),
                    "excerpt": h.get("body", h.get("snippet", "")),
                }
                for h in hits
            ]
    except Exception as exc:
        logger.warning("web search failed: %s", exc)
        return []


def format_web_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No relevant web results were found."
    parts = []
    for idx, item in enumerate(results, start=1):
        parts.append(
            f"[{idx}] {item['title']}\n"
            f"  URL: {item['url']}\n"
            f"  Excerpt: {item['excerpt']}"
        )
    return "\n\n".join(parts)
