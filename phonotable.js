/*
 * The "Phonological table" tab of the grammar editor.
 *
 * The author decides the columns and the rows of a chart of consonants or of vowels (starting from the suggested order, adding,
 * removing and reordering as needed), types the inventory of each language of the project, and sees the merged chart: black for
 * the sounds all the languages have, the colour of the language for those that are specific to it. The chart is written into the
 * section as a fenced block (```phonotable … ```) that the author never has to type. The preview is made by the server with the same
 * code as the page. See phonotable.py.
 */
const PhonoEditor = (() => {
  let DEFAULTS = null;
  const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const BLOCK = /^[ \t]*```[ \t]*phonotable[ \t]*\r?\n([\s\S]*?)\r?\n[ \t]*```[ \t]*\r?$/gm;
  const KIND_NAME = { consonants: 'consonant', vowels: 'vowel' };

  async function defaults() {
    if (!DEFAULTS) {
      const r = await fetch('/api/phonotable/defaults');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      DEFAULTS = await r.json();
    }
    return DEFAULTS;
  }
  const OLD_SERVER = 'The page is newer than the application running on the server: update the files there (git pull), restart the application (python app.py, or the service that runs it), and reload this page.';
  // the charts that are in a text: [{start, end, raw, spec or null}]
  function blocksOf(text) {
    const out = [];
    for (const m of text.matchAll(BLOCK)) {
      let spec = null;
      try { spec = JSON.parse(m[1]); } catch (e) { /* shown as unreadable */ }
      out.push({ start: m.index, end: m.index + m[0].length, raw: m[1], spec });
    }
    return out;
  }
  const lowerSet = list => new Set(list.map(x => x.trim().toLowerCase()));

  async function mount(id) {
    const root = document.getElementById('pt-' + id), ta = document.getElementById('textarea-' + id);
    if (!root || !ta) return;
    let D;
    try { D = await defaults(); }
    catch (e) {                                           // never an empty pane: say what is wrong
      root.innerHTML = `<div class="pt-msg error" style="font-size:1rem;"><b>The phonological table tool could not start.</b> The server did not give the suggested rows and columns (${esc(e.message)}). ${OLD_SERVER}</div>
        <div class="pt-bar" style="margin-top:0.5rem;"><button type="button" class="pt-btn" data-retry>Try again</button></div>`;
      root.querySelector('[data-retry]').addEventListener('click', () => { DEFAULTS = null; mount(id); }, { once: true });
      return;
    }
    const langs = D.languages, several = langs.length > 1;
    const st = { index: null, spec: null, lang: langs[0].code, timer: null, run: 0 };

    // ── the list of the charts of this section ──
    function showList(message) {
      st.spec = null; st.index = null;
      const blocks = blocksOf(ta.value);
      root.innerHTML = `<p class="pt-help">Make a chart of the consonants or of the vowels without writing any markup: choose the rows and the columns, type the sounds of ${several ? 'each language' : 'the language'}, and insert it into the text.</p>
        <h4>Charts in this section</h4>
        <div class="pt-bar" id="pt-list-${id}">${blocks.length ? blocks.map((b, i) => `<button type="button" class="pt-chip" data-act="edit" data-i="${i}">${b.spec && KIND_NAME[b.spec.kind] ? esc(b.spec.caption ?? b.spec.title ?? '') + ' <small>(' + KIND_NAME[b.spec.kind] + (b.spec.caption || b.spec.title ? '' : ', no caption') + ')</small>' : 'unreadable chart (see the Text tab)'}</button>`).join('') : '<span class="pt-help" style="margin:0;">None yet.</span>'}</div>
        <h4>Make a new one</h4>
        <div class="pt-bar"><button type="button" class="pt-btn primary" data-act="new" data-kind="consonants">＋ Consonant chart</button><button type="button" class="pt-btn primary" data-act="new" data-kind="vowels">＋ Vowel chart</button></div>
        <div class="pt-msg" id="pt-msg-${id}">${message ? esc(message) : ''}</div>`;
    }

    // ── the builder ──
    function openBuilder(spec, index) {
      st.spec = spec; st.index = index; st.lang = langs[0].code;
      const k = KIND_NAME[spec.kind];
      root.innerHTML = `<div class="pt-bar" style="justify-content:space-between;"><strong>${index === null ? 'New' : 'Edit the'} ${k} chart</strong><button type="button" class="pt-btn" data-act="back">← Charts of this section</button></div>
        <h4>Caption</h4>
        <p class="pt-help">Shown above the chart as “${esc(D.captions.table)} 3${esc(D.captions.separator)}…”: you write only the text, the number is automatic and goes on through the whole grammar. Leave it empty for the number alone.</p>
        <div class="pt-field"><input type="text" id="pt-caption-${id}" value="${esc(spec.caption)}" maxlength="400" aria-label="Caption of the chart"></div>
        <h4>Columns and rows</h4>
        <p class="pt-help">Start from the suggested order and change what you need: rename, move (↑ ↓), remove (✕), or add rows and columns of your own, with any names.</p>
        <div class="pt-axes"><div class="pt-axis" data-axis="columns"></div><div class="pt-axis" data-axis="rows"></div></div>
        <div class="pt-bar" style="margin-top:0.4rem;"><button type="button" class="pt-btn" data-act="reset">↺ Suggested columns and rows</button></div>
        <h4>${several ? 'Inventory of each language' : 'Inventory'}</h4>
        <p class="pt-help">${several ? 'Choose a language and type its sounds in the cells, separated by spaces (p b). The chart merges the languages: in <b>black</b> what all the languages that have an inventory share, in the <b>colour of the language</b> what is specific to it (a sound of several, but not all, shows their colours together).' : 'Type the sounds in the cells, separated by spaces (p b).'}</p>
        ${several ? `<div class="pt-langs" id="pt-langs-${id}">${langs.map(l => `<button type="button" class="pt-lang${l.code === st.lang ? ' active' : ''}" data-lang="${esc(l.code)}"><i style="background:${esc(l.color)}"></i>${esc(l.name)}</button>`).join('')}</div>` : ''}
        <div class="pt-grid-wrap"><table class="pt-grid" id="pt-grid-${id}"></table></div>
        <h4>Preview</h4><div class="pt-preview" id="pt-preview-${id}"></div>
        <div class="pt-bar" style="margin-top:0.6rem;">
          <button type="button" class="pt-btn primary" data-act="write" id="pt-write-${id}"></button>
          <button type="button" class="pt-btn danger" data-act="remove" id="pt-remove-${id}">Remove this chart from the text</button>
        </div>
        <div class="pt-msg" id="pt-msg-${id}"></div>`;
      renderAxes(); renderGrid(); renderWrite(); preview();
    }
    const $ = sel => root.querySelector(sel);
    function renderWrite() {
      $('#pt-write-' + id).textContent = st.index === null ? 'Insert into the text' : 'Update in the text';
      $('#pt-remove-' + id).style.display = st.index === null ? 'none' : '';
    }
    function renderAxes() {
      for (const axis of ['columns', 'rows']) {
        const items = st.spec[axis], low = items.map(x => x.trim().toLowerCase());
        root.querySelector(`.pt-axis[data-axis="${axis}"]`).innerHTML = `<h4 style="margin-top:0;">${axis === 'columns' ? 'Columns' : 'Rows'}</h4><ul>` +
          items.map((x, i) => `<li><input type="text" value="${esc(x)}" data-axis="${axis}" data-i="${i}" maxlength="60" aria-label="${axis === 'columns' ? 'Column' : 'Row'} ${i + 1}">
            <button type="button" class="mini" data-act="up" data-axis="${axis}" data-i="${i}" title="Move up" ${i === 0 ? 'disabled' : ''}>↑</button>
            <button type="button" class="mini" data-act="down" data-axis="${axis}" data-i="${i}" title="Move down" ${i === items.length - 1 ? 'disabled' : ''}>↓</button>
            <button type="button" class="mini" data-act="del" data-axis="${axis}" data-i="${i}" title="Remove">✕</button></li>`).join('') +
          `</ul><div class="pt-field"><input type="text" placeholder="${axis === 'columns' ? 'Add a column' : 'Add a row'}" data-add="${axis}" maxlength="60"><button type="button" class="pt-btn" data-act="add" data-axis="${axis}">＋ Add</button></div>`;
      }
    }
    function cell(code, r, c) { return ((st.spec.inventory[code] || {})[r] || {})[c] || ''; }
    function renderGrid() {
      const s = st.spec;
      $('#pt-grid-' + id).innerHTML = '<thead><tr><th></th>' + s.columns.map(c => `<th>${esc(c)}</th>`).join('') + '</tr></thead><tbody>' +
        s.rows.map((r, ri) => `<tr><th class="r">${esc(r)}</th>` + s.columns.map((c, ci) => `<td><input type="text" class="pt-cell" data-r="${ri}" data-c="${ci}" value="${esc(cell(st.lang, r, c))}" aria-label="${esc(r)}, ${esc(c)}" autocomplete="off" spellcheck="false"></td>`).join('') + '</tr>').join('') + '</tbody>';
    }
    function setCell(code, r, c, text) {
      const inv = st.spec.inventory;
      if (!text.trim()) { if (inv[code] && inv[code][r]) { delete inv[code][r][c]; if (!Object.keys(inv[code][r]).length) delete inv[code][r]; if (!Object.keys(inv[code]).length) delete inv[code]; } return; }
      ((inv[code] = inv[code] || {})[r] = inv[code][r] || {})[c] = text;
    }
    function renameKey(axis, from, to) {                  // a row or column was renamed: its sounds follow
      for (const code of Object.keys(st.spec.inventory)) {
        const byRow = st.spec.inventory[code];
        if (axis === 'rows') { if (from in byRow) { byRow[to] = byRow[from]; delete byRow[from]; } }
        else for (const r of Object.keys(byRow)) if (from in byRow[r]) { byRow[r][to] = byRow[r][from]; delete byRow[r][from]; }
      }
    }
    function dropKey(axis, name) {
      for (const code of Object.keys(st.spec.inventory)) {
        const byRow = st.spec.inventory[code];
        if (axis === 'rows') delete byRow[name]; else for (const r of Object.keys(byRow)) delete byRow[r][name];
      }
    }
    // what is written into the text
    function cleanSpec() {
      const s = st.spec, inv = {};
      for (const [code, byRow] of Object.entries(s.inventory)) for (const [r, byCol] of Object.entries(byRow)) for (const [c, t] of Object.entries(byCol))
        if (t.trim() && s.rows.includes(r) && s.columns.includes(c)) ((inv[code] = inv[code] || {})[r] = inv[code][r] || {})[c] = t.trim();
      return { kind: s.kind, caption: s.caption.trim(), columns: s.columns, rows: s.rows, inventory: inv };
    }
    function position() {                                // how many charts come before this one in the section (its number follows from that)
      if (st.index !== null) return st.index;
      return blocksOf(ta.value.slice(0, ta.selectionStart ?? ta.value.length)).length;
    }
    async function preview() {
      const my = ++st.run, box = $('#pt-preview-' + id), msg = $('#pt-msg-' + id);
      try {
        const r = await fetch('/api/phonotable/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ spec: cleanSpec(), section: id, position: position() }) });
        let j = null; try { j = await r.json(); } catch (e) { /* not JSON: an old server answers with a page */ }
        if (my !== st.run) return;
        if (!j || !r.ok || !j.ok) { box.innerHTML = ''; msg.className = 'pt-msg error'; msg.textContent = (j && j.error) || `The server could not make the preview (HTTP ${r.status}). ${OLD_SERVER}`; return; }
        box.innerHTML = j.html; if (msg.className.includes('error')) { msg.className = 'pt-msg'; msg.textContent = ''; }
      } catch (e) { /* offline: keep what is there */ }
    }
    const schedule = () => { clearTimeout(st.timer); st.timer = setTimeout(preview, 250); };

    // ── writing into the text ──
    function blockText() { return '```phonotable\n' + JSON.stringify(cleanSpec()) + '\n```'; }
    function write() {
      const text = ta.value, block = blockText();
      if (st.index !== null && blocksOf(text)[st.index]) {
        const b = blocksOf(text)[st.index];
        ta.value = text.slice(0, b.start) + block + text.slice(b.end);
      } else {
        const s = ta.selectionStart ?? text.length, e = ta.selectionEnd ?? s, before = text.slice(0, s), after = text.slice(e);
        const pre = !before ? '' : before.endsWith('\n\n') ? '' : before.endsWith('\n') ? '\n' : '\n\n';
        const post = !after ? '\n' : after.startsWith('\n\n') ? '' : after.startsWith('\n') ? '\n' : '\n\n';
        ta.value = before + pre + block + post + after;
        st.index = blocksOf(before).length;
        renderWrite();
      }
      const msg = $('#pt-msg-' + id); msg.className = 'pt-msg'; msg.textContent = 'Written into the text. Press “Save & render” to see it on the page.';
    }
    function removeBlock() {
      const b = blocksOf(ta.value)[st.index];
      if (b) ta.value = (ta.value.slice(0, b.start) + ta.value.slice(b.end)).replace(/\n{3,}/g, '\n\n');
      showList('The chart was removed from the text. Press “Save & render” to save.');
    }
    function fromBlock(i) {
      const b = blocksOf(ta.value)[i];
      if (!b || !b.spec || !KIND_NAME[b.spec.kind]) return null;
      const arr = x => (Array.isArray(x) ? x : []).filter(v => typeof v === 'string' && v.trim()).map(v => v.trim());
      const inv = {};
      for (const [code, byRow] of Object.entries(b.spec.inventory || {})) if (langs.some(l => l.code === code) && byRow && typeof byRow === 'object')
        for (const [r, byCol] of Object.entries(byRow)) if (byCol && typeof byCol === 'object') for (const [c, t] of Object.entries(byCol)) if (typeof t === 'string' && t.trim()) ((inv[code] = inv[code] || {})[r] = inv[code][r] || {})[c] = t;
      return { kind: b.spec.kind, caption: String(b.spec.caption ?? b.spec.title ?? ''), columns: arr(b.spec.columns), rows: arr(b.spec.rows), inventory: inv };
    }

    // ── what the author does ──
    root.addEventListener('click', ev => {
      const t = ev.target.closest('[data-act], [data-lang]'); if (!t) return;
      if (t.dataset.lang) { st.lang = t.dataset.lang; root.querySelectorAll('.pt-lang').forEach(b => b.classList.toggle('active', b.dataset.lang === st.lang)); renderGrid(); return; }
      const act = t.dataset.act, axis = t.dataset.axis, i = +t.dataset.i;
      if (act === 'new') { const k = t.dataset.kind; openBuilder({ kind: k, caption: '', columns: [...D.axes[k].columns], rows: [...D.axes[k].rows], inventory: {} }, null); }
      else if (act === 'edit') { const s = fromBlock(i); if (s) openBuilder(s, i); }
      else if (act === 'back') showList();
      else if (act === 'write') write();
      else if (act === 'remove') removeBlock();
      else if (act === 'reset') { const k = st.spec.kind; st.spec.columns = [...D.axes[k].columns]; st.spec.rows = [...D.axes[k].rows]; renderAxes(); renderGrid(); schedule(); }
      else if (act === 'up' || act === 'down') {
        const a = st.spec[axis], j = act === 'up' ? i - 1 : i + 1;
        if (j >= 0 && j < a.length) { [a[i], a[j]] = [a[j], a[i]]; renderAxes(); renderGrid(); schedule(); }
      } else if (act === 'del') { dropKey(axis, st.spec[axis][i]); st.spec[axis].splice(i, 1); renderAxes(); renderGrid(); schedule(); }
      else if (act === 'add') {
        const inp = root.querySelector(`input[data-add="${axis}"]`), v = inp.value.trim();
        if (v && !lowerSet(st.spec[axis]).has(v.toLowerCase())) { st.spec[axis].push(v); inp.value = ''; renderAxes(); renderGrid(); schedule(); }
        else if (v) inp.classList.add('dup');
      }
    });
    root.addEventListener('keydown', ev => { if (ev.key === 'Enter' && ev.target.dataset.add) { ev.preventDefault(); root.querySelector(`[data-act="add"][data-axis="${ev.target.dataset.add}"]`).click(); } });
    root.addEventListener('input', ev => {
      const t = ev.target;
      if (t.id === 'pt-caption-' + id) { st.spec.caption = t.value; schedule(); }
      else if (t.classList.contains('pt-cell')) { setCell(st.lang, st.spec.rows[+t.dataset.r], st.spec.columns[+t.dataset.c], t.value); schedule(); }
      else if (t.dataset.axis && t.dataset.i !== undefined && t.tagName === 'INPUT') {
        const axis = t.dataset.axis, i = +t.dataset.i, v = t.value.trim(), others = st.spec[axis].filter((_, j) => j !== i);
        const bad = !v || lowerSet(others).has(v.toLowerCase());
        t.classList.toggle('dup', bad);
        if (!bad && v !== st.spec[axis][i]) { renameKey(axis, st.spec[axis][i], v); st.spec[axis][i] = v; renderGrid(); schedule(); }
      } else if (t.dataset.add) t.classList.remove('dup');
    });
    root.addEventListener('focusout', ev => {            // an invalid name goes back to the last valid one
      const t = ev.target;
      if (t.dataset && t.dataset.axis && t.dataset.i !== undefined && t.tagName === 'INPUT' && t.classList.contains('dup')) { t.value = st.spec[t.dataset.axis][+t.dataset.i]; t.classList.remove('dup'); }
    });
    root._pt = { show: showList, state: st };
    showList();
  }

  function refresh(id) { const r = document.getElementById('pt-' + id); if (r && r._pt && !r._pt.state.spec) r._pt.show(); }

  // the tabs of the editor of a section: Text | Phonological table
  function tabs(id) {
    const wrap = document.getElementById('editor-' + id);
    wrap.querySelectorAll('.ed-tab').forEach(b => b.addEventListener('click', () => {
      wrap.querySelectorAll('.ed-tab').forEach(x => x.classList.toggle('active', x === b));
      wrap.querySelectorAll('.ed-pane').forEach(p => { p.hidden = p.dataset.pane !== b.dataset.tab; });
      if (b.dataset.tab === 'phono') refresh(id);
    }));
  }
  function showText(id) { const wrap = document.getElementById('editor-' + id); if (wrap) wrap.querySelector('.ed-tab[data-tab="text"]').click(); }

  return { mount, tabs, showText, blocksOf };
})();


/*
 * The legend under a chart is a set of check boxes, one for each language: the reader chooses the languages to show. A sound that none of
 * the ticked languages has is left out, and the colours are worked out again for the ticked ones: black for a sound that all of them have,
 * the language's colour for a sound of one, their colours together for a sound of some. It works for any chart in the page, as soon as it is there.
 */
(() => {
  const gradient = cols => 'linear-gradient(90deg,' + cols.map((c, i) => `${c} ${+(100 * i / cols.length).toFixed(2)}% ${+(100 * (i + 1) / cols.length).toFixed(2)}%`).join(',') + ')';
  function apply(fig) {
    const boxes = [...fig.querySelectorAll('.phono-legend input[data-lang]')];
    const on = boxes.filter(b => b.checked).map(b => b.dataset.lang);
    const color = Object.fromEntries(boxes.map(b => [b.dataset.lang, b.dataset.color]));
    const name = Object.fromEntries(boxes.map(b => [b.dataset.lang, b.parentElement.textContent.trim()]));
    fig.querySelectorAll('.ph[data-langs]').forEach(el => {
      const langs = el.dataset.langs.split(' ').filter(l => on.includes(l));
      el.className = 'ph'; el.removeAttribute('style'); el.removeAttribute('title');
      if (!langs.length) { el.classList.add('ph-off'); return; }
      if (langs.length === on.length) { el.classList.add('ph-all'); return; }
      el.title = langs.map(l => name[l]).join(', ');
      if (langs.length === 1) { el.classList.add('ph-one'); el.style.color = color[langs[0]]; }
      else { el.classList.add('ph-mix'); el.style.setProperty('--ph-c1', color[langs[0]]); el.style.setProperty('--ph-grad', gradient(langs.map(l => color[l]))); }
    });
  }
  document.addEventListener('change', ev => {
    const box = ev.target;
    if (box && box.matches && box.matches('.phono-legend input[data-lang]')) apply(box.closest('figure.phonotable'));
  });
})();
