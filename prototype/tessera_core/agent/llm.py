"""Small OpenRouter client (OpenAI-compatible chat API). Standard library only.

Reads OPENROUTER_API_KEY and OPENROUTER_MODEL from the environment or a .env file in
the project folder. The key is never printed or logged.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"


def load_env(path: Path = Path(__file__).resolve().parent.parent / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Usage:
    """Running totals for one session: feeds cost / latency metrics later."""

    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0
    log: list[dict] = field(default_factory=list)


class LLMError(RuntimeError):
    pass


class OpenRouterLLM:
    def __init__(self, model: str | None = None, timeout: float = 90, retries: int = 2):
        load_env()
        self.key = os.environ.get("OPENROUTER_API_KEY")
        if not self.key:
            raise LLMError("OPENROUTER_API_KEY is not set (put it in .env in the project folder)")
        self.model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.timeout, self.retries = timeout, retries
        self.usage = Usage()

    def chat_json(self, messages: list[dict], step: str = "") -> dict:
        """Send messages, expect one JSON object back. Retries network errors with backoff."""
        body = json.dumps({"model": self.model, "messages": messages, "temperature": 0,
                           "response_format": {"type": "json_object"},
                           "usage": {"include": True}}).encode()
        req = urllib.request.Request(URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
            "X-Title": "Tessera EECE scheduling (503P)"})
        last = None
        for attempt in range(self.retries + 1):
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}"
                if e.code in (400, 401, 402, 403):
                    raise LLMError(last) from None  # not worth retrying
            except (urllib.error.URLError, TimeoutError) as e:
                last = str(e)
            time.sleep(2 ** attempt)
        else:
            raise LLMError(f"LLM call failed after {self.retries + 1} tries: {last}")

        dt = time.perf_counter() - t0
        u = data.get("usage") or {}
        self.usage.calls += 1
        self.usage.prompt_tokens += u.get("prompt_tokens", 0)
        self.usage.completion_tokens += u.get("completion_tokens", 0)
        self.usage.cost_usd += float(u.get("cost") or 0)
        self.usage.seconds += dt
        self.usage.log.append({"step": step, "model": self.model, "seconds": round(dt, 2),
                               "prompt_tokens": u.get("prompt_tokens"),
                               "completion_tokens": u.get("completion_tokens"), "cost_usd": u.get("cost")})
        text = data["choices"][0]["message"]["content"]
        return parse_json(text)


def parse_json(text: str) -> dict:
    """Accept a bare JSON object, or one wrapped in ```json fences."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"LLM did not return JSON: {text[:200]!r}")
    return json.loads(t[start:end + 1])
