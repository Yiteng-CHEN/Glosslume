<div align="center">

# Glosslume

**Read in the original language. Click a word. See what it means in *that* sentence.**

A private, local-first reader for learning a language while you learn a subject.<br>
读原文，点词，看它在这句话里的意思 —— 一个完全在你电脑上运行的“边读专业文献、边学外语”阅读器。

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Runs locally](https://img.shields.io/badge/runs-100%25%20locally-brightgreen)
![Status](https://img.shields.io/badge/status-early%200.1-orange)

[English](#why-glosslume) · [中文](#中文介绍) · [Quick start](#quick-start) · [Roadmap](#roadmap)

</div>

---

## Why Glosslume

Dictionaries give you every meaning of a word. Translators give you a sentence with no explanation. Neither helps when you read a paper
in a language you are still learning, because the question is never "what does *account* mean?" but
**"what does *account* mean in "take into account"?"**

Glosslume answers exactly that question, in place, without leaving the page:

- **Click any word** → its meaning *in this sentence*, part of speech, why it is that and not the common meaning, plus other usual senses.
  Fixed phrases ("take into account", "in terms of") are detected and highlighted as one unit.
- **Select a sentence (or Option/Alt-click a word)** → translation, the main clause, a clause-by-clause structure breakdown and the hard words, streamed live.
- **Everything you look up goes into a vocabulary list together with its sentence**, so you review words in the context where you met them. Export to TSV for Anki.

## What makes it different

| | Glosslume | Browser translators | Dictionary apps | Chat with an AI |
|---|---|---|---|---|
| Meaning depends on the sentence | ✅ | ⚠️ whole-page only | ❌ lists all senses | ✅ but copy-paste each time |
| Works inside the PDF, original layout kept | ✅ | ❌ | ❌ | ❌ |
| Runs fully offline on your own machine | ✅ | ❌ | ✅ | ❌ |
| Documents never leave your computer | ✅ (local-only mode) | ❌ | ✅ | ❌ |
| Grammar structure of hard sentences | ✅ | ❌ | ❌ | ✅ |
| Vocabulary saved with the original sentence | ✅ | ❌ | ⚠️ word only | ❌ |

### Highlights

- 🔒 **Private by default.** The built-in model runs on your computer. A document can be marked **local only** and nothing from it is ever sent to the cloud.
- 📄 **Real papers, real layout.** PDFs open in their original two-column layout (bundled pdf.js, no CDN); click and select directly on the page. Also imports Word, web pages, plain text/Markdown, or an arXiv link (the clean HTML version is used).
- 🧠 **Nothing to install but Glosslume.** Pick a model in *Settings → Local models*; the app downloads the engine and the weights itself (resumable, SHA256-verified, switchable mirror) and starts them automatically on every launch. No Ollama, no Docker, no command line.
- ⚡ **Fast on a laptop.** Apple-silicon Macs use MLX; every other computer uses llama.cpp. Models range from 4B (runs on 8 GB RAM) to 32B.
- 🌍 **Any language pair.** The language is detected per paragraph (mixed-language documents are fine); you only choose the language you want explanations in.
- ☁️ **Cloud is optional.** Add any OpenAI-compatible API (OpenAI, Gemini, DeepSeek, DashScope, Moonshot, Zhipu, OpenRouter…) or Anthropic. If a cloud model runs out of quota or is rate limited, Glosslume falls back to your local model by itself.
- 🧾 **Honest about keys.** API keys live in your system keychain, never in a file or the database. The browser never talks to a model; the local server does. The server listens on 127.0.0.1 only.
- 🪶 **Small and hackable.** A Python standard-library core, a plain HTML/JS front end with no build step, and tests that need no model and no network.

## Quick start

**macOS, easiest:** double-click `Glosslume.command`. It opens Terminal, creates a virtual environment and installs the app on the first run
(needs Python 3.11+ and internet once), starts the server and opens the page. Close the Terminal window to stop it.

**Any system:**

```bash
git clone https://github.com/Yiteng-CHEN/Glosslume.git
cd Glosslume
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[all]'          # [all] = PDF support + keychain for API keys
glosslume serve --open           # http://127.0.0.1:8780
```

Then open **Settings → Local models** and press **Download** on a model (the recommended one is marked). That is the only setup.

| Model | Download | Memory | Good for |
|---|---|---|---|
| Qwen3.5 4B | 2.7 GB | 8 GB | Lightest; fine for common text |
| **Qwen3.5 9B** (recommended) | 5.7 GB | 16 GB | Balanced speed and quality, strong on CJK and English |
| Gemma 4 E4B | 5.0 GB | 16 GB | European languages |
| Gemma 4 12B | 7.1 GB | 24 GB | Clearly better than the small ones |
| Qwen3 14B | 9.0 GB | 24 GB | CJK and academic text |
| Gemma 4 26B-A4B | 17 GB | 32 GB | Mixture-of-experts: large-model quality, small-model speed |
| Qwen3 32B | 19.8 GB | 48 GB | Highest quality, slowest |

Everything the app downloads is pinned (exact model revision and file hashes in `src/glosslume/localmodel/catalog.json`) and checked before use.
In a country where Hugging Face is slow, switch the download source to a mirror such as `hf-mirror.com` in the same settings page.

## How to use it

1. **Import** a paper: paste a link, upload a PDF / Word / txt / md / html file, or paste text.
2. **Click a word** to see what it means here. Click elsewhere on the page and the card closes.
3. **Select a sentence** (or Option/Alt-click a word) for translation, main clause and structure. The reader makes room for the panel instead of covering the text.
4. **Vocabulary** collects every lookup with its sentence. *I know it* removes the underline; export a TSV for Anki.

Word lookups and sentence explanations can use different models (a small fast one for words, a bigger one for sentences).

| Mode | Behaviour |
|---|---|
| Prefer local (default) | local model first; cloud only if no local model answers |
| Prefer cloud | cloud first; falls back to local when out of quota, rate limited, or the key is rejected |
| Local only | cloud is never contacted |

### Optional: instant offline dictionary

English → Chinese words can show a basic meaning instantly while the model thinks. Download [ECDICT](https://github.com/skywind3000/ECDICT)
(`ecdict.csv`), then run `glosslume dict import ecdict.csv`.

## Privacy

Everything lives in `~/Library/Application Support/Glosslume/` (or `$GLOSSLUME_DATA`): one SQLite file with your library, vocabulary and lookup cache,
plus the downloaded models. Nothing is stored in the repository. Glosslume does **not** read other programs' login files and does not use
Claude/ChatGPT subscription logins. URL import refuses local and private addresses.

## Status and honesty

Glosslume is early (0.1). The reading and lookup loop works and is covered by 60+ automated tests. What has **not** been verified yet:

- The cloud vendor endpoints are tested against fake servers only, not yet against the real vendor APIs.
- Explanation quality of each catalog model on real papers has not been systematically evaluated. An evaluation set is on the roadmap.
- Windows and Linux paths are written and unit-tested but have not been run on real machines. **Reports are very welcome.**
- In the original PDF layout a sentence is read in full only within one page; words you already looked up are not highlighted there yet; scanned PDFs (no text layer) cannot be read.

## Roadmap

- [ ] Highlight already-looked-up words in the PDF view; sentences across page breaks; zoom and page-jump toolbar
- [ ] A ~100-sentence "one word, many meanings" evaluation set to compare models and tune prompts
- [ ] Spaced-repetition review (FSRS cloze cards that blank the word in its original sentence)
- [ ] Per-document glossary of technical terms, progress statistics
- [ ] Sign in with ChatGPT; browser extension; scanned-PDF OCR; EPUB

## Contributing

Issues and pull requests are welcome, especially: bug reports from Windows/Linux, hard sentences where the explanation is wrong (they become evaluation cases), and new languages.

```bash
pip install -e '.[dev,pdf]' && pytest
```

The tests start the real server against fake model servers, so no model or network is needed. Project notes for contributors are in [CLAUDE.md](CLAUDE.md).

If Glosslume is useful to you, a ⭐ on the repository helps other language learners find it.

---

## 中文介绍

**读原文，点词，看它在这句话里的意思。**

词典告诉你一个词的所有意思，翻译器给你一句译文却不解释。读外语专业论文时，真正的问题是“*account* 在 *take into account* 里是什么意思”，而不是“*account* 有哪些意思”。Glosslume 就是为这个问题做的。

### 功能
- **点词**：给出这个词在这句话里的含义、词性、为什么是这个意思，以及其他常见含义；固定搭配会整体识别并高亮。
- **划选整句（或 Alt/Option 单击）**：译文、主干、从句结构拆解、难点词，流式显示。
- **生词本**：查过的词连同原句一起保存，可导出 TSV 给 Anki；点“我认识了”就去掉下划线。
- **PDF 原版面**：论文按原来的排版显示，直接在页面上点词、划句；也支持 Word、网页、txt/md、粘贴文字，以及 arXiv 链接（自动用干净的 HTML 版）。
- **自动识别语言**：按段落识别，混合语言文档没问题，你只需选择“用什么语言解释”。

### 优势
- **默认私密**：内置本地模型在你自己的电脑上运行；文档可标为“仅本地”，内容绝不发到云端。
- **不用另装任何东西**：在“设置 → 本地模型”里选一个模型，应用自己下载引擎和模型（可断点续传、校验哈希、可切换镜像如 hf-mirror.com），以后每次启动自动加载。不需要 Ollama、Docker 或命令行。
- **笔记本也跑得快**：M 系列 Mac 用 MLX，其他电脑用 llama.cpp；模型从 4B（8 GB 内存即可）到 32B。
- **云端可选**：可接 OpenAI 兼容接口（OpenAI、Gemini、DeepSeek、通义、Kimi、智谱、OpenRouter 等）或 Anthropic；额度用完或被限流时自动回退到本地模型。
- **密钥安全**：API Key 存在系统钥匙串，不写进文件或数据库；浏览器从不直接调用模型，服务只监听 127.0.0.1。
- **小而易改**：核心只用 Python 标准库，前端是纯 HTML/JS、无需构建，测试不需要模型和网络。

### 快速开始
macOS 直接双击 `Glosslume.command`（第一次需要 Python 3.11+ 和网络）；其他系统见上面的 [Quick start](#quick-start)。然后在“设置 → 本地模型”点“下载”即可。

### 现状
项目处于早期（0.1）。主流程可用并有自动化测试；云端接口尚未用真实服务商 API 验证，各模型在真实论文上的解释质量还没系统评测，Windows / Linux 还没在真机上跑过，欢迎反馈。后续计划见 [Roadmap](#roadmap)。

## License

MIT
