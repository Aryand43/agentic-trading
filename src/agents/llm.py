"""Minimal OpenAI chat helper. No LangChain."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def llm_chat(
    system: str,
    user: str,
    *,
    model: str = "gpt-4o-mini",
    temperature: float = 0.4,
    timeout: int = 60,
) -> str | None:
    """Return assistant text, or None if unset / network / parse failure."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    url = base.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": os.environ.get("OPENAI_MODEL", model),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
        return payload["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError, OSError):
        return None
