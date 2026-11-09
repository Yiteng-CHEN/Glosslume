"""The two ways to run a model: llama.cpp (a prebuilt `llama-server` plus a GGUF file) and MLX (`mlx_lm.server` from the
mlx-lm package, installed into a virtual environment of its own so the app keeps no Python dependencies).

Both end up as an OpenAI-compatible server on 127.0.0.1, which is what the rest of Glosslume already talks to.
"""
from __future__ import annotations

import subprocess
import sys
import tarfile
import threading
import zipfile
from pathlib import Path

from . import catalog
from .download import DownloadError, Progress, fetch, hf_url


def _inside(root: Path, p: Path) -> bool:
    r, q = root.resolve(), p.resolve()
    return q == r or r in q.parents


def _safe_members(names: list[str], root: Path) -> None:
    for n in names:
        if not _inside(root, root / n):
            raise DownloadError("安装包里有不安全的路径，已拒绝")


def extract(archive: Path, dest: Path) -> None:
    """Unpack a release archive; refuses members (and links) that would land outside `dest`."""
    dest.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            _safe_members(z.namelist(), dest)
            z.extractall(dest)
        return
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            _safe_members([m.name], dest)
            if m.isdev() or (m.issym() and not _inside(dest, (dest / m.name).parent / m.linkname)) or (m.islnk() and not _inside(dest, dest / m.linkname)):
                raise DownloadError("安装包里有不安全的文件或链接，已拒绝")
        try:
            t.extractall(dest, filter="data")                 # Python 3.11.4+: refuses absolute paths, special files, setuid bits
        except TypeError:
            t.extractall(dest)


class Backend:
    name = ""

    def __init__(self, data: Path):
        self.data = data

    def engine_ready(self) -> bool: ...
    def install_engine(self, progress: Progress, cancel: threading.Event) -> None: ...
    def model_dir(self, model_id: str) -> Path: ...
    def model_ready(self, m: dict) -> bool: ...
    def install_model(self, m: dict, endpoint: str, progress: Progress, cancel: threading.Event) -> None: ...
    def command(self, m: dict, port: int) -> list[str]: ...
    def served_name(self, m: dict) -> str:
        return m["id"]


class LlamaCpp(Backend):
    name = "llamacpp"
    backoff = 2.0                                             # seconds before the first retry of a failed download (tests set 0)

    def __init__(self, data: Path):
        super().__init__(data)
        self.info = catalog.load()["llama_cpp"]
        self.asset = self.info["assets"].get(catalog.platform_key())
        self.home = data / "engines" / "llama.cpp" / self.info["tag"]

    def server(self) -> Path | None:
        exe = "llama-server.exe" if sys.platform == "win32" else "llama-server"
        return next(iter(self.home.rglob(exe)), None) if self.home.is_dir() else None

    def engine_ready(self) -> bool:
        return self.server() is not None and (self.home / ".ok").exists()

    def install_engine(self, progress: Progress, cancel: threading.Event) -> None:
        if not self.asset:
            raise DownloadError(f"这个系统（{catalog.platform_key()}）还没有现成的 llama.cpp 程序，暂时不能使用内置模型。")
        if self.engine_ready():
            return
        archive = self.data / "engines" / "downloads" / self.asset["name"]
        self._download(archive, progress, cancel)
        if self.home.exists():
            import shutil
            shutil.rmtree(self.home)                          # a half-extracted earlier attempt
        extract(archive, self.home)
        srv = self.server()
        if srv is None:
            raise DownloadError("安装包里没有找到 llama-server")
        if sys.platform != "win32":
            srv.chmod(srv.stat().st_mode | 0o755)
        (self.home / ".ok").write_text(self.info["tag"])
        archive.unlink(missing_ok=True)

    def _download(self, archive: Path, progress: Progress, cancel: threading.Event) -> None:
        """The release address first (one quick retry), then the GitHub API address, which still works where the first is blocked.
        Both are checked against the same pinned SHA256."""
        a = self.asset
        candidates = [(a["url"], None)] + ([(a["api_url"], {"Accept": "application/octet-stream"})] if a.get("api_url") else [])
        last: DownloadError | None = None
        for i, (url, headers) in enumerate(candidates):
            try:
                fetch(url, archive, a["size"], a["sha256"], progress, cancel, retries=1 if i < len(candidates) - 1 else 6,
                      headers=headers, backoff=self.backoff)
                return
            except DownloadError as e:
                last = e
        raise last or DownloadError("下载 llama.cpp 失败")

    def model_dir(self, model_id: str) -> Path:
        return self.data / "models" / model_id / "gguf"

    def model_file(self, m: dict) -> Path:
        return self.model_dir(m["id"]) / m["gguf"]["file"]

    def model_ready(self, m: dict) -> bool:
        f = self.model_file(m)
        return f.is_file() and f.stat().st_size == m["gguf"]["size"]

    def install_model(self, m, endpoint, progress, cancel) -> None:
        g = m["gguf"]
        fetch(hf_url(endpoint, g["repo"], g["rev"], g["file"]), self.model_file(m), g["size"], g["sha256"], progress, cancel)

    def command(self, m, port) -> list[str]:
        # --jinja: the model's own chat template; -c 8192: the default (the model's full context) can need tens of GB of memory;
        # -ngl 99: every layer on the GPU when there is one; --reasoning-budget 0: no thinking phase, which would only make word lookups slow
        return [str(self.server()), "--model", str(self.model_file(m)), "--host", "127.0.0.1", "--port", str(port),
                "--jinja", "-c", "8192", "-ngl", "99", "--reasoning-budget", "0", "--alias", m["id"]]


