"""Paths. Runtime data (library, vocabulary, cache) never lives in the repository."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP = "Glosslume"
WEB_DIR = Path(__file__).resolve().parent / "web"


def data_dir() -> Path:
    env = os.environ.get("GLOSSLUME_DATA")
    if env:
        p = Path(env).expanduser()
    elif sys.platform == "darwin":
        p = Path.home() / "Library" / "Application Support" / APP
    else:
        p = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "glosslume"
    p.mkdir(parents=True, exist_ok=True)
    return p
