# Glosslume

**Read in the original language. Click a word. See what it means in *that* sentence.**

Glosslume is a local reader for people who read papers and technical articles in a foreign language and want to
learn the language along the way. Import a text and Glosslume detects its language. Click any word and a model
explains it in the context of the sentence it sits in (so *account* in "take into account" is not "bank account").
Select a hard sentence and it gives a translation, the main clause and the structure. Every word you look up is
saved with its sentence in a vocabulary list.

It runs on a **local model that Glosslume downloads and starts for you**: pick one in *Settings → Local models* and it is
fetched once and loaded automatically every time the app starts. Nothing else to install (no Ollama needed); Apple-silicon
Macs use MLX, every other computer uses llama.cpp. Cloud models (any OpenAI-compatible API key, or Anthropic) are optional,
and when one runs out of quota Glosslume switches to your local model by itself. A document can be marked **local only**, and then nothing from it ever leaves your computer.

> Status: early (0.1). The reading and lookup loop works and is tested; see [What is not done yet](#what-is-not-done-yet).

## Quick start

```bash
cd Glosslume
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[all]'          # [all] = PDF support + keychain for API keys
glosslume serve --open           # http://127.0.0.1:8780
```

On macOS you can instead double-click `Glosslume.command`: it opens Terminal, creates `.venv` and installs the app on the
first run (needs Python 3.11+ and internet once), starts the server and opens the page. If Glosslume is already running it
just opens the page. Close the Terminal window to stop it.

Then open *Settings → Local models* and press **Download** on a model (the recommended one is marked). The first download
also fetches the engine (llama.cpp, about 20 MB; on Apple silicon the MLX package, a few hundred MB). Models are checked
against pinned SHA256 hashes, downloads resume after an interruption, and the download source can be switched to a mirror
(for example `hf-mirror.com`) if Hugging Face is slow for you. Already running Neurolume, Ollama or LM Studio? Use
*Settings → Find local models* to connect to it instead.

| Model | Download | Memory |
|---|---|---|
| Qwen3.5 4B | 2.7 GB | 8 GB |
| Qwen3.5 9B (recommended) | 5.7 GB | 16 GB |
| Gemma 4 E4B | 5.0 GB | 16 GB |
| Gemma 4 12B / Qwen3 14B | 7.1 / 9.0 GB | 24 GB |
| Gemma 4 26B-A4B | 17 GB | 32 GB |
| Qwen3 32B | 19.8 GB | 48 GB |

The list is pinned in `src/glosslume/localmodel/catalog.json`; `python tools/refresh_catalog.py` regenerates it.

1. **Import**: paste a link (arXiv links use the clean HTML version), upload a PDF / Word / txt / md / html file, or paste text.
2. **Click a word**: meaning in this sentence, part of speech, why, other common meanings. Fixed phrases are detected and highlighted.
3. **Option/Alt-click a word, or select a few words**: explains the whole sentence (translation, main clause, structure, hard words).
4. **Vocabulary**: every lookup is saved with its sentence. *I know it* removes the underline; export a TSV for Anki.

## Models and privacy

| Mode | Behaviour |
|---|---|
| Prefer local (default) | local model first; cloud only if no local model answers |
| Prefer cloud | cloud first; falls back to local when out of quota, rate limited, or the key is rejected |
| Local only | cloud is never contacted |

Word lookups and sentence explanations can each use a different model (a small fast one for words, a bigger one for sentences).
The browser never talks to a model: the local server does, so API keys stay out of the page. Keys are stored in the system
keychain (`pip install 'glosslume[keychain]'`), never in the database or a config file. Glosslume does **not** read other
programs' login files, and does not use Claude/ChatGPT subscription logins (see the project plan for why).

Cloud presets in Settings (OpenAI, Anthropic, Gemini, DeepSeek, DashScope, Moonshot, Zhipu, OpenRouter) fill in the base URL only;
enter the model name yourself, because vendors rename models often. The cloud paths are covered by tests against a fake server but
have **not yet been run against the real vendor APIs**.

## Offline dictionary (optional)

English → Chinese words show a basic meaning instantly while the model thinks. Download
[ECDICT](https://github.com/skywind3000/ECDICT) (`ecdict.csv`), then:

```bash
glosslume dict import ecdict.csv
```

## Data

Everything lives in `~/Library/Application Support/Glosslume/` (or `$GLOSSLUME_DATA`): one SQLite file with your library,
vocabulary and lookup cache. Nothing is stored in the repository.

## What is not done yet

- PDFs open in their original layout (pdf.js, bundled in `web/vendor/pdfjs`, no CDN); the "Text only" button switches to the extracted text. Importing a PDF still needs `pypdf`. In the original layout a sentence is read in full only within one page, and words you already looked up are not highlighted yet.
- No spaced-repetition review yet (planned: FSRS cards that blank the word in its original sentence).
- No per-document glossary of technical terms, no progress statistics.
- Scanned PDFs (no text layer) cannot be read.
- Sign in with ChatGPT is not implemented (planned, needs OpenAI's approval for open-source apps).

## Develop

```bash
pip install -e '.[dev]' && pytest
```

The tests start the real server against fake OpenAI-compatible model servers, so no model or network is needed.

---

## 简介

**读原文，点词，看它在这句话里的意思。**

导入论文或文章，自动识别语言；单击一个词，本地模型按所在句子给出此处的含义；划选或 Alt+单击解析整句；查过的词连同原句进入生词本。
默认使用 Glosslume 自己下载并启动的本地模型（设置 → 本地模型里选一个，自动下载、每次启动自动加载，不需要另装 Ollama；M 系列 Mac 用 MLX，其他电脑用 llama.cpp），云端模型可选，额度用完自动切回本地；
文档可标为“仅本地”，内容不会发到云端。运行方式见上面的 Quick start。

## License

MIT
