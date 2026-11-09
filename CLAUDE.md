# Glosslume — project notes for Claude

This file is the project's memory. A new chat opened in this folder should start from here, not from any earlier conversation.

## What this is
A local reader for learning a language while learning a subject. Import a paper or article (URL, PDF, Word, text);
the language is detected automatically per paragraph; the user only chooses the language to explain in. Click a word →
a model explains it **in the context of that sentence**. Select a sentence → translation, main clause, structure.
Looked-up words go to a vocabulary list with their sentence. Runs on a local model that Glosslume downloads and starts itself
(no Ollama needed); cloud is optional.

It is a **separate project from Neurolume** (the user's local fine-tuning / model-internals visualizer,
https://github.com/Yiteng-CHEN/neurolume). Do not mix their code, tests, docs or releases. The only link: Glosslume
can still connect to a running Neurolume/Ollama/LM Studio server as an extra provider (Settings → Find local models), but nothing is
auto-adopted any more.
Planned later: corrected word explanations saved as Neurolume training samples (`/api/samples/add`).

Project plan document (Chinese, more detail than this file): https://claude.ai/artifact/5w17UKuAnRZfhiQWwMT9UY

## Decisions already made
- Name: **Glosslume** (checked free on GitHub, PyPI, npm on 2026-11-06; trademark not checked).
- Stdlib-only core, Python ≥ 3.11; optional extras `pdf` (pypdf), `keychain` (keyring). Plain HTML/JS front end, no build step.
- The browser never calls a model. The local Python server does, so API keys never reach the page and no CORS setup is needed.
- Server binds 127.0.0.1 only, checks Host and Origin. URL import refuses local/private addresses.
- Model modes: prefer_local (default) / prefer_cloud / local_only; a document can be marked local-only (never goes to cloud).
  Cloud quota/rate-limit/auth/unavailable errors fall back to the next provider.
- Providers: the built-in local model (id `builtin`), any OpenAI-compatible server, plus Anthropic with an API key. Keys live in the system keychain, never in the DB or files.
- **Built-in local model (decided 2026-11-09, replaces "use the user's own Ollama")**: settings page lists a pinned catalog; the app downloads the engine and
  the weights itself (Hugging Face, switchable mirror, resumable, SHA256-pinned), runs the server on 127.0.0.1 and starts it with the app.
  Engine: MLX on Apple-silicon Macs (mlx-lm in its own venv under the data dir), llama.cpp `llama-server` everywhere else. Catalog = general instruction
  models (Qwen3.5/Qwen3/Gemma 4), not translation-only models (TranslateGemma, Hunyuan-MT): the app needs JSON explanations and structure analysis; add them later
  only if a test on real sentences shows they are better. Pins are regenerated with `tools/refresh_catalog.py`; never hand-edit catalog.json.
- **Do not** use Claude or Gemini subscription logins, and do not read other programs' credential files (`~/.codex/auth.json`, Claude Code credentials):
  Anthropic's terms forbid subscription OAuth tokens in third-party tools; Gemini has no sanctioned path. "Sign in with ChatGPT" (OpenAI, open-source apps, needs approval) is planned for phase 2.
- Do not train a local model on cloud-model outputs; only on explanations the user corrected themselves.
- Runtime data (library, vocabulary, cache, dictionary) lives in `~/Library/Application Support/Glosslume/` (`$GLOSSLUME_DATA`), never in the repo.

## Layout
```
src/glosslume/
  cli.py              glosslume serve | dict import
  server/app.py       HTTP server + JSON API (+ SSE for sentence analysis)
  importers.py        text / html / docx / pdf(pypdf; original bytes kept) / url (arXiv → HTML version)
  langdetect.py       offline per-paragraph language detection
  segment.py          sentence spans, UTF-16 ↔ code point offsets
  store.py            SQLite: docs, vocab, cache, kv
  providers/          openai_compat, anthropic, router (modes + fallback + per-provider prepare hook), keys
  localmodel/         catalog.json (pinned), catalog.py, download.py (resume + SHA256), engine.py (llama.cpp / MLX), manager.py (jobs, process, provider)
tools/refresh_catalog.py  regenerate localmodel/catalog.json from Hugging Face / GitHub / PyPI (read-only)
  gloss/              prompts, parse (tolerant JSON), service (word / sentence), dictionary (ECDICT, optional)
  web/                index.html, css/app.css, js/app.js, js/pdfview.js (pdf.js viewer + text-layer lookup),
                      vendor/pdfjs/ (pdfjs-dist 5.6.205, Apache-2.0, copied unmodified; see VERSION.txt)
Glosslume.command     macOS double-click launcher: finds Python ≥3.11, builds ./.venv, installs, runs `glosslume serve --open`
tests/                test_text.py, test_e2e.py (real server vs fake model servers), test_localmodel.py (download, archives, manager)
```
Run tests: `pip install -e '.[dev,pdf]' && pytest` (60 tests, no model or network needed; the PDF tests skip without pypdf).

## Status (0.1.0)
Working and tested: import (text, html, docx, URL), language detection, click-to-gloss with phrase detection, cache,
sentence analysis (streaming), vocabulary + TSV export, provider router with fallback, settings UI, UI check in headless Chromium,
PDF in its original layout (pdf.js canvas + text layer; click a word, select for a sentence, reading page remembered; checked in the
built-in browser on a 2-page generated PDF and by e2e tests — not yet on a real multi-column paper).

Not verified: cloud vendor endpoints (only tested against fake servers); explanation quality of the catalog models on real papers.

## Next steps (in order)
1. PDF follow-ups: highlight already-looked-up words in the PDF view (CSS Custom Highlight API), sentences that cross a page break, two-column reading order, a toolbar (zoom, page jump). Check the PDF view on a real multi-column paper.
2. Try it with a real local model on 5 real papers; tune prompts; build the ~100-sentence "one word, many meanings" evaluation set (`evals/`).
3. ECDICT download helper; instant first answer before the model replies.
4. Phase 2: cloze review cards (FSRS), per-document glossary, progress statistics, Sign in with ChatGPT, first public release.
5. Phase 3: Neurolume training loop, browser extension, scanned-PDF OCR, EPUB.

## AOCI repository cognition
This repo is managed with AOCI-CODE (https://github.com/aoci-spec/aoci-code). `aoci.txt` (root), `aoci.meta.txt` (tag dictionary)
and `aoci.code.txt` (one line per file: F/R/A/S) are the whole-repo index; keep them committed with the code.
At the start of a session call `aoci_rules` and `aoci_overview`; after code and tests are stable, call `aoci_maintain` once
and write the requested entries. The binary is `~/.local/share/aoci/bin/aoci` (MCP config in `.mcp.json` / `.codex/config.toml`, not committed).
The full AOCI agent rules are in AGENTS.md:
@AGENTS.md

## Working rules (from the user)
- Answer in Chinese when the user writes Chinese.
- Never read credentials: `~/.claude/.credentials.json`, `~/.codex/auth.json`, `.env`, the macOS keychain.
- Before deleting files, do a dry run and write a log.
- Do not commit, push or publish unless asked. Confirm before any public post.
