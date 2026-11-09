from __future__ import annotations

from dataclasses import asdict, dataclass


class ProviderError(Exception):
    """kind: quota | auth | unavailable | bad_request | other"""

    def __init__(self, message: str, kind: str = "other"):
        super().__init__(message)
        self.kind = kind


@dataclass
class Provider:
    id: str
    name: str
    kind: str = "openai"          # "openai" (any OpenAI-compatible server) | "anthropic"
    base_url: str = ""
    model: str = ""
    local: bool = False
    no_think: bool = False        # ask local reasoning models (Qwen3 etc.) to skip their thinking phase

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Provider":
        keys = Provider.__dataclass_fields__.keys()
        return Provider(**{k: v for k, v in d.items() if k in keys})


def classify_http(code: int, body: str) -> str:
    low = body.lower()
    if code in (402, 429) or "insufficient_quota" in low or "credit balance" in low or "quota" in low:
        return "quota"
    if code in (401, 403):
        return "auth"
    if code >= 500:
        return "unavailable"
    return "bad_request"
