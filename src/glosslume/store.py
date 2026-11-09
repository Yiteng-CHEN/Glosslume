"""One SQLite file in the data directory: library, vocabulary, lookup cache and settings."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs(
  id TEXT PRIMARY KEY, title TEXT, source TEXT, lang TEXT, local_only INTEGER DEFAULT 0,
  created REAL, progress INTEGER DEFAULT 0, paragraphs TEXT, langs TEXT);
CREATE TABLE IF NOT EXISTS vocab(
  id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT, clicked TEXT, lemma TEXT, sense TEXT, sentence TEXT, doc_id TEXT,
  kind TEXT, status TEXT DEFAULT 'new', created REAL, UNIQUE(lemma, sentence));
CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT, created REAL);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT);
"""


class Store:
    def __init__(self, path: Path | str):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript(SCHEMA)

    # ------------------------------------------------------------ settings
    def kv_get(self, key: str, default=None):
        with self.lock:
            r = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default

    def kv_set(self, key: str, value) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (key, json.dumps(value, ensure_ascii=False)))
            self.db.commit()

    def kv_delete(self, key: str) -> None:
        with self.lock:
            self.db.execute("DELETE FROM kv WHERE key=?", (key,))
            self.db.commit()

    # ------------------------------------------------------------ library
    def add_doc(self, title: str, source: str, lang: str, paragraphs: list[str], langs: list[str]) -> str:
        did = uuid.uuid4().hex[:12]
        with self.lock:
            self.db.execute("INSERT INTO docs(id,title,source,lang,created,paragraphs,langs) VALUES(?,?,?,?,?,?,?)",
                            (did, title, source, lang, time.time(), json.dumps(paragraphs, ensure_ascii=False), json.dumps(langs)))
            self.db.commit()
        return did

    def list_docs(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT id,title,source,lang,local_only,created,progress,"
                                   "length(paragraphs) AS size FROM docs ORDER BY created DESC").fetchall()
        return [dict(r) | {"local_only": bool(r["local_only"])} for r in rows]

    def get_doc(self, did: str) -> dict | None:
        with self.lock:
            r = self.db.execute("SELECT * FROM docs WHERE id=?", (did,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["paragraphs"] = json.loads(d["paragraphs"])
        d["langs"] = json.loads(d["langs"])
        d["local_only"] = bool(d["local_only"])
        return d

    def update_doc(self, did: str, **fields) -> None:
        allowed = {"title", "local_only", "progress", "lang"}
        sets = {k: (int(v) if k in ("local_only", "progress") else v) for k, v in fields.items() if k in allowed}
        if not sets:
            return
        with self.lock:
            self.db.execute(f"UPDATE docs SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), did))
            self.db.commit()

    def set_doc_lang(self, did: str, lang: str) -> None:
        """Override the detected language of a whole document (every paragraph)."""
        doc = self.get_doc(did)
        if not doc:
            return
        with self.lock:
            self.db.execute("UPDATE docs SET lang=?, langs=? WHERE id=?", (lang, json.dumps([lang] * len(doc["paragraphs"])), did))
            self.db.commit()

    def delete_doc(self, did: str) -> None:
        with self.lock:
            self.db.execute("DELETE FROM docs WHERE id=?", (did,))
            self.db.commit()

    # ------------------------------------------------------------ vocabulary
    def add_vocab(self, word: str, lemma: str, sense: str, sentence: str, doc_id: str, kind: str, clicked: str = "") -> dict:
        lemma = (lemma or word).strip()
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO vocab(word,clicked,lemma,sense,sentence,doc_id,kind,created) VALUES(?,?,?,?,?,?,?,?)",
                            (word, clicked or word, lemma, sense, sentence, doc_id, kind, time.time()))
            self.db.commit()
            r = self.db.execute("SELECT * FROM vocab WHERE lemma=? AND sentence=?", (lemma, sentence)).fetchone()
        return dict(r)

    def list_vocab(self, status: str | None = None, doc_id: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM vocab WHERE 1=1", []
        if status:
            q += " AND status=?"
            args.append(status)
        if doc_id:
            q += " AND doc_id=?"
            args.append(doc_id)
        with self.lock:
            rows = self.db.execute(q + " ORDER BY created DESC", args).fetchall()
        return [dict(r) for r in rows]

    def set_vocab_status(self, vid: int, status: str) -> None:
        if status not in ("new", "learning", "known"):
            raise ValueError("状态不对")
        with self.lock:
            self.db.execute("UPDATE vocab SET status=? WHERE id=?", (status, vid))
            self.db.commit()

    def delete_vocab(self, vid: int) -> None:
        with self.lock:
            self.db.execute("DELETE FROM vocab WHERE id=?", (vid,))
            self.db.commit()

    # ------------------------------------------------------------ cache
    def cache_get(self, key: str):
        with self.lock:
            r = self.db.execute("SELECT value FROM cache WHERE key=?", (key,)).fetchone()
        return json.loads(r["value"]) if r else None

    def cache_put(self, key: str, value) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO cache(key,value,created) VALUES(?,?,?)",
                            (key, json.dumps(value, ensure_ascii=False), time.time()))
            self.db.commit()
