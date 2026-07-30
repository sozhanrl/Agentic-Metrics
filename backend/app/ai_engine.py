"""
Optional LLM narrative layer.

The core prioritization logic in recommendation_engine.py is fully
deterministic and explainable on its own - it does not require this
module to function. This module is an optional enhancement: if an
ANTHROPIC_API_KEY is present in the environment, it rewrites the
templated explanation into a more natural, advisory tone while
preserving every factual claim from the reasoning trail.

If no key is configured, callers should just use the templated
explanation from recommendation_engine.py directly - nothing breaks.
"""

import os
import httpx

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"


def is_enabled() -> bool:
    return bool(ANTHROPIC_API_KEY)


def narrate_recommendation(title: str, explanation: str, reasoning_trail: list[str]) -> str:
    """
    Returns a more natural-language explanation grounded strictly in the
    reasoning trail. Falls back to the original explanation on any error
    so a flaky network call never breaks recommendation generation.
    """
    if not is_enabled():
        return explanation

    trail_text = "\n".join(f"- {line}" for line in reasoning_trail)

    prompt = (
        "You are writing a one or two sentence advisory note for an engineering "
        "manager, based ONLY on the facts below. Do not invent numbers or claims "
        "not present in the facts. Be direct and actionable.\n\n"
        f"Finding: {title}\n\nSupporting facts:\n{trail_text}"
    )

    try:
        response = httpx.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        narrated = " ".join(text_blocks).strip()
        return narrated or explanation
    except Exception:
        return explanation
