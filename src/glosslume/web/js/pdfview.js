// PDF in its original layout (pdf.js, vendored under /vendor/pdfjs — no CDN). Pages are rendered lazily as canvas plus
// a transparent text layer on top. The text layer is what click-to-gloss reads: we rebuild the page text from it and
// send that text (and offsets into it) to the server instead of a stored paragraph.
const VENDOR = "/vendor/pdfjs/";
let pdfjsP;
function loadPdfjs() {
  pdfjsP ||= import(VENDOR + "pdf.min.mjs").then(m => { m.GlobalWorkerOptions.workerSrc = VENDOR + "pdf.worker.min.mjs"; return m; });
  return pdfjsP;
}

// ------------------------------------------------------------------ page text <-> DOM
/** Page text rebuilt from the text layer: text nodes concatenated, a space at every line end. */
function layerText(layer) {
  if (layer._t) return layer._t;
  const nodes = []; let text = "";
  const w = document.createTreeWalker(layer, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    if (n.nodeType === 3) { nodes.push({ n, start: text.length }); text += n.nodeValue; }
    else if (n.tagName === "BR") text += " ";
  }
  return (layer._t = { text, nodes });
}
const layerOf = node => (node && (node.nodeType === 1 ? node : node.parentElement))?.closest?.(".textLayer") || null;

/** The page text around [a, b), cut to a window so a huge page does not go to the model; offsets are re-based. */
function windowed(text, a, b) {
  const lo = Math.max(0, a - 3000), hi = Math.min(text.length, b + 3000);
  return { ctx: text.slice(lo, hi), start: a - lo, end: b - lo };
}

/** Word under a click: {word, ctx, start, end, layer, a, b} (a, b are offsets in the whole page text) or null. */
export function wordAt(x, y, lang) {
  let node, off;
  if (document.caretPositionFromPoint) { const p = document.caretPositionFromPoint(x, y); node = p?.offsetNode; off = p?.offset; }
  else if (document.caretRangeFromPoint) { const r = document.caretRangeFromPoint(x, y); node = r?.startContainer; off = r?.startOffset; }
  const layer = layerOf(node);
  if (!layer || node.nodeType !== 3) return null;
  const { text, nodes } = layerText(layer);
  const hit = nodes.find(e => e.n === node); if (!hit) return null;
  const idx = hit.start + off;
  const seg = new Intl.Segmenter(!lang || lang === "und" ? undefined : lang, { granularity: "word" });
  // the caret sits between characters: on the right half of a word's last letter it points just past the word
  const pick = i => { const s = seg.segment(text).containing(i); return s && s.isWordLike && !/^[\d.,]+$/.test(s.segment) ? s : null; };
  const found = pick(idx) || (idx > 0 ? pick(idx - 1) : null);
  if (!found) return null;
  const a = found.index, b = a + found.segment.length;
  return { word: found.segment, layer, a, b, ...windowed(text, a, b) };
}

/** Current selection inside one text layer: {text, ctx, start, end, layer, a, b} or null. */
export function selectionInfo() {
  const sel = getSelection();
  if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
  const range = sel.getRangeAt(0), layer = layerOf(range.commonAncestorContainer);
  if (!layer) return null;
  const { text, nodes } = layerText(layer);
  const hit = nodes.filter(e => range.intersectsNode(e.n));
  if (!hit.length) return null;
  const first = hit[0], last = hit[hit.length - 1];
  const a = first.start + (first.n === range.startContainer ? range.startOffset : 0);
  const b = last.start + (last.n === range.endContainer ? range.endOffset : last.n.nodeValue.length);
  if (b <= a) return null;
  return { text: String(sel).trim(), layer, a, b, rect: range.getBoundingClientRect(), ...windowed(text, a, b) };
}

/** Highlight [a, b) of a page's text with the CSS Custom Highlight API (no-op where unsupported). */
export function mark(name, layer, a, b) {
  if (!globalThis.CSS?.highlights || !layer) return;
  const { nodes } = layerText(layer), range = document.createRange();
  const s = nodes.find(e => a >= e.start && a <= e.start + e.n.nodeValue.length);
  const t = nodes.find(e => b >= e.start && b <= e.start + e.n.nodeValue.length);
  if (!s || !t) return;
  range.setStart(s.n, a - s.start); range.setEnd(t.n, b - t.start);
  CSS.highlights.set(name, new Highlight(range));
}
export const unmark = name => globalThis.CSS?.highlights?.delete(name);
export const pageText = layer => layerText(layer).text;

