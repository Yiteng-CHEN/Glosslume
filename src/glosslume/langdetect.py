"""Offline language detection, paragraph by paragraph. Standard library only.

Non-Latin scripts are decided by which script the letters belong to. Latin-script languages are
decided by counting common function words. Short snippets return "und" instead of guessing.
"""
from __future__ import annotations

import re

# code -> (English name used in prompts, 中文名)
LANGS: dict[str, tuple[str, str]] = {
    "en": ("English", "英语"), "zh": ("Chinese", "中文"), "ja": ("Japanese", "日语"),
    "ko": ("Korean", "韩语"), "es": ("Spanish", "西班牙语"), "fr": ("French", "法语"),
    "de": ("German", "德语"), "it": ("Italian", "意大利语"), "pt": ("Portuguese", "葡萄牙语"),
    "nl": ("Dutch", "荷兰语"), "ru": ("Russian", "俄语"), "uk": ("Ukrainian", "乌克兰语"),
    "ar": ("Arabic", "阿拉伯语"), "hi": ("Hindi", "印地语"), "th": ("Thai", "泰语"),
    "el": ("Greek", "希腊语"), "he": ("Hebrew", "希伯来语"),
}


def lang_name(code: str) -> str:
    return LANGS.get(code, (code, code))[0]


_STOP = {
    "en": "the of and to in is that for it as with was on are by this be from or an at which have not but had we they their can has were been these also its more such than will would other into may only one when what there if about all our",
    "es": "el la de que y en los del las un por con para una su al es lo como más pero sus le ya o este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese eso ante ellos e esto antes algunos qué unos otro otras otra él tanto esa estos mucho cual poco ella estar estas algo",
    "fr": "le la les de des du un une et en que qui dans est pour pas sur au avec ce il elle ne se plus par son sa ses nous vous ils elles sont été être cette ces mais ou où comme aussi fait tout très sans sous entre même",
    "de": "der die das und in den von zu mit sich des auf für ist im dem nicht ein eine als auch es an werden aus er hat dass sie nach wird bei einer um am sind noch wie einem über einen so zum war haben nur oder aber vor zur bis mehr durch man sein wurde sei",
    "it": "il lo la i gli le di a da in con su per tra fra e che non un una è sono del della dei delle al alla ai alle nel nella ha come più ma anche se questo questa suo sua",
    "pt": "o a os as de da do das dos em no na nos nas um uma e que para com não por mais se como mas ao ele ela seu sua ou são foi há também já só pelo pela até isso entre",
    "nl": "de het een en van in is dat op te zijn voor met niet aan er maar om ook als dan bij nog uit wordt werd naar door over ze zich deze dit die",
}
_STOP = {k: set(v.split()) for k, v in _STOP.items()}
_WORD = re.compile(r"[a-zà-öø-ÿœ]+", re.I)


def _script(ch: str) -> str | None:
    o = ord(ch)
    if 0x3040 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF:
        return "kana"
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
        return "han"
    if 0xAC00 <= o <= 0xD7AF or 0x1100 <= o <= 0x11FF:
        return "hangul"
    if 0x0400 <= o <= 0x04FF:
        return "cyrillic"
    if 0x0600 <= o <= 0x06FF:
        return "arabic"
    if 0x0900 <= o <= 0x097F:
        return "devanagari"
    if 0x0E00 <= o <= 0x0E7F:
        return "thai"
    if 0x0370 <= o <= 0x03FF:
        return "greek"
    if 0x0590 <= o <= 0x05FF:
        return "hebrew"
    if ch.isalpha():
        return "latin"
    return None


_SINGLE = {"cyrillic": "ru", "arabic": "ar", "devanagari": "hi", "thai": "th", "greek": "el", "hebrew": "he"}


def detect(text: str) -> tuple[str, float]:
    """-> (language code or "und", confidence 0..1)."""
    sample = text[:4000]
    counts: dict[str, int] = {}
    for ch in sample:
        s = _script(ch)
        if s:
            counts[s] = counts.get(s, 0) + 1
    letters = sum(counts.values())
    if letters < 3:
        return "und", 0.0
    cjk = counts.get("han", 0) + counts.get("kana", 0) + counts.get("hangul", 0)
    if cjk / letters >= 0.25:
        kana, han, hangul = counts.get("kana", 0), counts.get("han", 0), counts.get("hangul", 0)
        if kana and kana / (kana + han) >= 0.1:
            return "ja", 0.95
        if hangul > han:
            return "ko", 0.95
        return "zh", 0.95
    top = max(counts, key=counts.get)
    if top in _SINGLE:
        if top == "cyrillic" and re.search(r"[іїєґ]", sample.lower()):
            return "uk", 0.9
        return _SINGLE[top], 0.9
    if top != "latin" or letters < 12:
        return "und", 0.0
    words = [w.lower() for w in _WORD.findall(sample)]
    if len(words) < 4:
        return "und", 0.0
    hits = {k: sum(1 for w in words if w in sw) for k, sw in _STOP.items()}
    total = sum(hits.values())
    if total < 2:
        return "und", 0.0
    best = max(hits, key=hits.get)
    return best, round(hits[best] / total, 2)


def detect_document(paragraphs: list[str]) -> tuple[str, list[str]]:
    """-> (main language, language of each paragraph). Paragraphs too short to tell inherit the main one."""
    per = [detect(p) for p in paragraphs]
    weight: dict[str, int] = {}
    for p, (code, conf) in zip(paragraphs, per):
        if code != "und":
            weight[code] = weight.get(code, 0) + len(p)
    main = max(weight, key=weight.get) if weight else "und"
    return main, [code if code != "und" else main for code, _ in per]
