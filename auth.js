/**
 * auth.js — Shared authentication module for the DBT
 * Included by every page. Provides:
 *   - checkAuth()       — checks session, updates UI
 *   - showLoginModal()  — opens the login modal
 *   - doLogout()        — logs out and updates UI
 *   - isLoggedIn        — current auth state
 *
 * Each page must include a #login-modal, #login-pw, #login-msg,
 * #login-submit, #login-cancel elements, and .auth-btn / .edit-tab
 * elements that this module controls.
 */

'use strict';

let isLoggedIn = false;

/* ── Update all auth-dependent UI ── */
function updateAuthUI() {
  // Auth button(s) in topnav
  document.querySelectorAll('.auth-btn.login-btn').forEach(btn => {
    btn.textContent = isLoggedIn ? '🔓 Author' : '🔒 Author';
    btn.classList.toggle('is-logged-in', isLoggedIn);
  });
  document.querySelectorAll('.auth-btn.logout-btn').forEach(btn => {
    btn.style.display = isLoggedIn ? '' : 'none';
  });
  // Edit tabs — every page shows its own
  document.querySelectorAll('.edit-tab').forEach(el => {
    el.classList.toggle('visible', isLoggedIn);
  });
  backupUI(isLoggedIn);                      // the Backup button and its reminder: the author's, in the top bar of every page
  // Page-specific callback
  if (typeof onAuthChange === 'function') onAuthChange(isLoggedIn);
}

/* ── Check session with Flask ── */
async function checkAuth() {
  try {
    const r = await fetch('/api/auth/status');
    if (!r.ok) return;
    const d = await r.json();
    isLoggedIn = d.logged_in;
  } catch(e) { /* Flask not reachable — view-only mode */ }
  updateAuthUI();
}

/* ── Login ── */
function showLoginModal() {
  const m = document.getElementById('login-modal');
  if (!m) return;
  document.getElementById('login-msg').textContent = '';
  document.getElementById('login-pw').value = '';
  m.classList.add('visible');
  setTimeout(() => document.getElementById('login-pw').focus(), 60);
}

function hideLoginModal() {
  const m = document.getElementById('login-modal');
  if (m) m.classList.remove('visible');
}

async function doLogin() {
  const pw  = document.getElementById('login-pw').value;
  const msg = document.getElementById('login-msg');
  msg.textContent = '';
  msg.className   = 'dbt-modal-msg';
  try {
    const r = await fetch('/api/auth/login', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ password: pw })
    });
    const d = await r.json();
    if (d.ok) {
      isLoggedIn = true;
      hideLoginModal();
      updateAuthUI();
    } else {
      // a wrong password keeps its short message; the other refusals (too many attempts, no password set yet) explain themselves
      msg.textContent = (r.status === 401 || !d.error) ? 'Wrong password.' : d.error;
      msg.className   = 'dbt-modal-msg error';
    }
  } catch(e) {
    msg.textContent = 'Cannot reach server.';
    msg.className   = 'dbt-modal-msg error';
  }
}

/* ── Logout ── */
async function doLogout() {
  try { await fetch('/api/auth/logout', { method: 'POST' }); } catch(e) {}
  isLoggedIn = false;
  updateAuthUI();
}

/* ── Wire up login modal buttons (called after DOM ready) ── */
function bindLoginModal() {
  const submit = document.getElementById('login-submit');
  const cancel = document.getElementById('login-cancel');
  const pw     = document.getElementById('login-pw');
  const modal  = document.getElementById('login-modal');

  if (submit) submit.addEventListener('click', doLogin);
  if (cancel) cancel.addEventListener('click', hideLoginModal);
  if (pw)     pw.addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
  if (modal)  modal.addEventListener('click', e => {
    if (e.target === modal) hideLoginModal();
  });

  // Auth button in topnav
  document.querySelectorAll('.auth-btn.login-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (isLoggedIn) return; // clicking when logged in does nothing; use logout btn
      showLoginModal();
    });
  });
  document.querySelectorAll('.auth-btn.logout-btn').forEach(btn => {
    btn.addEventListener('click', doLogout);
  });
}


