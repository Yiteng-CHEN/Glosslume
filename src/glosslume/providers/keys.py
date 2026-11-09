"""API keys live in the system keychain (via `keyring`), never in the database or config files.
Without `keyring` installed keys are kept in memory for this run only, and the UI says so."""
from __future__ import annotations

SERVICE = "glosslume"
_mem: dict[str, str] = {}

try:                                                                # optional dependency
    import keyring as _kr
except ImportError:
    _kr = None


def persistent() -> bool:
    return _kr is not None


def get(name: str) -> str:
    if _kr is not None:
        try:
            v = _kr.get_password(SERVICE, name)
            if v:
                return v
        except Exception:
            pass
    return _mem.get(name, "")


def set(name: str, value: str) -> None:
    if _kr is not None:
        try:
            _kr.set_password(SERVICE, name, value)
            _mem.pop(name, None)
            return
        except Exception:
            pass
    _mem[name] = value


def delete(name: str) -> None:
    _mem.pop(name, None)
    if _kr is not None:
        try:
            _kr.delete_password(SERVICE, name)
        except Exception:
            pass
