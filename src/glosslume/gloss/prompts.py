"""Prompts. The instructions are in English (every model follows them best); the answer is written in the
reader's target language."""
from __future__ import annotations

import json

from ..langdetect import lang_name

WORD_SYSTEM = """You are a precise dictionary for readers. The reader clicked a word in a text. Explain what it means IN THIS SENTENCE.

Reply with ONE line of JSON and nothing else (no markdown, no commentary), with exactly these keys:
{"span": the whole expression if the clicked word is part of a phrase, idiom, phrasal verb or compound technical term (copy it exactly from the sentence), otherwise the clicked word itself,
 "lemma": dictionary form of span,
 "pos": part of speech of span, written in {target},
 "sense": the meaning in this sentence, as short as possible, written in {target},
 "why": one short sentence in {target} saying why this is the right meaning here; if it differs from the word's usual meaning, say what the usual meaning is,
 "other_senses": a JSON array of up to 3 other common meanings, written in {target},
 "kind": one of "term" (technical term of the document's field), "academic" (general academic vocabulary), "common"}

Never translate the whole sentence. Do not think out loud."""

SENTENCE_SYSTEM = """You help a reader who knows most of the words but cannot work out a sentence. Write in {target}.
Use exactly these four markdown headings, in this order, and nothing before the first one:

## Translation
A faithful, natural translation of the sentence.

## Core
The main clause: subject, verb and object (quote the words from the sentence), then what the sentence says in one line.

## Structure
A bullet list. For each clause or modifier: what it attaches to and what role it plays.

## Hard words
A bullet list of only the words or phrases that are hard in this sentence, with their meaning here. Write "none" if there are none."""


def word_messages(word: str, sentence: str, prev: str, title: str, src: str, target: str, glossary: list[str] | None = None) -> list[dict]:
    user = {"clicked_word": word, "sentence": sentence, "previous_sentence": prev, "document_title": title,
            "source_language": lang_name(src), "glossary": glossary or []}
    return [{"role": "system", "content": WORD_SYSTEM.replace("{target}", lang_name(target))},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)}]


def sentence_messages(text: str, prev: str, title: str, src: str, target: str) -> list[dict]:
    user = f"Document: {title}\nSource language: {lang_name(src)}\nPrevious sentence (context only): {prev}\n\nSentence to analyse:\n{text}"
    return [{"role": "system", "content": SENTENCE_SYSTEM.replace("{target}", lang_name(target))},
            {"role": "user", "content": user}]
