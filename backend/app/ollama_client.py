import json
import re
from typing import Any

import httpx

from app import config

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def ollama_ok() -> bool:
    try:
        r = httpx.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = _FENCE_RE.search(text)
        if m:
            data = json.loads(m.group(1).strip())
        else:
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end <= start:
                raise
            data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Ollama response JSON is not an object")
    return data


def chat_json(
    prompt: str,
    *,
    format_schema: dict[str, Any] | None = None,
    temperature: float = 0.1,
    num_predict: int = 3072,
    num_ctx: int = 16384,
) -> dict:
    """Send prompt to Ollama and return parsed JSON object. Raises on failure.

    Default num_ctx is well above the runner's tiny 4k load — otherwise a long
    JD+transcript prompt fills the window and context-shift makes analyze take
    many minutes (or never finish).
    """
    body: dict[str, Any] = {
        "model": config.OLLAMA_CHAT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You output only valid JSON matching the requested schema. "
                    "Never omit required keys. Never wrap JSON in markdown. "
                    "Keep rationales and lists concise."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": format_schema if format_schema is not None else "json",
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
        },
    }
    r = httpx.post(
        f"{config.OLLAMA_BASE_URL}/api/chat",
        json=body,
        timeout=600.0,
    )
    r.raise_for_status()
    content = r.json()["message"]["content"]
    return _parse_json(content)
