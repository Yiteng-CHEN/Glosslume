import io
import zipfile

import pytest

from glosslume import importers, langdetect, segment
from glosslume.gloss import parse


# ------------------------------------------------------------------ language detection
def test_detects_scripts():
    assert langdetect.detect("深度学习模型在自然语言处理中取得了很好的效果。")[0] == "zh"
    assert langdetect.detect("これは日本語の文章です。モデルを訓練します。")[0] == "ja"
    assert langdetect.detect("이 모델은 자연어 처리에서 좋은 성능을 보인다")[0] == "ko"
    assert langdetect.detect("Это предложение написано по-русски, и оно длинное.")[0] == "ru"


def test_detects_latin_languages():
    assert langdetect.detect("We take into account the variance of each layer in the network.")[0] == "en"
    assert langdetect.detect("Der Hund ist nicht in dem Haus, aber die Katze ist auch da.")[0] == "de"
    assert langdetect.detect("Les modèles de langue sont utilisés dans une grande partie des applications.")[0] == "fr"
    assert langdetect.detect("El modelo se utiliza para los problemas que no tienen una solución simple.")[0] == "es"


def test_short_text_is_undetermined():
    assert langdetect.detect("ok")[0] == "und"
    assert langdetect.detect("12345 !!!")[0] == "und"


def test_document_with_mixed_languages():
    paras = ["Attention mechanisms allow the model to focus on the relevant parts of the input.",
             "这是一段中文的摘要，用来说明本文的主要贡献和实验结果。",
             "Figure 1"]
    main, per = langdetect.detect_document(paras)
    assert main == "en" and per == ["en", "zh", "en"]      # "Figure 1" is too short to tell: inherits the main language


# ------------------------------------------------------------------ sentences
def sents(t):
    return [t[s:e] for s, e in segment.sentence_spans(t)]


def test_splits_sentences_but_not_abbreviations():
    t = "We follow Smith et al. (2020) and use Fig. 3 for details, e.g. the loss. The score is 0.85. Next we test it."
    assert sents(t) == ["We follow Smith et al. (2020) and use Fig. 3 for details, e.g. the loss.",
                        "The score is 0.85.", "Next we test it."]


def test_splits_cjk_sentences():
    assert sents("第一句话。第二句话！") == ["第一句话。", "第二句话！"]


def test_sentence_at_and_utf16_offsets():
    t = "One two. Three four."
    spans = segment.sentence_spans(t)
    assert segment.sentence_at(spans, 10) == 1
    s = "a😀b c"                                     # the emoji is two UTF-16 units but one Python character
    assert segment.u16_to_cp(s, 3) == 2             # browser offset 3 is just before "b"
    assert s[segment.u16_to_cp(s, 3):segment.u16_to_cp(s, 4)] == "b"


# ------------------------------------------------------------------ importers
def test_text_paragraphs_unwrap_and_dehyphenate():
    raw = "This is a para-\ngraph that was wrapped\nby a PDF export.\n\nSecond paragraph."
    assert importers.paragraphs_from_text(raw) == ["This is a paragraph that was wrapped by a PDF export.", "Second paragraph."]


HTML = """<html><head><title>Site | A Good Post</title><style>p{}</style></head><body>
<nav><ul><li>Home</li><li>About</li></ul></nav>
<article><h1>A Good Post</h1>
<p>The model uses <math alttext="x_i"><mi>x</mi><mo>i</mo></math> as input and learns a representation.</p>
<p>It then <b>predicts</b> the next token.</p><p>Finally it stops.</p></article>
<footer>Copyright</footer><script>var a = 1;</script></body></html>"""


def test_html_extracts_article_only():
    imp = importers.from_html(HTML)
    assert imp.title == "A Good Post"
    assert imp.paragraphs[1] == "The model uses x_i as input and learns a representation."
    assert "Home" not in " ".join(imp.paragraphs) and "Copyright" not in " ".join(imp.paragraphs)
    assert "var a" not in " ".join(imp.paragraphs)


def test_html_without_article_falls_back_to_all_blocks():
    imp = importers.from_html("<html><body><p>Hello world again.</p><p>Second one here.</p></body></html>")
    assert imp.paragraphs == ["Hello world again.", "Second one here."]


def make_docx(paras):
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paras)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_docx_and_bad_files():
    imp = importers.from_file("notes.docx", make_docx(["First paragraph.", "Second one."]))
    assert imp.paragraphs == ["First paragraph.", "Second one."]
    with pytest.raises(importers.ImportFail):
        importers.from_file("broken.docx", b"not a zip")


def test_url_rules_block_local_addresses():
    for bad in ("ftp://example.com/x", "http://127.0.0.1:8765/v1", "http://localhost/x", "file:///etc/passwd"):
        with pytest.raises(importers.ImportFail):
            importers.check_url(bad)


def test_arxiv_urls_are_recognised():
    for u in ("https://arxiv.org/abs/2401.00001", "https://arxiv.org/pdf/2401.00001v2.pdf", "https://arxiv.org/html/2401.00001v1"):
        assert importers._ARXIV.search(u).group(1) == "2401.00001"


# ------------------------------------------------------------------ model output parsing
def test_parse_word_tolerates_fences_and_thinking():
    raw = '<think>hmm</think>\n```json\n{"span":"take into account","lemma":"take into account","pos":"动词短语","sense":"考虑到","why":"固定搭配","other_senses":["账户"],"kind":"common"}\n```'
    d = parse.parse_word(raw, "account")
    assert d["span"] == "take into account" and d["sense"] == "考虑到" and d["other_senses"] == ["账户"]


def test_parse_word_defaults_and_errors():
    d = parse.parse_word('Sure! {"sense": "核", "kind": "weird"} hope this helps', "kernel")
    assert d["span"] == "kernel" and d["kind"] == "common" and d["other_senses"] == []
    with pytest.raises(parse.ParseError):
        parse.parse_word("no json here", "x")
    with pytest.raises(parse.ParseError):
        parse.parse_word('{"pos": "n"}', "x")


def test_split_sections():
    out = parse.split_sections("## Translation\n你好\n\n## Core\n主语 是 X\n## Hard words\nnone")
    assert out == {"Translation": "你好", "Core": "主语 是 X", "Hard words": "none"}


def test_page_furniture_is_not_part_of_a_sentence():
    from glosslume.segment import sentence_spans
    t = ("https://doi.org/10.1177/1750 Discourse & Communication 1 –23 © The Author(s) 2026 journals.sagepub.com/home/dcm "
         "Title of the paper Abstract This article analyzes legitimacy (2020–2023). Next one.")
    got = [t[s:e] for s, e in sentence_spans(t)]
    assert "This article analyzes legitimacy (2020–2023)." in got
    assert not any("http" in g or "sagepub" in g for g in got if "analyzes" in g)
