"""Download one file: resumable (HTTP Range into a .part file), verified (size and SHA256), cancellable, retried.

Only https is accepted (plain http only to this computer, which the tests use). A file whose SHA256 does not match the
pinned value is deleted and reported, never kept.
"""
from __future__ import annotations

import hashlib
import http.client
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

CHUNK = 1 << 20
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
Progress = Callable[[int, "int | None", str], None]          # (bytes done, total or None, phase: download | verify)


class Cancelled(Exception):
    pass


class DownloadError(Exception):
    """The message is meant to be shown to the user."""


def check_url(url: str) -> None:
    p = urllib.parse.urlparse(url)
    if p.username or p.password or not p.hostname:
        raise DownloadError("下载地址不对")
    if p.scheme != "https" and not (p.scheme == "http" and p.hostname in LOCAL_HOSTS):
        raise DownloadError("只允许 https 下载地址")


def hf_url(endpoint: str, repo: str, rev: str, path: str) -> str:
    """File URL on Hugging Face or a mirror that serves the same /resolve/ paths."""
    return f"{endpoint.rstrip('/')}/{repo}/resolve/{rev}/{urllib.parse.quote(path)}"


def sha256_of(path: Path, progress: Progress | None = None, cancel: threading.Event | None = None) -> str:
    h, done, total = hashlib.sha256(), 0, path.stat().st_size
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            h.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total, "verify")
    return h.hexdigest()


def _transfer(url: str, part: Path, have: int, size: int | None, progress: Progress | None, cancel: threading.Event | None,
              timeout: float, extra: dict | None = None) -> None:
    headers = {"User-Agent": "Glosslume", "Accept-Encoding": "identity", **(extra or {})}
    if have:
        headers["Range"] = f"bytes={have}-"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        if have and r.status != 206:                         # the server ignored Range: start over
            have = 0
        with open(part, "ab" if have else "wb") as f:
            done = have
            while chunk := r.read(CHUNK):
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, size, "download")


def fetch(url: str, dest: Path, size: int | None = None, sha256: str | None = None, progress: Progress | None = None,
          cancel: threading.Event | None = None, retries: int = 6, backoff: float = 2.0, timeout: float = 30.0,
          headers: dict | None = None) -> None:
    """Make `dest` exist with the right content. Keeps `dest.part` between attempts and between runs."""
    check_url(url)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and (size is None or dest.stat().st_size == size) and (sha256 is None or sha256_of(dest, progress, cancel) == sha256):
        if progress:
            progress(dest.stat().st_size, size, "download")
        return
    part = dest.with_name(dest.name + ".part")
    failures = 0
    while True:
        have = part.stat().st_size if part.exists() else 0
        if size is not None and have > size:
            part.unlink()
            have = 0
        if size is None or have < size:
            try:
                _transfer(url, part, have, size, progress, cancel, timeout, headers)
            except urllib.error.HTTPError as e:
                if e.code == 416 and have:                   # asked for bytes past the end: the .part is already complete
                    pass
                elif e.code in (429, 500, 502, 503, 504):
                    failures += 1
                else:
                    raise DownloadError(f"服务器拒绝了下载（HTTP {e.code}）：{url}")
            except (urllib.error.URLError, OSError, http.client.HTTPException, TimeoutError) as e:
                failures += 1
                last = getattr(e, "reason", e)
                if failures > retries:
                    raise DownloadError(f"网络中断，重试多次仍失败：{last}。已下载的部分会保留，之后可以继续。")
            else:
                if size is None:
                    break                                    # no expected size: a clean end of stream is the end of the file
                failures = 0 if part.stat().st_size > have else failures + 1
            if failures:
                if failures > retries:
                    raise DownloadError("下载多次失败，请检查网络或在设置里换一个下载镜像。已下载的部分会保留。")
                time.sleep(min(backoff * 2 ** (failures - 1), 30))
                continue
        now = part.stat().st_size if part.exists() else 0
        if size is not None and now < size:                   # connection closed early without an error
            failures += 1
            if failures > retries:
                raise DownloadError("下载被提前中断，请稍后重试。已下载的部分会保留。")
            continue
        break
    if size is not None and part.stat().st_size != size:
        part.unlink(missing_ok=True)
        raise DownloadError("文件大小和预期不符，已丢弃，请重试。")
    if sha256 is not None and sha256_of(part, progress, cancel) != sha256:
        part.unlink(missing_ok=True)
        raise DownloadError("文件校验失败（SHA256 不一致），已丢弃。可能是网络被劫持或镜像不完整，请换个下载源再试。")
    os.replace(part, dest)
