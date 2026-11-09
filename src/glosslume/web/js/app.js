"use strict";
// Glosslume UI. Everything that comes from documents or models goes through esc() before it touches innerHTML.
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const UI = (() => { const v = localStorage.getItem("gl_ui"); return v || ((navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en"); })();

const M = {
  zh: {
    urlPh: "粘贴论文或网页链接，例如 arxiv.org/abs/…", go: "导入", file: "上传文件", paste: "粘贴文字",
    hint: "支持 PDF、Word、网页、txt、md；也可以把文件拖进来", importing: "正在导入…", viewPdf: "原版面", viewText: "纯文字", pdfFail: "原版面打不开，已切换到文字版：", pdfLoading: "正在打开 PDF…", pdfHint: "单击词语查看释义；Option（Alt）单击或划选解析整句。同一页内的句子才能完整解析。", shelf: "书架", vocab: "生词本", settings: "设置",
    noDocs: "还没有文章", pasteTitle: "标题（可不填）", pasteBody: "把要读的文字粘贴到这里", cancel: "取消", ok: "导入",
    delConfirm: "从书架删除这篇文章？（生词本里的词会保留）", paras: "段", lockOnly: "仅本地", detected: "检测到", translateTo: "释义语言",
    sameLang: "这篇文章已经是你选的目标语言，点词会用同一种语言解释。想学外语，请把“释义语言”改成你的母语。",
    undLang: "没能确定这篇文章的语言，请在上方手动选择。", lookingUp: "查询中", retry: "重试", known: "已认识", speak: "朗读", refresh: "重新查询",
    phrase: "这里是固定搭配", others: "其他常见意思", local: "本地", cloud: "云端", fellback: "已切换到另一个模型", cached: "来自缓存",
    sentenceBtn: "解析句子", sentenceTitle: "句子解析", thinking: "分析中…", sec_Translation: "译文", sec_Core: "主干", sec_Structure: "结构", "sec_Hard words": "难点词",
    kind_term: "术语", kind_academic: "学术词", kind_common: "普通词", pos: "词性",
    welcomeH: "读原文，学知识，顺便学外语", welcomeP: "导入一篇文章，点任何一个词，看它在这句话里的意思。",
    s1: "导入", s1d: "粘贴论文链接、上传 PDF / Word，或粘贴文字。语言会自动识别。", s2: "点词", s2d: "单击一个词，看它在当前句子里的意思；按住 Option（Alt）单击，或划选一段，解析整句。",
    s3: "积累", s3d: "查过的词连同原句自动进入生词本，可导出到 Anki。",
    noModel: "还没有可用的模型。到设置里选一个本地模型下载（完全在这台电脑上运行），或填入云端 API Key。", goSettings: "去设置",
    vAll: "全部", vNew: "新词", vKnown: "已认识", vEmpty: "还没有词。读文章时点词，就会自动记在这里。", export: "导出 TSV（Anki）", del: "删除", back: "回到“新词”",
    targetLang: "释义语言", targetD: "点词和整句解析都会用这种语言解释。", mode: "模型模式",
    m_prefer_local: "优先本地", m_prefer_localD: "先用本地模型，本地不可用时才用云端（推荐）", m_prefer_cloud: "优先云端", m_prefer_cloudD: "先用云端，额度用完或出错时自动切到本地",
    m_local_only: "仅本地", m_local_onlyD: "任何内容都不离开这台电脑", models: "模型", discover: "发现本机模型", found: "发现", none: "没有发现正在运行的本地模型服务",
    add: "添加", test: "测试", testing: "测试中…", noKeyYet: "未填密钥", keyOk: "密钥已保存", wordWith: "点词用", sentWith: "整句用", auto: "自动",
    lmTitle: "本地模型（内置）", lmD: "选一个模型，Glosslume 会自动下载，并在每次启动时自动加载。完全在这台电脑上运行，不需要另外安装 Ollama。", lmEngine: "引擎", lmEngAuto: "自动", lmRam: "内存", lmDisk: "磁盘剩余", lmSource: "下载源", lmCustom: "自定义…", lmCustomAsk: "输入下载源地址（https:// 开头，例如 https://hf-mirror.com）", lmDownload: "下载", lmCancel: "取消", lmUse: "使用", lmRemove: "删除", lmRetry: "重试", lmActive: "使用中", lmRec: "推荐", lmNoFit: "内存可能不够", lmEngineStep: "正在准备运行引擎（第一次需要几分钟）…", lmDownloading: "下载中", lmVerify: "校验中…", lmCancelled: "已取消，已下载的部分会保留，可以继续。", lmRemoveAsk: "删除这个模型的文件？", lmSt_ready: "已加载，可以使用", lmSt_starting: "正在加载模型…", lmSt_stopped: "未启动", lmSt_error: "出错了", lmNone: "还没有下载任何模型。点下面某个模型的“下载”开始。", lmSizeNote: "体积", lmLicense: "许可证", lmEngMlx: "MLX（Apple 芯片）", lmEngLlama: "llama.cpp", addCustom: "添加模型服务", addD: "可以添加云端模型（OpenAI、Claude、DeepSeek 等，需要 API Key；提问内容会发到对方服务器），也可以添加这台电脑上的其他本地模型服务（勾选“这是本机上的模型服务”，不需要 Key）。本机已经在运行的服务，直接点上面的“发现本机模型”即可。", localOnlyNote: "当前是“仅本地”模式：云端模型已停用，这里只能添加本机模型服务。要用云端模型，请先把上面的模式改成“优先本地”或“优先云端”。", cloudOff: "云端 · 仅本地模式下停用", need: "还没填：", needKey: "云端模型需要填 API Key", slow: "本地模型响应较慢，请再等一会儿（大模型第一次加载或推理型模型会先思考，可能要几十秒）。", preset: "常用服务", custom: "自定义", name: "名称", baseUrl: "接口地址", model: "模型名", key: "API Key", isLocal: "这是本机上的模型服务", save: "保存",
    keyMem: "未安装 keyring：密钥只在本次运行期间保存在内存里，下次启动要重新填。安装方法：pip install 'glosslume[keychain]'",
    dictH: "离线词典", dictOn: "已启用（英→中，点词时先显示基本释义）", dictOff: "未安装。运行 glosslume dict import ecdict.csv 后，英语点词会先瞬间显示基本释义。",
    uiLang: "界面语言", saved: "已保存", added: "已添加", copied: "已复制", localTag: "本地", cloudTag: "云端", selectOne: "选中的文字要在同一段里",
  },
  en: {
    urlPh: "Paste a paper or web link, e.g. arxiv.org/abs/…", go: "Import", file: "Upload file", paste: "Paste text",
    hint: "PDF, Word, web pages, txt, md; you can also drop a file here", importing: "Importing…", viewPdf: "Original layout", viewText: "Text only", pdfFail: "Could not open the original layout; showing text instead: ", pdfLoading: "Opening PDF…", pdfHint: "Click a word for its meaning; Option/Alt-click or select text to explain a sentence. A sentence is read in full only within one page.", shelf: "Library", vocab: "Vocabulary", settings: "Settings",
    noDocs: "Nothing here yet", pasteTitle: "Title (optional)", pasteBody: "Paste the text you want to read", cancel: "Cancel", ok: "Import",
    delConfirm: "Remove this text from the library? (Saved words are kept.)", paras: "paragraphs", lockOnly: "Local only", detected: "Detected", translateTo: "Explain in",
    sameLang: "This text is already in your target language, so lookups explain in the same language. To learn a foreign language, set “Explain in” to your own.",
    undLang: "Could not tell the language of this text. Please pick it above.", lookingUp: "Looking up", retry: "Retry", known: "I know it", speak: "Speak", refresh: "Look up again",
    phrase: "Fixed phrase here", others: "Other common meanings", local: "local", cloud: "cloud", fellback: "switched to another model", cached: "cached",
    sentenceBtn: "Explain sentence", sentenceTitle: "Sentence", thinking: "Analysing…", sec_Translation: "Translation", sec_Core: "Core", sec_Structure: "Structure", "sec_Hard words": "Hard words",
    kind_term: "term", kind_academic: "academic", kind_common: "common", pos: "POS",
    welcomeH: "Read the original, learn the subject, pick up the language", welcomeP: "Import a text and click any word to see what it means in that sentence.",
    s1: "Import", s1d: "Paste a paper link, upload a PDF or Word file, or paste text. The language is detected automatically.", s2: "Click a word", s2d: "Click a word for its meaning in this sentence. Option/Alt-click, or select some text, to explain the whole sentence.",
    s3: "Collect", s3d: "Every word you look up is saved with its sentence in your vocabulary, and can be exported to Anki.",
    noModel: "No model available yet. Pick a local model to download in Settings (it runs entirely on this computer), or add a cloud API key.", goSettings: "Open settings",
    vAll: "All", vNew: "New", vKnown: "Known", vEmpty: "No words yet. Click words while reading and they appear here.", export: "Export TSV (Anki)", del: "Delete", back: "Back to “New”",
    targetLang: "Explain in", targetD: "Word and sentence explanations are written in this language.", mode: "Model mode",
    m_prefer_local: "Prefer local", m_prefer_localD: "Local model first; cloud only if local is unavailable (recommended)", m_prefer_cloud: "Prefer cloud", m_prefer_cloudD: "Cloud first; falls back to local when out of quota or failing",
    m_local_only: "Local only", m_local_onlyD: "Nothing leaves this computer", models: "Models", discover: "Find local models", found: "Found", none: "No local model server is running",
    add: "Add", test: "Test", testing: "Testing…", noKeyYet: "no key", keyOk: "key saved", wordWith: "Word lookups use", sentWith: "Sentences use", auto: "Automatic",
    lmTitle: "Local models (built in)", lmD: "Pick a model; Glosslume downloads it and loads it automatically every time it starts. It runs entirely on this computer; no Ollama needed.", lmEngine: "Engine", lmEngAuto: "Auto", lmRam: "RAM", lmDisk: "Free disk", lmSource: "Download source", lmCustom: "Custom…", lmCustomAsk: "Enter the download source (https://…, e.g. https://hf-mirror.com)", lmDownload: "Download", lmCancel: "Cancel", lmUse: "Use", lmRemove: "Delete", lmRetry: "Retry", lmActive: "In use", lmRec: "Recommended", lmNoFit: "May not fit in memory", lmEngineStep: "Preparing the engine (a few minutes the first time)…", lmDownloading: "Downloading", lmVerify: "Verifying…", lmCancelled: "Cancelled; the part already downloaded is kept and can be resumed.", lmRemoveAsk: "Delete the files of this model?", lmSt_ready: "Loaded and ready", lmSt_starting: "Loading the model…", lmSt_stopped: "Not running", lmSt_error: "Something went wrong", lmNone: "No model downloaded yet. Press Download on one below.", lmSizeNote: "Size", lmLicense: "License", lmEngMlx: "MLX (Apple silicon)", lmEngLlama: "llama.cpp", addCustom: "Add a model service", addD: "Add a cloud model (OpenAI, Claude, DeepSeek…; needs an API key, and your questions are sent to that provider), or another model server on this computer (tick \"A model server on this computer\"; no key needed). Servers already running here: use \"Find local models\" above.", localOnlyNote: "\"Local only\" mode is on: cloud models are disabled and only servers on this computer can be added. Switch the mode above to use a cloud model.", cloudOff: "Cloud · disabled in Local only mode", need: "Missing: ", needKey: "A cloud model needs an API key", slow: "The local model is slow; please wait (a big model loading for the first time, or a reasoning model thinking, can take tens of seconds).", preset: "Service", custom: "Custom", name: "Name", baseUrl: "Base URL", model: "Model name", key: "API key", isLocal: "A model server on this computer", save: "Save",
    keyMem: "`keyring` is not installed: keys are kept in memory for this run only. Install with: pip install 'glosslume[keychain]'",
    dictH: "Offline dictionary", dictOn: "On (English→Chinese, shows a basic meaning instantly)", dictOff: "Not installed. Run glosslume dict import ecdict.csv to show basic meanings instantly for English words.",
    uiLang: "Interface language", saved: "Saved", added: "Added", copied: "Copied", localTag: "local", cloudTag: "cloud", selectOne: "Select text within one paragraph",
  },
};
const t = (k, ...a) => { let s = M[UI][k] ?? M.en[k] ?? k; a.forEach((v, i) => { s = s.replace("{" + i + "}", v); }); return s; };

const S = { pdf: null, st: null, docs: [], doc: null, view: "home", seen: new Set(), tok: 0, dtok: 0, vfilter: "new" };

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
let pdfModP;
const pdfMod = () => (pdfModP ||= import("/js/pdfview.js"));
const pdfMode = d => d.has_pdf && (localStorage.getItem("gl_view") || "pdf") === "pdf";
let toastT;
function toast(msg) { const el = $("#toast"); el.textContent = msg; el.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => { el.hidden = true; }, 3600); }
const langName = c => (S.st.langs[c] || [c, c])[UI === "zh" ? 1 : 0];
const target = () => S.st.settings.target_lang;

// ------------------------------------------------------------------ boot + sidebar
async function boot() {
  $("#urlIn").placeholder = t("urlPh"); $("#urlGo").textContent = t("go"); $("#fileBtn").textContent = t("file"); $("#pasteBtn").textContent = t("paste");
  $("#shelfTitle").textContent = t("shelf"); $("#navVocab").textContent = t("vocab"); $("#navSettings").textContent = t("settings");
  $("#pasteTitle").placeholder = t("pasteTitle"); $("#pasteText").placeholder = t("pasteBody"); $("#pasteCancel").textContent = t("cancel"); $("#pasteOk").textContent = t("ok");
  document.documentElement.lang = UI; setHint(t("hint"));
  await refreshState();
  if (!target()) {
    const guess = (navigator.language || "en").slice(0, 2).toLowerCase();
    await api("/api/settings", { target_lang: S.st.langs[guess] ? guess : "en" });
    await refreshState();
  }
  await loadDocs();
  go("home");
}
async function refreshState() { S.st = await api("/api/state"); }
async function loadDocs() { S.docs = (await api("/api/docs")).docs; renderShelf(); }
function setHint(msg, bad) { const h = $("#importHint"); h.textContent = msg; h.className = "hint" + (bad ? " bad" : ""); }

function renderShelf() {
  $("#shelf").innerHTML = S.docs.length ? S.docs.map(d => `
    <div class="doc ${S.doc && S.doc.id === d.id && S.view === "reader" ? "on" : ""}" data-doc="${d.id}">
      <div class="t">${esc(d.title)}</div>
      <div class="m"><span class="chip">${esc(langName(d.lang))}</span>${d.local_only ? `<span class="chip lock">🔒</span>` : ""}</div>
      <button class="del" data-del="${d.id}" title="${esc(t("del"))}">×</button>
    </div>`).join("") : `<div class="hint">${esc(t("noDocs"))}</div>`;
}

$("#shelf").addEventListener("click", async e => {
  const del = e.target.closest("[data-del]");
  if (del) {
    e.stopPropagation();
    if (confirm(t("delConfirm"))) { await api("/api/docs/delete", { id: del.dataset.del }); if (S.doc && S.doc.id === del.dataset.del) { S.doc = null; go("home"); } await loadDocs(); }
    return;
  }
  const d = e.target.closest("[data-doc]"); if (d) openDoc(d.dataset.doc);
});
$$(".navb").forEach(b => b.addEventListener("click", () => go(b.dataset.view)));

// ------------------------------------------------------------------ import
async function importDoc(body) {
  setHint(t("importing"));
  try {
    const r = await api("/api/docs/import", body);
    await loadDocs(); await openDoc(r.id); setHint(t("hint"));
    if (r.note) toast(r.note);
  } catch (err) { setHint(err.message, true); toast(err.message); }
}
$("#urlForm").addEventListener("submit", e => {
  e.preventDefault(); let v = $("#urlIn").value.trim(); if (!v) return;
  if (!/^https?:\/\//i.test(v)) v = "https://" + v;
  importDoc({ url: v }).then(() => { $("#urlIn").value = ""; });
});
$("#fileBtn").addEventListener("click", () => $("#fileIn").click());
$("#fileIn").addEventListener("change", e => { const f = e.target.files[0]; if (f) importFile(f); e.target.value = ""; });
function importFile(f) {
  const fr = new FileReader();
  fr.onload = () => importDoc({ name: f.name, data: String(fr.result).split(",")[1] || "" });
  fr.readAsDataURL(f);
}
$("#pasteBtn").addEventListener("click", () => $("#pasteDlg").showModal());
$("#pasteForm").addEventListener("submit", e => {
  const v = e.submitter && e.submitter.value, text = $("#pasteText").value.trim();
  if (v === "ok" && text) { importDoc({ text, title: $("#pasteTitle").value.trim() }); $("#pasteText").value = ""; $("#pasteTitle").value = ""; }
});
let dragN = 0;
addEventListener("dragenter", e => { if ([...(e.dataTransfer?.types || [])].includes("Files")) { dragN++; $("#drop").textContent = t("file"); $("#drop").hidden = false; } });
addEventListener("dragleave", () => { dragN = Math.max(0, dragN - 1); if (!dragN) $("#drop").hidden = true; });
addEventListener("dragover", e => e.preventDefault());
addEventListener("drop", e => { e.preventDefault(); dragN = 0; $("#drop").hidden = true; const f = e.dataTransfer?.files?.[0]; if (f) importFile(f); });

// ------------------------------------------------------------------ views
function go(view) {
  S.view = view; closeCard(); closeDrawer(); hideSel();
  $$(".navb").forEach(b => b.classList.toggle("on", b.dataset.view === view));
  renderShelf();
  ({ home: renderHome, reader: renderReader, vocab: renderVocab, settings: renderSettings })[view]();
}

function hasModel() { return S.st.providers.length > 0; }
function renderHome() {
  $("#main").innerHTML = `<div class="page"><h2>${esc(t("welcomeH"))}</h2><p class="lead">${esc(t("welcomeP"))}</p>
    ${hasModel() ? "" : `<div class="note">${esc(t("noModel"))} <button class="btn small" data-act="settings">${esc(t("goSettings"))}</button></div>`}
    <div class="steps">${[1, 2, 3].map(i => `<div class="step"><b class="n">${i}</b><div><b>${esc(t("s" + i))}</b><div>${esc(t("s" + i + "d"))}</div></div></div>`).join("")}</div></div>`;
}

async function openDoc(id) {
  S.doc = await api("/api/docs/" + id);
  const v = await api("/api/vocab?doc=" + id);
  S.seen = new Set(); v.vocab.filter(x => x.status !== "known").forEach(x => { S.seen.add(x.word.toLowerCase()); S.seen.add(x.lemma.toLowerCase()); S.seen.add((x.clicked || "").toLowerCase()); });
  go("reader");
}

function paraHtml(text, i, lang) {
  if (lang === target()) return `<p class="native" data-i="${i}">${esc(text)}</p>`;
  let out = "";
  const seg = new Intl.Segmenter(lang === "und" ? undefined : lang, { granularity: "word" });
  for (const s of seg.segment(text)) {
    if (s.isWordLike && !/^[\d.,]+$/.test(s.segment)) out += `<span class="w" data-s="${s.index}" data-e="${s.index + s.segment.length}">${esc(s.segment)}</span>`;
    else out += esc(s.segment);
  }
  return `<p data-i="${i}" lang="${esc(lang)}">${out}</p>`;
}
const langOptions = sel => Object.keys(S.st.langs).map(c => `<option value="${c}" ${c === sel ? "selected" : ""}>${esc(langName(c))}</option>`).join("");

function renderReader() {
  const d = S.doc, same = d.lang === target(), usePdf = pdfMode(d);
  S.pdf?.destroy(); S.pdf = null;
  $("#main").innerHTML = `
    <div class="bar">
      <span class="title" title="${esc(d.title)}">${esc(d.title)}</span><span class="sp"></span>
      ${d.has_pdf ? `<button class="btn small" id="viewTog">${esc(t(usePdf ? "viewText" : "viewPdf"))}</button>` : ""}
      <label>${esc(t("detected"))} <select id="srcLang">${d.lang === "und" ? `<option value="und" selected>?</option>` : ""}${langOptions(d.lang)}</select></label>
      <label>${esc(t("translateTo"))} <select id="tgtLang">${langOptions(target())}</select></label>
      <label><input type="checkbox" id="lockOnly" ${d.local_only ? "checked" : ""}> 🔒 ${esc(t("lockOnly"))}</label>
    </div>
    ${usePdf ? `<div class="pdfwrap"><div class="note">${esc(t("pdfHint"))}</div><div class="pdfhost" id="pdfhost"><p class="hint">${esc(t("pdfLoading"))}</p></div></div>` : `
    <article class="reader" id="reader">
      <h1>${esc(d.title)}</h1><div class="src">${esc(d.source)} · ${d.paragraphs.length} ${esc(t("paras"))}</div>
      ${d.lang === "und" ? `<div class="note">${esc(t("undLang"))}</div>` : same ? `<div class="note">${esc(t("sameLang"))}</div>` : ""}
      ${d.paragraphs.map((p, i) => paraHtml(p, i, d.langs[i])).join("")}
    </article>`}`;
  if ($("#viewTog")) $("#viewTog").onclick = () => { localStorage.setItem("gl_view", usePdf ? "text" : "pdf"); renderReader(); };
  if (usePdf) { wirePdf(d); } else markSeen();
  $("#srcLang").onchange = async e => { await api("/api/docs/update", { id: d.id, lang_override: e.target.value }); await loadDocs(); await openDoc(d.id); };
  $("#tgtLang").onchange = async e => { await api("/api/settings", { target_lang: e.target.value }); await refreshState(); renderReader(); };
  $("#lockOnly").onchange = async e => { await api("/api/docs/update", { id: d.id, local_only: e.target.checked }); d.local_only = e.target.checked; await loadDocs(); toast(t("saved")); };
  if (usePdf) return;
  const main = $("#main"), p = d.progress | 0;
  if (p > 0) { const el = $(`#reader p[data-i="${p}"]`); if (el) el.scrollIntoView({ block: "start" }); } else main.scrollTop = 0;
  main.onscroll = () => { clearTimeout(S.sc); S.sc = setTimeout(saveProgress, 900); hideSel(); };
  const reader = $("#reader");
  reader.addEventListener("click", onReaderClick);
  reader.addEventListener("mouseup", () => setTimeout(onSelect, 0));
}
async function wirePdf(d) {
  const host = $("#pdfhost"), main = $("#main");
  main.scrollTop = 0; main.onscroll = hideSel;
  try {
    const m = await pdfMod();
    if (S.doc !== d || $("#pdfhost") !== host) return;
    S.pdf = await m.mountPdf(host, main, `/api/docs/${d.id}/pdf`, d.pdf_page || 1, n => {
      d.pdf_page = n; clearTimeout(S.sc); S.sc = setTimeout(() => api("/api/docs/update", { id: d.id, pdf_page: n }).catch(() => {}), 900);
    });
  } catch (err) {
    if (S.doc !== d) return;
    toast(t("pdfFail") + (err.message || err)); localStorage.setItem("gl_view", "text"); renderReader(); return;
  }
  host.addEventListener("click", e => onPdfClick(e, d));
  host.addEventListener("mouseup", () => setTimeout(() => onPdfSelect(d), 0));
}
function markSeen() { $$("#reader .w").forEach(sp => sp.classList.toggle("seen", S.seen.has(sp.textContent.toLowerCase()))); }
function saveProgress() {
  if (S.view !== "reader" || !S.doc) return;
  const ps = $$("#reader p[data-i]"); const top = ps.find(p => p.getBoundingClientRect().bottom > 90);
  if (top) { S.doc.progress = +top.dataset.i; api("/api/docs/update", { id: S.doc.id, progress: S.doc.progress }).catch(() => {}); }
}

// ------------------------------------------------------------------ word card
function openCard(rect, html) {
  const c = $("#card"); c.innerHTML = html; c.hidden = false; placeCard(rect); c._rect = rect;
  $("#cardX")?.addEventListener("click", closeCard);
}
function placeCard(rect) {
  const c = $("#card"), W = c.offsetWidth, H = c.offsetHeight;
  let x = Math.min(Math.max(10, rect.left), innerWidth - W - 10), y = rect.bottom + 8;
  if (y + H > innerHeight - 10) y = Math.max(10, rect.top - H - 8);
  c.style.left = x + "px"; c.style.top = y + "px";
}
function closeCard() {
  S.tok++; $("#card").hidden = true; $$(".w.on,.w.phrase").forEach(x => x.classList.remove("on", "phrase"));
  globalThis.CSS?.highlights?.delete("gl-on"); globalThis.CSS?.highlights?.delete("gl-phrase");
}

/** Where a lookup happens: a word span in the text view, or a word in a PDF page's text layer. */
function spanTarget(sp) {
  const p = sp.closest("p"), para = +p.dataset.i, start = +sp.dataset.s, end = +sp.dataset.e;
  return { word: sp.textContent, lang: S.doc.langs[para], loc: { para, start, end }, rect: () => sp.getBoundingClientRect(),
           mark() { sp.classList.add("on"); }, phrase(r) { highlightPhrase(r, para, start); } };
}
function pdfTarget(m, w) {
  return { word: w.word, lang: S.doc.lang, loc: { ctx: w.ctx, start: w.start, end: w.end },
           rect: () => w.rect, mark() { m.mark("gl-on", w.layer, w.a, w.b); },
           phrase(r) {
             const text = w.ctx.toLowerCase(), needle = r.span.toLowerCase(); let from = 0;
             while ((from = text.indexOf(needle, from)) >= 0) {
               if (from <= w.start && w.start < from + needle.length) { const off = w.a - w.start; return m.mark("gl-phrase", w.layer, from + off, from + off + needle.length); }
               from += 1;
             }
           } };
}
function onReaderClick(e) {
  const sp = e.target.closest(".w"); if (!sp) return;
  if (String(getSelection()).trim()) return;
  if (e.altKey) return analyze(spanTarget(sp).loc, true);
  lookup(spanTarget(sp), false);
}
async function onPdfClick(e, d) {
  if (String(getSelection()).trim() || !e.target.closest(".textLayer")) return;
  const m = await pdfMod(), w = m.wordAt(e.clientX, e.clientY, d.lang);
  if (!w) return closeCard();                       // the text layer covers the whole page: a click on blank space is not on a word
  w.rect = new DOMRect(e.clientX - 4, e.clientY - 9, 8, 18);
  const tg = pdfTarget(m, w);
  if (e.altKey) return analyze(tg.loc, true);
  lookup(tg, false);
}
async function onPdfSelect(d) {
  const m = await pdfMod(), si = m.selectionInfo(); if (!si) return hideSel();
  const b = $("#selBtn"), words = si.text.split(/\s+/).length;
  b.textContent = t("sentenceBtn"); b.hidden = false;
  b.style.left = Math.min(si.rect.right, innerWidth - 150) + "px"; b.style.top = (si.rect.bottom + 8) + "px";
  b.onclick = () => { analyze({ ctx: si.ctx, start: si.start, end: si.end }, words < 4); getSelection().removeAllRanges(); hideSel(); };
}
document.addEventListener("mousedown", e => { if (!e.target.closest("#card,.w,.textLayer,#selBtn,#drawer")) { if (!$("#card").hidden) closeCard(); } });
document.addEventListener("keydown", e => { if (e.key === "Escape") { closeCard(); closeDrawer(); hideSel(); } });

async function lookup(tg, refresh) {
  const { word, lang } = tg;
  closeCard(); tg.mark();
  const tok = ++S.tok;
  const slow = setTimeout(() => { if (tok === S.tok && $("#cBody .dots")) $("#cBody").insertAdjacentHTML("beforeend", `<div class="hint">${esc(t("slow"))}</div>`); }, 8000);
  openCard(tg.rect(), `<div class="hd"><b>${esc(word)}</b><span class="sp"></span><button class="x" id="cardX">×</button></div>
    <div class="dict" id="cDict" hidden></div><div id="cBody"><div class="dots"><span></span><span></span><span></span></div></div>`);
  if (lang === "en" && S.st.dictionary && target() === "zh") {
    api("/api/dict?word=" + encodeURIComponent(word)).then(r => {
      if (tok !== S.tok || !r.entry) return;
      const en = r.entry; $("#cDict").hidden = false;
      $("#cDict").textContent = (en.phonetic ? `/${en.phonetic}/ ` : "") + en.translation.slice(0, 2).join(" ; ");
      placeCard($("#card")._rect);
    }).catch(() => {});
  }
  try {
    const r = await api("/api/gloss/word", { doc: S.doc.id, ...tg.loc, refresh });
    clearTimeout(slow);
    if (tok !== S.tok) return;
    renderResult(r, tg);
  } catch (err) {
    clearTimeout(slow);
    if (tok !== S.tok) return;
    $("#cBody").innerHTML = `<div class="bad">${esc(err.message)}</div>${hasModel() ? "" : `<div class="hint">${esc(t("noModel"))}</div>`}<div class="acts"><button class="btn small" id="retry">${esc(t("retry"))}</button></div>`;
    $("#retry").onclick = () => lookup(tg, true); placeCard($("#card")._rect);
  }
}
function renderResult(r, tg) {
  S.seen.add(r.word.toLowerCase()); if (r.span.indexOf(" ") < 0) S.seen.add(r.span.toLowerCase()); markSeen();
  const prov = r.provider ? `${r.provider.local ? t("local") : t("cloud")} · ${esc(r.provider.name)}` : "";
  $("#cBody").innerHTML = `
    <div class="sense">${esc(r.sense)}</div>
    <div class="meta">${r.pos ? `<span class="chip">${esc(r.pos)}</span>` : ""}<span class="chip k-${esc(r.kind)}">${esc(t("kind_" + r.kind))}</span></div>
    ${r.span.toLowerCase() !== r.word.toLowerCase() ? `<div class="why"><b>${esc(t("phrase"))}：</b>${esc(r.span)}</div>` : ""}
    ${r.why ? `<div class="why">${esc(r.why)}</div>` : ""}
    ${r.other_senses.length ? `<div class="oth">${esc(t("others"))}：${r.other_senses.map(esc).join(" · ")}</div>` : ""}
    <div class="src">${prov}${r.fell_back ? ` · <span class="fb">${esc(t("fellback"))}</span>` : ""}${r.cached ? ` · ${esc(t("cached"))}` : ""}</div>
    <div class="acts"><button class="btn small" id="aKnown">✓ ${esc(t("known"))}</button><button class="btn small" id="aSpeak">🔊 ${esc(t("speak"))}</button><button class="btn small" id="aSent">${esc(t("sentenceBtn"))}</button><button class="btn small" id="aRe">↻</button></div>`;
  tg.phrase(r);
  $("#aKnown").onclick = async () => { await api("/api/vocab/status", { id: r.vocab.id, status: "known" }); S.seen.delete(r.word.toLowerCase()); S.seen.delete(r.span.toLowerCase()); markSeen(); toast(t("saved")); closeCard(); };
  $("#aSpeak").onclick = () => { const u = new SpeechSynthesisUtterance(r.span); u.lang = r.src; speechSynthesis.cancel(); speechSynthesis.speak(u); };
  $("#aSent").onclick = () => analyze(tg.loc, true);
  $("#aRe").onclick = () => lookup(tg, true);
  placeCard($("#card")._rect);
}
function highlightPhrase(r, para, start) {
  if (r.span.toLowerCase() === r.word.toLowerCase()) return;
  const text = S.doc.paragraphs[para].toLowerCase(), needle = r.span.toLowerCase();
  let from = 0, hit = -1;
  while ((from = text.indexOf(needle, from)) >= 0) { if (from <= start && start < from + needle.length) { hit = from; break; } from += 1; }
  if (hit < 0) return;
  $$(`#reader p[data-i="${para}"] .w`).forEach(sp => { if (+sp.dataset.s >= hit && +sp.dataset.e <= hit + needle.length) sp.classList.add("phrase"); });
}

// ------------------------------------------------------------------ sentence analysis
function hideSel() { $("#selBtn").hidden = true; }
function onSelect() {
  const sel = getSelection();
  if (!sel || sel.isCollapsed || !$("#reader")) return hideSel();
  const range = sel.getRangeAt(0), host = range.commonAncestorContainer, el = host.nodeType === 1 ? host : host.parentElement;
  const p = el && el.closest && el.closest("#reader p[data-i]");
  if (!p) { if ($("#reader")?.contains(el)) toast(t("selectOne")); return hideSel(); }
  const spans = $$(".w", p).filter(x => range.intersectsNode(x)); if (!spans.length) return hideSel();
  const start = Math.min(...spans.map(x => +x.dataset.s)), end = Math.max(...spans.map(x => +x.dataset.e));
  const b = $("#selBtn"), rr = range.getBoundingClientRect();
  b.textContent = t("sentenceBtn"); b.hidden = false;
  b.style.left = Math.min(rr.right, innerWidth - 150) + "px"; b.style.top = (rr.bottom + 8) + "px";
  const words = String(sel).trim().split(/\s+/).length;
  b.onclick = () => { analyze({ para: +p.dataset.i, start, end }, words < 4); sel.removeAllRanges(); hideSel(); };
}
// the reader changes width when the drawer slides in or out; tell the PDF view right away (no slide animation, so the width is already final)
const nudgeResize = () => dispatchEvent(new Event("resize"));
function closeDrawer() { S.dtok++; $("#drawer").hidden = true; document.body.classList.remove("drawer-open"); nudgeResize(); }
$("#drawerX").onclick = closeDrawer;
function mdLite(s) {
  const html = esc(s).split("\n").map(l => /^\s*[-*•]\s+/.test(l) ? `<li>${l.replace(/^\s*[-*•]\s+/, "")}</li>` : l.trim() ? `<p>${l}</p>` : "").join("");
  return html.replace(/(<li>.*?<\/li>)+/gs, m => `<ul>${m}</ul>`).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}
function renderSections(text) {
  const parts = {}; let cur = null;
  for (const line of text.split("\n")) {
    const m = line.match(/^\s*#{1,3}\s*(Translation|Core|Structure|Hard words)\s*$/i);
    if (m) { cur = ["Translation", "Core", "Structure", "Hard words"].find(x => x.toLowerCase() === m[1].toLowerCase()); parts[cur] = ""; } else if (cur) parts[cur] += line + "\n";
  }
  const keys = Object.keys(parts);
  if (!keys.length) return mdLite(text);
  return keys.map(k => `<h4>${esc(t("sec_" + k))}</h4>${mdLite(parts[k].trim())}`).join("");
}
async function analyze(loc, expand) {
  closeCard(); hideSel();
  const tok = ++S.dtok, dr = $("#drawer");
  $("#drawerTitle").textContent = t("sentenceTitle"); $("#drawerQuote").textContent = ""; $("#drawerFoot").textContent = "";
  $("#drawerBody").innerHTML = `<p>${esc(t("thinking"))}</p><div class="dots"><span></span><span></span><span></span></div>`; dr.hidden = false; document.body.classList.add("drawer-open"); nudgeResize();
  let res;
  try {
    res = await fetch("/api/gloss/sentence", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ doc: S.doc.id, ...loc, expand }) });
  } catch (err) { $("#drawerBody").innerHTML = `<p class="bad">${esc(err.message)}</p>`; return; }
  if (!res.ok) { const j = await res.json().catch(() => ({})); $("#drawerBody").innerHTML = `<p class="bad">${esc(j.error || res.statusText)}</p>${hasModel() ? "" : `<p class="hint">${esc(t("noModel"))}</p>`}`; return; }
  const rd = res.body.getReader(), dec = new TextDecoder(); let buf = "", text = "";
  while (true) {
    const { value, done } = await rd.read(); if (done || tok !== S.dtok) break;
    buf += dec.decode(value, { stream: true });
    let i; while ((i = buf.indexOf("\n\n")) >= 0) {
      const ev = buf.slice(0, i); buf = buf.slice(i + 2);
      if (!ev.startsWith("data: ")) continue;
      const o = JSON.parse(ev.slice(6));
      if (o.meta) {
        $("#drawerQuote").textContent = o.meta.text;
        $("#drawerFoot").innerHTML = `${o.meta.provider.local ? esc(t("local")) : esc(t("cloud"))} · ${esc(o.meta.provider.name)}${o.meta.fell_back ? ` · <span class="bad">${esc(t("fellback"))}</span>` : ""}`;
      }
      if (o.delta) { text += o.delta; $("#drawerBody").innerHTML = renderSections(text); }
      if (o.error) $("#drawerBody").insertAdjacentHTML("beforeend", `<p class="bad">${esc(o.error)}</p>`);
    }
  }
}

// ------------------------------------------------------------------ vocabulary
async function renderVocab() {
  const f = S.vfilter, rows = (await api("/api/vocab" + (f === "all" ? "" : "?status=" + f))).vocab;
  const titles = Object.fromEntries(S.docs.map(d => [d.id, d.title]));
  const hl = (sent, w) => { const i = sent.toLowerCase().indexOf(w.toLowerCase()); return i < 0 ? esc(sent) : esc(sent.slice(0, i)) + "<mark>" + esc(sent.slice(i, i + w.length)) + "</mark>" + esc(sent.slice(i + w.length)); };
  $("#main").innerHTML = `<div class="page"><h2>${esc(t("vocab"))}</h2>
    <div class="tabs">${[["new", "vNew"], ["known", "vKnown"], ["all", "vAll"]].map(([k, l]) => `<button class="tab ${f === k ? "on" : ""}" data-vf="${k}">${esc(t(l))}</button>`).join("")}
      <span style="flex:1"></span><a class="btn small" href="/api/vocab/export${f === "all" ? "" : "?status=" + f}">${esc(t("export"))}</a></div>
    ${rows.length ? rows.map(r => `<div class="vrow"><span class="w1">${esc(r.word)}</span><span class="sn">${esc(r.sense)}</span>
      <div class="sent">${hl(r.sentence, r.word)}</div>
      <div class="act"><span>${esc(titles[r.doc_id] || "")}</span><span style="flex:1"></span>
        ${r.status === "known" ? `<button class="btn small" data-vs="${r.id}" data-to="new">${esc(t("back"))}</button>` : `<button class="btn small" data-vs="${r.id}" data-to="known">✓ ${esc(t("known"))}</button>`}
        <button class="btn small danger" data-vd="${r.id}">${esc(t("del"))}</button></div></div>`).join("") : `<p class="lead">${esc(t("vEmpty"))}</p>`}</div>`;
}

// ------------------------------------------------------------------ settings
function renderSettings() {
  const st = S.st, s = st.settings, provs = st.providers, lo = s.mode === "local_only";   // local only: cloud entries are inert
  const off = p => lo && !p.local;
  const pOpts = sel => `<option value="">${esc(t("auto"))}</option>` + provs.map(p => `<option value="${esc(p.id)}" ${p.id === sel ? "selected" : ""} ${off(p) ? "disabled" : ""}>${esc(p.name)} · ${esc(p.model)}</option>`).join("");
  $("#main").innerHTML = `<div class="page"><h2>${esc(t("settings"))}</h2>
    <h3>${esc(t("targetLang"))}</h3><p class="lead">${esc(t("targetD"))}</p>
    <select id="sTarget" style="max-width:240px">${langOptions(s.target_lang)}</select>
    <h3>${esc(t("mode"))}</h3>
    ${st.modes.map(m => `<label class="opt ${s.mode === m ? "on" : ""}"><input type="radio" name="mode" value="${m}" ${s.mode === m ? "checked" : ""}><span><b>${esc(t("m_" + m))}</b><small>${esc(t("m_" + m + "D"))}</small></span></label>`).join("")}
    <h3>${esc(t("lmTitle"))}</h3><p class="lead">${esc(t("lmD"))}</p>
    <div id="localBox"><div class="dots"><span></span><span></span><span></span></div></div>
    <h3>${esc(t("models"))}</h3>
    ${provs.map(p => `<div class="prov ${off(p) ? "off" : ""}"><div class="top"><b>${esc(p.name)}</b><span class="chip ${p.local ? "lock" : ""}">${esc(p.local ? t("localTag") : t("cloudTag"))}</span>
      ${p.local ? "" : `<span class="${p.has_key ? "ok" : "bad"}">${esc(p.has_key ? t("keyOk") : t("noKeyYet"))}</span>`}${off(p) ? `<small>${esc(t("cloudOff"))}</small>` : ""}
      <button class="btn small" data-test="${esc(p.id)}" ${off(p) ? "disabled" : ""}>${esc(t("test"))}</button>${p.id === "builtin" ? "" : `<button class="btn small danger" data-pdel="${esc(p.id)}">${esc(t("del"))}</button>`}</div>
      <small>${esc(p.model)} · ${esc(p.base_url || "api.anthropic.com")}</small><div id="t-${esc(p.id)}"></div></div>`).join("")}
    ${provs.length ? `<div class="two form" style="grid-template-columns:1fr 1fr"><label>${esc(t("wordWith"))}<select id="sWord">${pOpts(s.word_provider)}</select></label><label>${esc(t("sentWith"))}<select id="sSent">${pOpts(s.sentence_provider)}</select></label></div>` : ""}
    <div class="row gap"><button class="btn" id="disc">${esc(t("discover"))}</button></div><div id="discOut"></div>
    <h3>${esc(t("addCustom"))}</h3>
    <p class="lead">${esc(t("addD"))}</p>
    ${lo ? `<div class="note">${esc(t("localOnlyNote"))}</div>` : ""}
    <form class="form" id="pform">
      <div class="two"><label>${esc(t("preset"))}<select id="pPreset" ${lo ? "disabled" : ""}><option value="">${esc(t("custom"))}</option>${st.presets.map((p, i) => `<option value="${i}">${esc(p.name)}</option>`).join("")}</select></label>
        <label>${esc(t("name"))}<input type="text" id="pName"></label></div>
      <label>${esc(t("baseUrl"))}<input type="text" id="pUrl" placeholder="https://…/v1"></label>
      <div class="two"><label>${esc(t("model"))}<input type="text" id="pModel"></label><label>${esc(t("key"))}<input type="password" id="pKey" autocomplete="off" ${lo ? "disabled" : ""}></label></div>
      <label><input type="checkbox" id="pLocal" ${lo ? "checked disabled" : ""}> ${esc(t("isLocal"))}</label>
      <div class="row end"><span class="bad" id="pErr" style="flex:1"></span><button class="btn primary" type="submit">${esc(t("save"))}</button></div>
      ${st.keys_persistent ? "" : `<div class="hint">${esc(t("keyMem"))}</div>`}
    </form>
    <h3>${esc(t("dictH"))}</h3><p class="lead">${esc(st.dictionary ? t("dictOn") : t("dictOff"))}</p>
    <h3>${esc(t("uiLang"))}</h3><select id="sUi" style="max-width:200px"><option value="zh" ${UI === "zh" ? "selected" : ""}>中文</option><option value="en" ${UI === "en" ? "selected" : ""}>English</option></select>
  </div>`;
  $("#sTarget").onchange = async e => { await api("/api/settings", { target_lang: e.target.value }); await refreshState(); toast(t("saved")); };
  $$("input[name=mode]").forEach(r => { r.onchange = async () => { await api("/api/settings", { mode: r.value }); await refreshState(); renderSettings(); }; });
  if ($("#sWord")) { $("#sWord").onchange = async e => { await api("/api/settings", { word_provider: e.target.value }); toast(t("saved")); }; $("#sSent").onchange = async e => { await api("/api/settings", { sentence_provider: e.target.value }); toast(t("saved")); }; }
  $("#sUi").onchange = e => { localStorage.setItem("gl_ui", e.target.value); location.reload(); };
  $("#disc").onclick = discover;
  loadLocal();
  $("#pPreset").onchange = e => { const p = st.presets[e.target.value]; if (!p) return; $("#pName").value = p.name; $("#pUrl").value = p.base_url; $("#pLocal").checked = false; $("#pform").dataset.kind = p.kind; };
  $("#pform").onsubmit = async e => {
    e.preventDefault();
    const local = $("#pLocal").checked, url = $("#pUrl").value.trim(), model = $("#pModel").value.trim(), key = $("#pKey").value.trim();
    const name = $("#pName").value.trim() || model;                      // the name is optional: default to the model name
    const missing = [[url, "baseUrl", "#pUrl"], [model, "model", "#pModel"]].filter(([v]) => !v);
    ["#pUrl", "#pModel", "#pKey"].forEach(id => $(id).classList.remove("invalid"));
    missing.forEach(([, , id]) => $(id).classList.add("invalid"));
    if (missing.length) { $("#pErr").textContent = t("need") + missing.map(([, k]) => t(k)).join("、"); return; }
    if (!local && !key) { $("#pKey").classList.add("invalid"); $("#pErr").textContent = t("needKey"); return; }
    $("#pErr").textContent = "";
    try {
      await api("/api/providers/save", { name, base_url: url, model, key, local, kind: $("#pform").dataset.kind || "openai" });
      await refreshState(); toast(t("added")); renderSettings();
    } catch (err) { toast(err.message); }
  };
}
// ------------------------------------------------------------------ built-in local models
const gb = n => (n / 2 ** 30).toFixed(n >= 10 * 2 ** 30 ? 0 : 1) + " GB";
async function loadLocal() {
  const box = $("#localBox"); if (!box) return;
  let st;
  try { st = await api("/api/local"); } catch (err) { box.innerHTML = `<p class="bad">${esc(err.message)}</p>`; return; }
  if (!$("#localBox")) return;
  S.local = st; renderLocal(st);
  const busy = st.models.some(m => m.job && ["engine", "download", "verify"].includes(m.job.phase)) || st.running.status === "starting";
  clearTimeout(S.lmT);
  if (busy) S.lmT = setTimeout(() => { if (S.view === "settings") loadLocal(); }, 1000);
}
function localJob(m) {
  const j = m.job; if (!j) return "";
  if (j.phase === "engine") return `<div class="hint">${esc(t("lmEngineStep"))}</div>`;
  if (j.phase === "verify") return `<div class="hint">${esc(t("lmVerify"))}</div>`;
  if (j.phase === "download") {
    const pct = j.total ? Math.min(100, Math.round(100 * j.done / j.total)) : 0;
    return `<div class="bar2"><i style="width:${pct}%"></i></div><div class="hint">${esc(t("lmDownloading"))} ${pct}% · ${gb(j.done)} / ${gb(j.total)}</div>`;
  }
  if (j.phase === "error") return `<div class="bad">${esc(j.error)}</div>`;
  if (j.phase === "cancelled") return `<div class="hint">${esc(t("lmCancelled"))}</div>`;
  return "";
}
function renderLocal(st) {
  const box = $("#localBox"), r = st.running, anyBusy = st.models.some(m => m.job && ["engine", "download", "verify"].includes(m.job.phase));
  const eng = st.backend === "mlx" ? t("lmEngMlx") : t("lmEngLlama");
  const mirrors = st.mirrors.map(m => `<option value="${esc(m.url)}" ${m.url === st.endpoint ? "selected" : ""}>${esc(m.name)}</option>`).join("")
    + (st.mirrors.some(m => m.url === st.endpoint) ? "" : `<option value="${esc(st.endpoint)}" selected>${esc(st.endpoint.replace("https://", ""))}</option>`) + `<option value="__custom">${esc(t("lmCustom"))}</option>`;
  const stText = r.model ? `${esc(t("lmSt_" + r.status))} · ${esc((st.models.find(m => m.id === r.model) || {}).name || r.model)}` : esc(t("lmSt_" + r.status));
  box.innerHTML = `
    <div class="prov"><div class="top"><span class="chip ${r.status === "ready" ? "lock" : ""}">${stText}</span><span class="sp"></span>
      <small>${esc(t("lmEngine"))}: ${esc(eng)} · ${esc(t("lmRam"))} ${st.ram_gb} GB · ${esc(t("lmDisk"))} ${st.disk_free_gb} GB</small></div>
      ${r.status === "error" ? `<div class="bad" style="margin-top:6px">${esc(r.error)}</div>` : ""}
      <div class="two form" style="grid-template-columns:1fr 1fr;margin-top:8px">
        <label>${esc(t("lmSource"))}<select id="lmSource">${mirrors}</select></label>
        ${st.engine_can_choose_mlx ? `<label>${esc(t("lmEngine"))}<select id="lmEngine"><option value="auto" ${st.backend_setting === "auto" ? "selected" : ""}>${esc(t("lmEngAuto"))} (${esc(eng)})</option>
          <option value="mlx" ${st.backend_setting === "mlx" ? "selected" : ""}>${esc(t("lmEngMlx"))}</option><option value="llamacpp" ${st.backend_setting === "llamacpp" ? "selected" : ""}>${esc(t("lmEngLlama"))}</option></select></label>` : ""}
      </div></div>
    ${st.models.map(m => {
      const busy = m.job && ["engine", "download", "verify"].includes(m.job.phase);
      const btn = busy ? `<button class="btn small" data-lm="cancel" data-model="${m.id}">${esc(t("lmCancel"))}</button>`
        : m.installed ? `${m.active ? "" : `<button class="btn small" data-lm="select" data-model="${m.id}">${esc(t("lmUse"))}</button>`}<button class="btn small danger" data-lm="remove" data-model="${m.id}">${esc(t("lmRemove"))}</button>`
        : `<button class="btn small ${m.recommended ? "primary" : ""}" data-lm="install" data-model="${m.id}" ${anyBusy ? "disabled" : ""}>${esc(m.job && m.job.phase === "error" ? t("lmRetry") : t("lmDownload"))}</button>`;
      return `<div class="prov ${m.fits ? "" : "dim"}"><div class="top"><b>${esc(m.name)}</b>
        ${m.recommended ? `<span class="chip lock">${esc(t("lmRec"))}</span>` : ""}${m.active ? `<span class="chip lock">${esc(t("lmActive"))}</span>` : ""}${m.fits ? "" : `<span class="chip warn">${esc(t("lmNoFit"))}</span>`}
        ${btn}</div>
        <small>${esc(t("lmSizeNote"))} ${gb(m.bytes)} · ${m.ram_gb} GB+ ${esc(t("lmRam"))}${m.license ? ` · ${esc(t("lmLicense"))} ${esc(m.license)}` : ""} · ${esc(m.repo)}</small>
        <div>${esc(m.note[UI] || m.note.en)}</div>${localJob(m)}</div>`;
    }).join("")}`;
  $("#lmSource").onchange = async e => {
    let v = e.target.value;
    if (v === "__custom") { v = (prompt(t("lmCustomAsk"), "https://") || "").trim(); if (!v) return loadLocal(); }
    try { await api("/api/local/settings", { endpoint: v }); toast(t("saved")); } catch (err) { toast(err.message); }
    loadLocal();
  };
  if ($("#lmEngine")) $("#lmEngine").onchange = async e => {
    try { await api("/api/local/settings", { engine: e.target.value }); } catch (err) { toast(err.message); }
    loadLocal();
  };
}
async function localAction(el) {
  const act = el.dataset.lm, model = el.dataset.model;
  if (act === "remove" && !confirm(t("lmRemoveAsk"))) return;
  try { await api("/api/local/" + act, { model }); } catch (err) { toast(err.message); }
  await refreshState(); loadLocal();
}
async function discover() {
  const out = $("#discOut"); out.innerHTML = `<div class="dots"><span></span><span></span><span></span></div>`;
  const { found } = await api("/api/providers/discover");
  out.innerHTML = found.length ? found.map((f, i) => `<div class="prov"><div class="top"><b>${esc(t("found"))}：${esc(f.name)}</b>
      <select id="dm${i}">${f.models.map(m => `<option>${esc(m)}</option>`).join("")}</select><button class="btn small" data-adopt="${i}">${esc(t("add"))}</button></div><small>${esc(f.base_url)}</small></div>`).join("")
    : `<p class="hint">${esc(t("none"))}</p>`;
  out._found = found;
}

// ------------------------------------------------------------------ delegated clicks in the main area
$("#main").addEventListener("click", async e => {
  const el = e.target.closest("[data-act],[data-vf],[data-vs],[data-vd],[data-test],[data-pdel],[data-adopt],[data-lm]"); if (!el) return;
  try {
    if (el.dataset.lm) return localAction(el);
    if (el.dataset.act === "settings") return go("settings");
    if (el.dataset.vf) { S.vfilter = el.dataset.vf; return renderVocab(); }
    if (el.dataset.vs) { await api("/api/vocab/status", { id: +el.dataset.vs, status: el.dataset.to }); return renderVocab(); }
    if (el.dataset.vd) { await api("/api/vocab/delete", { id: +el.dataset.vd }); return renderVocab(); }
    if (el.dataset.pdel) { await api("/api/providers/delete", { id: el.dataset.pdel }); await refreshState(); return renderSettings(); }
    if (el.dataset.test) {
      const box = $("#t-" + el.dataset.test); box.innerHTML = `<small>${esc(t("testing"))}</small>`;
      const r = await api("/api/providers/test", { id: el.dataset.test });
      box.innerHTML = r.ok ? `<small class="ok">✓ ${esc(r.reply)}</small>` : `<small class="bad">${esc(r.error)}</small>`; return;
    }
    if (el.dataset.adopt) {
      const i = +el.dataset.adopt, f = $("#discOut")._found[i];
      await api("/api/providers/save", { name: f.name, base_url: f.base_url, model: $("#dm" + i).value, local: true, kind: "openai", no_think: true });
      await refreshState(); toast(t("added")); return renderSettings();
    }
  } catch (err) { toast(err.message); }
});

boot().catch(err => { $("#main").innerHTML = `<div class="page"><p class="bad">${esc(err.message)}</p></div>`; });