class Mlx(Backend):
    name = "mlx"

    def __init__(self, data: Path):
        super().__init__(data)
        self.version = catalog.load()["mlx_lm"]["version"]
        self.venv = data / "engines" / "mlx" / "venv"

    def python(self) -> Path:
        return self.venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    def engine_ready(self) -> bool:
        return self.python().exists() and (self.venv.parent / f".ok-{self.version}").exists()

    def install_engine(self, progress: Progress, cancel: threading.Event) -> None:
        if self.engine_ready():
            return
        progress(0, None, "engine")
        import shutil
        if self.venv.exists():
            shutil.rmtree(self.venv)
        self._run([sys.executable, "-m", "venv", str(self.venv)], "创建 MLX 运行环境失败")
        self._run([str(self.python()), "-m", "pip", "install", "--disable-pip-version-check", "-q", f"mlx-lm=={self.version}"],
                  "安装 mlx-lm 失败（需要联网访问 PyPI）", timeout=3600)
        self._run([str(self.python()), "-c", "import mlx_lm"], "mlx-lm 安装后无法导入")
        (self.venv.parent / f".ok-{self.version}").write_text(self.version)

    @staticmethod
    def _run(cmd: list[str], failure: str, timeout: float = 600) -> None:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise DownloadError(f"{failure}：{e}")
        if r.returncode != 0:
            raise DownloadError(f"{failure}：{(r.stderr or r.stdout).strip()[-400:]}")

    def model_dir(self, model_id: str) -> Path:
        return self.data / "models" / model_id / "mlx"

    def model_ready(self, m: dict) -> bool:
        d = self.model_dir(m["id"])
        return all((d / f["path"]).is_file() and (d / f["path"]).stat().st_size == f["size"] for f in m["mlx"]["files"])

    def install_model(self, m, endpoint, progress, cancel) -> None:
        mx, base = m["mlx"], 0
        total = sum(f["size"] for f in mx["files"])
        for f in mx["files"]:
            dest = self.model_dir(m["id"]) / f["path"]
            _safe_members([f["path"]], self.model_dir(m["id"]))
            fetch(hf_url(endpoint, mx["repo"], mx["rev"], f["path"]), dest, f["size"], f["sha256"],
                  lambda done, _t, phase, base=base: progress(base + done if phase == "download" else base + f["size"], total, phase), cancel)
            base += f["size"]

    def served_name(self, m: dict) -> str:
        return str(self.model_dir(m["id"]))

    def command(self, m, port) -> list[str]:
        return [str(self.python()), "-m", "mlx_lm.server", "--model", str(self.model_dir(m["id"])), "--host", "127.0.0.1", "--port", str(port)]


def make(name: str, data: Path) -> Backend:
    return Mlx(data) if name == "mlx" else LlamaCpp(data)