// ------------------------------------------------------------------ viewer
/**
 * Show a PDF in `host`. Calls onPage(n) when the page nearest the top changes. Returns {destroy, goto}.
 * Throws if the PDF cannot be opened (the caller falls back to the extracted text).
 */
export async function mountPdf(host, scroller, url, startPage, onPage) {
  const pdfjs = await loadPdfjs();
  const pdf = await pdfjs.getDocument({
    url, cMapUrl: VENDOR + "cmaps/", cMapPacked: true, standardFontDataUrl: VENDOR + "standard_fonts/", wasmUrl: VENDOR + "wasm/",
  }).promise;
  const first = await pdf.getPage(1);
  let width = 0, scale = 1, ratio = 1.3, pages = [], alive = true, io = null;

  const rendered = new Set();
  async function render(i) {
    const el = pages[i - 1]; if (!el || rendered.has(i)) return;
    rendered.add(i);
    try {
      const page = await pdf.getPage(i); if (!alive) return;
      const vp = page.getViewport({ scale });
      el.style.width = vp.width + "px"; el.style.height = vp.height + "px";
      el.style.setProperty("--scale-factor", String(scale)); el.style.setProperty("--user-unit", "1");
      el.style.setProperty("--total-scale-factor", "calc(var(--scale-factor) * var(--user-unit))");
      const dpr = Math.min(2, devicePixelRatio || 1), canvas = document.createElement("canvas");
      canvas.width = Math.floor(vp.width * dpr); canvas.height = Math.floor(vp.height * dpr);
      canvas.style.width = vp.width + "px"; canvas.style.height = vp.height + "px";
      const tl = document.createElement("div"); tl.className = "textLayer";
      tl.style.width = vp.width + "px"; tl.style.height = vp.height + "px";
      el.replaceChildren(canvas, tl);
      await page.render({ canvasContext: canvas.getContext("2d"), viewport: vp, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null }).promise;
      if (!alive) return;
      await new pdfjs.TextLayer({ textContentSource: page.streamTextContent(), container: tl, viewport: vp }).render();
      el.classList.add("done");
    } catch (err) {
      rendered.delete(i);
      if (alive) el.textContent = String(err.message || err);
    }
  }

  function layout() {
    width = Math.max(320, Math.min(1000, host.clientWidth - 8));
    scale = width / first.getViewport({ scale: 1 }).width;
    const vp1 = first.getViewport({ scale });
    ratio = vp1.height / vp1.width;
    io?.disconnect(); rendered.clear();
    host.replaceChildren();
    pages = Array.from({ length: pdf.numPages }, (_, k) => {
      const d = document.createElement("div"); d.className = "pdfpage"; d.dataset.page = String(k + 1);
      d.style.width = vp1.width + "px"; d.style.height = vp1.height + "px";
      host.append(d); return d;
    });
    io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) render(+e.target.dataset.page); }), { root: scroller, rootMargin: "1400px 0px" });
    pages.forEach(p => io.observe(p));
  }

  let cur = 0, t;
  const onScroll = () => {
    clearTimeout(t);
    t = setTimeout(() => {
      const top = scroller.getBoundingClientRect().top + 100;      // just below the sticky bar (pages scroll to 86px under it)
      const p = pages.find(e => e.getBoundingClientRect().bottom > top);
      const n = p ? +p.dataset.page : 1;
      if (n !== cur) { cur = n; onPage?.(n); }
    }, 250);
  };
  const goto = n => { pages[Math.min(Math.max(1, n), pages.length) - 1]?.scrollIntoView({ block: "start" }); };
  let lastW = 0, rt;
  const onResize = () => {
    clearTimeout(rt);
    rt = setTimeout(() => { if (Math.abs(host.clientWidth - lastW) > 40) { const keep = cur || startPage; lastW = host.clientWidth; layout(); goto(keep); } }, 60);
  };
  lastW = host.clientWidth; layout(); cur = startPage;
  goto(startPage);
  scroller.addEventListener("scroll", onScroll); addEventListener("resize", onResize);
  const ro = new ResizeObserver(onResize); ro.observe(scroller);   // the window is not the only thing that resizes the page: the sentence drawer does too
  return {
    pages: pdf.numPages, goto,
    destroy() {
      alive = false; io?.disconnect(); ro.disconnect(); scroller.removeEventListener("scroll", onScroll); removeEventListener("resize", onResize);
      unmark("gl-on"); unmark("gl-phrase"); pdf.destroy();
    },
  };
}