/* ── Backup: for the author, a button in the top bar of every page, with the date of the last backup beside it ──
   The button downloads one archive of everything edited in the browser (it lives only on the server). The note beside it counts from that last
   download; clicking it opens the daily snapshots kept on the server, which can be disposed of once they are a month old. */
const bkEsc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const bkAgo = d => d === 0 ? 'today' : d === 1 ? 'yesterday' : d + ' days ago';
const bkSize = b => b < 1024 * 1024 ? Math.max(1, Math.round(b / 1024)) + ' KB' : (b / 1024 / 1024).toFixed(1) + ' MB';

function backupUI(loggedIn) {
  const bar = document.querySelector('.topnav-auth');
  if (!bar) return;
  let box = document.getElementById('backup-box');
  if (!loggedIn) { if (box) box.remove(); const m = document.getElementById('backup-modal'); if (m) m.remove(); return; }
  if (!box) {
    box = document.createElement('div'); box.id = 'backup-box'; box.className = 'backup-box';
    box.innerHTML = '<button type="button" class="auth-btn backup-btn" id="backup-btn" title="Download a backup of everything you have edited (one zip file)">💾 <span class="backup-btn-text">Backup</span></button>' +
                    '<button type="button" class="backup-note" id="backup-note" title="The last backup, and the daily snapshots kept on the server"></button>';
    bar.appendChild(box);
    document.getElementById('backup-btn').addEventListener('click', bkDownload);
    document.getElementById('backup-note').addEventListener('click', bkOpenPanel);
  }
  bkRefresh();
}

function bkDownload() {
  const a = document.createElement('a'); a.href = '/api/backup/download'; a.download = '';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(bkRefresh, 1500);                      // the reminder now counts from this download
}

async function bkRefresh() {
  const note = document.getElementById('backup-note'), btn = document.getElementById('backup-btn');
  if (!note) return;
  try {
    const r = await fetch('/api/backup/status'); if (!r.ok) return;
    const s = await r.json();
    note.textContent = s.lastBackup ? 'last backup: ' + bkAgo(s.daysAgo) : 'no backup yet';
    note.className = 'backup-note ' + s.level; btn.dataset.level = s.level;
    const old = s.snapshots.eligible.count;
    note.title = (s.lastBackup ? 'Downloaded ' + s.lastBackup.replace('T', ' ').slice(0, 16) + (s.changedSince ? '; edited since.' : '; nothing edited since.') : 'You have not downloaded a backup yet.') +
      ' Daily snapshots on the server: ' + s.snapshots.count + ' (' + bkSize(s.snapshots.bytes) + ')' + (old ? ', ' + old + ' a month old or more that you can dispose of' : '') + '. Click for details.';
    window.BACKUP_STATUS = s;
  } catch (e) { /* the note stays as it was */ }
}

