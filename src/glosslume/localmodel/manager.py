"""Owns the built-in local model: downloads (one at a time, in a thread), the model server process, and the "builtin" provider.

Settings kept in the store's kv table:  local_model (the active model id), local_engine (auto | mlx | llamacpp),
hf_endpoint (Hugging Face or a mirror).
"""
from __future__ import annotations

import atexit
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..providers.base import Provider, ProviderError
from ..providers.router import Router
from ..store import Store
from . import catalog, engine
from .download import Cancelled, DownloadError

PROVIDER_ID = "builtin"
PREFERRED_PORT = 8781
DEFAULT_ENDPOINT = "https://huggingface.co"
MIRRORS = [("huggingface.co", DEFAULT_ENDPOINT), ("hf-mirror.com", "https://hf-mirror.com")]
START_TIMEOUT = 300                    # a 30B model can take a few minutes to load the first time


def _free_port() -> int:
    for port in (PREFERRED_PORT, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise OSError("没有可用的本机端口")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except OSError:
        return True                                                  # exists but belongs to someone else


class LocalModels:
    def __init__(self, data: Path, store: Store, router: Router):
        self.data, self.store, self.router = Path(data), store, router
        self.lock = threading.RLock()
        self.jobs: dict[str, dict] = {}
        self.cancels: dict[str, threading.Event] = {}
        self.proc: subprocess.Popen | None = None
        self.port = 0
        self.status, self.error, self.running = "stopped", "", ""
        self.ready = threading.Event()
        self.generation = 0                                          # bumps on every (re)start so stale waiters give up
        self.pidfile = self.data / "local-model.pid"
        self.log_path = self.data / "logs" / "local-model.log"
        router.hooks[PROVIDER_ID] = self.prepare
        atexit.register(self.stop)

    # ------------------------------------------------------------ settings
    def endpoint(self) -> str:
        return self.store.kv_get("hf_endpoint", DEFAULT_ENDPOINT) or DEFAULT_ENDPOINT

    def backend_name(self) -> str:
        pref = self.store.kv_get("local_engine", "auto")
        return pref if pref in catalog.BACKENDS else catalog.auto_backend()

    def backend(self) -> engine.Backend:
        return engine.make(self.backend_name(), self.data)

    def active(self) -> str:
        return self.store.kv_get("local_model", "") or ""

    def set_settings(self, endpoint: str | None = None, engine_name: str | None = None) -> None:
        if endpoint is not None:
            u = urllib.parse.urlparse(endpoint.strip())
            if u.scheme != "https" or not u.hostname or u.username or u.password or u.path.strip("/"):
                raise ValueError("下载源必须是 https:// 开头的网站地址，例如 https://hf-mirror.com")
            self.store.kv_set("hf_endpoint", f"https://{u.netloc}")
        if engine_name is not None:
            if engine_name not in ("auto", *catalog.BACKENDS):
                raise ValueError("不支持这个引擎")
            if engine_name == "mlx" and catalog.platform_key() != "darwin-arm64":
                raise ValueError("MLX 只能用在 Apple 芯片的 Mac 上")
            self.store.kv_set("local_engine", engine_name)
            if self.status != "stopped" and self.running and not self.backend().model_ready(catalog.get(self.running)):
                self.stop()

    # ------------------------------------------------------------ state for the settings page
    def state(self) -> dict:
        be, ram = self.backend(), catalog.total_ram_gb()
        rec = catalog.recommended_for(ram)
        rows = []
        for m in catalog.models():
            rows.append({"id": m["id"], "name": m["name"], "note": m["note"], "ram_gb": m["ram_gb"], "bytes": catalog.model_bytes(m, be.name),
                         "license": catalog.licence(m, be.name), "repo": (m["mlx"] if be.name == "mlx" else m["gguf"])["repo"],
                         "installed": be.model_ready(m), "fits": ram == 0 or m["ram_gb"] <= ram, "recommended": m["id"] == rec,
                         "active": m["id"] == self.active(), "job": self.jobs.get(m["id"])})
        free = shutil.disk_usage(self.data).free / 2**30 if self.data.exists() else 0
        return {"backend": be.name, "backend_setting": self.store.kv_get("local_engine", "auto"), "engine_ready": be.engine_ready(),
                "engine_can_choose_mlx": catalog.platform_key() == "darwin-arm64", "ram_gb": round(ram, 1), "disk_free_gb": round(free, 1),
                "endpoint": self.endpoint(), "mirrors": [{"name": n, "url": u} for n, u in MIRRORS],
                "running": {"status": self.status, "model": self.running, "error": self.error, "port": self.port}, "models": rows}

    # ------------------------------------------------------------ downloads
    def install(self, model_id: str) -> None:
        m = catalog.get(model_id)
        if not m:
            raise ValueError("没有这个模型")
        be = self.backend()
        with self.lock:
            if any(j["phase"] in ("engine", "download", "verify") for j in self.jobs.values()):
                raise ValueError("已经有一个下载在进行，请等它完成或先取消")
            need = catalog.model_bytes(m, be.name) + (0 if be.engine_ready() else (2 * 2**30 if be.name == "mlx" else 150 * 2**20)) + 2**30
            self.data.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(self.data).free
            if free < need:
                raise ValueError(f"磁盘空间不够：需要约 {need / 2**30:.1f} GB，现在只剩 {free / 2**30:.1f} GB")
            self.cancels[model_id] = threading.Event()
            self.jobs[model_id] = {"phase": "engine" if not be.engine_ready() else "download", "done": 0, "total": catalog.model_bytes(m, be.name), "error": ""}
        threading.Thread(target=self._install, args=(m, be), daemon=True).start()

    def _install(self, m: dict, be: engine.Backend) -> None:
        mid, cancel = m["id"], self.cancels[m["id"]]
        job = self.jobs[mid]

        def on_engine(done, total, phase):
            job.update(phase="verify" if phase == "verify" else "engine", done=done, total=total or 0)

        def on_model(done, total, phase):
            job.update(phase="verify" if phase == "verify" else "download", done=done, total=total or job["total"])
        try:
            be.install_engine(on_engine, cancel)
            job.update(phase="download", done=0, total=catalog.model_bytes(m, be.name))
            be.install_model(m, self.endpoint(), on_model, cancel)
            job.update(phase="done", done=job["total"])
            if not self.active() or not catalog.get(self.active()) or not be.model_ready(catalog.get(self.active())):
                self.store.kv_set("local_model", mid)
            if self.active() == mid:
                self.start()
        except Cancelled:
            job.update(phase="cancelled", error="")
        except DownloadError as e:
            job.update(phase="error", error=str(e))
        except Exception as e:                                        # never leave the page waiting on a dead thread
            job.update(phase="error", error=f"安装失败：{e}")

    def cancel(self, model_id: str) -> None:
        if model_id in self.cancels:
            self.cancels[model_id].set()

    def remove(self, model_id: str) -> None:
        m = catalog.get(model_id)
        if not m:
            raise ValueError("没有这个模型")
        job = self.jobs.get(model_id)
        if job and job["phase"] in ("engine", "download", "verify"):
            raise ValueError("这个模型正在下载，请先取消")
        if self.running == model_id:
            self.stop()
        target = (self.data / "models" / model_id).resolve()
        if (self.data / "models").resolve() in target.parents and target.is_dir():
            shutil.rmtree(target)
        self.jobs.pop(model_id, None)
        if self.active() == model_id:
            self.store.kv_set("local_model", "")
            self.router.delete_provider(PROVIDER_ID)

    def select(self, model_id: str) -> None:
        m = catalog.get(model_id)
        if not m or not self.backend().model_ready(m):
            raise ValueError("这个模型还没有下载")
        self.store.kv_set("local_model", model_id)
        self.start()

    # ------------------------------------------------------------ the server process
    def start(self) -> None:
        """(Re)start the active model in the background; returns at once, status says how it goes."""
        threading.Thread(target=self._start, daemon=True).start()

    def autostart(self) -> None:
        m = catalog.get(self.active())
        if m and self.backend().engine_ready() and self.backend().model_ready(m):
            self.start()

    def _start(self) -> None:
        with self.lock:
            self._stop_locked()
            m, be = catalog.get(self.active()), self.backend()
            if not m or not be.engine_ready() or not be.model_ready(m):
                return
            self._reap_stale()
            self.generation += 1
            gen = self.generation
            try:
                self.port = _free_port()
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                log = open(self.log_path, "wb")
                kw = {"creationflags": 0x08000000} if sys.platform == "win32" else {"start_new_session": True}
                self.proc = subprocess.Popen(be.command(m, self.port), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
            except OSError as e:
                self.status, self.error = "error", f"启动内置模型失败：{e}"
                return
            self.pidfile.write_text(f"{self.proc.pid} {os.getpid()}")          # model server pid, owner (this Glosslume) pid
            self.status, self.error, self.running = "starting", "", m["id"]
            self.ready.clear()
            self.router.save_provider({"id": PROVIDER_ID, "name": f"内置 · {m['name']}", "kind": "openai", "base_url": f"http://127.0.0.1:{self.port}/v1",
                                       "model": be.served_name(m), "local": True, "no_think": True})
            proc, port = self.proc, self.port
        deadline = time.time() + START_TIMEOUT
        while time.time() < deadline:
            with self.lock:
                if gen != self.generation:
                    return                                           # superseded by a newer start or a stop
            if proc.poll() is not None:
                with self.lock:
                    self.status, self.error = "error", "内置模型启动后退出了：" + self._log_tail()
                return
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=2) as r:
                    if r.status == 200:
                        break
            except (urllib.error.URLError, OSError, TimeoutError):
                pass
            time.sleep(1)
        else:
            with self.lock:
                if gen == self.generation:
                    self.status, self.error = "error", "内置模型加载超时：" + self._log_tail()
            return
        with self.lock:
            if gen != self.generation:
                return
            self.status = "ready"
            self.ready.set()

    def _log_tail(self) -> str:
        try:
            return self.log_path.read_text(errors="replace").strip()[-500:]
        except OSError:
            return ""

    def _reap_stale(self) -> None:
        """A previous Glosslume that was killed hard may have left its model server running: stop that one.
        A server whose owner Glosslume is still alive (a second window on the same data folder) is left alone."""
        if sys.platform == "win32":
            return
        try:
            pid, owner = (int(x) for x in self.pidfile.read_text().split())
        except (OSError, ValueError):
            return
        if owner != os.getpid() and _alive(owner):
            return
        try:
            cmd = subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True, timeout=5)
            if "llama-server" in cmd or "mlx_lm.server" in cmd:
                os.killpg(pid, signal.SIGTERM) if os.getpgid(pid) == pid else os.kill(pid, signal.SIGTERM)
                for _ in range(30):                                  # let it release its port before we pick one
                    if not _alive(pid):
                        break
                    time.sleep(0.1)
        except (subprocess.SubprocessError, OSError):
            pass

    def stop(self) -> None:
        with self.lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        self.generation += 1
        proc, self.proc = self.proc, None
        self.ready.clear()
        if proc and proc.poll() is None:
            try:
                (os.killpg(proc.pid, signal.SIGTERM) if sys.platform != "win32" else proc.terminate())
                proc.wait(timeout=8)
            except (OSError, subprocess.TimeoutExpired):
                proc.kill()
        self.status, self.running, self.port = "stopped", "", 0
        self.pidfile.unlink(missing_ok=True)

    # ------------------------------------------------------------ router hook
    def current_provider(self):
        """The built-in provider as this process runs it now (built from our own state, not from the shared settings)."""
        m = catalog.get(self.running)
        if not m or not self.port:
            return None
        return Provider(id=PROVIDER_ID, name=f"内置 · {m['name']}", kind="openai", base_url=f"http://127.0.0.1:{self.port}/v1",
                        model=self.backend().served_name(m), local=True, no_think=True)

    def prepare(self, _provider):
        """Called before each request to the built-in model: make sure it is up, waiting for a load in progress.
        Returns the provider as it is now (a restart changes the port)."""
        with self.lock:
            alive = self.proc is not None and self.proc.poll() is None
            if self.status == "ready" and alive:
                return self.current_provider()
            m = catalog.get(self.active())
            if not m or not self.backend().model_ready(m):
                raise ProviderError("内置模型还没有下载：请到设置里选一个模型并下载。", "unavailable")
            if not (self.status == "starting" and alive):
                self.start()
                self.status, self.error = "starting", ""
        deadline = time.time() + START_TIMEOUT
        while time.time() < deadline:
            if self.ready.wait(1):
                return self.current_provider()
            if self.status == "error":
                raise ProviderError(self.error or "内置模型没能启动", "unavailable")
        raise ProviderError("内置模型还在加载，请稍后再试（大模型第一次载入要一两分钟）。", "unavailable")
