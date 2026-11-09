"""Decides which model answers, and falls back when one cannot.

Modes (setting `mode`):
  prefer_local  local models first, cloud as backup          (default: privacy first)
  prefer_cloud  cloud first, local when the cloud is out of quota / down / rejects the key
  local_only    never leave this computer
A document marked "local only" behaves like local_only whatever the mode is.
Word lookups and sentence analysis can each name a preferred provider (`word_provider`, `sentence_provider`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from ..store import Store
from . import anthropic, keys, openai_compat
from .base import Provider, ProviderError

LOCAL_SERVICES = [                                   # (name, base url) probed on this computer
    ("Neurolume", "http://127.0.0.1:8765/v1"),
    ("Ollama", "http://127.0.0.1:11434/v1"),
    ("LM Studio", "http://127.0.0.1:1234/v1"),
    ("mlx_lm.server", "http://127.0.0.1:8080/v1"),
]
# Cloud presets for the settings page. Model names are left to the user because vendors rename them often.
PRESETS = [
    {"name": "OpenAI", "kind": "openai", "base_url": "https://api.openai.com/v1"},
    {"name": "Anthropic", "kind": "anthropic", "base_url": "https://api.anthropic.com"},
    {"name": "Gemini", "kind": "openai", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
    {"name": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com/v1"},
    {"name": "通义千问 (DashScope)", "kind": "openai", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    {"name": "Kimi (Moonshot)", "kind": "openai", "base_url": "https://api.moonshot.cn/v1"},
    {"name": "智谱 GLM", "kind": "openai", "base_url": "https://open.bigmodel.cn/api/paas/v4"},
    {"name": "OpenRouter", "kind": "openai", "base_url": "https://openrouter.ai/api/v1"},
]
MODES = ("prefer_local", "prefer_cloud", "local_only")


class NoProvider(Exception):
    pass


@dataclass
class Routed:
    text: str
    provider: Provider
    fell_back: bool


def discover_local() -> list[dict]:
    found = []
    for name, base in LOCAL_SERVICES:
        models = openai_compat.list_models(base)
        if models:
            found.append({"name": name, "base_url": base, "models": models})
    return found


class Router:
    def __init__(self, store: Store):
        self.store = store
        self.hooks: dict = {}                                  # provider id -> callable(provider) run before each request (the built-in model uses it to wait for its load)

    # ---------------------------------------------------------- configuration
    def providers(self) -> list[Provider]:
        return [Provider.from_dict(d) for d in self.store.kv_get("providers", [])]

    def save_provider(self, d: dict) -> Provider:
        p = Provider.from_dict(d)
        if not p.id or not p.base_url.strip() and p.kind != "anthropic" or not p.model.strip():
            raise ValueError("名称、地址和模型名都要填")
        p.base_url = p.base_url.strip()
        items = [x for x in self.providers() if x.id != p.id] + [p]
        self.store.kv_set("providers", [x.to_dict() for x in items])
        return p

    def delete_provider(self, pid: str) -> None:
        self.store.kv_set("providers", [x.to_dict() for x in self.providers() if x.id != pid])
        keys.delete(pid)
        for task in ("word", "sentence"):
            if self.store.kv_get(f"{task}_provider") == pid:
                self.store.kv_set(f"{task}_provider", "")

    def mode(self) -> str:
        m = self.store.kv_get("mode", "prefer_local")
        return m if m in MODES else "prefer_local"

    # ---------------------------------------------------------- routing
    def order(self, task: str, local_only: bool = False) -> list[Provider]:
        provs = self.providers()
        local = [p for p in provs if p.local]
        cloud = [p for p in provs if not p.local and keys.get(p.id)]
        mode = self.mode()
        if local_only or mode == "local_only":
            seq = local
        elif mode == "prefer_cloud":
            seq = cloud + local
        else:
            seq = local + cloud
        pref = self.store.kv_get(f"{task}_provider", "")
        seq = sorted(seq, key=lambda p: 0 if p.id == pref else 1)       # stable: preferred first
        if not seq:
            raise NoProvider("没有可用的模型：" + ("这篇文档设为了“仅本地”，但没有本地模型在运行。" if local_only or mode == "local_only"
                                              else "请在设置里添加本地模型，或填入云端 API Key。"))
        return seq

    def _prepare(self, p: Provider) -> Provider:
        """Run the provider's hook; it may return a refreshed provider (the built-in model gets a new port when it restarts)."""
        return (self.hooks[p.id](p) or p) if p.id in self.hooks else p

    def _call(self, p: Provider, messages, **kw) -> str:
        p = self._prepare(p)
        key = keys.get(p.id)
        fn = anthropic.complete if p.kind == "anthropic" else openai_compat.complete
        return fn(p, key, messages, **kw)

    def complete(self, task: str, messages: list[dict], local_only: bool = False, **kw) -> Routed:
        errors = []
        for i, p in enumerate(self.order(task, local_only)):
            try:
                return Routed(self._call(p, messages, **kw), p, i > 0)
            except ProviderError as e:
                errors.append(f"{p.name}: {e}")
        raise ProviderError("所有模型都没能回答：" + "；".join(errors), "unavailable")

    def stream(self, task: str, messages: list[dict], local_only: bool = False, **kw) -> tuple[Provider, bool, Iterator[str]]:
        """Fall back only until the first chunk arrives; once text is flowing, errors surface to the caller."""
        errors = []
        for i, p in enumerate(self.order(task, local_only)):
            key = keys.get(p.id)
            fn = anthropic.stream if p.kind == "anthropic" else openai_compat.stream
            try:
                p = self._prepare(p)
                it = fn(p, key, messages, **kw)
                first = next(it)
            except StopIteration:
                return p, i > 0, iter(())
            except ProviderError as e:
                errors.append(f"{p.name}: {e}")
                continue

            def chain(first=first, it=it):
                yield first
                yield from it
            return p, i > 0, chain()
        raise ProviderError("所有模型都没能回答：" + "；".join(errors), "unavailable")

    def test(self, pid: str) -> dict:
        p = next((x for x in self.providers() if x.id == pid), None)
        if not p:
            raise ValueError("没有这个模型")
        try:
            text = self._call(p, [{"role": "user", "content": "Reply with the single word: ok"}], max_tokens=8, timeout=30)
            return {"ok": True, "reply": text.strip()[:40]}
        except ProviderError as e:
            return {"ok": False, "kind": e.kind, "error": str(e)}