async function bkOpenPanel() {
  let m = document.getElementById('backup-modal');
  if (!m) {
    m = document.createElement('div'); m.id = 'backup-modal'; m.className = 'dbt-modal-backdrop';
    m.addEventListener('click', e => { if (e.target === m) bkClosePanel(); });
    document.body.appendChild(m);
  }
  m.innerHTML = '<div class="dbt-modal backup-panel"><h3>Backup</h3><p class="modal-desc">Loading…</p></div>';
  m.classList.add('visible');
  let s, sn;
  try { s = await (await fetch('/api/backup/status')).json(); sn = await (await fetch('/api/backup/snapshots')).json(); }
  catch (e) { m.querySelector('.modal-desc').textContent = 'Could not read the backups: ' + e.message; return; }
  const old = s.snapshots.eligible, days = sn.disposeAfterDays;
  const rows = sn.snapshots.map(x => `<tr><td>${bkEsc(x.date)}</td><td>${bkAgo(x.ageDays)}</td><td>${bkSize(x.bytes)}</td>
      <td><a href="/api/backup/snapshots/${encodeURIComponent(x.name)}" download>download</a></td>
      <td>${x.eligible ? `<button type="button" class="bk-x" data-name="${bkEsc(x.name)}" title="Dispose of this snapshot">🗑</button>` : `<span class="bk-wait" title="A snapshot can be disposed of once it is ${days} days old">after ${days} days</span>`}</td></tr>`).join('');
  m.innerHTML = `<div class="dbt-modal backup-panel">
    <h3>Backup</h3>
    <p class="bk-line"><button type="button" class="modal-btn primary" id="bk-download">💾 Download a backup now</button></p>
    <p class="bk-line">${s.lastBackup ? 'Last backup downloaded <b>' + bkAgo(s.daysAgo) + '</b> (' + bkEsc(s.lastBackup.replace('T', ' ').slice(0, 16)) + '). ' + (s.changedSince ? 'You have edited since.' : 'Nothing has been edited since.') : '<b>You have not downloaded a backup yet.</b>'}</p>
    <p class="modal-desc">The backup is one zip file with everything you edit in the browser (the dictionary, the grammar, the glossary, the references, the texts and their glosses, the images, the settings). Keep it on your own computer: it is what protects you if the server is lost. The archive says inside how to restore it.</p>
    <h4 class="st-h">Daily snapshots, kept on the server</h4>
    <p class="modal-desc">Once a day, when the site is used and something has changed, the server keeps a snapshot of the same kind. A snapshot brings back what a mistake destroyed (an entry deleted, a bad import); it does not survive the loss of the server. Snapshots are never removed by themselves: you can dispose of one once it is ${days} days old.</p>
    ${sn.snapshots.length ? `<table class="imp-table bk-table"><tr><th>day</th><th>age</th><th>size</th><th></th><th></th></tr>${rows}</table>` : '<p class="bk-line"><i>No snapshot yet.</i></p>'}
    <p class="bk-line">${s.snapshots.count} snapshot${s.snapshots.count === 1 ? '' : 's'}, ${bkSize(s.snapshots.bytes)}.
      ${old.count ? `<b>${old.count}</b> ${old.count === 1 ? 'is' : 'are'} ${days} days old or more (${bkSize(old.bytes)}): <button type="button" class="modal-btn" id="bk-dispose-all">Dispose of ${old.count === 1 ? 'it' : 'them'}</button>` : ''}</p>
    <div class="dbt-modal-msg" id="bk-msg"></div>
    <div class="dbt-modal-row"><button type="button" class="modal-btn" id="bk-close">Close</button></div></div>`;
  document.getElementById('bk-close').addEventListener('click', bkClosePanel);
  document.getElementById('bk-download').addEventListener('click', () => { bkDownload(); setTimeout(bkOpenPanel, 1800); });
  const dispose = async (body, what) => {
    if (!confirm(`Dispose of ${what}?\n\nThis cannot be undone.`)) return;
    const r = await (await fetch('/api/backup/snapshots/dispose', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json();
    await bkOpenPanel(); bkRefresh();
    const msg = document.getElementById('bk-msg'); if (msg) { msg.className = 'dbt-modal-msg success'; msg.textContent = r.removed.length + ' snapshot' + (r.removed.length === 1 ? '' : 's') + ' disposed of (' + bkSize(r.freed) + ' freed).'; }
  };
  m.querySelectorAll('.bk-x').forEach(b => b.addEventListener('click', () => dispose({ names: [b.dataset.name] }, 'the snapshot of ' + b.dataset.name.replace(/^daily-|\.zip$/g, ''))));
  const all = document.getElementById('bk-dispose-all');
  if (all) all.addEventListener('click', () => dispose({ eligible: true }, `the ${old.count} snapshot${old.count === 1 ? '' : 's'} that ${old.count === 1 ? 'is' : 'are'} ${days} days old or more (${bkSize(old.bytes)})`));
}
function bkClosePanel() { const m = document.getElementById('backup-modal'); if (m) m.classList.remove('visible'); }
