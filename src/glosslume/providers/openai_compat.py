"""Any OpenAI-compatible chat server: Neurolume, Ollama, LM Studio, mlx_lm.server, and most cloud vendors."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterator

from .base import Provider, ProviderError, classify_http


def _request(p: Provider, key: str, messages: list[dict], max_tokens: int, temperature: float, stream: bool,
             think_off: bool = True) -> urllib.request.Request:
    body: dict = {"model": p.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature, "stream": stream}
    if p.local and p.no_think and think_off:
        body["chat_template_kwargs"] = {"enable_thinking": False}     # Qwen3-style templates; ignored by servers that do not know it
        body["reasoning_effort"] = "none"                              # Ollama (deepseek-r1, gpt-oss...): without it a 70B model thinks past the timeout
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream" if stream else "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    url = p.base_url.rstrip("/") + "/chat/completions"
    return urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")


def _open(req: urllib.request.Request, timeout: float):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read(2000).decode("utf-8", "replace")
        raise ProviderError(f"HTTP {e.code}: {body[:200]}", classify_http(e.code, body))
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise ProviderError(f"连不上 {req.full_url}：{getattr(e, 'reason', e)}", "unavailable")


def _open_request(p: Provider, key: str, messages: list[dict], max_tokens: int, temperature: float, stream: bool, timeout: float):
    """Open the request; a server that rejects the think-off parameters (HTTP 400) is retried once without them."""
    try:
        return _open(_request(p, key, messages, max_tokens, temperature, stream), timeout)
    except ProviderError as e:
        if e.kind != "bad_request" or not (p.local and p.no_think):
            raise
        return _open(_request(p, key, messages, max_tokens, temperature, stream, think_off=False), timeout)


def complete(p: Provider, key: str, messages: list[dict], max_tokens: int = 400, temperature: float = 0.1,
             timeout: float | None = None) -> str:
    with _open_request(p, key, messages, max_tokens, temperature, False, timeout or (120 if p.local else 60)) as r:
        try:
            data = json.loads(r.read())
            return data["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError("模型服务返回的格式不对", "other")


def stream(p: Provider, key: str, messages: list[dict], max_tokens: int = 700, temperature: float = 0.2,
           timeout: float | None = None) -> Iterator[str]:
    r = _open_request(p, key, messages, max_tokens, temperature, True, timeout or (120 if p.local else 60))
    with r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                return
            try:
                delta = json.loads(payload)["choices"][0].get("delta", {}).get("content")
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if delta:
                yield delta


def list_models(base_url: str, timeout: float = 0.8) -> list[str]:
    """GET /models on an OpenAI-compatible server. [] when nothing answers."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=timeout) as r:
            data = json.loads(r.read())
        items = data.get("data") or data.get("models") or []
        return [str(m.get("id") or m.get("name")) for m in items if isinstance(m, dict)]
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, AttributeError):
        return []
