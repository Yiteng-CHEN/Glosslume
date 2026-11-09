"""Offline English→Chinese dictionary for instant first answers (ECDICT, MIT licensed, imported from its CSV).

The dictionary is optional: without it the card simply waits for the model. Build it once with
    glosslume dict import /path/to/ecdict.csv
(ECDICT: https://github.com/skywind3000/ECDICT). The database is created in the data directory, not in the repo.
"""
from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path


class Dictionary:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._db: sqlite3.Connection | None = None

    def available(self) -> bool:
        return self.path.exists()

    def _conn(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        return self._db

    def import_csv(self, csv_path: Path) -> int:
        csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
        tmp = self.path.with_suffix(".tmp")
        tmp.unlink(missing_ok=True)
        db = sqlite3.connect(str(tmp))
        db.execute("CREATE TABLE d(word TEXT PRIMARY KEY, phonetic TEXT, translation TEXT, pos TEXT, tag TEXT)")
        n = 0
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                w = (row.get("word") or "").strip().lower()
                if not w or not (row.get("translation") or "").strip():
                    continue
                db.execute("INSERT OR IGNORE INTO d VALUES(?,?,?,?,?)",
                           (w, row.get("phonetic", ""), row["translation"], row.get("pos", ""), row.get("tag", "")))
                n += 1
        db.commit()
        db.close()
        if self._db:
            self._db.close()
            self._db = None
        tmp.replace(self.path)
        return n

    @staticmethod
    def _candidates(word: str) -> list[str]:
        w = word.lower().strip("'’-")
        c = [w]
        for suf, rep in (("ies", "y"), ("es", ""), ("s", ""), ("ied", "y"), ("ed", ""), ("ed", "e"), ("ing", ""),
                         ("ing", "e"), ("ly", ""), ("er", ""), ("est", "")):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                c.append(w[:-len(suf)] + rep)
        if len(w) > 4 and w[-1] == w[-2]:
            c.append(w[:-1])
        return list(dict.fromkeys(c))

    def lookup(self, word: str) -> dict | None:
        if not self.available():
            return None
        for cand in self._candidates(word):
            r = self._conn().execute("SELECT word,phonetic,translation,pos,tag FROM d WHERE word=?", (cand,)).fetchone()
            if r:
                lines = [ln.strip() for ln in r[2].replace("\\n", "\n").splitlines() if ln.strip()]
                return {"word": r[0], "phonetic": r[1], "translation": lines[:4], "pos": r[3], "tag": r[4]}
        return None
