"""Local web server: serves the reader UI and a small JSON API.

Binds to 127.0.0.1 only, rejects requests whose Host header is not localhost (DNS rebinding) and POSTs whose
Origin is not this page (cross-site requests). The browser never talks to a model: this server does, so API keys
stay out of the page and no CORS setup is needed on Neurolume, Ollama or LM Studio.
"""
from __future__ import annotations

import base64
import json
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import __version__, importers, langdetect
from ..config import WEB_DIR, data_dir
from ..gloss.dictionary import Dictionary
from ..gloss.service import Glosser, LookupError_
from ..localmodel.manager import LocalModels
from ..providers import keys
from ..providers.base import Provider, ProviderError
from ..providers.router import MODES, PRESETS, NoProvider, Router, discover_local
from ..store import Store

TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".mjs": "text/javascript; charset=utf-8",
         ".wasm": "application/wasm", ".txt": "text/plain; charset=utf-8"}
DOC_ID = re.compile(r"^[0-9a-f]{12}$")
MAX_BODY = 80_000_000
USER_ERRORS = (ValueError, LookupError_, importers.ImportFail, NoProvider)


class App:
    def __init__(self, data: Path | None = None):
        self.data = Path(data) if data else data_dir()
        self.data.mkdir(parents=True, exist_ok=True)
        self.store = Store(self.data / "glosslume.db")
        self.router = Router(self.store)
        self.glosser = Glosser(self.store, self.router)
        self.dictionary = Dictionary(self.data / "ecdict.db")
        self.files = self.data / "files"
        self.local = LocalModels(self.data, self.store, self.router)      # the built-in local model (download, start, stop)

    # ------------------------------------------------------------ original PDFs
    def pdf_path(self, did: str) -> Path | None:
        """Where the original PDF of a document lives, if it has one. Ids are validated: they become file names."""
        if not DOC_ID.match(did or ""):
            return None
        p = self.files / f"{did}.pdf"
        return p if p.is_file() else None

    def doc_view(self, did: str) -> dict:
        d = self.store.get_doc(did)
        if not d:
            raise ValueError("文档不存在")
        d["has_pdf"] = self.pdf_path(did) is not None
        d["pdf_page"] = int(self.store.kv_get(f"pdf_page:{did}", 1) or 1)
        return d

    def delete_doc(self, did: str) -> None:
        self.store.delete_doc(did)
        self.store.kv_delete(f"pdf_page:{did}")
        p = self.pdf_path(did)
        if p:
            p.unlink(missing_ok=True)

    def state(self) -> dict:
        provs = []
        for p in self.router.providers():
            provs.append(p.to_dict() | {"has_key": bool(keys.get(p.id)) if not p.local else None})
        return {
            "version": __version__,
            "settings": {"target_lang": self.store.kv_get("target_lang"), "mode": self.router.mode(),
                         "word_provider": self.store.kv_get("word_provider", ""),
                         "sentence_provider": self.store.kv_get("sentence_provider", "")},
            "providers": provs, "presets": PRESETS, "modes": list(MODES), "keys_persistent": keys.persistent(),
            "langs": {k: list(v) for k, v in langdetect.LANGS.items()}, "dictionary": self.dictionary.available(),
        }

    # ------------------------------------------------------------ actions
    def import_doc(self, body: dict) -> dict:
        if body.get("url"):
            imp = importers.from_url(str(body["url"]))
        elif body.get("data"):
            try:
                raw = base64.b64decode(body["data"], validate=False)
            except ValueError:
                raise ValueError("文件内容读取失败")
            imp = importers.from_file(str(body.get("name") or "file.txt"), raw)
        elif body.get("text"):
            imp = importers.from_text(str(body["text"]), str(body.get("title") or ""))
        else:
            raise ValueError("请提供网址、文件或文字")
        lang, langs = langdetect.detect_document(imp.paragraphs)
        did = self.store.add_doc(imp.title, imp.source, lang, imp.paragraphs, langs)
        if imp.pdf:
            self.files.mkdir(parents=True, exist_ok=True)
            (self.files / f"{did}.pdf").write_bytes(imp.pdf)
        return {"id": did, "title": imp.title, "lang": lang, "note": imp.note, "paragraphs": len(imp.paragraphs), "has_pdf": bool(imp.pdf)}

    def save_provider(self, body: dict) -> dict:
        name = str(body.get("name") or "").strip()
        pid = str(body.get("id") or "") or (re.sub(r"\W+", "-", name.lower()).strip("-") or "model") + "-" + uuid.uuid4().hex[:4]
        p = self.router.save_provider({
            "id": pid, "name": name or pid, "kind": body.get("kind") or "openai", "base_url": body.get("base_url") or "",
            "model": body.get("model") or "", "local": bool(body.get("local")), "no_think": bool(body.get("no_think", body.get("local")))})
        if body.get("key"):
            keys.set(p.id, str(body["key"]).strip())
        return p.to_dict()


