"""Sentence splitting with character offsets, tuned for papers (et al., Fig., e.g., decimals)."""
from __future__ import annotations

import re

_ABBR = {"e.g", "i.e", "et al", "al", "fig", "figs", "eq", "eqs", "vs", "etc", "dr", "mr", "mrs", "ms", "prof",
         "no", "cf", "sec", "ref", "refs", "vol", "pp", "approx", "inc", "ltd", "st", "jr", "sr", "resp", "viz",
         "ca", "tab", "ch", "ed", "eds", "col", "dept", "univ", "u.s", "u.k"}
_END = re.compile(r"""([.!?]+["'”’)\]]*)(\s+)|([。！？]+["'」』”’）]*)""")
_TOKEN = re.compile(r"([A-Za-z][A-Za-z.]*)$")
# Page furniture that has no full stop (links, DOIs, e-mails, copyright lines, the word "Abstract") would glue the
# front matter of a paper to the first real sentence. Each such item ends a sentence, so it never reaches the reader or the model.
_FURNITURE = re.compile(
    r"https?://\S+|www\.\S+|\b(?:doi:\s*)?10\.\d{4,9}/\S+|\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|edu|gov|io|ac\.\w\w)(?:/\S*)?|©[^.\n]{0,60}?\b(?:19|20)\d\d"
    r"|\b(?:Abstract|Keywords?)\b:?(?=\s+[A-Z])", re.I)
MAX_LEN = 500                                                    # a "sentence" longer than this is page furniture or a missing full stop


def sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _END.finditer(text):
        if m.group(1):
            term, end, nxt_at = m.group(1), m.end(1), m.end()
            nxt = text[nxt_at:nxt_at + 1]
            if nxt and nxt.islower():
                continue
            if term == ".":
                tok = _TOKEN.search(text[start:m.start()])
                w = tok.group(1).lower().rstrip(".") if tok else ""
                if w in _ABBR or (len(w) == 1 and w.isalpha()):
                    continue
            new_start = m.end()
        else:
            end = new_start = m.end(3)
        if text[start:end].strip():
            spans.append((start, end))
        start = new_start
    if text[start:].strip():
        spans.append((start, len(text)))
    spans = [x for sp in spans for x in _split_furniture(text, *sp)]
    out = []
    for s, e in spans:                                            # trim whitespace
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            out.append((s, e))
    return out


def _split_furniture(text: str, s: int, e: int) -> list[tuple[int, int]]:
    cuts, last = [], s
    for m in _FURNITURE.finditer(text, s, e):
        if m.start() > last:
            cuts.append((last, m.start()))
        cuts.append((m.start(), m.end()))
        last = m.end()
    if last < e:
        cuts.append((last, e))
    out = []
    for a, b in cuts:                                             # still too long: break at the last ; : , or space inside the limit
        while b - a > MAX_LEN:
            k = max(text.rfind(c, a + MAX_LEN // 2, a + MAX_LEN) for c in (";", ":", ","))
            k = k + 1 if k > 0 else text.rfind(" ", a + MAX_LEN // 2, a + MAX_LEN) + 1 or a + MAX_LEN
            out.append((a, k))
            a = k
        out.append((a, b))
    return out


def sentence_at(spans: list[tuple[int, int]], pos: int) -> int:
    """Index of the sentence containing pos (or the nearest one before it)."""
    best = 0
    for i, (s, e) in enumerate(spans):
        if s <= pos < e:
            return i
        if s <= pos:
            best = i
    return best


def u16_to_cp(text: str, off: int) -> int:
    """Browsers count UTF-16 code units, Python counts code points; convert an offset from the former."""
    if off <= 0:
        return 0
    units = 0
    for i, ch in enumerate(text):
        if units >= off:
            return i
        units += 2 if ord(ch) > 0xFFFF else 1
    return len(text)
