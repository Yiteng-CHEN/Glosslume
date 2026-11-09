"""End to end: the real Glosslume server, talking to fake OpenAI-compatible model servers."""
import base64
import http.client
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from glosslume.providers import keys
from glosslume.server.app import App, serve_in_thread

WORD_JSON = ('{"span":"take into account","lemma":"take into account","pos":"动词短语","sense":"考虑到",'
             '"why":"这里 account 是固定搭配的一部分","other_senses":["账户","描述"],"kind":"common"}')
SENTENCE_TEXT = "## Translation\n我们考虑每一层的方差。\n\n## Core\n主语 We，谓语 take into account。\n\n## Structure\n- of each layer 修饰 variance\n\n## Hard words\nnone"


def fake_model(reply: str, status: int = 200, stream_chunks=None):
    """A tiny OpenAI-compatible server. Returns (server, calls list)."""
    calls = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):                                     # /v1/models
            body = json.dumps({"data": [{"id": "fake-model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append({"req": req, "auth": self.headers.get("Authorization")})
            if status != 200:
                body = json.dumps({"error": {"message": "insufficient_quota"}}).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if req.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for piece in (stream_chunks or [reply]):
                    self.wfile.write(b"data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}).encode() + b"\n\n")
                self.wfile.write(b"data: [DONE]\n\n")
                return
            body = json.dumps({"choices": [{"message": {"content": reply}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, calls


class Client:
    def __init__(self, port):
        self.port = port

    def call(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Content-Type": "application/json"} | (headers or {})
        c.request(method, path, json.dumps(body) if body is not None else None, h)
        r = c.getresponse()
        raw = r.read().decode()
        c.close()
        return r.status, raw

    def get(self, path):
        s, raw = self.call("GET", path)
        return s, json.loads(raw)

    def post(self, path, body, headers=None):
        s, raw = self.call("POST", path, body, headers)
        return s, json.loads(raw)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(keys, "_kr", None)                     # keep keys in memory, never touch a real keychain
    keys._mem.clear()
    app = App(tmp_path)
    srv, _ = serve_in_thread(app)
    started = []
    yield app, Client(srv.server_address[1]), started
    srv.shutdown()
    for s in started:
        s.shutdown()


def add_local(app, base_url, name="Local", **kw):
    return app.router.save_provider({"id": "local-1", "name": name, "kind": "openai", "base_url": base_url,
                                     "model": "fake-model", "local": True, **kw})


def url_of(srv):
    return f"http://127.0.0.1:{srv.server_address[1]}/v1"


def import_doc(client, local_only=False):
    st, d = client.post("/api/docs/import", {"text": "We take into account the variance of each layer. It is small.\n\nSecond paragraph here with more words."})
    assert st == 200, d
    if local_only:
        client.post("/api/docs/update", {"id": d["id"], "local_only": True})
    return d


# "We take into account ..." -> "account" is at utf-16 offsets 13..20
ACC = {"para": 0, "start": 13, "end": 20}


def test_import_detects_language_and_lists(env):
    app, c, _ = env
    d = import_doc(c)
    assert d["lang"] == "en" and d["paragraphs"] == 2
    docs = c.get("/api/docs")[1]["docs"]
    assert docs[0]["id"] == d["id"] and docs[0]["lang"] == "en"
    assert c.get(f"/api/docs/{d['id']}")[1]["paragraphs"][1].startswith("Second paragraph")


def test_word_lookup_cache_and_vocab(env):
    app, c, started = env
    model, calls = fake_model(WORD_JSON)
    started.append(model)
    add_local(app, url_of(model))
    c.post("/api/settings", {"target_lang": "zh"})
    d = import_doc(c)
    st, r = c.post("/api/gloss/word", {"doc": d["id"], **ACC})
    assert st == 200, r
    assert r["span"] == "take into account" and r["sense"] == "考虑到" and r["provider"]["local"] is True
    assert r["sentence"].startswith("We take into account") and r["cached"] is False
    sent = json.loads(calls[0]["req"]["messages"][1]["content"])
    assert sent["clicked_word"] == "account" and "variance" in sent["sentence"]
    assert "Chinese" in calls[0]["req"]["messages"][0]["content"]
    st, r2 = c.post("/api/gloss/word", {"doc": d["id"], **ACC})            # same place again: no second model call
    assert r2["cached"] is True and len(calls) == 1
    vocab = c.get("/api/vocab")[1]["vocab"]
    assert len(vocab) == 1 and vocab[0]["lemma"] == "take into account" and vocab[0]["status"] == "new"
    c.post("/api/vocab/status", {"id": vocab[0]["id"], "status": "known"})
    assert c.get("/api/vocab?status=known")[1]["vocab"][0]["id"] == vocab[0]["id"]


def test_garbled_answer_retries_then_degrades(env):
    app, c, started = env
    model, calls = fake_model("not json at all")
    started.append(model)
    add_local(app, url_of(model))
    c.post("/api/settings", {"target_lang": "zh"})
    d = import_doc(c)
    st, r = c.post("/api/gloss/word", {"doc": d["id"], **ACC})
    assert st == 200 and r["sense"] == "not json at all" and len(calls) == 2


def test_cloud_out_of_quota_falls_back_to_local(env):
    app, c, started = env
    local, local_calls = fake_model(WORD_JSON)
    cloud, cloud_calls = fake_model("", status=429)
    started += [local, cloud]
    add_local(app, url_of(local))
    app.router.save_provider({"id": "cloud-1", "name": "Cloud", "kind": "openai", "base_url": url_of(cloud), "model": "big"})
    keys.set("cloud-1", "sk-test")
    c.post("/api/settings", {"target_lang": "zh", "mode": "prefer_cloud"})
    d = import_doc(c)
    st, r = c.post("/api/gloss/word", {"doc": d["id"], **ACC})
    assert st == 200 and r["fell_back"] is True and r["provider"]["id"] == "local-1"
    assert len(cloud_calls) == 1 and cloud_calls[0]["auth"] == "Bearer sk-test" and len(local_calls) == 1


def test_prefer_local_never_calls_cloud_when_local_works(env):
    app, c, started = env
    local, _ = fake_model(WORD_JSON)
    cloud, cloud_calls = fake_model(WORD_JSON)
    started += [local, cloud]
    add_local(app, url_of(local))
    app.router.save_provider({"id": "cloud-1", "name": "Cloud", "kind": "openai", "base_url": url_of(cloud), "model": "big"})
    keys.set("cloud-1", "sk-test")
    c.post("/api/settings", {"target_lang": "zh", "mode": "prefer_local"})
    d = import_doc(c)
    st, r = c.post("/api/gloss/word", {"doc": d["id"], **ACC})
    assert r["provider"]["id"] == "local-1" and r["fell_back"] is False and cloud_calls == []


def test_local_only_document_never_reaches_the_cloud(env):
    app, c, started = env
    cloud, cloud_calls = fake_model(WORD_JSON)
    started.append(cloud)
    app.router.save_provider({"id": "cloud-1", "name": "Cloud", "kind": "openai", "base_url": url_of(cloud), "model": "big"})
    keys.set("cloud-1", "sk-test")
    c.post("/api/settings", {"target_lang": "zh", "mode": "prefer_cloud"})
    d = import_doc(c, local_only=True)
    st, r = c.post("/api/gloss/word", {"doc": d["id"], **ACC})
    assert st == 400 and "仅本地" in r["error"] and cloud_calls == []


def test_all_models_down_reports_a_clear_error(env):
    app, c, _ = env
    add_local(app, "http://127.0.0.1:1/v1")                                  # nothing listens here
    c.post("/api/settings", {"target_lang": "zh"})
    d = import_doc(c)
    st, r = c.post("/api/gloss/word", {"doc": d["id"], **ACC})
    assert st == 502 and "没能回答" in r["error"]


def test_sentence_streams_in_sections(env):
    app, c, started = env
    model, calls = fake_model("", stream_chunks=[SENTENCE_TEXT[:20], SENTENCE_TEXT[20:]])
    started.append(model)
    add_local(app, url_of(model))
    c.post("/api/settings", {"target_lang": "zh"})
    d = import_doc(c)
    s, raw = c.call("POST", "/api/gloss/sentence", {"doc": d["id"], "para": 0, "start": 13, "end": 20})
    assert s == 200
    events = [json.loads(ln[6:]) for ln in raw.split("\n\n") if ln.startswith("data: ")]
    assert events[0]["meta"]["text"] == "We take into account the variance of each layer."     # expanded to the whole sentence
    assert "".join(e.get("delta", "") for e in events) == SENTENCE_TEXT and events[-1] == {"done": True}


def test_settings_and_target_language_are_required(env):
    app, c, started = env
    model, _ = fake_model(WORD_JSON)
    started.append(model)
    add_local(app, url_of(model))
    d = import_doc(c)
    st, r = c.post("/api/gloss/word", {"doc": d["id"], **ACC})            # no target language chosen yet
    assert st == 400 and "目标语言" in r["error"]
    assert c.post("/api/settings", {"target_lang": "xx"})[0] == 400
    assert c.post("/api/settings", {"target_lang": "ja"})[1]["target_lang"] == "ja"


def test_security_checks(env):
    app, c, _ = env
    st, _ = c.call("GET", "/api/state", headers={"Host": "evil.example.com"})
    assert st == 403
    st, _ = c.call("POST", "/api/settings", {"mode": "local_only"}, headers={"Origin": "https://evil.example.com"})
    assert st == 403
    st, _ = c.call("GET", "/../../etc/passwd")
    assert st == 404
    assert c.post("/api/docs/import", {"url": "http://127.0.0.1:8765/"})[0] == 400      # no importing local addresses


def test_provider_management_never_returns_keys(env):
    app, c, _ = env
    st, p = c.post("/api/providers/save", {"name": "DeepSeek", "kind": "openai", "base_url": "https://api.deepseek.com/v1",
                                          "model": "m", "key": "sk-secret"})
    assert st == 200
    state = c.get("/api/state")[1]
    assert "sk-secret" not in json.dumps(state)
    assert [x["has_key"] for x in state["providers"]] == [True]
    c.post("/api/providers/delete", {"id": p["id"]})
    assert c.get("/api/state")[1]["providers"] == [] and keys.get(p["id"]) == ""


def test_vocab_export_is_tab_separated(env):
    app, c, started = env
    model, _ = fake_model(WORD_JSON)
    started.append(model)
    add_local(app, url_of(model))
    c.post("/api/settings", {"target_lang": "zh"})
    d = import_doc(c)
    c.post("/api/gloss/word", {"doc": d["id"], **ACC})
    s, raw = c.call("GET", "/api/vocab/export")
    assert s == 200 and raw.split("\t")[:2] == ["take into account", "考虑到"]


# ---------------------------------------------------------------- PDF in its original layout
def tiny_pdf(lines):
    """A one-page PDF with real text (Helvetica), built by hand so no PDF writer is needed."""
    ops = ["BT /F1 14 Tf"] + [f"1 0 0 1 60 {740 - 30 * i} Tm ({ln}) Tj" for i, ln in enumerate(lines)] + ["ET"]
    stream = "\n".join(ops).encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    return bytes(out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode())


def import_pdf(client):
    pytest.importorskip("pypdf")
    data = base64.b64encode(tiny_pdf(["We take into account the variance of each layer. It is small.", "Another line of text for the page."])).decode()
    st, d = client.post("/api/docs/import", {"name": "paper.pdf", "data": data})
    assert st == 200, d
    return d


def test_pdf_original_is_kept_served_and_removed(env):
    app, c, _ = env
    d = import_pdf(c)
    assert d["has_pdf"] is True and (app.data / "files" / f"{d['id']}.pdf").is_file()
    st, raw = c.call("GET", f"/api/docs/{d['id']}/pdf")
    assert st == 200 and raw.startswith("%PDF-")
    assert c.get(f"/api/docs/{d['id']}")[1]["has_pdf"] is True and c.get(f"/api/docs/{d['id']}")[1]["pdf_page"] == 1
    assert c.get("/api/docs")[1]["docs"][0]["has_pdf"] is True
    c.post("/api/docs/update", {"id": d["id"], "pdf_page": 7})
    assert c.get(f"/api/docs/{d['id']}")[1]["pdf_page"] == 7
    c.post("/api/docs/delete", {"id": d["id"]})
    assert not (app.data / "files" / f"{d['id']}.pdf").exists() and c.call("GET", f"/api/docs/{d['id']}/pdf")[0] == 404
    assert app.store.kv_get(f"pdf_page:{d['id']}") is None


def test_pdf_endpoint_refuses_text_docs_and_odd_ids(env):
    app, c, _ = env
    d = import_doc(c)                                                       # pasted text: no original file
    assert d["has_pdf"] is False and c.call("GET", f"/api/docs/{d['id']}/pdf")[0] == 404
    (app.data / "secret.pdf").write_bytes(b"%PDF-secret")
    for bad in ("..%2Fsecret", "../secret", "%2e%2e%2fsecret", "A" * 12):
        assert c.call("GET", f"/api/docs/{bad}/pdf")[0] == 404, bad


def test_word_lookup_from_pdf_page_text(env):
    app, c, started = env
    model, calls = fake_model(WORD_JSON)
    started.append(model)
    add_local(app, url_of(model))
    c.post("/api/settings", {"target_lang": "zh"})
    d = import_pdf(c)
    page = "Intro sentence. We take into account the variance of each layer. It is small."
    i = page.index("account")
    st, r = c.post("/api/gloss/word", {"doc": d["id"], "ctx": page, "start": i, "end": i + 7})
    assert st == 200, r
    sent = json.loads(calls[0]["req"]["messages"][1]["content"])
    assert sent["clicked_word"] == "account" and sent["sentence"] == "We take into account the variance of each layer."
    assert sent["previous_sentence"] == "Intro sentence."
    st, r2 = c.post("/api/gloss/word", {"doc": d["id"], "ctx": page, "start": i, "end": i + 7})
    assert r2["cached"] is True and len(calls) == 1
    assert c.post("/api/gloss/word", {"doc": d["id"], "ctx": "  ", "start": 0, "end": 1})[0] == 400
    assert c.post("/api/gloss/word", {"doc": d["id"], "ctx": "x" * 13000, "start": 0, "end": 1})[0] == 400
    assert c.post("/api/gloss/word", {"doc": d["id"], "ctx": page, "start": 9, "end": 5})[0] == 400
    assert c.post("/api/gloss/word", {"doc": d["id"], "ctx": 5, "start": 0, "end": 1})[0] == 400


def test_pdf_page_context_respects_local_only(env):
    app, c, started = env
    cloud, calls = fake_model(WORD_JSON)
    started.append(cloud)
    app.router.save_provider({"id": "cloud-1", "name": "Cloud", "kind": "openai", "base_url": url_of(cloud), "model": "m", "local": False})
    keys.set("cloud-1", "sk-test")
    c.post("/api/settings", {"target_lang": "zh", "mode": "prefer_cloud"})
    d = import_pdf(c)
    c.post("/api/docs/update", {"id": d["id"], "local_only": True})
    st, r = c.post("/api/gloss/word", {"doc": d["id"], "ctx": "Some page text here.", "start": 5, "end": 9})
    assert st == 400 and not calls                                          # no local model, and the cloud one is never asked


def test_sentence_from_pdf_page_text_streams(env):
    app, c, started = env
    model, calls = fake_model(SENTENCE_TEXT, stream_chunks=[SENTENCE_TEXT[:20], SENTENCE_TEXT[20:]])
    started.append(model)
    add_local(app, url_of(model))
    c.post("/api/settings", {"target_lang": "zh"})
    d = import_pdf(c)
    page = "One. We take into account the variance of each layer. Three."
    i = page.index("variance")
    st, raw = c.call("POST", "/api/gloss/sentence", {"doc": d["id"], "ctx": page, "start": i, "end": i + 8, "expand": True})
    assert st == 200 and '"done": true' in raw
    assert "We take into account the variance of each layer." in calls[0]["req"]["messages"][1]["content"]


def test_vendored_pdfjs_is_served_with_a_script_type(env):
    app, c, _ = env
    for path, ctype in (("/vendor/pdfjs/pdf.min.mjs", "text/javascript"), ("/vendor/pdfjs/pdf.worker.min.mjs", "text/javascript")):
        conn = http.client.HTTPConnection("127.0.0.1", c.port, timeout=10)
        conn.request("GET", path)
        r = conn.getresponse()
        r.read()
        conn.close()
        assert r.status == 200 and r.getheader("Content-Type").startswith(ctype) and "max-age" in r.getheader("Cache-Control"), path


# ---------------------------------------------------------------- think-off parameters for local reasoning models
def test_local_no_think_sends_think_off_parameters(env):
    app, c, started = env
    model, calls = fake_model(WORD_JSON)
    started.append(model)
    add_local(app, url_of(model), no_think=True)
    c.post("/api/settings", {"target_lang": "zh"})
    d = import_doc(c)
    assert c.post("/api/gloss/word", {"doc": d["id"], **ACC})[0] == 200
    req = calls[0]["req"]
    assert req["reasoning_effort"] == "none" and req["chat_template_kwargs"] == {"enable_thinking": False}


def test_server_rejecting_think_off_parameters_is_retried_without_them(env):
    seen = []

    class Strict(BaseHTTPRequestHandler):                       # a server that answers 400 to parameters it does not know
        def log_message(self, *a):
            pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(sorted(k for k in req if k in ("reasoning_effort", "chat_template_kwargs")))
            ok = "reasoning_effort" not in req
            body = json.dumps({"choices": [{"message": {"content": WORD_JSON}}]} if ok else {"error": {"message": "unknown field"}}).encode()
            self.send_response(200 if ok else 400)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Strict)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    app, c, started = env
    started.append(srv)
    add_local(app, url_of(srv), no_think=True)
    c.post("/api/settings", {"target_lang": "zh"})
    d = import_doc(c)
    st, r = c.post("/api/gloss/word", {"doc": d["id"], **ACC})
    assert st == 200 and r["sense"] == "考虑到"
    assert seen == [["chat_template_kwargs", "reasoning_effort"], []]          # first with, then without