def make_server(app: App, port: int = 8780, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    store, router, glosser = app.store, app.router, app.glosser

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "Glosslume"

        def log_message(self, *a):
            pass

        # ---- plumbing
        def _host_ok(self) -> bool:
            host_h = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            return host_h in ("localhost", "127.0.0.1", "::1")

        def _origin_ok(self) -> bool:
            o = self.headers.get("Origin")
            if not o:
                return True
            return (urlparse(o).hostname or "") in ("localhost", "127.0.0.1", "::1")

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in ({"Cache-Control": "no-store"} | (extra or {})).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _guard(self, fn):
            try:
                self._json(fn())
            except USER_ERRORS as e:
                self._json({"error": str(e)}, 400)
            except ProviderError as e:
                self._json({"error": str(e), "kind": e.kind}, 502)
            except Exception as e:                                     # never leave the browser hanging
                self._json({"error": f"内部错误：{e}"}, 500)

        # ---- GET
        def do_GET(self):
            if not self._host_ok():
                return self._json({"error": "forbidden"}, 403)
            u = urlparse(self.path)
            q = parse_qs(u.query)
            p = u.path
            if p == "/api/state":
                return self._guard(app.state)
            if p == "/api/docs":
                files = app.files
                return self._guard(lambda: {"docs": [d | {"has_pdf": (files / f"{d['id']}.pdf").is_file()} for d in store.list_docs()]})
            if p.startswith("/api/docs/") and p.endswith("/pdf"):
                f = app.pdf_path(p.split("/")[-2])
                if not f:
                    return self._json({"error": "not found"}, 404)
                return self._send(200, f.read_bytes(), "application/pdf", {"Content-Disposition": "inline"})
            if p.startswith("/api/docs/"):
                return self._guard(lambda: app.doc_view(p.rsplit("/", 1)[1]))
            if p == "/api/dict":
                w = (q.get("word") or [""])[0]
                return self._guard(lambda: {"entry": app.dictionary.lookup(w) if w else None})
            if p == "/api/vocab":
                return self._guard(lambda: {"vocab": store.list_vocab((q.get("status") or [None])[0], (q.get("doc") or [None])[0])})
            if p == "/api/vocab/export":
                rows = store.list_vocab((q.get("status") or [None])[0])
                titles = {d["id"]: d["title"] for d in store.list_docs()}
                esc = lambda s: re.sub(r"[\t\r\n]+", " ", s or "")
                tsv = "".join(f"{esc(r['word'])}\t{esc(r['sense'])}\t{esc(r['sentence'])}\t{esc(titles.get(r['doc_id'], ''))}\n" for r in rows)
                return self._send(200, tsv.encode(), "text/tab-separated-values; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="glosslume-vocab.tsv"'})
            if p == "/api/local":
                return self._guard(app.local.state)
            if p == "/api/providers/discover":
                return self._guard(lambda: {"found": discover_local()})
            return self._static(p)

        def _static(self, p: str):
            rel = "index.html" if p in ("", "/") else p.lstrip("/")
            f = (WEB_DIR / rel).resolve()
            if WEB_DIR.resolve() not in f.parents or not f.is_file():
                return self._json({"error": "not found"}, 404)
            vendored = (WEB_DIR / "vendor").resolve() in f.parents          # pinned third-party files never change
            self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"),
                       {"Cache-Control": "max-age=86400"} if vendored else None)

        # ---- POST
        def do_POST(self):
            if not self._host_ok() or not self._origin_ok():
                return self._json({"error": "forbidden"}, 403)
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._json({"error": "内容太大"}, 413)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._json({"error": "请求格式不对"}, 400)
            p = urlparse(self.path).path
            if p == "/api/gloss/sentence":
                return self._sentence(body)
            routes = {
                "/api/docs/import": lambda: app.import_doc(body),
                "/api/docs/update": lambda: self._update_doc(body),
                "/api/docs/delete": lambda: (app.delete_doc(str(body.get("id"))), {"ok": True})[1],
                "/api/gloss/word": lambda: glosser.word(str(body["doc"]), self._para(body), int(body["start"]), int(body["end"]),
                                                       self._target(body), bool(body.get("refresh")), self._ctx(body)),
                "/api/vocab/status": lambda: (store.set_vocab_status(int(body["id"]), str(body["status"])), {"ok": True})[1],
                "/api/vocab/delete": lambda: (store.delete_vocab(int(body["id"])), {"ok": True})[1],
                "/api/settings": lambda: self._settings(body),
                "/api/providers/save": lambda: app.save_provider(body),
                "/api/providers/delete": lambda: (router.delete_provider(str(body["id"])), {"ok": True})[1],
                "/api/providers/test": lambda: router.test(str(body["id"])),
                "/api/local/install": lambda: (app.local.install(str(body.get("model"))), {"ok": True})[1],
                "/api/local/cancel": lambda: (app.local.cancel(str(body.get("model"))), {"ok": True})[1],
                "/api/local/remove": lambda: (app.local.remove(str(body.get("model"))), {"ok": True})[1],
                "/api/local/select": lambda: (app.local.select(str(body.get("model"))), {"ok": True})[1],
                "/api/local/settings": lambda: (app.local.set_settings(body.get("endpoint"), body.get("engine")), {"ok": True})[1],
            }
            fn = routes.get(p)
            if not fn:
                return self._json({"error": "not found"}, 404)
            self._guard(fn)

        @staticmethod
        def _ctx(body: dict) -> str | None:
            """Page text from the PDF view (used instead of a stored paragraph)."""
            c = body.get("ctx")
            if c is None:
                return None
            if not isinstance(c, str):
                raise ValueError("请求格式不对")
            return c

        @staticmethod
        def _para(body: dict) -> int | None:
            return None if body.get("ctx") is not None else int(body["para"])

        def _target(self, body: dict) -> str:
            t = body.get("target") or store.kv_get("target_lang")
            if t not in langdetect.LANGS:
                raise ValueError("请先在设置里选择目标语言")
            return t

        def _update_doc(self, body: dict) -> dict:
            did = str(body.get("id"))
            if not store.get_doc(did):
                raise ValueError("文档不存在")
            if body.get("lang_override") in langdetect.LANGS:
                store.set_doc_lang(did, body["lang_override"])
            store.update_doc(did, **{k: body[k] for k in ("title", "local_only", "progress") if k in body})
            if "pdf_page" in body:
                store.kv_set(f"pdf_page:{did}", max(1, int(body["pdf_page"])))
            return {"ok": True}

        def _settings(self, body: dict) -> dict:
            if "target_lang" in body:
                if body["target_lang"] not in langdetect.LANGS:
                    raise ValueError("不支持这个语言")
                store.kv_set("target_lang", body["target_lang"])
            if "mode" in body:
                if body["mode"] not in MODES:
                    raise ValueError("模式不对")
                store.kv_set("mode", body["mode"])
            for k in ("word_provider", "sentence_provider"):
                if k in body:
                    store.kv_set(k, str(body[k] or ""))
            return app.state()["settings"]

        def _sentence(self, body: dict):
            try:
                meta, it = glosser.sentence(str(body["doc"]), self._para(body), int(body["start"]), int(body["end"]),
                                            self._target(body), bool(body.get("expand", True)), self._ctx(body))
            except USER_ERRORS as e:
                return self._json({"error": str(e)}, 400)
            except ProviderError as e:
                return self._json({"error": str(e), "kind": e.kind}, 502)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

            def emit(obj):
                self.wfile.write(b"data: " + json.dumps(obj, ensure_ascii=False).encode() + b"\n\n")
                self.wfile.flush()
            try:
                emit({"meta": meta})
                for chunk in it:
                    emit({"delta": chunk})
                emit({"done": True})
            except ProviderError as e:
                emit({"error": str(e)})
            except (BrokenPipeError, ConnectionResetError):
                pass

    srv = ThreadingHTTPServer((host, port), H)
    srv.daemon_threads = True
    return srv


def serve_in_thread(app: App, port: int = 0) -> tuple[ThreadingHTTPServer, threading.Thread]:
    srv = make_server(app, port)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, t
