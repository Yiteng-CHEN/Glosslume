"""Built-in local model: catalog pins, resumable verified downloads, safe archive extraction, and the manager's lifecycle
(install -> start -> provider "builtin" answers -> remove) against a fake model server process. No network, no real model."""
import hashlib
import http.client
import io
import json
import re
import sys
import tarfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from glosslume.localmodel import catalog, engine
from glosslume.localmodel.download import Cancelled, DownloadError, fetch, hf_url
from glosslume.localmodel.manager import PROVIDER_ID, LocalModels
from glosslume.providers import keys
from glosslume.providers.base import ProviderError
from glosslume.server.app import App, serve_in_thread

PAYLOAD = bytes(range(256)) * 4096                                     # 1 MiB of non-repeating-ish data
SHA = hashlib.sha256(PAYLOAD).hexdigest()
WORD = ('{"span":"take into account","lemma":"take into account","pos":"v","sense":"考虑到","why":"fixed phrase",'
        '"other_senses":["账户"],"kind":"common"}')


# ---------------------------------------------------------------- a file server with Range support and misbehaviours
def file_server(body: bytes = PAYLOAD, *, ignore_range=False, drop_first=False, status=200):
    seen = {"ranges": [], "hits": 0, "accept": []}

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def do_GET(self):
            seen["hits"] += 1
            seen["accept"].append(self.headers.get("Accept"))
            if status != 200:
                self.send_response(status)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            rng = self.headers.get("Range")
            seen["ranges"].append(rng)
            start = 0
            if rng and not ignore_range:
                start = int(re.match(r"bytes=(\d+)-", rng).group(1))
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
            else:
                self.send_response(200)
            data = body[start:]
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if drop_first and seen["hits"] == 1:
                self.wfile.write(data[: len(data) // 3])               # promise more than we send, then hang up
                self.wfile.flush()
                self.close_connection = True
                return
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/m.bin", seen


# ---------------------------------------------------------------- catalog
def test_catalog_pins_everything_the_app_downloads():
    cat = catalog.load()
    assert catalog.get(cat["recommended"]) and len(catalog.models()) >= 5
    for m in catalog.models():
        g = m["gguf"]
        assert re.fullmatch(r"[0-9a-f]{64}", g["sha256"]) and g["size"] > 10**9 and re.fullmatch(r"[0-9a-f]{40}", g["rev"]), m["id"]
        assert g["file"].endswith(".gguf") and m["ram_gb"] > 0 and m["note"]["zh"] and m["note"]["en"]
        big = [f for f in m["mlx"]["files"] if f["path"].endswith(".safetensors")]
        assert big and all(re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) for f in big), m["id"]    # weights are always hash-checked
        assert all(".." not in f["path"] and not f["path"].startswith("/") for f in m["mlx"]["files"])
    for key, a in cat["llama_cpp"]["assets"].items():
        assert re.fullmatch(r"[0-9a-f]{64}", a["sha256"]) and a["url"].startswith("https://github.com/ggml-org/llama.cpp/"), key
    assert {"darwin-arm64", "linux-x86_64", "windows-x86_64"} <= set(cat["llama_cpp"]["assets"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", cat["mlx_lm"]["version"])


def test_recommendation_follows_memory_and_backend_follows_platform(monkeypatch):
    assert catalog.recommended_for(128) == catalog.load()["recommended"] and catalog.recommended_for(8) == "qwen3.5-4b"
    assert catalog.recommended_for(2) == "qwen3.5-4b"                        # nothing fits: the smallest one
    monkeypatch.setattr(catalog, "platform_key", lambda: "darwin-arm64")
    assert catalog.auto_backend() == "mlx"
    monkeypatch.setattr(catalog, "platform_key", lambda: "linux-x86_64")
    assert catalog.auto_backend() == "llamacpp"
    assert hf_url("https://hf-mirror.com/", "a/b", "abc", "dir/x y.gguf") == "https://hf-mirror.com/a/b/resolve/abc/dir/x%20y.gguf"


# ---------------------------------------------------------------- download
def test_fetch_downloads_and_verifies(tmp_path):
    srv, url, _ = file_server()
    seen = []
    fetch(url, tmp_path / "m.bin", len(PAYLOAD), SHA, lambda d, t, ph: seen.append((d, t, ph)))
    assert (tmp_path / "m.bin").read_bytes() == PAYLOAD and not (tmp_path / "m.bin.part").exists()
    assert seen[-1][2] == "verify" and any(p == "download" for _, _, p in seen)
    srv.shutdown()


def test_fetch_resumes_from_a_part_file(tmp_path):
    srv, url, seen = file_server()
    (tmp_path / "m.bin.part").write_bytes(PAYLOAD[:300_000])
    fetch(url, tmp_path / "m.bin", len(PAYLOAD), SHA)
    assert (tmp_path / "m.bin").read_bytes() == PAYLOAD and seen["ranges"] == ["bytes=300000-"]
    srv.shutdown()


def test_fetch_restarts_when_the_server_ignores_range(tmp_path):
    srv, url, _ = file_server(ignore_range=True)
    (tmp_path / "m.bin.part").write_bytes(PAYLOAD[:1000])
    fetch(url, tmp_path / "m.bin", len(PAYLOAD), SHA)
    assert (tmp_path / "m.bin").read_bytes() == PAYLOAD
    srv.shutdown()


def test_fetch_retries_a_dropped_connection_and_continues(tmp_path):
    srv, url, seen = file_server(drop_first=True)
    fetch(url, tmp_path / "m.bin", len(PAYLOAD), SHA, backoff=0)
    assert (tmp_path / "m.bin").read_bytes() == PAYLOAD and seen["hits"] >= 2 and seen["ranges"][1] and seen["ranges"][1].startswith("bytes=")
    srv.shutdown()


def test_fetch_rejects_wrong_hash_and_removes_the_file(tmp_path):
    srv, url, _ = file_server()
    with pytest.raises(DownloadError, match="校验失败"):
        fetch(url, tmp_path / "m.bin", len(PAYLOAD), "0" * 64)
    assert not (tmp_path / "m.bin").exists() and not (tmp_path / "m.bin.part").exists()
    srv.shutdown()


def test_fetch_rejects_wrong_size_http_errors_and_plain_http(tmp_path):
    srv, url, _ = file_server()
    with pytest.raises(DownloadError):
        fetch(url, tmp_path / "a.bin", len(PAYLOAD) - 5, None)               # the server has more than promised
    srv.shutdown()
    srv, url, _ = file_server(status=404)
    with pytest.raises(DownloadError, match="404"):
        fetch(url, tmp_path / "b.bin", 10, None)
    srv.shutdown()
    with pytest.raises(DownloadError, match="https"):
        fetch("http://example.com/x.bin", tmp_path / "c.bin", 1, None)
    with pytest.raises(DownloadError):
        fetch("https://user:pw@example.com/x.bin", tmp_path / "d.bin", 1, None)


def test_fetch_cancel_keeps_the_partial_file_for_later(tmp_path):
    srv, url, _ = file_server()
    ev = threading.Event()
    ev.set()
    with pytest.raises(Cancelled):
        fetch(url, tmp_path / "m.bin", len(PAYLOAD), SHA, cancel=ev)
    assert not (tmp_path / "m.bin").exists()
    ev.clear()
    fetch(url, tmp_path / "m.bin", len(PAYLOAD), SHA, cancel=ev)
    assert (tmp_path / "m.bin").read_bytes() == PAYLOAD
    srv.shutdown()


def test_an_already_complete_file_is_not_downloaded_again(tmp_path):
    srv, url, seen = file_server()
    (tmp_path / "m.bin").write_bytes(PAYLOAD)
    fetch(url, tmp_path / "m.bin", len(PAYLOAD), SHA)
    assert seen["hits"] == 0
    srv.shutdown()


def test_engine_download_falls_back_to_the_api_address_when_the_release_address_fails(tmp_path):
    bad, bad_url, bad_seen = file_server(status=504)
    good, good_url, good_seen = file_server()
    be = engine.LlamaCpp(tmp_path)
    be.backoff = 0
    be.asset = {"name": "llama.tar.gz", "url": bad_url, "api_url": good_url, "size": len(PAYLOAD), "sha256": SHA}
    be._download(tmp_path / "llama.tar.gz", lambda *a: None, threading.Event())
    assert (tmp_path / "llama.tar.gz").read_bytes() == PAYLOAD
    assert bad_seen["hits"] >= 1 and good_seen["accept"] == ["application/octet-stream"]
    be.asset = {**be.asset, "api_url": bad_url}                                 # both fail: the error is reported
    (tmp_path / "llama.tar.gz").unlink()
    with pytest.raises(DownloadError):
        be._download(tmp_path / "llama.tar.gz", lambda *a: None, threading.Event())
    bad.shutdown()
    good.shutdown()


# ---------------------------------------------------------------- archives
def make_tar(path: Path, members: list):
    with tarfile.open(path, "w:gz") as t:
        for name, data, kind in members:
            ti = tarfile.TarInfo(name)
            if kind == "sym":
                ti.type, ti.linkname = tarfile.SYMTYPE, data
                t.addfile(ti)
            else:
                ti.size = len(data)
                t.addfile(ti, io.BytesIO(data))


def test_extract_unpacks_a_normal_release(tmp_path):
    make_tar(tmp_path / "ok.tar.gz", [("llama/llama-server", b"#!/bin/sh\n", "file"), ("llama/libx.dylib", b"x", "file"), ("llama/libx.0.dylib", "libx.dylib", "sym")])
    engine.extract(tmp_path / "ok.tar.gz", tmp_path / "out")
    assert (tmp_path / "out/llama/llama-server").is_file() and (tmp_path / "out/llama/libx.0.dylib").is_symlink()


@pytest.mark.parametrize("members", [[("../evil", b"x", "file")], [("/abs/evil", b"x", "file")], [("a/link", "../../outside", "sym")]])
def test_extract_refuses_paths_and_links_that_escape(tmp_path, members):
    make_tar(tmp_path / "bad.tar.gz", members)
    with pytest.raises(DownloadError, match="不安全"):
        engine.extract(tmp_path / "bad.tar.gz", tmp_path / "out")
    assert not (tmp_path / "evil").exists() and not (tmp_path / "outside").exists()


# ---------------------------------------------------------------- manager lifecycle with a fake engine and a fake model server
FAKE_SERVER = '''
import json, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj):
        body = json.dumps(obj).encode(); self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self): self._send({"data": [{"id": "fake"}]})
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"])); self._send({"choices": [{"message": {"content": %r}}]})
ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
''' % WORD


class FakeBackend(engine.Backend):
    name = "llamacpp"

    def __init__(self, data, url):
        super().__init__(data)
        self.url, self.installed_engine = url, False

    def engine_ready(self):
        return self.installed_engine

    def install_engine(self, progress, cancel):
        self.installed_engine = True

    def model_dir(self, mid):
        return self.data / "models" / mid / "gguf"

    def model_ready(self, m):
        f = self.model_dir(m["id"]) / "m.gguf"
        return f.is_file() and f.stat().st_size == len(PAYLOAD)

    def install_model(self, m, endpoint, progress, cancel):
        fetch(self.url, self.model_dir(m["id"]) / "m.gguf", len(PAYLOAD), SHA, progress, cancel, backoff=0)

    def command(self, m, port):
        return [sys.executable, "-c", FAKE_SERVER, str(port)]


FAKE_MODEL = {"id": "fake-1", "name": "Fake 1", "ram_gb": 1, "note": {"zh": "测试", "en": "test"},
              "gguf": {"repo": "x/y", "rev": "r", "file": "m.gguf", "size": len(PAYLOAD), "sha256": SHA, "license": "mit"},
              "mlx": {"repo": "x/z", "rev": "r", "files": [], "license": ""}}


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(keys, "_kr", None)
    keys._mem.clear()
    monkeypatch.setattr(catalog, "load", lambda: {"recommended": "fake-1", "models": [FAKE_MODEL], "llama_cpp": {"tag": "t", "assets": {}}, "mlx_lm": {"version": "0"}})
    srv, url, _ = file_server()
    app = App(tmp_path)
    fake = FakeBackend(tmp_path, url)
    monkeypatch.setattr(LocalModels, "backend", lambda self: fake)
    yield app, fake
    app.local.stop()
    srv.shutdown()


def wait(cond, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def test_install_then_start_registers_a_local_provider_that_answers(local):
    app, fake = local
    lm = app.local
    st = lm.state()
    assert st["models"][0]["installed"] is False and st["running"]["status"] == "stopped" and st["models"][0]["recommended"] is True
    lm.install("fake-1")
    assert wait(lambda: lm.jobs["fake-1"]["phase"] in ("done", "error")), lm.jobs
    assert lm.jobs["fake-1"]["phase"] == "done" and lm.active() == "fake-1"
    assert wait(lambda: lm.status == "ready"), lm.error
    p = next(x for x in app.router.providers() if x.id == PROVIDER_ID)
    assert p.local and p.no_think and p.base_url == f"http://127.0.0.1:{lm.port}/v1" and "Fake 1" in p.name
    app.store.kv_set("target_lang", "zh")
    d = app.store.add_doc("t", "s", "en", ["We take into account the variance."], ["en"])
    r = app.glosser.word(d, 0, 13, 20, "zh")
    assert r["sense"] == "考虑到" and r["provider"]["id"] == PROVIDER_ID
    assert lm.state()["models"][0]["installed"] is True and lm.state()["models"][0]["active"] is True


def test_the_model_server_is_started_on_demand_after_a_restart(local):
    app, fake = local
    lm = app.local
    lm.install("fake-1")
    assert wait(lambda: lm.status == "ready")
    lm.stop()
    assert lm.status == "stopped"
    app.store.kv_set("target_lang", "zh")
    d = app.store.add_doc("t", "s", "en", ["We take into account the variance."], ["en"])
    assert app.glosser.word(d, 0, 13, 20, "zh")["sense"] == "考虑到"           # the router hook starts it and waits
    assert lm.status == "ready"


def test_without_a_downloaded_model_the_provider_says_so(local):
    app, fake = local
    with pytest.raises(ProviderError, match="还没有下载"):
        app.local.prepare(None)
    with pytest.raises(ValueError, match="还没有下载"):
        app.local.select("fake-1")
    with pytest.raises(ValueError, match="没有这个模型"):
        app.local.install("nope")


def test_only_one_download_at_a_time_and_cancel(local, monkeypatch):
    app, fake = local
    lm = app.local
    gate = threading.Event()
    real = fake.install_model

    def slow(m, endpoint, progress, cancel):
        gate.wait(10)
        if cancel.is_set():
            raise Cancelled()
        real(m, endpoint, progress, cancel)
    monkeypatch.setattr(fake, "install_model", slow)
    lm.install("fake-1")
    with pytest.raises(ValueError, match="已经有一个下载"):
        lm.install("fake-1")
    with pytest.raises(ValueError, match="正在下载"):
        lm.remove("fake-1")
    lm.cancel("fake-1")
    gate.set()
    assert wait(lambda: lm.jobs["fake-1"]["phase"] == "cancelled")
    assert lm.state()["models"][0]["installed"] is False and lm.active() == ""


def test_remove_stops_the_server_and_deletes_the_files_and_the_provider(local):
    app, fake = local
    lm = app.local
    lm.install("fake-1")
    assert wait(lambda: lm.status == "ready")
    assert (app.data / "models" / "fake-1").is_dir()
    lm.remove("fake-1")
    assert lm.status == "stopped" and lm.active() == "" and not (app.data / "models" / "fake-1").exists()
    assert all(p.id != PROVIDER_ID for p in app.router.providers())


def test_a_download_failure_is_reported_not_swallowed(local, monkeypatch):
    app, fake = local
    lm = app.local

    def boom(m, endpoint, progress, cancel):
        raise DownloadError("文件校验失败（SHA256 不一致）")
    monkeypatch.setattr(fake, "install_model", boom)
    lm.install("fake-1")
    assert wait(lambda: lm.jobs["fake-1"]["phase"] == "error")
    assert "校验失败" in lm.jobs["fake-1"]["error"] and lm.active() == ""


def test_settings_validate_the_download_source_and_engine(local):
    lm = local[0].local
    lm.set_settings(endpoint="https://hf-mirror.com/")
    assert lm.endpoint() == "https://hf-mirror.com"
    for bad in ("http://hf-mirror.com", "https://user:pw@x.com", "https://x.com/some/path", "ftp://x", "hf-mirror.com", ""):
        with pytest.raises(ValueError):
            lm.set_settings(endpoint=bad)
    with pytest.raises(ValueError):
        lm.set_settings(engine_name="cuda")
    assert lm.endpoint() == "https://hf-mirror.com"


def test_local_api_routes(local):
    app, fake = local
    srv, _ = serve_in_thread(app)
    port = srv.server_address[1]

    def call(method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request(method, path, json.dumps(body) if body is not None else None, {"Content-Type": "application/json"})
        r = c.getresponse()
        return r.status, json.loads(r.read())
    st, d = call("GET", "/api/local")
    assert st == 200 and d["models"][0]["id"] == "fake-1" and d["running"]["status"] == "stopped"
    assert call("POST", "/api/local/install", {"model": "nope"})[0] == 400
    assert call("POST", "/api/local/install", {"model": "fake-1"})[0] == 200
    assert wait(lambda: call("GET", "/api/local")[1]["running"]["status"] == "ready")
    assert call("POST", "/api/local/settings", {"endpoint": "http://bad"})[0] == 400
    assert call("POST", "/api/local/remove", {"model": "fake-1"})[0] == 200
    assert call("GET", "/api/local")[1]["models"][0]["installed"] is False
    srv.shutdown()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process handling")
def test_stale_model_servers_are_reaped_only_when_their_owner_is_gone(local):
    import subprocess
    lm = local[0].local

    def decoy():                                              # a process whose command line looks like a model server
        return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", "llama-server"], start_new_session=True)
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    alive_owner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        d = decoy()
        lm.pidfile.write_text(f"{d.pid} {alive_owner.pid}")                    # another Glosslume still owns it: hands off
        lm._reap_stale()
        time.sleep(0.3)
        assert d.poll() is None
        lm.pidfile.write_text(f"{d.pid} {gone.pid}")                            # its owner died: stop it
        lm._reap_stale()
        assert d.wait(timeout=5) is not None
    finally:
        alive_owner.kill()
        if d.poll() is None:
            d.kill()
