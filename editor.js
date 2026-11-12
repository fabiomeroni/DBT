/* The Markdown editor shared by the Grammar and the Glossary pages: the same toolbar, the same shortcodes, the same image upload and the same
   Phonological table tab. A page gives the id of the text it edits (the textarea is textarea-<id>, the chart tab pt-<id>) and the names of its
   own functions that cancel and save. */

function insertAtCursor(textarea, text, selectLen) {
  const s = textarea.selectionStart, e = textarea.selectionEnd;
  textarea.value = textarea.value.slice(0, s) + text + textarea.value.slice(e);
  const pos = s + (selectLen !== undefined ? selectLen : text.length);
  textarea.selectionStart = textarea.selectionEnd = pos;
  textarea.focus();
}

const MARKUP = {
  bold:    (sel) => `**${sel || 'bold text'}**`,
  italic:  (sel) => `*${sel || 'italic text'}*`,
  h3:      ()    => '\n### Heading\n',
  table:   ()    => '\n| Column 1 | Column 2 | Column 3 |\n|---|---|---|\n| Cell | Cell | Cell |\n',
  example: ()    => '{{example: negation_example_01}}',
  entry:   ()    => '{{entry: speech}}',
  source:  ()    => '{{source: Author 2020, p. 12}}',
  glossary: (sel) => `{{glossary: ${sel || 'predicate'}}}`,
};

function insertMarkup(id, type) {
  const ta  = document.getElementById('textarea-' + id);
  const sel = ta.value.slice(ta.selectionStart, ta.selectionEnd);
  const fn  = MARKUP[type];
  if (!fn) return;
  insertAtCursor(ta, fn(sel));
}

async function uploadAndInsertImage(id, input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData(); form.append('file', file);
  try {
    const r = await fetch('/api/upload/image', { method: 'POST', body: form });
    const d = await r.json();
    if (d.ok) {
      const ta  = document.getElementById('textarea-' + id);
      const slot = 'Write the caption of the figure here';
      const label = String(d.filename || '').replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^[-_]+|[-_]+$/g, '').slice(0, 40);
      // a figure is an image alone in its paragraph: blank lines on both sides, even when the cursor is at the end of a line of text.
      // The label lets the text refer to the figure: {{ref: label}}
      const md  = `\n\n![${slot}](${d.url})${label ? '{#' + label + '}' : ''}\n\n`;
      const at  = ta.selectionStart + 4;                // inside the brackets, after "\n\n!["
      insertAtCursor(ta, md);
      ta.setSelectionRange(at, at + slot.length);       // the caption is typed over the placeholder
    } else {
      alert('Image upload failed: ' + (d.error || 'Unknown error'));
    }
  } catch(e) { alert('Upload error: ' + e.message); }
  input.value = ''; // reset so same file can be re-selected
}

// ── Referring to a table or a figure: the menu inserts {{ref: label}} ──
async function toggleRefMenu(id, btn) {
  const old = document.getElementById('xref-menu-' + id);
  if (old) { old.remove(); return; }
  let d = { items: [], duplicates: [] };
  try { d = await (await fetch('/api/captions')).json(); } catch (e) { /* an empty menu says so */ }
  const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const menu = document.createElement('div'); menu.id = 'xref-menu-' + id; menu.className = 'xref-menu';
  const dup = new Set((d.duplicates || []).map(x => x.toLowerCase()));
  menu.innerHTML = (d.items.length ? d.items.map(it => it.label
      ? `<button type="button" data-label="${esc(it.label)}"><b>${esc(it.name)}</b> <small>${esc(it.label)}${dup.has(it.label.toLowerCase()) ? ' — used twice' : ''}</small><br>${esc(it.text) || '<small>(no caption)</small>'}</button>`
      : `<div class="xref-none"><b>${esc(it.name)}</b> has no label${esc(it.text) ? ' (' + esc(it.text) + ')' : ''}: a chart has a Label box, a figure ends with {#name}</div>`).join('')
    : '<div class="xref-none">There is no table or figure in the grammar yet.</div>');
  btn.parentElement.appendChild(menu);
  menu.addEventListener('click', ev => {
    const b = ev.target.closest('button[data-label]'); if (!b) return;
    insertAtCursor(document.getElementById('textarea-' + id), '{{ref: ' + b.dataset.label + '}}');
    menu.remove();
  });
  setTimeout(() => document.addEventListener('click', function away(ev) { if (!menu.contains(ev.target) && ev.target !== btn) { menu.remove(); document.removeEventListener('click', away); } }), 0);
}

// ── Referring to an entry of the Glossary: the menu inserts {{glossary: id}} ──
async function toggleGlossMenu(id, btn) {
  const old = document.getElementById('gloss-menu-' + id);
  if (old) { old.remove(); return; }
  let d = { entries: [] };
  try { d = await (await fetch('/api/glossary')).json(); } catch (e) { /* an empty menu says so */ }
  const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const menu = document.createElement('div'); menu.id = 'gloss-menu-' + id; menu.className = 'xref-menu';
  menu.innerHTML = d.entries.length ? d.entries.map(e => `<button type="button" data-id="${esc(e.id)}"><b>${esc(e.term)}</b> <small>${esc(e.id)}</small><br>${esc((e.snippet || '').slice(0, 90))}</button>`).join('')
                                    : '<div class="xref-none">The Glossary has no entry yet.</div>';
  btn.parentElement.appendChild(menu);
  menu.addEventListener('click', ev => {
    const b = ev.target.closest('button[data-id]'); if (!b) return;
    insertAtCursor(document.getElementById('textarea-' + id), '{{glossary: ' + b.dataset.id + '}}');
    menu.remove();
  });
  setTimeout(() => document.addEventListener('click', function away(ev) { if (!menu.contains(ev.target) && ev.target !== btn) { menu.remove(); document.removeEventListener('click', away); } }), 0);
}

