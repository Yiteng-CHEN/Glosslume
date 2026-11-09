"""Word lookup and sentence analysis for one document position."""
from __future__ import annotations

import hashlib
import json
from typing import Iterator

from ..providers.router import Router
from ..segment import sentence_at, sentence_spans, u16_to_cp
from ..store import Store
from . import prompts
from .parse import ParseError, parse_word, split_sections


MAX_CTX = 12_000


class LookupError_(Exception):
    """A request the user can fix (bad position, unknown document)."""


def _provider_info(p) -> dict:
    return {"id": p.id, "name": p.name, "local": p.local, "model": p.model}


class Glosser:
    def __init__(self, store: Store, router: Router):
        self.store, self.router = store, router

    def _locate(self, doc_id: str, para: int | None, start: int, end: int, expand: bool = False, ctx: str | None = None):
        """Find the sentence for a position. `ctx` is page text taken from the original PDF layout (the reader
        cannot map it onto the stored paragraphs); then `para` is None and offsets index into `ctx`."""
        doc = self.store.get_doc(doc_id)
        if not doc:
            raise LookupError_("找不到这个位置")
        if ctx is not None:
            if not ctx.strip() or len(ctx) > MAX_CTX:
                raise LookupError_("选中的范围不对")
            text, para = ctx, 0
            doc["paragraphs"], doc["langs"] = [ctx], [doc["lang"]]
        elif para is None or not (0 <= para < len(doc["paragraphs"])):
            raise LookupError_("找不到这个位置")
        else:
            text = doc["paragraphs"][para]
        s, e = u16_to_cp(text, start), u16_to_cp(text, end)
        if not (0 <= s < e <= len(text)):
            raise LookupError_("选中的范围不对")
        spans = sentence_spans(text) or [(0, len(text))]
        i = sentence_at(spans, s)
        if expand:                                           # whole sentence(s) touched by the selection
            j = sentence_at(spans, max(s, e - 1))
            s, e = spans[i][0], spans[j][1]
        prev = ""
        if i > 0:
            prev = text[spans[i - 1][0]:spans[i - 1][1]]
        elif para > 0:
            pt = doc["paragraphs"][para - 1]
            ps = sentence_spans(pt)
            prev = pt[ps[-1][0]:ps[-1][1]] if ps else pt[-300:]
        return doc, text, (s, e), text[spans[i][0]:spans[i][1]], prev, doc["langs"][para]

    # ------------------------------------------------------------ word
    def word(self, doc_id: str, para: int | None, start: int, end: int, target: str, refresh: bool = False,
             ctx: str | None = None) -> dict:
        doc, text, (s, e), sentence, prev, src = self._locate(doc_id, para, start, end, ctx=ctx)
        word = text[s:e]
        key = hashlib.sha1(json.dumps([word.lower(), sentence, src, target]).encode()).hexdigest()
        cached = None if refresh else self.store.cache_get(key)
        if cached:
            result = cached | {"cached": True}
        else:
            msgs = prompts.word_messages(word, sentence, prev, doc["title"], src, target)
            routed = self.router.complete("word", msgs, local_only=doc["local_only"], max_tokens=350, temperature=0.1)
            try:
                data = parse_word(routed.text, word)
            except ParseError:                               # one retry, with a firmer reminder
                msgs = msgs + [{"role": "assistant", "content": routed.text[:300]},
                               {"role": "user", "content": "Reply again with only the one-line JSON object."}]
                routed = self.router.complete("word", msgs, local_only=doc["local_only"], max_tokens=350, temperature=0)
                try:
                    data = parse_word(routed.text, word)
                except ParseError:
                    data = {"span": word, "lemma": word, "pos": "", "sense": routed.text.strip()[:200] or "?",
                            "why": "", "other_senses": [], "kind": "common"}
            result = data | {"provider": _provider_info(routed.provider), "fell_back": routed.fell_back, "cached": False}
            self.store.cache_put(key, {k: v for k, v in result.items() if k not in ("cached", "fell_back")})
        result.update({"word": word, "sentence": sentence, "src": src})
        row = self.store.add_vocab(result["span"], result["lemma"], result["sense"], sentence, doc_id, result["kind"], clicked=word)
        result["vocab"] = {"id": row["id"], "status": row["status"]}
        return result

    # ------------------------------------------------------------ sentence
    def sentence(self, doc_id: str, para: int | None, start: int, end: int, target: str, expand: bool = True,
                 ctx: str | None = None) -> tuple[dict, Iterator[str]]:
        doc, text, (s, e), _sent, prev, src = self._locate(doc_id, para, start, end, expand=expand, ctx=ctx)
        msgs = prompts.sentence_messages(text[s:e], prev, doc["title"], src, target)
        provider, fell_back, it = self.router.stream("sentence", msgs, local_only=doc["local_only"], max_tokens=900, temperature=0.2)
        return {"text": text[s:e], "provider": _provider_info(provider), "fell_back": fell_back}, it


def sections(text: str) -> dict[str, str]:
    return split_sections(text)
