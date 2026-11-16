/**
 * display.js — the Orthography / IPA choice, shared by every page.
 * A visitor chooses (in the Settings, ⚙ in the top bar) whether the linguistic data are shown in the orthography or in IPA; the choice is kept in the browser.
 * The vernacular text of the page (the examples, the entries, the texts, the tables of words, the concordance) is found by the selectors below;
 * its text is converted by the server with the table of the Settings, and put back when the visitor returns to the orthography.
 * A headword that has an IPA form in the dictionary carries it in data-ipa: that form is shown (it is the author's own), not a derived one.
 */
'use strict';
(function () {
  const KEY = 'dbt.script';
  const SELECTORS = [
    '.ex-cell', '.cite-form-cell', '.cite-fn-form',            // examples of the grammar and of the dictionary, cited sentences
    '.chip-form', '.lx-form',                                  // {{entry}} chips, tables of words
    '.tx-form', '.tx-word-form', '.fn-form-cell',              // texts
    '.entry-headword', '.sg-hw', '.hw-index a', '.idiome_lang',// dictionary: headwords, the index, cognates
    '.cc-left', '.cc-match', '.cc-right', 'span.cc-form',      // concordance
    '[data-vern]'                                              // anything else a page marks as vernacular
  ].join(',');
  let mode = 'orth';
  try { mode = localStorage.getItem(KEY) === 'ipa' ? 'ipa' : 'orth'; } catch (e) { /* no storage: orthography */ }

  const original = new Map();                      // text node -> its text in the orthography
  const cache = new Map();                         // orthographic text -> IPA
  let busy = false, queue = new Set(), timer = null;

  const inSup = n => !!n.parentElement && !!n.parentElement.closest('sup');
  function nodesOf(root) {
    const els = [];
    if (root.nodeType === 1) { if (root.matches(SELECTORS)) els.push(root); root.querySelectorAll(SELECTORS).forEach(e => els.push(e)); }
    else if (root.parentElement && root.parentElement.closest(SELECTORS)) els.push(root.parentElement.closest(SELECTORS));
    const seen = new Set(), out = [];
    els.forEach(el => {
      if (el.closest('input, textarea, select, script, style')) return;
      const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let first = true, n;
      const stored = el.getAttribute('data-ipa');
      while ((n = w.nextNode())) {
        if (seen.has(n) || !n.nodeValue.trim() || inSup(n)) continue;
        seen.add(n);
        out.push({ n, stored: stored ? (first ? stored : '') : null }); first = false;
      }
    });
    return out;
  }

  async function convert(texts) {
    const need = [...new Set(texts)].filter(t => !cache.has(t));
    for (let i = 0; i < need.length; i += 2000) {
      const part = need.slice(i, i + 2000);
      try {
        const r = await fetch('/api/ipa/convert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texts: part }) });
        const d = await r.json();
        part.forEach((t, k) => cache.set(t, r.ok ? d.ipa[k] : t));
      } catch (e) { part.forEach(t => cache.set(t, t)); }
    }
  }

  async function toIpa(root) {
    const items = nodesOf(root).filter(({ n }) => !original.has(n));
    if (!items.length) return;
    items.forEach(({ n }) => original.set(n, n.nodeValue));
    await convert(items.filter(i => i.stored === null).map(i => i.n.nodeValue));
    if (mode !== 'ipa') { restore(); return; }                         // the visitor switched back meanwhile
    busy = true;
    items.forEach(({ n, stored }) => { if (n.isConnected) n.nodeValue = stored !== null ? stored : cache.get(original.get(n)) ?? n.nodeValue; });
    busy = false;
  }

  function restore() {
    busy = true;
    original.forEach((text, n) => { if (n.isConnected) n.nodeValue = text; });
    original.clear();
    busy = false;
  }

  function apply(root) { if (mode === 'ipa') return toIpa(root || document.body); }

  function setMode(m) {
    mode = m === 'ipa' ? 'ipa' : 'orth';
    try { localStorage.setItem(KEY, mode); } catch (e) { /* kept for this page only */ }
    document.documentElement.classList.toggle('script-ipa', mode === 'ipa');
    document.querySelectorAll('input[name="st-script"]').forEach(r => { r.checked = r.value === mode; });      // the Settings dialog
    if (mode === 'ipa') apply(document.body); else restore();
  }

  function refresh() { cache.clear(); if (mode === 'ipa') { restore(); apply(document.body); } }     // the table of the Settings changed

  // what a page draws later (the dictionary, the texts, the concordance, the grammar sections) is converted as it appears
  const obs = new MutationObserver(muts => {
    if (busy || mode !== 'ipa') return;
    muts.forEach(m => { m.addedNodes.forEach(n => { if (n.nodeType === 1 || n.nodeType === 3) queue.add(n); }); });
    if (!queue.size || timer) return;
    timer = setTimeout(() => { const q = [...queue]; queue = new Set(); timer = null; q.forEach(n => { if (n.isConnected) apply(n); }); }, 30);
  });

  function start() {
    document.documentElement.classList.toggle('script-ipa', mode === 'ipa');
    obs.observe(document.body, { childList: true, subtree: true });
    if (mode === 'ipa') apply(document.body);
  }
  window.dbtDisplay = { setMode, refresh, apply, get mode() { return mode; } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
