import json
import re

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


def chat_json(prompt: str) -> dict:
    """Send prompt to Ollama and return parsed JSON object. Raises on failure."""
    r = httpx.post(
        f"{config.OLLAMA_BASE_URL}/api/chat",
        json={
            "model": config.OLLAMA_CHAT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        },
        timeout=300.0,
    )
    r.raise_for_status()
    content = r.json()["message"]["content"]
    return _parse_json(content)
