"""Read what a model returned, forgiving about fences, thinking tags and stray text."""
from __future__ import annotations

import json
import re

KINDS = ("term", "academic", "common")


class ParseError(Exception):
    pass


def _clean(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    text = re.sub(r"^.*?</think>", "", text, flags=re.S | re.I)      # thinking tag opened elsewhere
    return text.strip()


def _first_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ParseError("no JSON object")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ParseError("unterminated JSON object")


def parse_word(text: str, clicked: str) -> dict:
    raw = _first_object(_clean(text).replace("```json", "").replace("```", ""))
    try:
        d = json.loads(raw)
    except ValueError as e:
        raise ParseError(str(e))
    if not isinstance(d, dict) or not str(d.get("sense", "")).strip():
        raise ParseError("no sense")
    others = d.get("other_senses") or []
    if isinstance(others, str):
        others = [others]
    kind = str(d.get("kind", "common")).lower()
    return {
        "span": str(d.get("span") or clicked).strip() or clicked,
        "lemma": str(d.get("lemma") or d.get("span") or clicked).strip(),
        "pos": str(d.get("pos", "")).strip(),
        "sense": str(d["sense"]).strip(),
        "why": str(d.get("why", "")).strip(),
        "other_senses": [str(x).strip() for x in others if str(x).strip()][:3],
        "kind": kind if kind in KINDS else "common",
    }


SECTIONS = ("Translation", "Core", "Structure", "Hard words")


def split_sections(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    cur = None
    for line in _clean(text).splitlines():
        m = re.match(r"^\s*#{1,3}\s*(Translation|Core|Structure|Hard words)\s*$", line, re.I)
        if m:
            cur = next(s for s in SECTIONS if s.lower() == m.group(1).lower())
            out[cur] = ""
        elif cur:
            out[cur] += line + "\n"
    return {k: v.strip() for k, v in out.items()}
