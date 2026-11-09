"""Anthropic Messages API with an API key. (Claude subscription logins are not used: Anthropic's terms
do not allow subscription credentials in third-party tools.)"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterator

from .base import Provider, ProviderError, classify_http

VERSION = "2023-06-01"


def _request(p: Provider, key: str, messages: list[dict], max_tokens: int, temperature: float, stream: bool):
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    body = {"model": p.model, "max_tokens": max_tokens, "temperature": temperature, "stream": stream,
            "messages": [m for m in messages if m["role"] != "system"]}
    if system:
        body["system"] = system
    headers = {"Content-Type": "application/json", "x-api-key": key, "anthropic-version": VERSION}
    url = (p.base_url.rstrip("/") or "https://api.anthropic.com") + "/v1/messages"
    return urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")


def _open(req, timeout: float):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read(2000).decode("utf-8", "replace")
        kind = "unavailable" if e.code == 529 else classify_http(e.code, body)
        raise ProviderError(f"HTTP {e.code}: {body[:200]}", kind)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        raise ProviderError(f"连不上 Anthropic：{getattr(e, 'reason', e)}", "unavailable")


def complete(p: Provider, key: str, messages: list[dict], max_tokens: int = 400, temperature: float = 0.1,
             timeout: float | None = None) -> str:
    with _open(_request(p, key, messages, max_tokens, temperature, False), timeout or 60) as r:
        try:
            return "".join(b.get("text", "") for b in json.loads(r.read())["content"] if b.get("type") == "text")
        except (ValueError, KeyError, TypeError):
            raise ProviderError("Anthropic 返回的格式不对", "other")


def stream(p: Provider, key: str, messages: list[dict], max_tokens: int = 700, temperature: float = 0.2,
           timeout: float | None = None) -> Iterator[str]:
    with _open(_request(p, key, messages, max_tokens, temperature, True), timeout or 60) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:])
            except ValueError:
                continue
            if ev.get("type") == "content_block_delta" and ev.get("delta", {}).get("type") == "text_delta":
                yield ev["delta"].get("text", "")
