"""Turn a URL, a file or pasted text into clean paragraphs. Standard library only (PDF needs `pypdf`)."""
from __future__ import annotations

import io
import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

MAX_BYTES = 25_000_000
UA = "Glosslume/0.1 (+local reader)"


class ImportFail(Exception):
    """The message is meant to be shown to the user."""


@dataclass
class Imported:
    title: str
    source: str
    paragraphs: list[str]
    note: str = ""
    pdf: bytes | None = None          # the original PDF bytes, kept so the reader can show the real page layout


# ---------------------------------------------------------------- plain text
def paragraphs_from_text(raw: str) -> list[str]:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    raw = re.sub(r"(?<=[A-Za-z])-\n(?=[a-z])", "", raw)            # words hyphenated at a line break
    out = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [re.sub(r"^#{1,6}\s+", "", ln.strip()) for ln in block.split("\n") if ln.strip()]
        if lines:
            out.append(re.sub(r"\s+", " ", " ".join(lines)).strip())
    return [p for p in out if p]


def _title_from(paragraphs: list[str], fallback: str = "Untitled") -> str:
    if not paragraphs:
        return fallback
    first = paragraphs[0]
    return first if len(first) <= 80 else first[:77].rstrip() + "…"


def from_text(text: str, title: str = "", source: str = "pasted text") -> Imported:
    paras = paragraphs_from_text(text)
    if not paras:
        raise ImportFail("没有读到任何文字")
    return Imported(title.strip() or _title_from(paras), source, paras)


# ---------------------------------------------------------------- HTML
_BLOCK = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "figcaption", "td", "th", "dd", "dt"}
_BREAK = {"div", "section", "br", "article", "main", "tr", "ul", "ol", "table", "body"}
_SKIP = {"script", "style", "noscript", "template", "svg", "nav", "header", "footer", "aside", "form", "button",
         "select", "iframe", "head"}
_VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "area", "base", "col", "embed", "param", "track"}


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, bool]] = []
        self.cur: list[str] = []
        self.skip: list[str] = []
        self.article = 0
        self.math = 0
        self.title = ""
        self.h1 = ""
        self._in_title = False
        self._in_h1 = False
        self._h1_done = False

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self.cur)).strip()
        self.cur = []
        if len(text) >= 3:
            self.blocks.append((text, self.article > 0))

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        if self.skip:
            if tag in _SKIP:
                self.skip.append(tag)
            return
        if tag in _SKIP:
            self.skip.append(tag)
            self._flush()
            return
        if tag == "math":
            alt = dict(attrs).get("alttext")
            if alt and not self.math:
                self.cur.append(alt)
            self.math += 1
            return
        if tag in ("article", "main"):
            self._flush()
            self.article += 1
        elif tag in _BLOCK or tag in _BREAK:
            self._flush()
        if tag == "h1":
            self._in_h1 = True

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.skip and not self.math:
            self._flush()

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag == "math":
            self.math = max(0, self.math - 1)
            return
        if tag in ("article", "main"):
            self._flush()
            self.article = max(0, self.article - 1)
        elif tag in _BLOCK or tag in _BREAK:
            self._flush()
        if tag == "h1":
            self._in_h1 = False
            self._h1_done = self._h1_done or bool(self.h1.strip())

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self.skip or self.math:
            return
        if self._in_h1 and not self._h1_done:
            self.h1 += data
        self.cur.append(data)


def from_html(html: str, source: str = "web page") -> Imported:
    ex = _Extractor()
    ex.feed(html)
    ex._flush()
    article = [t for t, a in ex.blocks if a]
    paras = article if len(article) >= 3 else [t for t, _ in ex.blocks]
    if not paras:
        raise ImportFail("没能从这个网页里提取到正文。可以把页面另存为 PDF，或直接复制文字粘贴进来。")
    title = re.sub(r"\s+", " ", ex.h1 or ex.title).strip() or _title_from(paras)
    return Imported(title, source, paras)


