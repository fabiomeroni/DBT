/*
 * Lexical diversity of the texts: tokens, types, type-token ratio and Root TTR.
 *   TTR      = types / tokens
 *   Root TTR = types / √tokens   (Guiraud's index: less dependent on the length of the text)
 * A token is a word (case and the punctuation at its edges ignored); the types are the different words.
 * The numbers come from /api/texts/stats; this file only draws them. Used by the Texts page and by the text viewer.
 */
const TTR = (() => {
  let cache = null;
  const HELP = 'Tokens: the words of the text (case and punctuation ignored). Types: the different words. ' +
               'TTR = types ÷ tokens. Root TTR (Guiraud) = types ÷ √tokens, which depends less on the length of the text.';
  const num  = n => Number(n).toLocaleString('en-US');
  const ttr  = v => (v === null || v === undefined) ? '–' : Number(v).toFixed(3);
  const rttr = v => (v === null || v === undefined) ? '–' : Number(v).toFixed(2);
  const esc  = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const known = () => (window.DBT && DBT.langs) || [];
  const langName  = c => (window.DBT && DBT.nameByCode && DBT.nameByCode[c]) || String(c).toUpperCase();
  const langColor = c => (known().find(l => l.code === c) || {}).color || '#7a6a58';

  async function load() {
    if (!cache) {
      try { const r = await fetch('/api/texts/stats'); cache = r.ok ? await r.json() : { collections: {}, texts: {} }; }
      catch (e) { cache = { collections: {}, texts: {} }; }
    }
    return cache;
  }
  function langs(entry) {                       // the languages of an entry, in the project's order, then the others
    const order = known().map(l => l.code), have = Object.keys(entry.byLang || {});
    return have.filter(c => order.includes(c)).sort((a, b) => order.indexOf(a) - order.indexOf(b)).concat(have.filter(c => !order.includes(c)).sort());
  }
  const cells = m => `<td>${num(m.tokens)}</td><td>${num(m.types)}</td><td>${ttr(m.ttr)}</td><td>${rttr(m.rttr)}</td>`;

  // A table for the upper right corner of a page or of a section: the whole, then each language when there are several.
  function boxHTML(entry, allLabel) {
    if (!entry || !entry.all || !entry.all.tokens) return '';
    const ls = langs(entry), several = ls.length > 1;
    const rows = several
      ? `<tr class="ttr-all"><th>${esc(allLabel || 'All languages')}</th>${cells(entry.all)}</tr>` +
        ls.map(c => `<tr class="ttr-lang" data-lang="${esc(c)}"><th style="color:${langColor(c)};">${esc(langName(c))}</th>${cells(entry.byLang[c])}</tr>`).join('')
      : `<tr class="ttr-all" data-lang="${esc(ls[0] || '')}"><th style="color:${ls.length ? langColor(ls[0]) : 'inherit'};">${esc(ls.length ? langName(ls[0]) : (allLabel || 'All'))}</th>${cells(entry.all)}</tr>`;
    return `<table class="ttr-table" title="${esc(HELP)}"><thead><tr><th></th><th>tokens</th><th>types</th><th>TTR</th><th>Root TTR</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  // Two short lines for the corner of a card: the measures, then the counts they come from; the title lists them by language.
  function miniHTML(entry) {
    if (!entry || !entry.all || !entry.all.tokens) return '';
    const a = entry.all, ls = langs(entry);
    const tip = HELP + (ls.length > 1 ? '\n' + ls.map(c => `${langName(c)}: ${num(entry.byLang[c].tokens)} tokens, ${num(entry.byLang[c].types)} types, TTR ${ttr(entry.byLang[c].ttr)}, Root TTR ${rttr(entry.byLang[c].rttr)}`).join('\n') : '');
    return `<span class="ttr-mini" title="${esc(tip)}"><span>TTR ${ttr(a.ttr)} · Root TTR ${rttr(a.rttr)}</span><span>${num(a.tokens)} tokens · ${num(a.types)} types</span></span>`;
  }
  return { load, boxHTML, miniHTML, num, ttr, rttr, HELP };
})();
