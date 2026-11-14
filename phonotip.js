/*
 * The box that opens when the reader hovers over a sound in a phonological chart (see phonotable.py): the sound, its description (place and
 * manner of articulation, as the author typed it), a button that plays it (audio_icon.svg) and a link to PHOIBLE (phoible_logo.png).
 * It works for any chart in the page, as soon as it is there. The box stays open while the pointer is over it (so the buttons can be reached),
 * closes with Escape or when the page scrolls, and opens on a tap on a touch screen. A button that has nothing behind it (no audio file, no
 * link yet) is shown dimmed and does nothing. Everything the author typed is put in the box as text, never as markup.
 */
(() => {
  let box = null, owner = null, timer = null, audio = null;
  const SEG = '.phonotable .ph-seg';

  function build() {
    box = document.createElement('div');
    box.id = 'phono-tip'; box.setAttribute('role', 'tooltip'); box.hidden = true;
    box.innerHTML = '<div class="pt-head"><span class="pt-sound"></span><span class="pt-btns"></span></div><div class="pt-desc"></div>';
    document.body.appendChild(box);
    box.addEventListener('mouseenter', () => clearTimeout(timer));
    box.addEventListener('mouseleave', () => hideSoon());
    box.addEventListener('click', ev => {
      const b = ev.target.closest('button.pt-audio');
      if (b && !b.classList.contains('off')) { ev.preventDefault(); play(b.dataset.src); }
      const a = ev.target.closest('a.pt-phoible');
      if (a && a.classList.contains('off')) ev.preventDefault();
    });
  }
  function play(src) {
    try { if (audio) audio.pause(); audio = new Audio(src); const p = audio.play(); if (p && p.catch) p.catch(() => {}); } catch (e) { /* no sound: nothing to do */ }
  }
  function icon(src, alt, fallback) {
    const img = document.createElement('img');
    img.className = 'pt-icon'; img.src = src; img.alt = alt;
    img.addEventListener('error', () => { const s = document.createElement('span'); s.className = 'pt-icon-fallback'; s.textContent = fallback; img.replaceWith(s); });
    return img;
  }
  function show(el) {
    if (!box) build();
    clearTimeout(timer);
    owner = el;
    box.querySelector('.pt-sound').textContent = el.dataset.seg || el.textContent;
    const d = box.querySelector('.pt-desc'), desc = (el.dataset.desc || '').trim();
    d.textContent = desc || 'No description yet.'; d.classList.toggle('empty', !desc);
    const btns = box.querySelector('.pt-btns'); btns.textContent = '';
    const src = el.dataset.audio || '', link = el.dataset.phoible || '';
    const a = document.createElement('button');
    a.type = 'button'; a.className = 'pt-audio' + (src ? '' : ' off'); a.dataset.src = src; a.title = src ? 'Listen' : 'No recording yet';
    a.setAttribute('aria-label', 'Play the sound'); if (!src) a.setAttribute('aria-disabled', 'true');
    a.appendChild(icon('audio_icon.svg', '', '🔊'));
    const p = document.createElement('a');
    p.className = 'pt-phoible' + (link ? '' : ' off'); p.title = link ? 'See it in PHOIBLE' : 'No PHOIBLE link yet';
    p.setAttribute('aria-label', 'See the sound in PHOIBLE');
    if (link) { p.href = link; p.target = '_blank'; p.rel = 'noopener noreferrer'; } else p.setAttribute('aria-disabled', 'true');
    p.appendChild(icon('phoible_logo.png', 'PHOIBLE', 'PHOIBLE'));
    btns.append(a, p);
    box.hidden = false;
    const r = el.getBoundingClientRect(), w = box.offsetWidth, h = box.offsetHeight;
    let x = Math.max(6, Math.min(r.left + r.width / 2 - w / 2, document.documentElement.clientWidth - w - 6));
    let y = r.top - h - 6; if (y < 6) y = r.bottom + 6;
    box.style.left = (x + window.scrollX) + 'px'; box.style.top = (y + window.scrollY) + 'px';
  }
  function hide() { clearTimeout(timer); if (box) box.hidden = true; owner = null; }
  function hideSoon() { clearTimeout(timer); timer = setTimeout(hide, 220); }

  document.addEventListener('mouseover', ev => {
    const el = ev.target.closest && ev.target.closest(SEG);
    if (el) { if (el !== owner || (box && box.hidden)) show(el); else clearTimeout(timer); }
  });
  document.addEventListener('mouseout', ev => {
    const el = ev.target.closest && ev.target.closest(SEG);
    if (el && !(ev.relatedTarget && box && box.contains(ev.relatedTarget))) hideSoon();
  });
  document.addEventListener('click', ev => {                       // a tap (no hover on a touch screen) opens it; a tap elsewhere closes it
    const el = ev.target.closest && ev.target.closest(SEG);
    if (el) { if (owner === el && box && !box.hidden && ev.detail === 0) hide(); else show(el); }
    else if (box && !box.hidden && !box.contains(ev.target)) hide();
  });
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape') hide(); });
  document.addEventListener('focusin', ev => { const el = ev.target.closest && ev.target.closest(SEG); if (el) show(el); });
  window.addEventListener('scroll', hide, { passive: true });
  const makeFocusable = () => document.querySelectorAll(SEG).forEach(s => { if (!s.hasAttribute('tabindex')) s.tabIndex = 0; });
  makeFocusable(); new MutationObserver(makeFocusable).observe(document.body, { childList: true, subtree: true });
})();