# ---------------------------------------------------------------- docx / pdf
def from_docx(data: bytes, source: str = "docx") -> Imported:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        raise ImportFail("这个 Word 文件打不开（只支持 .docx）")
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paras = []
    for p in root.iter(w + "p"):
        text = "".join((t.text or "") if t.tag == w + "t" else ("\t" if t.tag == w + "tab" else "")
                       for t in p.iter() if t.tag in (w + "t", w + "tab"))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            paras.append(text)
    if not paras:
        raise ImportFail("这个 Word 文件里没有文字")
    return Imported(_title_from(paras), source, paras)


def from_pdf(data: bytes, source: str = "pdf") -> Imported:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportFail("读取 PDF 需要安装 pypdf：pip install 'glosslume[pdf]'")
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(pg.extract_text() or "") for pg in reader.pages]
    except Exception as e:                                          # pypdf raises many types
        raise ImportFail(f"这个 PDF 打不开：{e}")
    text = "\n\n".join(pages)
    if len(text.strip()) < 40:
        raise ImportFail("这个 PDF 没有文字层（可能是扫描件），暂时无法选词。")
    paras = paragraphs_from_text(text)
    meta_title = ""
    try:
        meta_title = (reader.metadata.title or "").strip() if reader.metadata else ""
    except Exception:
        pass
    return Imported(meta_title or _title_from(paras), source, paras, pdf=data)


# ---------------------------------------------------------------- files
def from_file(name: str, data: bytes) -> Imported:
    low = name.lower()
    if low.endswith(".docx"):
        return from_docx(data, name)
    if low.endswith(".pdf"):
        return from_pdf(data, name)
    text = _decode(data, "")
    if low.endswith((".html", ".htm")):
        imp = from_html(text, name)
        return imp
    imp = from_text(text, source=name)
    imp.title = re.sub(r"\.(txt|md|markdown|text)$", "", name, flags=re.I) or imp.title
    return imp


def _decode(data: bytes, content_type: str) -> str:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I) or re.search(rb"charset=[\"']?([\w-]+)", data[:2048], re.I)
    enc = (m.group(1).decode() if m and isinstance(m.group(1), bytes) else m.group(1) if m else "utf-8")
    for e in (enc, "utf-8"):
        try:
            return data.decode(e)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("latin-1", errors="replace")


# ---------------------------------------------------------------- URL
def check_url(url: str) -> None:
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ImportFail("请输入以 http:// 或 https:// 开头的网址")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror:
        raise ImportFail("找不到这个网址的服务器")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ImportFail("不能导入本机或内网地址")


class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str) -> tuple[bytes, str]:
    check_url(url)
    opener = urllib.request.build_opener(_Redirects)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/pdf,text/plain,*/*;q=0.5"})
    try:
        with opener.open(req, timeout=25) as r:
            data = r.read(MAX_BYTES + 1)
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raise ImportFail(f"网站返回了 {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ImportFail(f"连不上这个网址：{getattr(e, 'reason', e)}")
    if len(data) > MAX_BYTES:
        raise ImportFail("文件太大（超过 25MB）")
    return data, ctype


_ARXIV = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([\w.\-/]+?)(?:v\d+)?(?:\.pdf)?/?$")


def from_url(url: str) -> Imported:
    url = url.strip()
    note = ""
    m = _ARXIV.search(url)
    if m:                                                         # arXiv: the HTML version is far cleaner than the PDF
        aid = m.group(1)
        try:
            data, ctype = _fetch(f"https://arxiv.org/html/{aid}")
            imp = from_html(_decode(data, ctype), url)
            imp.title = imp.title or f"arXiv:{aid}"
            return imp
        except ImportFail:
            note = "这篇论文没有 HTML 版本，只导入了摘要页；想读全文请下载 PDF 后上传。"
            url = f"https://arxiv.org/abs/{aid}"
    data, ctype = _fetch(url)
    low = ctype.lower()
    if "pdf" in low or data[:5] == b"%PDF-":
        imp = from_pdf(data, url)
    elif "html" in low or data.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
        imp = from_html(_decode(data, ctype), url)
    else:
        imp = from_text(_decode(data, ctype), source=url)
    imp.source = url
    imp.note = note
    return imp
