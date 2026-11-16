/**
 * settings.js — the Settings dialog, shared by every page (the author's ⚙ in the top bar).
 * It holds: the dictionary's display option, the language colours, the orthography <-> IPA table, the author password.
 * A page that depends on a setting defines window.dbtSettingsSaved(display) and redraws itself there.
 */
'use strict';
(function () {
const escS = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const esc0 = escS;
const ORTH_NAME = () => (window.DBT && DBT.project && DBT.project.orthographyName) || '';

const DIALOG_HTML = () => `<div class="dbt-modal-backdrop" id="settings-modal">
  <div class="dbt-modal" style="max-width:700px;width:96vw;max-height:92vh;overflow-y:auto;">
    <h3>Settings</h3>
    <h4 class="st-h">Display</h4>
    <label class="st-check"><input type="checkbox" id="st-rel"> In the dictionary, show the semantic relations (synonyms, antonyms) under the senses</label>
    <p class="modal-desc" style="margin-top:0.4rem;">Visitors choose for themselves, with the <b>Orthography / IPA</b> switch in the top bar of every page, whether the linguistic data are shown in the orthography or in IPA.</p>
    <h4 class="st-h" style="margin-top:1.1rem;">Language colours</h4>
    <p class="modal-desc">The colour that codes each language everywhere on the site: headwords, tables, texts, the grammar and the LaTeX export.</p>
    <div id="st-colors" class="st-colors"></div>
    <div class="st-actions" style="margin-top:0.2rem;">
      <button type="button" class="fn-col-add" id="st-colors-reset">↺ Default colours</button>
    </div>
    <h4 class="st-h" style="margin-top:1.1rem;">Orthography ↔ IPA</h4>
    <p class="modal-desc">One row per correspondence. These rows suggest the IPA of a form from its orthography, read forms
      typed in IPA, and give the IPA shown on every page when a visitor switches to IPA. If a language has one letter standing for several sounds, add a row for each and tick <b>default</b> on the one
      to suggest; every row is still understood when reading IPA.</p>
    <div class="st-top">
      <label>Orthography <input id="st-name" class="em-input" placeholder="e.g. ${esc0(ORTH_NAME())}" spellcheck="false"></label>
      <label class="st-check"><input type="checkbox" id="st-long"> A doubled vowel letter is a long vowel (ēē = ɪː)</label>
    </div>
    <div style="max-height:40vh;overflow-y:auto;border:1px solid var(--border);border-radius:4px;">
      <table class="st-table">
        <thead><tr><th>Orthography</th><th>IPA</th><th>Type</th><th title="Suggested when going from orthography to IPA">Default</th><th></th></tr></thead>
        <tbody id="st-rows"></tbody>
      </table>
    </div>
    <div class="st-actions">
      <button type="button" class="fn-col-add" id="st-add-row">＋ Add a correspondence</button>
      <button type="button" class="fn-col-add" id="st-reset" style="border-color:#c06060;color:#c06060;">↺ Reset to ${esc0(ORTH_NAME())}</button>
    </div>
    <div class="st-try">
      <b>Try it</b> (uses the table as it is now, saved or not)
      <div><span>orthography</span> <input id="st-try-orth" class="em-input" placeholder="tuqa" spellcheck="false"> → <b>IPA</b> <span id="st-try-ipa" class="st-out"></span></div>
      <div><span>IPA</span> <input id="st-try-ipa-in" class="em-input" placeholder="tuk͡pʷa" spellcheck="false"> → <b>orthography</b> <span id="st-try-orth-out" class="st-out"></span></div>
    </div>
    <label class="st-check" style="margin-top:0.7rem;"><input type="checkbox" id="st-rederive" checked>
      Also re-derive the transcriptions still marked <b>?</b> with this table (confirmed ones are never changed)</label>
    <details class="st-pw">
      <summary>Author password</summary>
      <p class="modal-desc">The password is stored on the server only as a hash (in <code>instance/</code>, never in the code or the repository).
        Use at least 8 characters.</p>
      <div class="st-pw-grid">
        <label>Current password <input type="password" id="pw-current" class="em-input" autocomplete="current-password"></label>
        <label>New password <input type="password" id="pw-new" class="em-input" autocomplete="new-password"></label>
        <label>Repeat the new password <input type="password" id="pw-new2" class="em-input" autocomplete="new-password"></label>
      </div>
      <button type="button" class="fn-col-add" id="pw-change">Change password</button>
      <div class="dbt-modal-msg" id="pw-msg"></div>
    </details>
    <div class="dbt-modal-msg" id="st-msg"></div>
    <div class="dbt-modal-row">
      <button class="modal-btn" id="st-cancel">Close</button>
      <button class="modal-btn primary" id="st-save">Save settings</button>
    </div>
  </div>
</div>`;

function ensureDialog() {
  if (document.getElementById('settings-modal')) return;
  const wrap = document.createElement('div');
  wrap.innerHTML = DIALOG_HTML();
  document.body.appendChild(wrap.firstElementChild);
  bindSettings();
}

// ── Settings: the orthography ↔ IPA correspondence table ──
let _stRows = [], _stDefaults = null, _stTryTimer = null;
let _stColors = {}, _stColorsLoaded = {}, _stDefaultColors = {}, _stColorNames = {};

function renderSettingsRows() {
  const count = {};
  _stRows.forEach(r => { count[r.orth] = (count[r.orth] || 0) + 1; });
  document.getElementById('st-rows').innerHTML = _stRows.map((r, i) => `
    <tr data-i="${i}" class="${r.orth && count[r.orth] > 1 ? 'st-shared' : ''}">
      <td><input class="em-input" data-f="orth" value="${escS(r.orth)}" size="4" spellcheck="false"></td>
      <td><input class="em-input" data-f="ipa" value="${escS(r.ipa)}" size="8" spellcheck="false"></td>
      <td><select data-f="type"><option value="consonant"${r.type !== 'vowel' ? ' selected' : ''}>consonant</option>
                                <option value="vowel"${r.type === 'vowel' ? ' selected' : ''}>vowel</option></select></td>
      <td style="text-align:center;"><input type="checkbox" data-f="default"${r.default ? ' checked' : ''}
          title="${count[r.orth] > 1 ? 'Several sounds share this letter: tick the one to suggest' : 'Suggested for this letter'}"></td>
      <td><button type="button" class="st-del" data-act="del" title="Remove this row">✕</button></td>
    </tr>`).join('');
}

function stCollect() {
  return { name: document.getElementById('st-name').value.trim(),
           long_vowel_doubling: document.getElementById('st-long').checked,
           rows: _stRows.map(r => ({ orth: r.orth.trim(), ipa: r.ipa.trim(), type: r.type, default: !!r.default })) };
}

function stTry() {
  clearTimeout(_stTryTimer);
  _stTryTimer = setTimeout(async () => {
    const orth = document.getElementById('st-try-orth').value, ipa = document.getElementById('st-try-ipa-in').value;
    try {
      const r = await fetch('/api/dictionary/settings/test', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                                             body: JSON.stringify({ correspondences: stCollect(), orth, ipa }) });
      const d = await r.json();
      document.getElementById('st-try-ipa').textContent      = r.ok && orth ? '[' + d.ipa + ']' : '';
      document.getElementById('st-try-orth-out').textContent = r.ok && ipa  ? d.orth : '';
    } catch (e) { /* offline */ }
  }, 200);
}

const _HEX_RE = /^#[0-9a-fA-F]{6}$/;
const _colorOrder = () => DBT.codes.filter(c => c in _stColorNames);      // the project's order
function renderColorRows() {
  document.getElementById('st-colors').innerHTML = _colorOrder().map(c => `
    <div class="st-color">
      <label style="color:${_stColors[c]};">${escS(_stColorNames[c])}</label>
      <input type="color" data-c="${c}" value="${_stColors[c]}" title="Choose the colour of ${escS(_stColorNames[c])}">
      <input class="em-input" data-c="${c}" data-hex="1" value="${_stColors[c]}" maxlength="7" spellcheck="false">
      <button type="button" data-reset="${c}" title="Back to the default colour">↺</button>
    </div>`).join('');
}
function setColor(c, v) {
  _stColors[c] = v.toLowerCase();
  const row = document.querySelector(`#st-colors .st-color input[type=color][data-c="${c}"]`).closest('.st-color');
  row.querySelector('input[type=color]').value = _stColors[c];
  const hex = row.querySelector('input[data-hex]'); if (document.activeElement !== hex) hex.value = _stColors[c]; hex.classList.remove('bad');
  row.querySelector('label').style.color = _stColors[c];
}
function bindColorRows() {
  const box = document.getElementById('st-colors');
  box.addEventListener('input', e => {
    const c = e.target.dataset.c; if (!c) return;
    if (e.target.type === 'color') setColor(c, e.target.value);
    else if (e.target.dataset.hex) {
      let v = e.target.value.trim(); if (v && v[0] !== '#') v = '#' + v;
      if (_HEX_RE.test(v)) setColor(c, v); else e.target.classList.toggle('bad', v.length > 0);
    }
  });
  box.addEventListener('focusout', e => { if (e.target.dataset.hex) { e.target.value = _stColors[e.target.dataset.c]; e.target.classList.remove('bad'); } });
  box.addEventListener('click', e => { const b = e.target.closest('button[data-reset]'); if (b) setColor(b.dataset.reset, _stDefaultColors[b.dataset.reset]); });
  document.getElementById('st-colors-reset').addEventListener('click', () => _colorOrder().forEach(c => setColor(c, _stDefaultColors[c])));
}

function stLoad(cfg) {
  document.getElementById('st-name').value = cfg.name || '';
  document.getElementById('st-long').checked = !!cfg.long_vowel_doubling;
  _stRows = cfg.rows.map(r => ({ orth: r.orth, ipa: r.ipa, type: r.type === 'vowel' ? 'vowel' : 'consonant', default: !!r.default }));
  renderSettingsRows(); stTry();
}

async function openSettings() {
  if (!isLoggedIn) { showLoginModal(); return; }
  const msg = document.getElementById('st-msg');
  msg.textContent = ''; msg.className = 'dbt-modal-msg';
  document.getElementById('settings-modal').classList.add('visible');
  try {
    const r = await fetch('/api/dictionary/settings');
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
    _stDefaults = d.defaults;
    document.getElementById('st-rel').checked = !d.display || d.display.relations !== false;
    _stColors = {...d.colors}; _stColorsLoaded = {...d.colors}; _stDefaultColors = d.default_colors; _stColorNames = d.color_names;
    renderColorRows();
    stLoad(d.correspondences);
  } catch (e) { msg.textContent = 'Could not load the settings: ' + e.message; msg.className = 'dbt-modal-msg error'; }
}

async function saveSettings() {
  const msg = document.getElementById('st-msg'), btn = document.getElementById('st-save');
  msg.textContent = 'Saving…'; msg.className = 'dbt-modal-msg'; btn.disabled = true;
  try {
    const r = await fetch('/api/dictionary/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correspondences: stCollect(), colors: _stColors, display: { relations: document.getElementById('st-rel').checked }, rederive: document.getElementById('st-rederive').checked }) });
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error(d.error || ('HTTP ' + r.status));
    const display = { relations: document.getElementById('st-rel').checked };
    msg.textContent = 'Saved.' + (d.rederived ? ` ${d.rederived} provisional transcription${d.rederived > 1 ? 's' : ''} re-derived.` : '');
    msg.className = 'dbt-modal-msg success';
    if (JSON.stringify(_stColors) !== JSON.stringify(_stColorsLoaded)) {      // the colours are used by every page: reload to apply them
      msg.textContent += ' Applying the new colours…';
      setTimeout(() => location.reload(), 700);
      return;
    }
    const g = await (await fetch('/api/dictionary/settings')).json();      // show what the server really kept
    if (g.correspondences) stLoad(g.correspondences);
    if (window.dbtDisplay) window.dbtDisplay.refresh();                  // the table may have changed: what is shown in IPA is converted again
    if (typeof window.dbtSettingsSaved === 'function') await window.dbtSettingsSaved(display);     // a page redraws what depends on the settings
  } catch (e) { msg.textContent = 'Not saved: ' + e.message; msg.className = 'dbt-modal-msg error'; }
  finally { btn.disabled = false; }
}

async function changePassword() {
  const msg = document.getElementById('pw-msg'), cur = document.getElementById('pw-current').value,
        nw = document.getElementById('pw-new').value, nw2 = document.getElementById('pw-new2').value;
  msg.className = 'dbt-modal-msg';
  if (nw !== nw2) { msg.textContent = 'The two new passwords differ.'; msg.className = 'dbt-modal-msg error'; return; }
  try {
    const r = await fetch('/api/auth/password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ current: cur, new: nw }) });
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error(d.error || ('HTTP ' + r.status));
    msg.textContent = 'Password changed.'; msg.className = 'dbt-modal-msg success';
    ['pw-current', 'pw-new', 'pw-new2'].forEach(id => { document.getElementById(id).value = ''; });
  } catch (e) { msg.textContent = e.message; msg.className = 'dbt-modal-msg error'; }
}

function bindSettings() {
  bindColorRows();
  document.getElementById('pw-change').addEventListener('click', changePassword);
  document.getElementById('settings-btn')?.addEventListener('click', openSettings);
  document.getElementById('st-cancel').addEventListener('click', () => document.getElementById('settings-modal').classList.remove('visible'));
  document.getElementById('settings-modal').addEventListener('click', e => { if (e.target === e.currentTarget) e.currentTarget.classList.remove('visible'); });
  document.getElementById('st-save').addEventListener('click', saveSettings);
  document.getElementById('st-add-row').addEventListener('click', () => {
    _stRows.push({ orth: '', ipa: '', type: 'consonant', default: false }); renderSettingsRows();
    document.getElementById('st-rows').lastElementChild?.querySelector('input')?.focus();
  });
  document.getElementById('st-reset').addEventListener('click', () => {
    if (_stDefaults && confirm('Replace the table by the project default' + (_stDefaults.name ? ' (' + _stDefaults.name + ')' : '') + '? Nothing is saved until you press "Save settings".')) stLoad(_stDefaults);
  });
  ['st-try-orth', 'st-try-ipa-in', 'st-long'].forEach(id => document.getElementById(id).addEventListener('input', stTry));
  const body = document.getElementById('st-rows');
  body.addEventListener('input', e => {
    const tr = e.target.closest('tr'), f = e.target.dataset.f;
    if (!tr || !f || f === 'default') return;
    const idx = +tr.dataset.i, row = _stRows[idx];
    row[f] = e.target.value;
    if (f === 'orth') {
      // the default of a letter: this row, unless another row of the same letter already is
      row.default = !!row.orth.trim() && !_stRows.some((o, k) => k !== idx && o.orth === row.orth && o.default);
      tr.querySelector('input[data-f="default"]').checked = row.default;
      renderSettingsRowsKeepFocus(tr, e.target);
    }
    stTry();
  });
  body.addEventListener('change', e => {
    const tr = e.target.closest('tr'), f = e.target.dataset.f;
    if (!tr) return;
    const row = _stRows[+tr.dataset.i];
    if (f === 'type') row.type = e.target.value;
    if (f === 'default') {
      row.default = e.target.checked;
      if (row.default) _stRows.forEach(o => { if (o !== row && o.orth === row.orth) o.default = false; });
      else if (!_stRows.some(o => o !== row && o.orth === row.orth && o.default) && !_stRows.some(o => o !== row && o.orth === row.orth)) row.default = true;
      renderSettingsRows(); stTry();
    }
  });
  body.addEventListener('click', e => {
    const b = e.target.closest('button[data-act="del"]');
    if (!b) return;
    _stRows.splice(+b.closest('tr').dataset.i, 1); renderSettingsRows(); stTry();
  });
}
// re-colour the "shared letter" rows while typing in an orthography box, without losing the cursor
function renderSettingsRowsKeepFocus(tr, input) {
  const count = {};
  _stRows.forEach(r => { count[r.orth] = (count[r.orth] || 0) + 1; });
  document.querySelectorAll('#st-rows tr').forEach(row => {
    const r = _stRows[+row.dataset.i];
    row.classList.toggle('st-shared', !!(r && r.orth && count[r.orth] > 1));
  });
}

const _openSettings = openSettings;
window.openSettings = function () { if (!isLoggedIn) { showLoginModal(); return; } ensureDialog(); return _openSettings(); };

// the author's button, in the top bar of every page (shown once logged in)
window.settingsUI = function (loggedIn) {
  const bar = document.querySelector('.topnav-auth');
  if (!bar) return;
  let b = document.getElementById('settings-btn');
  if (!loggedIn) { if (b) b.remove(); return; }
  if (!b) {
    b = document.createElement('button'); b.type = 'button'; b.id = 'settings-btn'; b.className = 'auth-btn settings-btn';
    b.title = 'Settings: language colours, the orthography ↔ IPA table, the dictionary display, the password'; b.textContent = '⚙ Settings';
    b.addEventListener('click', () => window.openSettings());
    const login = bar.querySelector('.login-btn'); bar.insertBefore(b, login || bar.firstChild);
  }
};
})();