// The editor of a text, as a block to put in the page: o = { onCancel: 'cancelEdit', onSave: 'saveSection', saveLabel: 'Save &amp; render' }
function mdEditorHTML(id, o) {
  return `
    <div class="md-editor-wrap" id="editor-${id}">
      <div class="ed-tabs" role="tablist">
        <button type="button" class="ed-tab active" data-tab="text" role="tab">Text</button>
        <button type="button" class="ed-tab" data-tab="phono" role="tab" title="Make a chart of the consonants or of the vowels, without writing markup">Phonological table</button>
      </div>
      <div class="ed-pane" data-pane="text">
      <div class="editor-toolbar">
        <span style="font-family:'Crimson Pro',serif;font-size:0.75rem;
                     letter-spacing:0.08em;text-transform:uppercase;
                     color:var(--ink-light);margin-right:0.3rem;">Insert</span>
        <button class="editor-toolbar-btn" onclick="insertMarkup('${id}','bold')"
                title="Bold"><b>B</b></button>
        <button class="editor-toolbar-btn" onclick="insertMarkup('${id}','italic')"
                title="Italic"><i>I</i></button>
        <div class="editor-toolbar-sep"></div>
        <button class="editor-toolbar-btn" onclick="insertMarkup('${id}','h3')"
                title="Subheading">H3</button>
        <button class="editor-toolbar-btn" onclick="insertMarkup('${id}','table')"
                title="Table skeleton">⊞ Table</button>
        <div class="editor-toolbar-sep"></div>
        <span style="position:relative;display:inline-block;"><button class="editor-toolbar-btn" onclick="toggleRefMenu('${id}', this)"
                title="Refer to a table or a figure of the grammar: inserts {{ref: label}}">🔗 Reference</button></span>
        <span style="position:relative;display:inline-block;"><button class="editor-toolbar-btn" onclick="toggleGlossMenu('${id}', this)"
                title="Refer to an entry of the Glossary: inserts {{glossary: id}}">📖 Glossary</button></span>
        <div class="editor-toolbar-sep"></div>
        <label class="editor-toolbar-btn" title="Upload and insert image" style="cursor:pointer;">
          📷 Image
          <input type="file" accept="image/*" style="display:none;"
                 onchange="uploadAndInsertImage('${id}', this)">
        </label>
        <div class="editor-toolbar-sep"></div>
        <button class="editor-toolbar-btn" onclick="insertMarkup('${id}','example')"
                title="Example shortcode">{{example}}</button>
        <button class="editor-toolbar-btn" onclick="insertMarkup('${id}','entry')"
                title="Entry shortcode">{{entry}}</button>
        <button class="editor-toolbar-btn" onclick="insertMarkup('${id}','source')"
                title="Cite a reference (see the References page)">{{source}}</button>
      </div>
      <textarea id="textarea-${id}" spellcheck="false"
                style="border-radius:0 0 4px 4px;"></textarea>
      <div class="shortcode-ref">
        <strong>Shortcodes:</strong>
        <ul>
          <li><code>{{example: ID}}</code> — numbered example from "Examples from papers"</li>
          <li><code>{{entry: ID}}</code> — inline word chip from dictionary XML</li>
          <li><code>{{source: Author 2020}}</code> — cite a reference: (Author, 2020). Add <code>, p. 12</code> for a page, <code>, narrative</code> for Author (2020), or cite several with <code>;</code>. The reference's key works too</li>
          <li><code>![the caption](images/file.jpg)</code> — uploaded image. On a line of its own it is a <b>figure</b>: the caption you write between the brackets goes below it as “Figure 3 – …”, the number being automatic through the whole grammar (an image in the middle of a line of text has no caption). Charts made in the Phonological table tab are numbered as tables, above. To be able to refer to a figure, give it a label after the image: <code>![the caption](images/map.png){#map}</code> (a chart has a Label box).</li>
        <li><code>{{glossary: id}}</code> — a link to an entry of the <b>Glossary</b>, reading as its term, with its definition as a tooltip; <code>{{glossary: id | the text shown}}</code> shows your own words. The 📖 Glossary button lists the entries.</li>
        <li><code>{{ref: label}}</code> — a link that reads “Table 2” or “Figure 3”, with the number it has now (<code>{{ref: a, b}}</code> for several). The 🔗 Reference button lists what can be referred to. It works in the dictionary too.</li>
        </ul>
        <li><code>{{cite: file.xml#sentId}}</code> — numbered example from a transcribed narrative</li>
          <li><code>{{cite: fieldnotes#0#d01.Road:01}}</code> — numbered example from fieldnotes</li>
          <li><code>{{cite: papers#negation_example_01}}</code> — numbered example from "Examples from papers"</li>
        </ul>
        Markdown: <code>**bold**</code>, <code>*italic*</code>,
        <code>### heading</code>, <code>| col | col |</code> tables.<br>
        Charts of the consonants and of the vowels are made in the <b>Phonological table</b> tab (they appear here as a <code>&#96;&#96;&#96;phonotable</code> block: leave it to the tab).
      </div>
      </div>
      <div class="ed-pane" data-pane="phono" hidden><div class="pt-root" id="pt-${id}"></div></div>
      <div style="display:flex;gap:0.5rem;justify-content:flex-end;">
        <button class="modal-btn" onclick="${o.onCancel}('${id}')">Cancel</button>
        <button class="modal-btn primary" onclick="${o.onSave}('${id}')">${o.saveLabel}</button>
      </div>
    </div>`;
}
