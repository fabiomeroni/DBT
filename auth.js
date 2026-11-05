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
