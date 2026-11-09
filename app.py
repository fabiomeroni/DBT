"""
Digital Boasian Trilogy: a comparative dictionary, grammar and text corpus for a language or a group of languages.
Everything specific to one project (its languages, titles and files) is read from project/project.json.
Flask backend: auth · XML upload · grammar rendering · shortcode resolution
Run: python app.py   (then open http://localhost:5000)
"""

import os
import re
import sys
import json
import unicodedata
import html as _html
from html import escape as _esc
from flask import Flask, request, jsonify, session, send_from_directory, abort, Response, redirect
from lxml import etree
import markdown as md_lib

import security
import references as refs_lib
import concordance as conc

# python app.py --set-password : store the author's password (hashed, in instance/) and stop
if __name__ == '__main__' and '--set-password' in sys.argv:
    security.cli_set_password()
    sys.exit(0)

# ── App setup ──────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)      # static files are served by static_files() below, which restricts them
app.secret_key = security.secret_key()          # random, kept in instance/ (never in the code)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

# ── The project: everything specific to one language or group of languages ────
# project/project.json holds the project's name, its languages (code, name, abbreviation, colour and the other
# codes texts use for them), the wording of the pages, and where its data files are. It is read once, at start-up.
PROJECT_PATH = os.path.join('project', 'project.json')
# Without a project file this DBT has not been set up yet: the site only offers the first-run setup page (/setup),
# and a placeholder project keeps the rest of the code happy until the real one is written.
SETUP_MODE = not os.path.exists(PROJECT_PATH)

def _load_project():
    def fail(msg):
        raise SystemExit(f"{PROJECT_PATH}: {msg}")
    if SETUP_MODE:
        p = {'name': 'DBT', 'languages': [{'code': 'aaa', 'name': 'Language', 'abbr': 'Lng', 'color': '#8a5f18'}]}
    else:
        try:
            with open(PROJECT_PATH, encoding='utf-8') as f:
                p = json.load(f)
        except ValueError as e:
            fail(f"is not valid JSON ({e})")
    langs = p.get('languages')
    if not isinstance(langs, list) or not langs:
        fail('needs a non-empty "languages" list.')
    seen = set()
    for l in langs:
        code = str(l.get('code', '')).strip()
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,11}', code):
            fail(f'language code "{code}" must be lower case letters, digits, - or _ (e.g. "num").')
        if code in seen:
            fail(f'language code "{code}" is used twice.')
        seen.add(code)
        l['code'] = code
        l['name'] = str(l.get('name') or code)
        l['abbr'] = str(l.get('abbr') or l['name'][:3])
        col = str(l.get('color') or '')
        l['color'] = col.lower() if re.fullmatch(r'#[0-9a-fA-F]{6}', col) else '#888888'
        l['aliases'] = [str(x) for x in (l.get('aliases') or [])]
    p['name'] = str(p.get('name') or 'DBT')
    p.setdefault('titleSuffix', p['name'])
    p.setdefault('homeTitle', p['name'])
    p['nav'] = p.get('nav') or {}
    p['recordings'] = p.get('recordings') or {}
    p['latex'] = p.get('latex') or {}
    p['footer'] = str(p.get('footer') or '')
    p['redirects'] = p.get('redirects') or {}
    p['legacyFiles'] = p.get('legacyFiles') or {}
    p['grammaticalDomains'] = [str(x) for x in (p.get('grammaticalDomains') or ['Grammar'])]
    p['headwordLanguage'] = p.get('headwordLanguage') if p.get('headwordLanguage') in seen else langs[0]['code']
    files = {'dictionary': 'project/dictionary.xml', 'fieldnotes': 'project/fieldnotes.xml',
             'grammarDir': 'project/grammar', 'recordingsDir': 'project/texts', 'imagesDir': 'project/images',
             'orthography': 'project/orthography.json', 'seedPhonetic': 'project/seed-phonetic-forms.json',
             'pagesDir': 'project/pages', 'references': 'project/references.json'}
    files.update(p.get('files') or {})
    p['files'] = files
    return p

PROJECT = _load_project()

UPLOAD_FOLDER  = 'uploads'
GRAMMAR_FOLDER = PROJECT['files']['grammarDir']

DICT_FILE             = PROJECT['files']['dictionary']
REFERENCES_FILE       = PROJECT['files']['references']
GRAMMATICAL_DOMAINS   = {d.strip().lower() for d in PROJECT['grammaticalDomains']}
FIELDNOTES_FILE       = PROJECT['files']['fieldnotes']
IMAGES_FOLDER         = PROJECT['files']['imagesDir']
TRANSCRIPTIONS_FOLDER = PROJECT['files']['recordingsDir']
GLOSSES_FOLDER        = os.path.join(TRANSCRIPTIONS_FOLDER, 'glosses')
TRANSCRIPTIONS_INDEX  = os.path.join(TRANSCRIPTIONS_FOLDER, 'index.json')

# ── Moving a project's data into the project folder (once) ──────────────────────
# Before the data lived in the site's root (dbt_dictionary.xml, grammar_content/, transcribed_narratives/ ...).
# project.json lists those old locations in "legacyFiles", next to the "files" they became. The first time the
# server starts and finds one of them, it moves the data into the project folder:
#   1. a full copy of every old location goes to uploads/backups/legacy-layout-<date>/
#   2. the old data is copied into the project folder; the LIVE (old) version wins over a shipped copy
#   3. every file is checked (size) in its new place
#   4. only then are the old locations removed
# If anything fails, the server stops with a message and nothing has been deleted. It happens once, recorded in
# uploads/layout-migrated.json, so an old file that reappears later (e.g. through git) can never overwrite live data.
def _migrate_legacy_layout():
    import shutil, time
    legacy = PROJECT.get('legacyFiles') or {}
    marker = os.path.join(UPLOAD_FOLDER, 'layout-migrated.json')
    if SETUP_MODE or not legacy or os.path.exists(marker):
        return
    todo = [(old, PROJECT['files'][key]) for key, old in legacy.items()
            if key in PROJECT['files'] and old and os.path.normpath(old) != os.path.normpath(PROJECT['files'][key]) and os.path.exists(old)]
    if not todo:
        return
    backup = os.path.join(UPLOAD_FOLDER, 'backups', 'legacy-layout-' + time.strftime('%Y%m%d-%H%M%S'))
    def copy(src, dst):
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
            shutil.copy2(src, dst)
    def files_of(path):
        if os.path.isdir(path):
            return [os.path.relpath(os.path.join(d, f), path) for d, _, fs in os.walk(path) for f in fs]
        return ['']
    try:
        for old, new in todo:
            copy(old, os.path.join(backup, old))                    # 1. a safe copy of what was there
        for old, new in todo:
            copy(old, new)                                          # 2. into the project folder, live version winning
        for old, new in todo:                                       # 3. every file arrived whole
            for rel in files_of(old):
                src, dst = os.path.join(old, rel) if rel else old, os.path.join(new, rel) if rel else new
                if not os.path.exists(dst) or os.path.getsize(src) != os.path.getsize(dst):
                    raise RuntimeError(f'{dst} did not arrive whole')
        for old, new in todo:                                       # 4. only now remove the old locations
            shutil.rmtree(old) if os.path.isdir(old) else os.remove(old)
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        with open(marker, 'w', encoding='utf-8') as f:
            json.dump({'movedAt': time.strftime('%Y-%m-%d %H:%M:%S'), 'backup': backup,
                       'moved': [{'from': o, 'to': n} for o, n in todo]}, f, indent=1)
    except Exception as e:
        raise SystemExit(f"\nCould not move the data into the project folder: {e}\n"
                         f"Nothing has been deleted. A copy of the old data is in {backup} (if it got that far).\n")
    print("\n  Your data now lives in the project folder:")
    for old, new in todo:
        print(f"    {old}  ->  {new}")
    print(f"  A backup of the old locations is in {backup}\n", flush=True)

_migrate_legacy_layout()

os.makedirs(UPLOAD_FOLDER,         exist_ok=True)
os.makedirs(GRAMMAR_FOLDER,        exist_ok=True)
os.makedirs(IMAGES_FOLDER,         exist_ok=True)
os.makedirs(TRANSCRIPTIONS_FOLDER, exist_ok=True)
os.makedirs(GLOSSES_FOLDER,        exist_ok=True)

# ── Language tables, all derived from the project's language list ──────────────
_LANGS      = PROJECT['languages']
LANG_NAMES      = [l['name'] for l in _LANGS]                      # names, in the project's order
LANG_CODES  = [l['code'] for l in _LANGS]
LANG_MAP    = dict(zip(LANG_CODES, LANG_NAMES))
LANG_ABBR   = {l['name']: l['abbr'] for l in _LANGS}
_DEFAULT_COLORS = {l['code']: l['color'] for l in _LANGS}      # the Settings can override them
_COLOR_NAMES   = {l['code']: l['name'] for l in _LANGS}
# every code a text may use for a language (its own code, plus the other codes such as ISO 639-3 / Pangloss)
_LANG_FROM_CODE  = {c: l['name'] for l in _LANGS for c in [l['code']] + l['aliases']}
_TX_LANG_TO_CODE = {c: l['code'] for l in _LANGS for c in [l['code']] + l['aliases']}
_FN_LANGS   = [(l['code'], l['abbr'], l['name']) for l in _LANGS]
# language whose form seeds the id of a new dictionary entry (then the others, in the project's order)
_ID_ORDER   = [PROJECT['headwordLanguage']] + [c for c in LANG_CODES if c != PROJECT['headwordLanguage']]

class _LiveColors(dict):
    """LANG_COLORS[name] -> the colour the author chose in the Settings for that language (read at each use)."""
    def _cur(self):
        return {_COLOR_NAMES[k]: v for k, v in _colors_current().items()}
    def __getitem__(self, k): return self._cur()[k]
    def get(self, k, default=None): return self._cur().get(k, default)
    def __contains__(self, k): return k in self._cur()

LANG_COLORS = _LiveColors()

# ══════════════════════════════════════════════════════════════
#  XML HELPERS
# ══════════════════════════════════════════════════════════════

def _load_xml(upload_name, fallback):
    """Load XML from uploads/ folder, falling back to project root."""
    primary = os.path.join(UPLOAD_FOLDER, upload_name)
    path = primary if os.path.exists(primary) else fallback
    if not os.path.exists(path):
        return None
    try:
        return etree.parse(path)
    except etree.XMLSyntaxError:
        return None

def get_dict_xml():
    return _load_xml('dictionary.xml', DICT_FILE)

def get_fieldnotes_xml():
    return _load_xml('fieldnotes.xml', FIELDNOTES_FILE)

# ══════════════════════════════════════════════════════════════

# ── Citation builders ─────────────────────────────────────────

def _stored_tokens(g, code):
    """The tokens of a recording's saved alignment: {code: [...]} (shared with fieldwork texts) or the older plain list."""
    t = g.get('tokens') if isinstance(g, dict) else None
    if isinstance(t, list):
        return t
    if isinstance(t, dict):
        return t[code] if code in t else next(iter(t.values()), [])
    return []

def _tokenize_form(form):
    """Python mirror of the JS tokenizeForm() in transcription.html.
    Splits on whitespace then on morpheme boundaries (- and =),
    keeping the marker with the left fragment and stripping trailing punctuation."""
    if not form or form == '—':
        return []
    tokens = []
    for word in form.strip().split():
        clean = re.sub(r'[.,;!?]+$', '', word)
        if not clean:
            continue
        if '-' not in clean and '=' not in clean:
            tokens.append(clean)
            continue
        parts = re.split(r'([-=])', clean)
        current = ''
        frags   = []
        for p in parts:
            if p in ('-', '='):
                current += p
                frags.append(current)
                current = ''
            else:
                current = p
        if current:
            frags.append(current)
        tokens.extend(f for f in frags if f)
    return tokens

def _load_stored_glosses(key):
    p = _gloss_path(key)
    if not os.path.exists(p):
        return {}
    with open(p, encoding='utf-8') as f:
        content = f.read().strip()
    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # File may have extra data (two objects concatenated after interrupted save).
        # raw_decode parses the first valid JSON value and ignores the rest.
        try:
            obj, _ = json.JSONDecoder().raw_decode(content)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        return {}

def _cite_ilg_table(words, stored_gloss, lang_code='', form=''):
    """Word-aligned interlinear table from _parse_tx words + stored gloss. `form` is the whole sentence, shown
    when the sentence has no word-by-word glosses (yet)."""
    if words and any(w.get('gloss') for w in words):
        fc = ''.join(f'<td class="cite-form-cell" data-lang="{lang_code}" data-form="{w["form"]}">{w["form"]}</td>' for w in words)
        gc = ''.join(f'<td class="cite-gloss-cell">{w["gloss"] or ""}</td>' for w in words)
        return f'<table class="cite-ilg-table"><tr>{fc}</tr><tr class="cite-gloss-row">{gc}</tr></table>'
    elif isinstance(stored_gloss, str) and stored_gloss:
        form = words[0]['form'] if words else form
        return (f'<table class="cite-ilg-table">'
                f'<tr><td class="cite-form-cell">{form}</td></tr>'
                f'<tr class="cite-gloss-row"><td class="cite-gloss-cell">{stored_gloss}</td></tr>'
                f'</table>')
    else:
        form = words[0]['form'] if words else form
        return f'<table class="cite-ilg-table"><tr><td class="cite-form-cell">{form}</td></tr></table>'

def build_narrative_citation(filename, sent_id, n):
    path = os.path.join(TRANSCRIPTIONS_FOLDER, filename)
    if not os.path.exists(path):
        return f'<span class="shortcode-error">Transcription not found: {filename}</span>'
    try:
        data = _parse_tx(path)
    except Exception as e:
        return f'<span class="shortcode-error">Parse error in {filename}: {e}</span>'
    sent = next((s for s in data['sentences'] if s['id'] == sent_id), None)
    if not sent:
        return f'<span class="shortcode-error">Sentence {sent_id} not found in {filename}</span>'
    stored_glosses = _load_stored_glosses(filename)
    stored   = stored_glosses.get(sent_id)
    lang_code = data.get('lang', '')
    lang_name = _LANG_FROM_CODE.get(lang_code, lang_code)
    color     = LANG_COLORS.get(lang_name, '#8a5f18')
    credit    = ' '.join(x for x in (PROJECT['recordings'].get('author'), PROJECT['recordings'].get('year')) if x)
    ref       = ' · '.join(x for x in (lang_name, filename[:-4], sent_id, credit) if x)
    if isinstance(stored, dict) and stored.get('tokens'):          # glossed and aligned in the viewer
        code = _TX_LANG_TO_CODE.get(lang_code) or lang_code
        toks = _stored_tokens(stored, code)
        transl = stored.get('translation') if stored.get('translation') is not None else sent['transl']
        abbr = next((x[1] for x in _FN_LANGS if x[0] == code), str(code).upper())
        return _cite_fn_table({code: toks}, stored.get('glosses', []), len(toks), transl, ref, n,
                              langs=[(code, abbr, lang_name)], show_abbr=False)
    ilg       = _cite_ilg_table(sent.get('words', []), stored, lang_code, form=sent['form'])
    return (f'<div class="grammar-cite">'
            f'<span class="cite-n">({n})</span>'
            f'<div class="cite-body">'
            f'<div class="cite-ilg" style="--cite-color:{color};">{ilg}</div>'
            f'<div class="cite-transl">‘{sent["transl"]}’</div>'
            f'<div class="cite-ref">[{ref}]</div>'
            f'</div></div>')

def build_fieldnotes_citation(group_index, sent_id, n):
    xml = get_fieldnotes_xml()
    if xml is None:
        return '<span class="shortcode-error">No fieldnotes XML loaded</span>'
    tgs = xml.findall('.//tiGroup')
    if group_index < 0 or group_index >= len(tgs):
        return f'<span class="shortcode-error">Fieldnotes group {group_index} not found</span>'
    tg  = tgs[group_index]
    ti  = (tg.findtext('ti') or '').strip()
    rfg = next((r for r in tg.findall('rfGroup')
                if (r.findtext('rf') or '').strip() == sent_id), None)
    if rfg is None:
        return f'<span class="shortcode-error">{sent_id} not found in fieldnotes group {group_index}</span>'
    grp    = rfg.find('bslGroup') or rfg.find('frGroup')
    prompt = (grp.findtext('bsl') or grp.findtext('fr') or '').strip() if grp else ''
    raw = {}
    for code, abbr, name in _FN_LANGS:
        nodes = grp.findall(code) if grp else []
        vals  = [nd.text.strip() for nd in nodes if nd.text and nd.text.strip()]
        raw[code] = ' '.join(vals) if vals else '—'
    stored_glosses = _load_stored_glosses(f'fieldnotes_{group_index}')
    stored         = stored_glosses.get(sent_id)
    if stored and isinstance(stored, dict) and stored.get('tokens'):
        tokens      = stored['tokens']
        col_glosses = stored.get('glosses', [])
        n_cols      = max((len(tokens.get(c, [])) for c, _, _ in _FN_LANGS), default=0)
    else:
        tokens = {}; n_cols = 0
        for code, _, _ in _FN_LANGS:
            toks = _tokenize_form(raw[code]) if raw[code] != '—' else []
            tokens[code] = toks; n_cols = max(n_cols, len(toks))
        col_glosses = [''] * n_cols
        for code, _, _ in _FN_LANGS:
            while len(tokens[code]) < n_cols: tokens[code].append('')
    # Prefer author-stored translation; fall back to Bislama prompt
    display_transl = (
        stored.get('translation')
        if stored and isinstance(stored, dict) and stored.get('translation') is not None
        else prompt
    )
    return _cite_fn_table(tokens, col_glosses, n_cols, display_transl,
                          f'Fieldnotes \u00b7 {ti} \u00b7 {sent_id}', n)


# ── "Examples from papers": a text made of the <Example>s of the corpus XML ──────────
# Shown and cited exactly like a fieldwork text (aligned columns, glosses, translation),
# but with its own gloss store (glosses/papers_0.json) so fieldnotes glosses are never touched.
PAPERS_TITLE = 'Examples from papers'

def _root_tag(path):
    """Root element name, read without parsing the whole file (or fetching its DTD)."""
    try:
        for _ev, el in etree.iterparse(path, events=('start',), load_dtd=False,
                                       no_network=True, resolve_entities=False):
            return el.tag
    except Exception:
        return None

def _is_examples_file(path):
    return _root_tag(path) == 'Examples'

def _paper_examples():
    """Every <Example> of the files in transcribed_narratives/ whose root is <Examples>."""
    out, seen = [], set()
    for fn in sorted(os.listdir(TRANSCRIPTIONS_FOLDER)):
        path = os.path.join(TRANSCRIPTIONS_FOLDER, fn)
        if not fn.endswith('.xml') or not _is_examples_file(path):
            continue
        try:
            root = etree.parse(path, _XML_PARSER).getroot()
        except Exception:
            continue
        for ex in root.findall('.//Example'):
            if ex.get('id') not in seen:          # ids are unique; the first one wins
                seen.add(ex.get('id'))
                out.append(ex)
    return out

def _paper_example(example_id):
    return next((e for e in _paper_examples() if e.get('id') == example_id), None)

def _paper_tokens(ex):
    """{lang code: [token, ...]} from an <Example>'s tiers ('—' = no word in that language)."""
    out = {}
    for code, _abbr, _name in _FN_LANGS:
        tier = ex.find(f'Tier[@lang="{code}"]')
        toks = tier.text.split() if tier is not None and tier.text else []
        out[code] = ['' if t == '\u2014' else t for t in toks]
    return out

def _paper_defaults(ex):
    """Alignment + glosses exactly as published; used until the author edits them."""
    tokens  = _paper_tokens(ex)
    glosses = (ex.findtext('Glosses') or '').split()
    n = max([len(glosses)] + [len(v) for v in tokens.values()])
    for c in tokens:
        tokens[c] += [''] * (n - len(tokens[c]))
    return {'tokens': tokens, 'glosses': glosses + [''] * (n - len(glosses))}

def _paper_link_map(ex):
    """(lang code, cleaned form) -> dictionary entry id, from the example's <TokenLinks>.
    Keyed by form rather than column, so the links survive a re-alignment by the author."""
    toks, links = _paper_tokens(ex), {}
    for tk in ex.findall('TokenLinks/Token'):
        idx, did = tk.get('index', ''), tk.get('dictId', '')
        if idx.isdigit() and did:
            for code in toks:
                t = toks[code][int(idx)] if int(idx) < len(toks[code]) else ''
                if t:
                    links[(code, _clean_form(t))] = did
    return links

def _paper_state(ex):
    """(tokens, column glosses, n columns, translation) to display for an example."""
    stored = _load_stored_glosses('papers_0').get(ex.get('id'))
    d = _paper_defaults(ex)
    if isinstance(stored, dict) and isinstance(stored.get('tokens'), dict):
        tokens, glosses = stored['tokens'], stored.get('glosses', [])
    else:
        tokens, glosses = d['tokens'], d['glosses']
    n_cols = max((len(tokens.get(c, [])) for c, _, _ in _FN_LANGS), default=0)
    transl = (stored.get('translation') if isinstance(stored, dict) and stored.get('translation') is not None
              else (ex.findtext('Translation[@lang="eng"]') or '').strip())
    return tokens, glosses, n_cols, transl

def _cite_fn_table(tokens, col_glosses, n_cols, transl, ref, n, dict_links=None, langs=None, show_abbr=None):
    """Numbered example: the forms in each language, gloss line, translation, reference.
    Each form carries data-lang / data-form / data-gloss so the page can link it to the
    dictionary (only where the gloss agrees); words with a known entry also carry data-dict-id."""
    dict_links = dict_links or {}
    if show_abbr is None:
        show_abbr = len(langs or _FN_LANGS) > 1          # one language: no label in front of its row
    lang_rows = ''
    for code, abbr, name in (langs or _FN_LANGS):
        color = LANG_COLORS.get(name, '#888')
        toks, cells = tokens.get(code, []), ''
        for i in range(n_cols):
            tok   = toks[i] if i < len(toks) else ''
            gl    = col_glosses[i] if i < len(col_glosses) else ''
            shown = tok or '\u2014'
            link  = dict_links.get((code, _clean_form(tok))) if tok else None
            attrs = (f' data-lang="{code}" data-form="{_esc(shown)}" data-gloss="{_esc(gl)}"'
                     + (f' data-dict-id="{_esc(link)}"' if link else ''))
            cells += f'<td class="cite-fn-form" style="color:{color};"{attrs}>{_esc(shown)}</td>'
        lang_rows += f'<tr><td class="cite-fn-abbr" style="color:{color};">{abbr if show_abbr else ""}</td>{cells}</tr>'
    sep    = '<td></td>' * (n_cols + 1)
    gcells = ''.join(f'<td class="cite-fn-gloss">{_esc(col_glosses[i]) if i < len(col_glosses) else ""}</td>'
                     for i in range(n_cols))
    return (f'<div class="grammar-cite">'
            f'<span class="cite-n">({n})</span>'
            f'<div class="cite-body">'
            f'<div class="cite-ilg"><table class="cite-fn-table">{lang_rows}'
            f'<tr class="cite-fn-sep">{sep}</tr>'
            f'<tr><td></td>{gcells}</tr></table></div>'
            f'<div class="cite-transl">\u2018{_esc(transl)}\u2019</div>'
            f'<div class="cite-ref">[{_esc(ref)}]</div>'
            f'</div></div>')

def build_papers_citation(example_id, n):
    """{{cite: papers#ID}} - an example from the "Examples from papers" text."""
    ex = _paper_example(example_id)
    if ex is None:
        return f'<span class="shortcode-error">Example not found in "{PAPERS_TITLE}": {_esc(example_id)}</span>'
    tokens, glosses, n_cols, transl = _paper_state(ex)
    label = (ex.findtext('Label') or '').strip()
    ref   = f'{PAPERS_TITLE} \u00b7 {label}' if label else f'{PAPERS_TITLE} \u00b7 {example_id}'
    return _cite_fn_table(tokens, glosses, n_cols, transl, ref, n, _paper_link_map(ex))

def build_citation(spec, n):
    """Dispatch {{cite: spec}} — all exceptions become inline error spans, never HTML."""
    try:
        if spec.startswith('papers#'):
            return build_papers_citation(spec.split('#', 1)[1].strip(), n)
        if spec.startswith('fieldnotes#'):
            parts = spec.split('#', 2)
            if len(parts) < 3:
                return f'<span class="shortcode-error">Invalid fieldnotes cite: {spec}</span>'
            try:
                idx = int(parts[1])
            except ValueError:
                return f'<span class="shortcode-error">Bad group index: {parts[1]}</span>'
            return build_fieldnotes_citation(idx, parts[2].strip(), n)
        elif '#' in spec:
            filename, sent_id = spec.split('#', 1)
            return build_narrative_citation(filename.strip(), sent_id.strip(), n)
        return f'<span class="shortcode-error">Invalid cite spec: {spec}</span>'
    except Exception as e:
        import traceback as _tb
        return (f'<details class="shortcode-error">'
                f'<summary>Citation error: {e}</summary>'
                f'<pre>{_tb.format_exc()}</pre></details>')

#  SHORTCODE RESOLVERS
# ══════════════════════════════════════════════════════════════

def build_example_table(ex_id, n=None):
    """
    Resolve {{example: ID}} — builds a numbered interlinear example
    from the corpus XML: "(n)  <source label>", the aligned forms, the gloss line
    and the translation. Each language row carries data-lang="…" so the client-side
    language-toggle pills can show/hide rows without a round-trip.
    Words that have no explicit <TokenLinks> entry still carry data-lang / data-form /
    data-gloss, so the page can link them to the dictionary - but only where the
    gloss agrees with the dictionary entry (so a homophone is not linked wrongly).
    """
    ex = _paper_example(ex_id)
    if ex is None:
        return f'<p class="shortcode-error">Example not found in "Examples from papers": <code>{_esc(ex_id)}</code></p>'

    translation  = ex.findtext('Translation[@lang="eng"]', '').strip()
    glosses_raw  = ex.findtext('Glosses', '').strip()
    glosses      = glosses_raw.split() if glosses_raw else []
    label        = (ex.findtext('Label') or '').strip()
    pangloss_url = ex.findtext('Source/PanglossURL', '').strip()

    # Token → dict-entry link map
    token_links = {}
    for tok in ex.findall('TokenLinks/Token'):
        idx     = tok.get('index', '')
        dict_id = tok.get('dictId', '')
        if idx.isdigit() and dict_id:
            token_links[int(idx)] = dict_id

    # Build one table row per language
    rows_html = ''
    for code in LANG_CODES:
        lang = LANG_MAP[code]
        tier = ex.find(f'Tier[@lang="{code}"]')
        if tier is None or not tier.text:
            continue
        forms  = tier.text.strip().split()
        color  = LANG_COLORS[lang]
        abbr   = LANG_ABBR[lang]

        cells = ''
        for i, form in enumerate(forms):
            dict_id = token_links.get(i, '')
            f_esc   = _esc(form)
            if form == '—':
                cells += '<td class="ex-cell ex-dash">—</td>'
            elif dict_id:
                cells += (f'<td class="ex-cell">'
                          f'<a class="lexlink" href="dictionary.html#{dict_id}" '
                          f'data-dict-id="{dict_id}">{f_esc}</a></td>')
            else:
                g_esc = _esc(glosses[i]) if i < len(glosses) else ''
                cells += (f'<td class="ex-cell" data-lang="{code}" '
                          f'data-form="{f_esc}" data-gloss="{g_esc}">{f_esc}</td>')

        rows_html += (f'<tr data-lang="{lang}">'
                      f'<td class="ex-abbr" style="color:{color};">{abbr}</td>'
                      f'{cells}</tr>\n')

    # Separator + gloss row
    n_cols     = len(glosses)
    sep_cells  = '<td></td>' + '<td></td>' * n_cols
    gloss_cells = ''.join(f'<td class="ex-gloss">{_esc(g)}</td>' for g in glosses)

    pangloss_link = ''
    if pangloss_url:
        pangloss_link = (f'<a class="corpus-ref" href="{_esc(pangloss_url)}" target="_blank" '
                         f'rel="noopener">🎧 Pangloss archive →</a>')

    number = f'<span class="cite-n">({n})</span>' if n is not None else ''
    source = f'<div class="ex-source">{_esc(label)}</div>' if label else ''
    transl = f'<div class="ex-transl">\u2018{_esc(translation)}\u2019</div>' if translation else ''

    return f'''<div class="example-block grammar-cite" data-example-id="{_esc(ex_id)}">
  {number}
  <div class="cite-body">
    {source}
    <div class="example-wrap">
      <table class="ex-table">
        {rows_html}
        <tr class="ex-sep">{sep_cells}</tr>
        <tr><td class="ex-gloss-empty"></td>{gloss_cells}</tr>
      </table>
      {transl}
      {pangloss_link}
    </div>
  </div>
</div>'''


def _entry_is_grammatical(el):
    """Grammatical material (markers, pronouns, TAMP forms …) is marked by its semantic domain, set in the project's
    `grammaticalDomains` (default: Grammar). Everything else is lexical."""
    return (el.findtext('DomaineSémantique') or '').strip().lower() in GRAMMATICAL_DOMAINS

def _chip_forms(el):
    """The forms of an entry a grammar chip shows, {language code: form}.
    Grammatical material: every form. Lexical material: only the cognates, i.e. the languages of the entry's etymons (an etymon
    that names no languages covers all of them). An entry that names no cognates shows its form in the project's headword
    language (or, lacking it, the first form), since the words that merely mean the same are not its parallels."""
    forms = {}
    for node in el.findall('Lemme/ReprésentationDeForme'):
        code, text = node.get('langue', ''), (node.text or '').strip()
        if code in LANG_MAP and text and text != '\u2014':
            forms[code] = text
    if _entry_is_grammatical(el):
        return forms
    cognate, everywhere = set(), False
    for et in el.findall('Étymologie/Étymon'):
        codes = _langs_attr(et)
        if codes is None:
            everywhere = True
        else:
            cognate.update(codes)
    if everywhere:
        return forms
    if cognate:
        return {c: f for c, f in forms.items() if c in cognate}
    own = PROJECT.get('headwordLanguage')
    first = own if own in forms else next((c for c in LANG_CODES if c in forms), None)
    return {first: forms[first]} if first else {}

def build_entry_chip(entry_id):
    """
    Resolve {{entry: ID}} — builds a compact inline citation chip
    showing the forms in every language and the gloss, hyperlinked to
    the full dictionary entry.
    """
    d = get_dict_xml()
    if d is None:
        return f'<span class="shortcode-error">Dictionary XML not found</span>'

    entry = d.find(f'.//EntréeLexicale[@identifiant="{entry_id}"]')
    if entry is None:
        return f'<span class="shortcode-error">Dictionary entry not found: <code>{entry_id}</code></span>'

    shown = _chip_forms(entry)                         # code -> form
    forms = {LANG_MAP[c]: f for c, f in shown.items()}
    gloss = (entry.findtext('Sens/Glose[@langue="eng"]', '') or '').strip()
    pos   = (entry.findtext('ClasseGrammaticale', '') or '').strip()

    # grammatical material shows a slot for every language (— where there is no form); lexical material only its cognates
    langs = LANG_NAMES if _entry_is_grammatical(entry) else [l for l in LANG_NAMES if l in forms]
    forms_html = ' · '.join(
        f'<span class="chip-form" style="color:{LANG_COLORS[lang]};">'
        f'{forms.get(lang, "—")}</span>'
        for lang in langs
    )

    return (f'<a href="dictionary.html#{entry_id}" class="entry-chip" '
            f'title="{pos} — {gloss}">'
            f'<span class="chip-forms">{forms_html}</span>'
            f'<span class="chip-gloss"> \u2018{gloss}\u2019</span>'
            f'</a>')


# ══════════════════════════════════════════════════════════════
#  CONCORDANCE  (search the texts for a string, with its context)
#  concordance.py does the searching; here the corpus is turned into lines (one sentence in one language) and served.
# ══════════════════════════════════════════════════════════════
from urllib.parse import quote as _urlq

_CORPUS = {'sig': None, 'lines': [], 'stats': {}}

def _corpus_signature():
    paths = [os.path.join(UPLOAD_FOLDER, 'fieldnotes.xml'), FIELDNOTES_FILE]
    for folder in (TRANSCRIPTIONS_FOLDER, GLOSSES_FOLDER):
        try:
            paths += [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(('.xml', '.json'))]
        except OSError:
            pass
    sig = []
    for p in sorted(paths):
        try:
            st = os.stat(p)
            sig.append((p, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    return tuple(sig)

def _tokens_of(forms, glosses):
    return [{'form': f, 'gloss': (glosses[i] if i < len(glosses) else '') or ''} for i, f in enumerate(forms) if f]

def _lines_fieldnotes():
    xml, out = get_fieldnotes_xml(), []
    if xml is None:
        return out
    for idx, tg in enumerate(xml.findall('.//tiGroup')):
        title = (tg.findtext('ti') or '').strip()
        stored_all = _load_stored_glosses(f'fieldnotes_{idx}')
        for rfg in tg.findall('rfGroup'):
            sid = (rfg.findtext('rf') or '').strip()
            grp = rfg.find('bslGroup') if rfg.find('bslGroup') is not None else rfg.find('frGroup')
            if grp is None or not sid:
                continue
            prompt = (grp.findtext('bsl') or grp.findtext('fr') or '').strip()
            st = stored_all.get(sid) if isinstance(stored_all.get(sid), dict) else None
            transl = st.get('translation') if st and st.get('translation') is not None else prompt
            for code in LANG_CODES:
                text = ' '.join(nd.text.strip() for nd in grp.findall(code) if nd.text and nd.text.strip())
                if not text or text == '\u2014':
                    continue
                if st and isinstance(st.get('tokens'), dict) and st['tokens'].get(code):
                    tokens = _tokens_of(st['tokens'][code], st.get('glosses', []))
                else:
                    tokens = [{'form': t, 'gloss': ''} for t in _tokenize_form(text)]
                out.append({'src': 'fieldnotes', 'lang': code, 'sid': sid, 'label': f'{title} · {sid}', 'text': text, 'translation': transl, 'tokens': tokens,
                            'tkey': f'fieldnotes:{idx}', 'ttitle': title,
                            'link': f'transcription.html?fieldnotes=1&index={idx}&title={_urlq(title)}#{_urlq(sid)}'})
    return out

def _lines_papers():
    out = []
    for ex in _paper_examples():
        sid = ex.get('id', '')
        tokens, glosses, _n, transl = _paper_state(ex)
        label = (ex.findtext('Label') or '').strip() or sid
        for code in LANG_CODES:
            tier = ex.find(f'Tier[@lang="{code}"]')
            text = (tier.text or '').strip() if tier is not None else ''
            if not text or text == '\u2014':
                continue
            out.append({'src': 'papers', 'lang': code, 'sid': sid, 'label': f'{PAPERS_TITLE} · {label}', 'text': text, 'translation': transl, 'tkey': 'papers:0', 'ttitle': PAPERS_TITLE,
                        'tokens': _tokens_of(tokens.get(code, []), glosses),
                        'link': f'transcription.html?papers=1&index=0&title={_urlq(PAPERS_TITLE)}#{_urlq(sid)}'})
    return out

def _lines_recordings():
    out = []
    for fn in sorted(os.listdir(TRANSCRIPTIONS_FOLDER)):
        path = os.path.join(TRANSCRIPTIONS_FOLDER, fn)
        if not fn.endswith('.xml') or _is_examples_file(path):
            continue
        try:
            data = _parse_tx(path)
        except Exception:
            continue
        tx_lang = data['lang']
        code = _TX_LANG_TO_CODE.get(tx_lang) or tx_lang             # a recording in a language outside the project keeps its own code
        stored_all = _load_stored_glosses(fn)
        for s in data['sentences']:
            st = stored_all.get(s['id']) if isinstance(stored_all.get(s['id']), dict) else None
            if st and st.get('tokens'):
                tokens = _tokens_of(_stored_tokens(st, code), st.get('glosses', []))
                transl = st.get('translation') if st.get('translation') is not None else s['transl']
            else:
                tokens = [{'form': w['form'], 'gloss': w.get('gloss', '')} for w in s.get('words', [])]
                transl = s['transl']
            out.append({'src': 'recording', 'lang': code, 'sid': s['id'], 'label': f"{data['title']} · {s['id']}", 'text': s['form'], 'translation': transl, 'tokens': tokens,
                        'tkey': f'recording:{fn}', 'ttitle': data['title'],
                        'link': f"transcription.html?key={_urlq(fn)}&title={_urlq(data['title'])}&lang={_urlq(tx_lang)}#{_urlq(s['id'])}"})
    return out

def _corpus_lines():
    """The corpus as lines. Built again only when a text, a gloss file or the questionnaire has changed."""
    sig = _corpus_signature()
    if _CORPUS['sig'] != sig:
        _CORPUS['lines'] = [conc.prepare_line(l) for l in _lines_fieldnotes() + _lines_papers() + _lines_recordings()]
        _CORPUS['sig'] = sig
        _CORPUS['stats'] = {}
    return _CORPUS['lines']

_SOURCE_LABELS = {'fieldnotes': 'Fieldnotes', 'papers': PAPERS_TITLE, 'recording': 'Recordings'}

def _form_annotator():
    """annotate(line, token) -> {entry, pos}: the dictionary entry whose form in that language is the word (when only one is)."""
    d = get_dict_xml()
    index = {}
    if d is not None:
        for el in d.findall('.//EntréeLexicale'):
            pos = (el.findtext('ClasseGrammaticale') or '').strip()
            for code, form in _entry_forms_clean(el).items():
                index.setdefault((code, form), []).append((el.get('identifiant', ''), pos))
    def annotate(line, token):
        found = index.get((line.get('lang'), _clean_form(token.get('form', ''))), [])
        return {'entry': found[0][0], 'pos': found[0][1]} if len(found) == 1 else {}
    return annotate

def _flag(name, default):
    v = request.args.get(name)
    return default if v is None else v not in ('0', 'false', '')

@app.route('/api/concordance/info')
def concordance_info():
    """What can be searched: the languages and the sources of the corpus, with their sizes."""
    lines = _corpus_lines()
    by_lang, by_src, words = {}, {}, 0
    for l in lines:
        by_lang[l['lang']] = by_lang.get(l['lang'], 0) + 1
        by_src[l['src']] = by_src.get(l['src'], 0) + 1
        words += len(l['text'].split())
    known = {l['code']: l for l in PROJECT['languages']}
    order = [c for c in LANG_CODES if c in by_lang] + sorted(c for c in by_lang if c not in known)
    return jsonify({'lines': len(lines), 'words': words,
                    'languages': [{'code': c, 'name': known[c]['name'] if c in known else c.upper(), 'abbr': known[c]['abbr'] if c in known else c.upper(),
                                   'lines': by_lang[c]} for c in order],
                    'sources': [{'id': s, 'label': _SOURCE_LABELS[s], 'lines': by_src[s]} for s in ('fieldnotes', 'recording', 'papers') if s in by_src]})

@app.route('/api/ngrams')
def concordance_ngrams():
    """The n-grams that contain the query: /api/ngrams?q=…&n=3&unit=word|morpheme&scope=forms|glosses|translation&case=1&diac=0
    &lang=code&source=…&min=1&limit=200"""
    try:
        n, mn, limit = int(request.args.get('n', 3)), int(request.args.get('min', 1)), int(request.args.get('limit', 200))
    except ValueError:
        return jsonify({'error': 'n, min and limit must be numbers.'}), 400
    sources = [s for s in request.args.get('source', '').split(',') if s]
    if any(s not in _SOURCE_LABELS for s in sources):
        return jsonify({'error': 'Unknown source.'}), 400
    try:
        res = conc.ngrams(_corpus_lines(), request.args.get('q', ''), n=n, scope=request.args.get('scope', 'forms'), unit=request.args.get('unit', 'word'),
                          ignore_case=_flag('case', True), ignore_diacritics=_flag('diac', False), lang=request.args.get('lang') or None,
                          sources=sources or None, min_count=mn, limit=limit)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(res)

@app.route('/api/texts/stats')
def texts_stats():
    """Tokens, types, TTR and Root TTR of each text, of each collection (fieldnotes, recordings, papers) and by language."""
    unit = request.args.get('unit', 'word')
    lines = _corpus_lines()
    if unit not in conc.UNITS:
        return jsonify({'error': 'Unknown unit.'}), 400
    if unit not in _CORPUS['stats']:
        _CORPUS['stats'][unit] = conc.corpus_stats(lines, unit=unit)
    return jsonify(_CORPUS['stats'][unit])

@app.route('/api/concordance')
def concordance_search():
    """Search the texts for a string: /api/concordance?q=…&scope=forms|glosses|translation&match=anywhere|word|morpheme
    &case=1&diac=0&lang=code&source=fieldnotes,recording,papers&width=6&limit=1000"""
    q = request.args.get('q', '')
    try:
        width, limit = int(request.args.get('width', 6)), int(request.args.get('limit', 1000))
    except ValueError:
        return jsonify({'error': 'width and limit must be numbers.'}), 400
    sources = [s for s in request.args.get('source', '').split(',') if s]
    if any(s not in _SOURCE_LABELS for s in sources):
        return jsonify({'error': 'Unknown source.'}), 400
    try:
        res = conc.search(_corpus_lines(), q, scope=request.args.get('scope', 'forms'), match=request.args.get('match', 'anywhere'),
                          ignore_case=_flag('case', True), ignore_diacritics=_flag('diac', False), lang=request.args.get('lang') or None,
                          sources=sources or None, width=width, limit=limit, annotate=_form_annotator())
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    return jsonify(res)

# ══════════════════════════════════════════════════════════════
#  REFERENCES (the project's bibliography, APA 7)
#  project/references.json holds what the author typed in the form; the formatting is done by references.py.
#  {{source: key}} cites one in the grammar; the References page lists them; they export to BibTeX and EndNote.
# ══════════════════════════════════════════════════════════════
import threading as _threading
_REFS_LOCK = _threading.Lock()

def _refs_load():
    try:
        with open(REFERENCES_FILE, encoding='utf-8') as f:
            raw = (json.load(f) or {}).get('references', [])
    except (OSError, ValueError):
        return []
    out, taken = [], set()
    for r in raw if isinstance(raw, list) else []:
        c, err = refs_lib.clean(r)
        if c is None:
            continue
        c['id'] = c['id'] or refs_lib.suggest_id(c, taken)
        if c['id'] in taken:
            continue
        taken.add(c['id'])
        out.append(c)
    return out

def _refs_save(refs):
    os.makedirs(os.path.dirname(REFERENCES_FILE) or '.', exist_ok=True)
    tmp = REFERENCES_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump({'references': refs}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, REFERENCES_FILE)

_SOURCE_RE = re.compile(r'\{\{\s*source\s*:\s*([^\}]+)\}\}')

def _grammar_citations():
    """{reference key: [grammar section ids that cite it]} (a citation by author and year counts for the reference it finds)"""
    found = {}
    refs = _refs_load()
    ctx = refs_lib.Context(refs)
    keys = {r['id'] for r in refs}
    try:
        names = sorted(os.listdir(GRAMMAR_FOLDER))
    except OSError:
        return found
    for fn in names:
        if not fn.endswith('.md'):
            continue
        with open(os.path.join(GRAMMAR_FOLDER, fn), encoding='utf-8') as f:
            text = f.read()
        for m in _SOURCE_RE.finditer(text):
            for key, _loc, _nar in refs_lib.parse_source_spec(_html.unescape(m.group(1)), keys):
                ref, _why = refs_lib.find_reference(key, refs, ctx)
                rid = ref['id'] if ref else key
                if fn[:-3] not in found.setdefault(rid, []):
                    found[rid].append(fn[:-3])
    return found

def _resolve_sources(spec):
    """Parse a {{source: …}} spec against the stored references: each item is a key, or the author(s) and year as one writes
    them in the text (Smith 2020b). Returns (items, narrative, ctx, problems); a problem is a ready-made message."""
    refs = _refs_load()
    ctx = refs_lib.Context(refs)
    items, problems, narrative = [], [], False
    for what, loc, nar in refs_lib.parse_source_spec(spec, {r['id'] for r in refs}):
        ref, why = refs_lib.find_reference(what, refs, ctx)
        if ref:
            items.append((ref, loc))
            narrative = narrative or nar
        elif why.startswith('ambiguous'):
            problems.append(f'Ambiguous reference: {what} ({why[len("ambiguous: "):]}): add the letter')
        else:
            problems.append(f'Reference not found: {what}')
    return items, narrative, ctx, problems

def build_source_cite(spec):
    """{{source: smith2020, p. 12}} -> (Smith, 2020, p. 12), a link to the reference with the full APA entry on hover."""
    items, narrative, ctx, missing = _resolve_sources(spec)
    if missing and not items:
        return f'<span class="shortcode-error">{_esc("; ".join(missing))}</span>'
    text, parts = refs_lib.intext(items, ctx, narrative and len(items) == 1)
    byid = {r['id']: r for r, _ in items}
    def link(label, rid):
        return (f'<a class="source-cite" href="references.html#{_esc(rid)}" '
                f'data-ref="{_esc(refs_lib.apa(byid[rid], ctx)[0], quote=True)}">{_esc(label)}</a>')
    if narrative and len(items) == 1:
        out = link(parts[0][0], parts[0][1])
    else:
        out = '(' + '; '.join(link(t, rid) for t, rid in parts) + ')'
    if missing:
        out += f' <span class="shortcode-error">{_esc("; ".join(missing))}</span>'
    return out

def _source_latex(spec, cited):
    items, narrative, ctx, missing = _resolve_sources(spec)
    if missing and not items:
        return f'\\textit{{[{_le("; ".join(missing))}]}}'
    text, _parts = refs_lib.intext(items, ctx, narrative and len(items) == 1)
    cited.update(r['id'] for r, _ in items)
    return _le(text)

def _ref_view(r, ctx, cited_in=None):
    html_, text_ = refs_lib.apa(r, ctx)
    return dict(r, html=html_, text=text_, yearDisplay=ctx.year(r),
                intext=refs_lib.intext([(r, '')], ctx)[0], narrative=refs_lib.intext([(r, '')], ctx, True)[0],
                citedIn=(cited_in or {}).get(r['id'], []))

@app.route('/api/references')
def references_list():
    refs = _refs_load()
    ctx = refs_lib.Context(refs)
    cited = _grammar_citations()
    return jsonify({'references': [_ref_view(r, ctx, cited) for r in ctx.sorted()],
                    'types': [{'id': i, 'label': l} for i, l in refs_lib.TYPES]})

@app.route('/api/references/preview', methods=['POST'])
def references_preview():
    """How a reference that is being typed will look (the author's form calls this as they type)."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    ref, err = refs_lib.clean(data)
    if err:
        return jsonify({'ok': False, 'error': err})
    others = [r for r in _refs_load() if r['id'] != (data.get('editing') or '')]
    taken = {r['id'] for r in others}
    ref['id'] = ref['id'] or refs_lib.suggest_id(ref, taken)
    ctx = refs_lib.Context(others + [ref])
    view = _ref_view(ref, ctx)
    view['suggestedId'] = refs_lib.suggest_id(ref, taken)
    return jsonify({'ok': True, 'view': view})

@app.route('/api/references', methods=['POST'])
def references_create():
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    ref, err = refs_lib.clean(request.get_json(silent=True) or {})
    if err:
        return jsonify({'ok': False, 'error': err}), 400
    with _REFS_LOCK:
        refs = _refs_load()
        taken = {r['id'] for r in refs}
        if ref['id'] and ref['id'] in taken:
            return jsonify({'ok': False, 'error': f'The key "{ref["id"]}" is already used by another reference.'}), 409
        ref['id'] = ref['id'] or refs_lib.suggest_id(ref, taken)
        refs.append(ref)
        _refs_save(refs)
    return jsonify({'ok': True, 'id': ref['id']})

def _rename_in_grammar(old, new):
    """Rewrite {{source: old …}} as {{source: new …}} in every grammar section. Returns the sections changed."""
    changed = []
    for fn in sorted(os.listdir(GRAMMAR_FOLDER)):
        if not fn.endswith('.md'):
            continue
        path = os.path.join(GRAMMAR_FOLDER, fn)
        with open(path, encoding='utf-8') as f:
            text = f.read()
        def fix(m):
            chunks = m.group(1).split(';')
            for i, ch in enumerate(chunks):
                core = ch.lstrip()
                head = re.match(r'[^,;\s}]+', core)
                if head and head.group(0).lower() == old:
                    chunks[i] = ch[:len(ch) - len(core)] + new + core[len(head.group(0)):]
            return '{{source:' + (' ' if not m.group(1).startswith(' ') else '') + ';'.join(chunks) + '}}'
        new_text = _SOURCE_RE.sub(fix, text)
        if new_text != text:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_text)
            changed.append(fn[:-3])
    return changed

@app.route('/api/references/<ref_id>', methods=['PUT'])
def references_update(ref_id):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    ref, err = refs_lib.clean(request.get_json(silent=True) or {})
    if err:
        return jsonify({'ok': False, 'error': err}), 400
    with _REFS_LOCK:
        refs = _refs_load()
        idx = next((i for i, r in enumerate(refs) if r['id'] == ref_id), None)
        if idx is None:
            return jsonify({'ok': False, 'error': 'Reference not found.'}), 404
        new_id = ref['id'] or ref_id
        if new_id != ref_id and any(r['id'] == new_id for r in refs):
            return jsonify({'ok': False, 'error': f'The key "{new_id}" is already used by another reference.'}), 409
        ref['id'] = new_id
        refs[idx] = ref
        _refs_save(refs)
        renamed_in = _rename_in_grammar(ref_id, new_id) if new_id != ref_id else []
    return jsonify({'ok': True, 'id': new_id, 'updatedGrammarSections': renamed_in})

@app.route('/api/references/<ref_id>', methods=['DELETE'])
def references_delete(ref_id):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    with _REFS_LOCK:
        refs = _refs_load()
        kept = [r for r in refs if r['id'] != ref_id]
        if len(kept) == len(refs):
            return jsonify({'ok': False, 'error': 'Reference not found.'}), 404
        _refs_save(kept)
    return jsonify({'ok': True, 'citedIn': _grammar_citations().get(ref_id, [])})

def _export_name(ext):
    return f"{re.sub(r'[^a-z0-9]+', '-', str(PROJECT.get('id') or 'dbt').lower()).strip('-') or 'dbt'}-references.{ext}"

@app.route('/api/references/export/bibtex')
def references_export_bibtex():
    return Response(refs_lib.to_bibtex(_refs_load()), mimetype='text/plain; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{_export_name("bib")}"'})

@app.route('/api/references/export/endnote')
def references_export_endnote():
    return Response(refs_lib.to_endnote(_refs_load()), mimetype='text/plain; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{_export_name("enw")}"'})

# One reference as a file, for anybody: BibTeX or EndNote, to drop into one's own reference manager
@app.route('/api/references/<ref_id>/export/<fmt>')
def references_export_one(ref_id, fmt):
    if fmt not in ('bibtex', 'endnote'):
        return jsonify({'error': 'Unknown format.'}), 404
    ref = next((r for r in _refs_load() if r['id'] == ref_id), None)
    if ref is None:
        return jsonify({'error': 'Reference not found.'}), 404
    body = refs_lib.to_bibtex([ref]) if fmt == 'bibtex' else refs_lib.to_endnote([ref])
    return Response(body, mimetype='text/plain; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{ref_id}.{"bib" if fmt == "bibtex" else "enw"}"'})

_FORMAT_NAMES = {'bibtex': 'BibTeX', 'endnote': 'EndNote', 'ris': 'RIS'}

@app.route('/api/references/import', methods=['POST'])
def references_import():
    """Read lists of references in BibTeX, EndNote (tagged format) or RIS: {files: [{name, text}], text: 'pasted', commit: false}.
    Without commit nothing is saved: the answer says what would happen to each reference (new, renamed, duplicate, rejected)."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    if (request.content_length or 0) > 3 * refs_lib.MAX_IMPORT_CHARS:
        return jsonify({'ok': False, 'error': 'That is too much to read at once (more than 2 million characters).'}), 413
    data = request.get_json(silent=True) or {}
    sources = [(str(f.get('name') or 'file')[:120], f.get('text')) for f in (data.get('files') or [])[:50] if isinstance(f, dict)]
    if isinstance(data.get('text'), str) and data['text'].strip():
        sources.append(('the pasted text', data['text']))
    sources = [(n, t) for n, t in sources if isinstance(t, str)]
    if not sources:
        return jsonify({'ok': False, 'error': 'Choose a file, or paste the references.'}), 400
    if sum(len(t) for _n, t in sources) > refs_lib.MAX_IMPORT_CHARS:
        return jsonify({'ok': False, 'error': 'That is too much to read at once (more than 2 million characters).'}), 413
    items, formats, unrecognised = [], [], []
    for name, text in sources:
        fmt, found = refs_lib.parse_references(text)
        if not fmt:
            unrecognised.append(name); continue
        formats.append({'name': name, 'format': _FORMAT_NAMES[fmt], 'count': len(found)})
        items += [dict(it, source=name) for it in found]
    if not items:
        return jsonify({'ok': False, 'error': 'No references were found: the file should be in BibTeX (.bib), EndNote (.enw) or RIS (.ris) format.',
                        'unrecognised': unrecognised}), 400
    commit = bool(data.get('commit'))
    with _REFS_LOCK:
        existing = _refs_load()
        add, report = refs_lib.merge_import(existing, items)
        if commit and add:
            _refs_save(existing + add)
    ctx = refs_lib.Context(existing + add)
    byid = {r['id']: r for r in add}
    entries = [{'status': x['status'], 'id': x['id'], 'source': x['source'], 'what': x.get('what', ''), 'error': x.get('error'), 'warnings': x.get('warnings', []),
                'html': refs_lib.apa(byid[x['id']], ctx)[0] if x['status'] in ('new', 'renamed') else ''} for x in report]
    counts = {k: sum(1 for e in entries if e['status'] == k) for k in ('new', 'renamed', 'duplicate', 'rejected')}
    return jsonify({'ok': True, 'committed': bool(commit and add), 'counts': counts, 'formats': formats, 'unrecognised': unrecognised, 'entries': entries})

# ══════════════════════════════════════════════════════════════
#  GRAMMAR RENDERER
#  Pass 1: Markdown → HTML
#  Pass 2: resolve {{example:…}}, {{cite:…}}, {{entry:…}} and {{source:…}} shortcodes
# ══════════════════════════════════════════════════════════════

_MD = md_lib.Markdown(extensions=['extra', 'tables', 'attr_list', 'toc'])

def render_grammar(md_text):
    _MD.reset()
    html = _MD.convert(md_text)

    # A shortcode alone on a line becomes <p>{{…}}</p>; the block it expands to must not sit in a <p>
    html = re.sub(r'<p>\s*(\{\{\s*(?:example|cite)\s*:[^}]*\}\})\s*</p>', r'\1', html)

    # {{example:}} and {{cite:}} share one counter, numbered in document order
    counter = [0]
    def _numbered(m):
        counter[0] += 1
        kind, arg = m.group(1), m.group(2).strip()
        return (build_example_table(arg, counter[0]) if kind == 'example'
                else build_citation(arg, counter[0]))
    html = re.sub(r'\{\{\s*(example|cite)\s*:\s*([^\}]+)\}\}', _numbered, html)

    html = re.sub(
        r'\{\{\s*entry\s*:\s*([^\}]+)\}\}',
        lambda m: build_entry_chip(m.group(1).strip()),
        html
    )
    html = _SOURCE_RE.sub(lambda m: build_source_cite(_html.unescape(m.group(1)).strip()), html)
    return html


def _section_path(section_id):
    # Sanitise: only allow alphanumeric + underscore to prevent path traversal
    safe = re.sub(r'[^a-zA-Z0-9_]', '', section_id)
    return os.path.join(GRAMMAR_FOLDER, f'{safe}.md')


# ══════════════════════════════════════════════════════════════
#  API ROUTES
# ══════════════════════════════════════════════════════════════

# ── Auth ──────────────────────────────────────────────────────

@app.route('/api/auth/status')
def auth_status():
    return jsonify({'logged_in': bool(session.get('author'))})


_LOGIN_LIMITER = security.LoginLimiter()

def _too_many(key):
    wait = _LOGIN_LIMITER.blocked_for(key)
    if wait:
        return jsonify({'ok': False, 'error': f'Too many wrong passwords. Try again in {wait // 60 + 1} min.'}), 429
    return None

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.get_json(silent=True) or {}
    key = request.remote_addr or '?'
    refused = _too_many(key)
    if refused:
        return refused
    if not security.password_configured():
        return jsonify({'ok': False, 'error': 'No author password has been set on this server yet. '
                        'On the server, run: python app.py --set-password'}), 403
    if security.check_password(data.get('password')):
        _LOGIN_LIMITER.reset(key)
        session['author'] = True
        return jsonify({'ok': True})
    _LOGIN_LIMITER.fail(key)
    return jsonify({'ok': False, 'error': 'Wrong password'}), 401

@app.route('/api/auth/password', methods=['POST'])
def auth_change_password():
    """Change the author's password (author only, and the current password must be given again)."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    key = request.remote_addr or '?'
    refused = _too_many(key)
    if refused:
        return refused
    if not security.check_password(data.get('current')):
        _LOGIN_LIMITER.fail(key)
        return jsonify({'ok': False, 'error': 'The current password is not right.'}), 403
    problem = security.validate_new_password(data.get('new'))
    if problem:
        return jsonify({'ok': False, 'error': problem}), 400
    security.set_password(data['new'])
    return jsonify({'ok': True})


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    session.pop('author', None)
    return jsonify({'ok': True})


# ── XML upload ────────────────────────────────────────────────

def _handle_upload(filename):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No file provided'}), 400
    try:
        etree.parse(f)          # validate XML before saving
    except etree.XMLSyntaxError as e:
        return jsonify({'error': f'Invalid XML: {e}'}), 400
    f.seek(0)
    f.save(os.path.join(UPLOAD_FOLDER, filename))
    if filename == 'dictionary.xml':           # an uploaded dictionary gets the same care as the shipped one
        _auto_orthography(); _auto_ipa()
    return jsonify({'ok': True, 'message': f'{filename} saved.'})


@app.route('/api/upload/dictionary', methods=['POST'])
def upload_dictionary():
    return _handle_upload('dictionary.xml')


@app.route('/api/upload/fieldnotes', methods=['POST'])
def upload_fieldnotes():
    return _handle_upload('fieldnotes.xml')

# (the language columns of the comparative displays are _FN_LANGS, from the project's languages)

# ── "Examples from papers" text: same shape as a fieldnotes text, so the viewer reuses it ──
@app.route('/api/papers/groups')
def papers_groups():
    n = len(_paper_examples())
    return jsonify({'groups': [{'index': 0, 'title': PAPERS_TITLE, 'count': n}] if n else []})

@app.route('/api/papers/tx/<int:index>')
def papers_tx(index):
    if index != 0:
        return jsonify({'error': 'Group not found'}), 404
    try:
        sentences = []
        for ex in _paper_examples():
            toks = _paper_tokens(ex)
            words = [{'form': ' '.join(t for t in toks[code] if t) or '\u2014',
                      'gloss': abbr, 'lang': code, 'lang_name': name}
                     for code, abbr, name in _FN_LANGS]
            sentences.append({
                'id': ex.get('id'), 'form': '', 'label': (ex.findtext('Label') or '').strip(),
                'transl': (ex.findtext('Translation[@lang="eng"]') or '').strip(),
                'transl_lang': 'eng', 'words': words, 'has_gloss': True,
                'is_comparative': True, 'audio': None})
        return jsonify({'title': PAPERS_TITLE, 'is_fieldnotes': True, 'is_papers': True,
                        'lang': 'comparative', 'sentences': sentences})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/papers/tx/<int:index>/glosses', methods=['GET'])
def get_papers_glosses(index):
    # the alignment and glosses as published, overlaid with whatever the author has saved
    merged = {e.get('id'): _paper_defaults(e) for e in _paper_examples()}
    merged.update(_load_stored_glosses('papers_0'))
    return jsonify(merged)

@app.route('/api/papers/tx/<int:index>/glosses', methods=['POST'])
def save_papers_gloss(index):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data    = request.get_json(silent=True) or {}
    sent_id = data.get('sentence_id', '')
    if not sent_id:
        return jsonify({'error': 'No sentence_id'}), 400
    stored = _load_stored_glosses('papers_0')
    stored[sent_id] = data.get('gloss', '')
    p, tmp = _gloss_path('papers_0'), _gloss_path('papers_0') + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(stored, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return jsonify({'ok': True})

@app.route('/api/fieldnotes/tx/<int:index>/glosses', methods=['GET'])
def get_fieldnotes_glosses(index):
    """Dedicated gloss GET for fieldnotes — avoids routing ambiguity."""
    return jsonify(_load_stored_glosses(f'fieldnotes_{index}'))

@app.route('/api/fieldnotes/tx/<int:index>/glosses', methods=['POST'])
def save_fieldnotes_gloss(index):
    """Dedicated gloss POST for fieldnotes — avoids routing ambiguity."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data    = request.get_json(silent=True) or {}
    sent_id = data.get('sentence_id', '')
    gloss   = data.get('gloss', '')
    if not sent_id:
        return jsonify({'error': 'No sentence_id'}), 400
    p      = _gloss_path(f'fieldnotes_{index}')
    stored = _load_stored_glosses(f'fieldnotes_{index}')   # robust: handles corrupted files
    stored[sent_id] = gloss
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(stored, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return jsonify({'ok': True})

@app.route('/api/fieldnotes/tx/<int:index>')
def fieldnotes_tx(index):
    """Return a fieldnotes tiGroup in transcription-viewer format."""
    try:
        xml = get_fieldnotes_xml()
        if xml is None:
            return jsonify({'error': 'No fieldnotes XML found'}), 404
        tgs = xml.findall('.//tiGroup')
        if index < 0 or index >= len(tgs):
            return jsonify({'error': 'Group not found'}), 404
        tg = tgs[index]
        ti = (tg.findtext('ti') or '').strip()
        sentences = []
        for rfg in tg.findall('rfGroup'):
            rf  = (rfg.findtext('rf') or '').strip()
            grp = rfg.find('bslGroup')
            if grp is None:
                grp = rfg.find('frGroup')
            if grp is None:
                continue
            prompt = (grp.findtext('bsl') or grp.findtext('fr') or '').strip()
            words = []
            for code, abbr, name in _FN_LANGS:
                nodes = grp.findall(code)
                vals  = [n.text.strip() for n in nodes if n.text and n.text.strip()]
                form  = ' / '.join(vals) if vals else '—'
                words.append({'form': form, 'gloss': abbr,
                              'lang': code, 'lang_name': name})
            if prompt or any(w['form'] != '—' for w in words):
                sentences.append({
                    'id':            rf,
                    'form':          '',
                    'transl':        prompt,
                    'transl_lang':   'bsl',
                    'words':         words,
                    'has_gloss':     True,
                    'is_comparative': True,
                    'audio':         None,
                })
        return jsonify({
            'title':        ti,
            'is_fieldnotes': True,
            'lang':         'comparative',
            'sentences':    sentences,
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Fieldnotes routes ─────────────────────────────────────────

@app.route('/api/fieldnotes/groups')
def fieldnotes_groups():
    xml = get_fieldnotes_xml()
    if xml is None:
        return jsonify({'groups': [], 'error': 'No fieldnotes XML found'})
    groups = []
    for i, tg in enumerate(xml.findall('.//tiGroup')):
        ti = (tg.findtext('ti') or '').strip()
        if ti:
            groups.append({'index': i, 'title': ti})
    return jsonify({'groups': groups})

@app.route('/api/fieldnotes/group/<int:index>')
def fieldnotes_group(index):
    xml = get_fieldnotes_xml()
    if xml is None:
        return jsonify({'error': 'No fieldnotes XML found'}), 404
    tgs = xml.findall('.//tiGroup')
    if index < 0 or index >= len(tgs):
        return jsonify({'error': 'Group not found'}), 404
    tg  = tgs[index]
    ti  = (tg.findtext('ti') or '').strip()
    items = []
    for rfg in tg.findall('rfGroup'):
        rf  = (rfg.findtext('rf') or '').strip()
        grp = rfg.find('bslGroup') or rfg.find('frGroup')
        if grp is None:
            continue
        prompt = (grp.findtext('bsl') or grp.findtext('fr') or '').strip()
        forms  = {}
        for code in LANG_CODES:
            nodes = grp.findall(code)
            vals  = [n.text.strip() for n in nodes if n.text and n.text.strip()]
            forms[code] = ' / '.join(vals)
        if prompt or any(forms.values()):
            items.append({'rf': rf, 'prompt': prompt, 'forms': forms})
    return jsonify({'title': ti, 'index': index, 'items': items})

@app.route('/api/upload/status')
def upload_status():
    """Tell the client which XMLs are currently loaded."""
    return jsonify({
        'dictionary': os.path.exists(os.path.join(UPLOAD_FOLDER, 'dictionary.xml'))
                      or os.path.exists(DICT_FILE),
    })


# ── Grammar sections ──────────────────────────────────────────

@app.route('/api/grammar/<section_id>')
def get_grammar_html(section_id):
    path = _section_path(section_id)
    if not os.path.exists(path):
        return jsonify({'error': f'Section not found: {section_id}'}), 404
    with open(path, encoding='utf-8') as f:
        source = f.read()
    try:
        html = render_grammar(source)
    except Exception as e:
        html = f'<div class="shortcode-error">Render error: {e}</div>'
    return jsonify({'html': html, 'id': section_id})


@app.route('/api/grammar/<section_id>/source')
def get_grammar_source(section_id):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    path = _section_path(section_id)
    if not os.path.exists(path):
        return jsonify({'error': f'Section not found: {section_id}'}), 404
    with open(path, encoding='utf-8') as f:
        return jsonify({'source': f.read(), 'id': section_id})


@app.route('/api/grammar/<section_id>', methods=['POST'])
def save_grammar(section_id):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    source = data.get('source', '')
    path = _section_path(section_id)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(source)
    try:
        html = render_grammar(source)
    except Exception as e:
        html = f'<div class="shortcode-error">Render error: {e}</div>'
    return jsonify({'ok': True, 'html': html})


@app.route('/api/grammar/<section_id>', methods=['DELETE'])
def delete_grammar(section_id):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    path = _section_path(section_id)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({'ok': True})


@app.route('/api/grammar', methods=['POST'])
def create_grammar_section():
    """Create a new grammar section with an auto-generated ID."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data    = request.get_json(silent=True) or {}
    title   = data.get('title', '').strip() or 'New section'
    # Auto-generate next available sN id
    n = len([f for f in os.listdir(GRAMMAR_FOLDER) if f.endswith('.md')]) + 1
    section_id = f's{n}'
    while os.path.exists(_section_path(section_id)):
        n += 1
        section_id = f's{n}'
    initial = f'## {title}\n\n[Start writing here…]\n'
    with open(_section_path(section_id), 'w', encoding='utf-8') as f:
        f.write(initial)
    return jsonify({'ok': True, 'id': section_id, 'title': title})


_ALLOWED_IMG_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}

@app.route('/api/upload/image', methods=['POST'])
def upload_image():
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No file provided'}), 400
    ext = os.path.splitext(f.filename or '')[1].lower()
    if ext not in _ALLOWED_IMG_EXT:
        return jsonify({'error': f'Allowed types: {", ".join(_ALLOWED_IMG_EXT)}'}), 400
    safe = re.sub(r'[^a-zA-Z0-9._-]', '_', f.filename)
    f.save(os.path.join(IMAGES_FOLDER, safe))
    return jsonify({'ok': True, 'url': f'images/{safe}', 'filename': safe})


@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_FOLDER, filename)


# ── Dictionary entries (compact JSON for client-side gloss lookup) ────────────
_ABBREV_LINKS_PATH      = os.path.join(TRANSCRIPTIONS_FOLDER, 'abbrev_links.json')
_CONFIRMED_GLOSSES_PATH = os.path.join(TRANSCRIPTIONS_FOLDER, 'confirmed_glosses.json')

def _load_confirmed_glosses():
    if os.path.exists(_CONFIRMED_GLOSSES_PATH):
        with open(_CONFIRMED_GLOSSES_PATH, encoding='utf-8') as f:
            content = f.read().strip()
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                try:
                    obj, _ = json.JSONDecoder().raw_decode(content)
                    return obj if isinstance(obj, dict) else {}
                except Exception:
                    pass
    return {}

_PROPOSED_ENTRIES_PATH = os.path.join(TRANSCRIPTIONS_FOLDER, 'proposed_entries.json')

def _load_proposed_entries():
    if os.path.exists(_PROPOSED_ENTRIES_PATH):
        with open(_PROPOSED_ENTRIES_PATH, encoding='utf-8') as f:
            content = f.read().strip()
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                try:
                    obj, _ = json.JSONDecoder().raw_decode(content)
                    return obj if isinstance(obj, dict) else {}
                except Exception:
                    pass
    return {}

def _save_proposed_entries(data):
    tmp = _PROPOSED_ENTRIES_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _PROPOSED_ENTRIES_PATH)

def _existing_dict_forms():
    """Return a set of lowercase forms already in the dictionary."""
    d = get_dict_xml()
    if d is None:
        return set()
    forms = set()
    for el in d.findall('.//EntréeLexicale'):
        for node in el.findall('Lemme/ReprésentationDeForme'):
            if node.text:
                forms.add(node.text.strip().lower())
    return forms

@app.route('/api/dictionary/proposed')
def get_proposed_entries():
    """The words that confirmed texts propose to the dictionary: for the author only (a visitor sees the dictionary, not its worklist)."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    return jsonify(_load_proposed_entries())

@app.route('/api/dictionary/proposed', methods=['POST'])
def save_proposed_entries():
    """Receive {colKey: {gloss, examples}} from confirmed sentences.
    Skip any entry whose forms are already in the dictionary."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data       = request.get_json(silent=True) or {}
    stored     = _load_proposed_entries()
    existing   = _existing_dict_forms()
    fn_codes   = [c for c, _, _ in _FN_LANGS]

    for col_key, entry_data in data.items():
        gloss    = entry_data.get('gloss', '').strip()
        examples = entry_data.get('examples', [])
        if not gloss:
            continue
        # The forms as written (a name keeps its capital); older callers only send the positional key
        sent = entry_data.get('forms')
        if isinstance(sent, dict):
            forms = {c: str(v).strip() for c, v in sent.items() if c in fn_codes and str(v).strip()}
        else:
            parts = col_key.split('|')
            forms = {fn_codes[i]: parts[i] for i in range(min(len(fn_codes), len(parts)))}
        # Skip if any form already in dictionary
        if any(f.strip().lower() in existing for f in forms.values() if f and f != '—'):
            continue
        if col_key not in stored:
            stored[col_key] = {'gloss': gloss, 'forms': forms, 'examples': []}
        # Merge examples (deduplicate by sentence_id)
        known = {e['sentence_id'] for e in stored[col_key]['examples']}
        for ex in examples:
            if ex.get('sentence_id') not in known:
                stored[col_key]['examples'].append(ex)
                known.add(ex.get('sentence_id'))

    _save_proposed_entries(stored)
    return jsonify({'ok': True})

@app.route('/api/dictionary/proposed/add', methods=['POST'])
def add_proposed_to_dictionary():
    """Add a proposed entry to the dictionary XML and remove it from proposed."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data    = request.get_json(silent=True) or {}
    col_key = data.get('col_key', '')
    stored  = _load_proposed_entries()
    if col_key not in stored:
        return jsonify({'error': 'Entry not found'}), 404
    entry = stored[col_key]
    gloss = entry.get('gloss', '')
    forms = entry.get('forms', {})

    # Find the active dictionary file
    dict_path = os.path.join(UPLOAD_FOLDER, 'dictionary.xml')
    if not os.path.exists(dict_path):
        dict_path = DICT_FILE
    if not os.path.exists(dict_path):
        return jsonify({'error': 'Dictionary XML not found'}), 404

    tree = etree.parse(dict_path, _XML_PARSER)
    root = tree.getroot()

    # Generate a unique identifiant
    base_id   = re.sub(r'[^a-zA-Z0-9]', '_', gloss.lower())[:20]
    entry_id  = f'proposed_{base_id}'
    taken     = {el.get('identifiant', '') for el in root.findall('.//EntréeLexicale')}
    counter   = 1
    while entry_id in taken:
        entry_id = f'proposed_{base_id}_{counter}'; counter += 1

    dictionnaire = root.find('Dictionnaire')
    if dictionnaire is None:
        return jsonify({'error': 'No <Dictionnaire> element in XML'}), 500

    # Build new entry element (one sense: the confirmed gloss)
    el, _ = _build_entry_el(
        {'forms': {c: f for c, f in forms.items() if f and f != '\u2014'},
         'senses': [{'ref': None, 'definition': gloss, 'shortGloss': gloss}]},
        force_id=entry_id)
    dictionnaire.append(el)

    # Write back atomically
    tmp = dict_path + '.tmp'
    tree.write(tmp, pretty_print=True, encoding='UTF-8', xml_declaration=True)
    os.replace(tmp, dict_path)

    # Remove from proposed
    del stored[col_key]
    _save_proposed_entries(stored)
    return jsonify({'ok': True, 'id': entry_id})

@app.route('/api/dictionary/proposed/dismiss', methods=['POST'])
def dismiss_proposed_entry():
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    col_key = (request.get_json(silent=True) or {}).get('col_key', '')
    stored  = _load_proposed_entries()
    stored.pop(col_key, None)
    _save_proposed_entries(stored)
    return jsonify({'ok': True})

@app.route('/api/confirmed_glosses')
def get_confirmed_glosses():
    return jsonify(_load_confirmed_glosses())

@app.route('/api/confirmed_glosses', methods=['POST'])
def save_confirmed_glosses():
    """Receive {colKey: [gloss, ...]} pairs from confirmed sentences."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data   = request.get_json(silent=True) or {}
    stored = _load_confirmed_glosses()
    for col_key, glist in data.items():
        if col_key not in stored:
            stored[col_key] = []
        for g in glist:
            if g and g not in stored[col_key]:
                stored[col_key].append(g)
    tmp = _CONFIRMED_GLOSSES_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(stored, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _CONFIRMED_GLOSSES_PATH)
    return jsonify({'ok': True})

@app.route('/api/abbrev_links')
def get_abbrev_links():
    if os.path.exists(_ABBREV_LINKS_PATH):
        with open(_ABBREV_LINKS_PATH, encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({})

@app.route('/api/abbrev_links', methods=['POST'])
def save_abbrev_link():
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data  = request.get_json(silent=True) or {}
    abbr  = data.get('abbr', '').strip()
    link  = data.get('link', '').strip()
    if not abbr:
        return jsonify({'error': 'No abbreviation provided'}), 400
    links = {}
    if os.path.exists(_ABBREV_LINKS_PATH):
        with open(_ABBREV_LINKS_PATH, encoding='utf-8') as f:
            links = json.load(f)
    if link:
        links[abbr] = link
    else:
        links.pop(abbr, None)   # empty link = remove
    with open(_ABBREV_LINKS_PATH, 'w', encoding='utf-8') as f:
        json.dump(links, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True})

def _dict_path():
    """Return path of the currently active dictionary XML."""
    p = os.path.join(UPLOAD_FOLDER, 'dictionary.xml')
    return p if os.path.exists(p) else DICT_FILE

def _read_dict():
    return etree.parse(_dict_path(), _XML_PARSER)

def _write_dict(tree):
    p   = _dict_path()
    tmp = p + '.tmp'
    tree.write(tmp, pretty_print=True, encoding='UTF-8', xml_declaration=True)
    os.replace(tmp, p)

# ── Entry editing: multiple senses, homonym numbers, edits made in place ─────────────────
#
# Model (the same as the Mwotlap / LEXICA dictionaries):
#   <EntréeLexicale>  one per homonym; homonyms share a lemma form and carry <NuméroDHomonyme>
#     <Lemme> … <NuméroDHomonyme> <ClasseGrammaticale> <DomaineSémantique> <Étymologie> …
#     <Sens identifiant="…ⓢN">  one per sense, numbered by <NuméroDeSens>
#       <Glose langue="eng">definition</Glose>  <gloss>short gloss</gloss>  <Notes>…</Notes>
#
# An existing entry is edited IN PLACE, so whatever else it contains (examples, semantic
# relations, images … in a LEXICA-style entry) is left alone; a field is only rewritten when
# the author actually changed it.

_ENTRY_ORDER = ['Lemme', 'NuméroDHomonyme', 'ClasseGrammaticale', 'DomaineSémantique',
                'Étymologie', 'Sens']
def _text_of(el):
    return ''.join(el.itertext()).strip() if el is not None else ''

def _set_text(el, text):
    """Set an element's text, but leave it (and any markup inside) alone if it already reads so."""
    text = (text or '').strip()
    if _text_of(el) == text:
        return
    for ch in list(el):
        el.remove(ch)
    el.text = text

def _entry_child(el, tag, create=False):
    """The entry's child <tag>; create it (in the conventional place) if asked and missing."""
    c = el.find(tag)
    if c is None and create:
        c = etree.Element(tag)
        pos, idx = _ENTRY_ORDER.index(tag), 0
        for i, ch in enumerate(el):
            if ch.tag in _ENTRY_ORDER and _ENTRY_ORDER.index(ch.tag) < pos:
                idx = i + 1
        el.insert(idx, c)
    return c

# ── Languages: what a sense or an etymology applies to ──────────────────────────────────
# <Sens langues="aa cc"> and <Étymon langues="aa cc"> name the languages (codes, space separated) whose form of the
# entry the sense, or the etymology, belongs to. No attribute = all the languages, so older dictionaries are unchanged.
def _langs_attr(el):
    """The language codes an element is restricted to, or None for 'all of them'."""
    codes = [c for c in (el.get('langues') or '').split() if c in LANG_CODES]
    return codes or None

def _set_langs_attr(el, codes, keep_all=False):
    """Write the languages an element applies to. For a sense, all of them (or none given) means no restriction: no
    attribute. For an etymon, ticking every language is a statement (cognates in all the languages): keep_all writes it."""
    chosen = [c for c in LANG_CODES if c in {str(x) for x in (codes or [])}]
    if not chosen or (len(chosen) == len(LANG_CODES) and not keep_all):
        el.attrib.pop('langues', None)
    else:
        el.set('langues', ' '.join(chosen))

# ── Examples chosen for a sense ──────────────────────────────────────────────────────────
# <Sens><Exemples>{{cite: fieldnotes#0#d01.Road:02}} …</Exemples></Sens>: the examples the author wants shown for that sense, written
# with the same {{cite: …}} markup as the grammar (fieldnotes#group#sentence, papers#id, or recording.xml#sentence).
_CITE_RE = re.compile(r'\{\{\s*cite\s*:\s*([^}]*?)\s*\}\}')
_CITE_KEY_RE = re.compile(r'(?:fieldnotes#\d+#\S+|papers#\S+|[^#\s]+\.xml#\S+)')

def _example_keys(text):
    """The valid citation keys of a text, in order and without repeats."""
    keys = []
    for m in _CITE_RE.finditer(str(text or '')):
        k = m.group(1).strip()
        if _CITE_KEY_RE.fullmatch(k) and k not in keys:
            keys.append(k)
    return keys

def _examples_text(text):
    return '\n'.join('{{cite: %s}}' % k for k in _example_keys(text))

def _sense_current(s):
    """The values the editor shows for an existing <Sens> (kept in step with the page's parser)."""
    gl = s.find('Glose[@langue="eng"]')
    df = s.find('Définition/ReprésentationDeTexte[@langue="eng"]')
    definition = _text_of(df) or _text_of(gl)
    short = _text_of(s.find('gloss'))          # the real short gloss only (blank if none)
    notes = _text_of(s.find('Notes/ReprésentationDeTexte[@langue="eng"]'))
    return {'definition': definition, 'short': short, 'notes': notes, 'examples': _examples_text(_text_of(s.find('Exemples')))}

def _fill_sense(node, sd, existing):
    definition = (sd.get('definition') or '').strip()
    short      = (sd.get('shortGloss') or '').strip()
    notes      = (sd.get('notes') or '').strip()
    cur = _sense_current(node) if existing else {'definition': '', 'short': '', 'notes': '', 'examples': ''}
    if node.find('NuméroDeSens') is None:
        node.insert(0, etree.Element('NuméroDeSens'))
    nsens = node.find('NuméroDeSens')

    def place_after_number(new_el):
        node.insert(list(node).index(nsens) + 1, new_el)

    # definition: written wherever the page reads it from (Définition and/or Glose)
    if definition != cur['definition']:
        df = node.find('Définition/ReprésentationDeTexte[@langue="eng"]')
        gl = node.find('Glose[@langue="eng"]')
        if df is not None: _set_text(df, definition)
        if gl is not None: _set_text(gl, definition)
        if df is None and gl is None and definition:
            gl = etree.Element('Glose', langue='eng'); gl.text = definition
            place_after_number(gl)
    # short (interlinear) gloss
    want_short = short if existing else (short or definition)
    if existing and want_short == cur['short']:
        pass
    else:
        g = node.find('gloss')
        if want_short:
            if g is None:
                g = etree.Element('gloss')
                gl = node.find('Glose[@langue="eng"]')
                anchor = gl if gl is not None else nsens
                node.insert(list(node).index(anchor) + 1, g)
            _set_text(g, want_short)
        elif g is not None:
            node.remove(g)
    # notes
    if notes != cur['notes']:
        n_el = node.find('Notes')
        if notes:
            if n_el is None:
                n_el = etree.SubElement(node, 'Notes')
            rt = n_el.find('ReprésentationDeTexte[@langue="eng"]')
            if rt is None:
                rt = etree.SubElement(n_el, 'ReprésentationDeTexte', langue='eng')
            _set_text(rt, notes)
        elif n_el is not None:
            node.remove(n_el)
    # the examples chosen for the sense (an unchanged choice rewrites nothing; none removes the element)
    if isinstance(sd.get('examples'), str):
        want = _examples_text(sd['examples'])
        if want != cur['examples']:
            ex_el = node.find('Exemples')
            if want:
                if ex_el is None:
                    ex_el = etree.SubElement(node, 'Exemples')
                _set_text(ex_el, want)
            elif ex_el is not None:
                node.remove(ex_el)
    # the languages the sense applies to (sent whole by the editor; an unchanged choice rewrites nothing)
    if isinstance(sd.get('langs'), list):
        _set_langs_attr(node, sd['langs'])

def _apply_senses(el, eid, payload):
    existing = el.findall('Sens')
    used, ordered = set(), []
    taken = {s.get('identifiant') for s in existing}
    for sd in payload:
        ref, node = sd.get('ref'), None
        if isinstance(ref, int) and 0 <= ref < len(existing) and ref not in used:
            node = existing[ref]; used.add(ref)
            _fill_sense(node, sd, existing=True)
        else:
            if not any((sd.get(k) or '').strip() for k in ('definition', 'shortGloss', 'notes')):
                continue                       # an empty new sense card is simply dropped
            k = 1
            while f'{eid}\u24e2{k}' in taken: k += 1
            sid = f'{eid}\u24e2{k}'; taken.add(sid)
            node = etree.Element('Sens', identifiant=sid)
            _fill_sense(node, sd, existing=False)
        ordered.append(node)
    # existing senses that were not referenced were removed by the author
    insert_at = list(el).index(existing[0]) if existing else len(el)
    for s in existing:
        el.remove(s)
    for i, node in enumerate(ordered):
        el.insert(insert_at + i, node)
        node.find('NuméroDeSens').text = str(i + 1)

def _senses_payload(data):
    """The senses sent by the editor; older callers send one flat sense."""
    if isinstance(data.get('senses'), list):
        return data['senses']
    if any(data.get(k) for k in ('gloss', 'shortGloss', 'notes')):
        return [{'ref': None, 'definition': data.get('gloss', ''),
                 'shortGloss': data.get('shortGloss', ''), 'notes': data.get('notes', '')}]
    return []

def _fill_etymon(ety, ed):
    def put(tag, val, attrs=None, keep_blank=True):
        sel = tag + (f'[@langue="{attrs["langue"]}"]' if attrs else '')
        node = ety.find(sel)
        if val:
            if node is None:
                node = etree.SubElement(ety, tag, **(attrs or {}))
            _set_text(node, val)
        elif node is not None and not keep_blank:
            ety.remove(node)
        elif node is not None:
            _set_text(node, '')
    if not str(ed.get('form') or '').strip():
        # cognates declared, proto-form unknown: the etymon then keeps only the list of its languages
        for tag in ('Langue', 'Forme', 'Glose', 'LienTLOPO', 'LienEtymograph'):
            for n in ety.findall(tag):
                ety.remove(n)
    else:
        put('Langue', str(ed.get('lang') or 'POc').strip())
        put('Forme', str(ed.get('form') or '').strip())
        put('Glose', str(ed.get('gloss') or '').strip(), {'langue': 'eng'})
        put('LienTLOPO', str(ed.get('tlopo') or '').strip(), keep_blank=False)
        put('LienEtymograph', str(ed.get('etymograph') or '').strip(), keep_blank=False)
    if isinstance(ed.get('langs'), list):
        _set_langs_attr(ety, ed['langs'], keep_all=True)

def _apply_etymons(el, payload):
    """Make the entry's etymons the ones listed. An existing etymon is edited in place (its `ref` is its position), so
    anything else it holds is kept. A language belongs to one etymon only: the first one listing it keeps it."""
    ety_el = _entry_child(el, 'Étymologie')
    existing = ety_el.findall('Étymon') if ety_el is not None else []
    used, ordered, taken = set(), [], set()
    def declared(d):           # a proto-form, or at least two languages named as cognates
        return bool(str(d.get('form') or '').strip()) or (isinstance(d.get('langs'), list) and len({c for c in d['langs'] if c in LANG_CODES}) >= 2)
    items = [d for d in payload[:20] if isinstance(d, dict) and declared(d)]
    for ed in items:
        if isinstance(ed.get('langs'), list):
            mine = [c for c in LANG_CODES if c in {str(x) for x in ed['langs']} and c not in taken]
            taken.update(mine)
            if not mine and len(items) > 1:
                continue                       # every language it asked for belongs to another etymon
            ed = dict(ed, langs=mine)
        ref, node = ed.get('ref'), None
        if isinstance(ref, int) and 0 <= ref < len(existing) and ref not in used:
            node = existing[ref]; used.add(ref)
        else:
            node = etree.Element('Étymon')
        _fill_etymon(node, ed)
        ordered.append(node)
    if not ordered:
        if ety_el is not None:
            el.remove(ety_el)
        return
    ety_el = _entry_child(el, 'Étymologie', create=True)
    for n in existing:
        ety_el.remove(n)
    for n in ordered:
        ety_el.append(n)

def _apply_entry_data(el, eid, data):
    forms = data.get('forms') or {}
    lemme = _entry_child(el, 'Lemme', create=True)
    for code in LANG_CODES:
        form = unicodedata.normalize('NFC', (forms.get(code) or '').strip())
        node = lemme.find(f'ReprésentationDeForme[@langue="{code}"]')
        if form:
            if node is None:
                node = etree.SubElement(lemme, 'ReprésentationDeForme', langue=code)
            _set_text(node, form)
        elif node is not None:
            lemme.remove(node)

    # phonetic forms: {code: {text, auto}}; a language whose form was removed loses its IPA too
    ipa = data.get('ipa') if isinstance(data.get('ipa'), dict) else {}
    for code in LANG_CODES:
        node = lemme.find(f'FormePhonétique[@langue="{code}"]')
        rf_node = lemme.find(f'ReprésentationDeForme[@langue="{code}"]')
        has_form = rf_node is not None and _text_of(rf_node) not in ('', '\u2014')
        v = ipa.get(code)
        text = ((v.get('text') if isinstance(v, dict) else v) or '').strip() if v is not None else None
        if not has_form:
            if node is not None:
                lemme.remove(node)
        elif text:
            if node is None:
                node = etree.SubElement(lemme, 'FormePhonétique', langue=code)
            _set_text(node, text)
            if isinstance(v, dict) and v.get('auto'):
                node.set('statut', 'auto')
            else:
                node.attrib.pop('statut', None)
        elif text == '' and node is not None:
            lemme.remove(node)                 # cleared: it is re-derived just below

    hom = str(data.get('homonym') or '').strip()
    h = _entry_child(el, 'NuméroDHomonyme')
    if hom.isdigit():
        h = _entry_child(el, 'NuméroDHomonyme', create=True)
        _set_text(h, hom)
    elif h is not None:
        el.remove(h)

    for tag, key in (('ClasseGrammaticale', 'pos'), ('DomaineSémantique', 'domain')):
        val = (data.get(key) or '').strip()
        c = _entry_child(el, tag)
        if val:
            _set_text(_entry_child(el, tag, create=True), val)
        elif c is not None:
            _set_text(c, '')

    # etymology: `etyms` = the whole list of etymons (absent = leave them as they are), each {ref, lang, form, gloss,
    # tlopo, etymograph, langs}; older callers send one `etym` (absent = leave, {} = remove, {form: …} = write)
    if isinstance(data.get('etyms'), list):
        _apply_etymons(el, data['etyms'])
    elif isinstance(data.get('etym'), dict):                 # older callers: one etymology, written to the first etymon
        e = data['etym']
        if not e.get('form'):
            _apply_etymons(el, [])
        else:
            first = _entry_child(el, 'Étymologie', create=True).find('Étymon')
            if first is None:
                first = etree.SubElement(_entry_child(el, 'Étymologie'), 'Étymon')
            _fill_etymon(first, e)

    _apply_senses(el, eid, _senses_payload(data))
    _ensure_ipa(el)                              # whatever is still missing is derived

def _build_entry_el(data, existing_ids=None, force_id=None):
    """A new <EntréeLexicale> built from the editor's data. Returns (element, id)."""
    forms = data.get('forms') or {}
    if force_id:
        eid = force_id
    else:
        base = (_slug_id(next((forms[c] for c in _ID_ORDER if forms.get(c)), ''))
                or _slug_id((_senses_payload(data) or [{}])[0].get('definition', '')) or 'new')
        eid, n = base, 2                       # a second entry with the same form becomes …_2
        while existing_ids and eid in existing_ids:
            eid = f'{base}_{n}'; n += 1
    el = etree.Element('EntréeLexicale', identifiant=eid)
    _apply_entry_data(el, eid, data)
    return el, eid

def _slug_id(s):
    """ASCII id from a form: diacritics dropped (mōrōs -> moros), anything else -> _."""
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-zA-Z0-9]+', '_', s).strip('_').lower()[:20]

def _entry_form_set(e):
    out = set()
    for n in e.findall('Lemme/ReprésentationDeForme'):
        c, code = _clean_form(n.text), n.get('langue', '')
        if code in LANG_CODES and c and c != '\u2014':
            out.add((code, c))
    return out

def _number_homonyms(root, el):
    """When an entry carries a homonym number, give the other entries that share one of its
    forms (and have no number yet) the smallest free numbers, so the whole group is numbered."""
    h = (el.findtext('NuméroDHomonyme') or '').strip()
    if not h.isdigit():
        return
    mine = _entry_form_set(el)
    sharers = [e for e in root.findall('.//EntréeLexicale') if e is not el and _entry_form_set(e) & mine]
    used = {int(x.findtext('NuméroDHomonyme')) for x in sharers + [el]
            if (x.findtext('NuméroDHomonyme') or '').strip().isdigit()}
    for e in sharers:
        if (e.findtext('NuméroDHomonyme') or '').strip():
            continue
        n = 1
        while n in used: n += 1
        used.add(n)
        _set_text(_entry_child(e, 'NuméroDHomonyme', create=True), str(n))

# ── Orthography <-> IPA correspondences ─────────────────────────────────────────────────
# One table drives every conversion: the IPA suggested for a form, the reading of forms typed in
# IPA, and the start-up clean-up. It is edited in the dictionary's Settings (⚙) and kept in
# uploads/dictionary_settings.json; without that file the project's default table (project/orthography.json) applies.
# Several rows may share an orthographic letter (for a language where one letter stands for two sounds); the row ticked "default" is the
# one suggested when going from orthography to IPA, while EVERY row is understood when reading IPA.
_SETTINGS_PATH = os.path.join(UPLOAD_FOLDER, 'dictionary_settings.json')

def _row(orth, ipa, typ='consonant', default=True):
    return {'orth': unicodedata.normalize('NFC', orth), 'ipa': ipa, 'type': typ, 'default': default}

def _load_orthography():
    """The project's default orthography <-> IPA table (project/orthography.json). Without that file the table
    is empty: nothing is converted until the author fills in the Settings."""
    try:
        with open(PROJECT['files']['orthography'], encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    mk = lambda r: _row(str(r.get('orth', '')), str(r.get('ipa', '')), r.get('type', 'consonant'), bool(r.get('default', True)))
    default = {'name': str(data.get('name') or ''),
               'long_vowel_doubling': bool(data.get('longVowelDoubling', True)),   # a doubled vowel letter is long: ēē = ɪː
               'rows': [mk(r) for r in data.get('rows', []) if r.get('orth') and r.get('ipa')]}
    earlier = [[mk(r) for r in t] for t in data.get('previousDefaults', [])]       # tables of earlier releases
    return default, earlier

_DEFAULT_CORR, _LEGACY_DEFAULTS = _load_orthography()
def _rows_sig(rows):
    return sorted((r['orth'], r['ipa'], r.get('type', 'consonant'), bool(r.get('default'))) for r in rows)

# a settings file saved unchanged from an earlier default table is ignored: the project's current default applies
_AFFRICATES = {'ʧ': 't͡ʃ', 'ʤ': 'd͡ʒ', 'ʦ': 't͡s', 'ʣ': 'd͡z'}   # the one-glyph and the tie-bar spelling of an affricate

def _ipa_norm(s):
    return (s or '').replace('\u2011', '-')

def _clean_corr(cfg):
    """Validate a correspondence table from the Settings dialog. Returns (clean table, error)."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get('rows'), list):
        return None, 'The table is missing.'
    rows, seen = [], set()
    for r in cfg['rows'][:500]:
        if not isinstance(r, dict):
            continue
        o = unicodedata.normalize('NFC', str(r.get('orth') or '').strip())
        i = str(r.get('ipa') or '').strip()
        if not o and not i:
            continue                                   # a blank line
        if not o or not i:
            return None, f'Each row needs both an orthographic letter and an IPA value ("{o or "?"}" / "{i or "?"}").'
        if len(o) > 6 or len(i) > 14:
            return None, f'"{o}" / "{i}" is too long for a single letter or sound.'
        if (o, i) in seen:
            continue
        seen.add((o, i))
        rows.append({'orth': o, 'ipa': i, 'type': 'vowel' if r.get('type') == 'vowel' else 'consonant',
                     'default': bool(r.get('default'))})
    if not rows:
        return None, 'The table needs at least one correspondence.'
    chosen = set()                                     # exactly one default per orthographic letter
    for r in rows:
        if r['default'] and r['orth'] not in chosen:
            chosen.add(r['orth'])
        else:
            r['default'] = False
    for r in rows:
        if r['orth'] not in chosen:
            r['default'] = True; chosen.add(r['orth'])
    return {'name': str(cfg.get('name') or '').strip()[:80],
            'long_vowel_doubling': bool(cfg.get('long_vowel_doubling', True)), 'rows': rows}, None

def _compile_corr(cfg):
    rows = [{'orth': unicodedata.normalize('NFC', r['orth']), 'ipa': r['ipa'],
             'vowel': r.get('type') == 'vowel', 'default': bool(r.get('default'))} for r in cfg['rows']]
    default = {}
    for r in rows:
        if r['default']:
            default.setdefault(r['orth'], r['ipa'])
    for r in rows:
        default.setdefault(r['orth'], r['ipa'])
    ipa_to_orth = {}
    for r in rows:
        ipa_to_orth.setdefault(r['ipa'], r['orth'])
    for glyph, tie in _AFFRICATES.items():           # t͡ʃ and ʧ are one sound: a table row serves both spellings
        if tie in ipa_to_orth and glyph not in ipa_to_orth:
            ipa_to_orth[glyph] = ipa_to_orth[tie]
        elif glyph in ipa_to_orth and tie not in ipa_to_orth:
            ipa_to_orth[tie] = ipa_to_orth[glyph]
    orth_chars = set(''.join(r['orth'] for r in rows))
    ipa_only = {c for c in ''.join(ipa_to_orth) if c not in orth_chars}
    long_v = bool(cfg.get('long_vowel_doubling', True))
    if long_v:
        ipa_only.add('ː')
    return {
        'orth_syms': sorted(default, key=len, reverse=True),          # longest letter first (n̄ before n)
        'default': default, 'ipa_syms': sorted(ipa_to_orth, key=len, reverse=True),
        'ipa_to_orth': ipa_to_orth, 'vowels': {r['orth'] for r in rows if r['vowel']}, 'long': long_v,
        'ipa_only': ipa_only,
        # sequences made of orthographic letters that the orthography writes differently (mb -> b)
        'ambiguous': [i for i, o in ipa_to_orth.items() if len(i) > 1 and i != o and all(c in orth_chars for c in i)],
    }

_corr_cache = {'mtime': None, 'cfg': None, 'compiled': None}

def _cfg_current():
    """The author's table (from Settings) or, if none was saved, the default one."""
    try:
        with open(_SETTINGS_PATH, encoding='utf-8') as f:
            cfg, err = _clean_corr((json.load(f) or {}).get('correspondences'))
        if cfg:
            sig = _rows_sig(cfg['rows'])
            if any(sig == _rows_sig(old) for old in _LEGACY_DEFAULTS):
                return _DEFAULT_CORR, False                  # saved unchanged from an earlier default
            return cfg, True
    except (OSError, ValueError):
        pass
    return _DEFAULT_CORR, False

_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')

def _clean_colors(c):
    """{code: '#rrggbb'} with defaults for anything missing. Returns (colours, error)."""
    out = dict(_DEFAULT_COLORS)
    if isinstance(c, dict):
        for k in _DEFAULT_COLORS:
            v = str(c.get(k) or '').strip()
            if v:
                if not _HEX.match(v):
                    return None, f'"{v}" is not a colour like #2e5c8a.'
                out[k] = v.lower()
    return out, None

def _colors_current():
    try:
        with open(_SETTINGS_PATH, encoding='utf-8') as f:
            cols, err = _clean_colors((json.load(f) or {}).get('colors'))
        if cols:
            return cols
    except (OSError, ValueError):
        pass
    return dict(_DEFAULT_COLORS)

def _corr(cfg=None):
    """The compiled table (cached until the settings file changes)."""
    if cfg is not None:
        return _compile_corr(cfg)
    try:
        mt = os.path.getmtime(_SETTINGS_PATH)
    except OSError:
        mt = None
    if _corr_cache['compiled'] is None or _corr_cache['mtime'] != mt:
        c, _custom = _cfg_current()
        _corr_cache.update(mtime=mt, cfg=c, compiled=_compile_corr(c))
    return _corr_cache['compiled']

def _ipa_to_orth(s, corr=None):
    c = corr or _corr()
    s, out, i = _ipa_norm(s), [], 0
    while i < len(s):
        for ipa in c['ipa_syms']:
            if s.startswith(ipa, i):
                out.append(c['ipa_to_orth'][ipa]); i += len(ipa); break
        else:
            ch = s[i]
            out.append(out[-1] if (ch == 'ː' and c['long'] and out and out[-1] in c['vowels']) else ch)
            i += 1
    return unicodedata.normalize('NFC', ''.join(out))

def _looks_ipa(s, strict=False, corr=None):
    """True only when the form shows IPA-only signs. A form made of plain letters is left alone:
    it is either identical in both notations, or already orthographic (where j is /t͡ʃ/, not [j]).
    strict=True looks for unmistakable IPA symbols only (no 'mb'/'nd' guess): that is what runs
    on its own, because there is nobody to review the preview."""
    c = corr or _corr()
    t = _ipa_norm(s)
    return any(ch in c['ipa_only'] for ch in t) or (not strict and any(q in t for q in c['ambiguous']))

def _orth_to_ipa(s, corr=None):
    """Orthography -> IPA by the default row of each letter (a doubled vowel is long)."""
    c = corr or _corr()
    s = unicodedata.normalize('NFC', (s or '').replace('\u2011', '-')).lower()
    out, i, prev = [], 0, None
    while i < len(s):
        for sym in c['orth_syms']:
            if s.startswith(sym, i):
                long_here = c['long'] and sym in c['vowels'] and prev == sym
                out.append('ː' if long_here else c['default'][sym])
                prev = sym if sym in c['vowels'] else None
                i += len(sym); break
        else:
            out.append(s[i]); prev = None; i += 1
    return ''.join(out)

# ── Phonetic forms: <Lemme><FormePhonétique langue="…"> (as in the Mwotlap dictionary) ─────────
# Every form of an entry carries its IPA, shown in [ ] next to the headword. A transcription that
# was DERIVED from the orthography is stored with statut="auto" until the author confirms it:
# the derivation follows the correspondence table of the Settings (⚙).
def _load_seed_phonetic():
    """project/seed-phonetic-forms.json: {entry id: {language code: IPA}} the author gave for entries that were
    written before phonetic forms existed. Used (as confirmed) only while the entry still has that form."""
    try:
        with open(PROJECT['files']['seedPhonetic'], encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

_SEED_IPA = _load_seed_phonetic()

def _ensure_ipa(el):
    """Give every form of the entry its phonetic form (none is overwritten). Returns how many were added."""
    lemme = el.find('Lemme')
    if lemme is None or not _corr()['orth_syms']:          # no orthography <-> IPA table: nothing to derive from
        return 0
    added, eid = 0, el.get('identifiant', '')

    def tail():                                # the last orthographic / phonetic form: new IPA goes right after it
        kids = [c for c in lemme if c.tag in ('ReprésentationDeForme', 'FormePhonétique')]
        return kids[-1] if kids else None

    for rf in lemme.findall('ReprésentationDeForme'):
        code, text = rf.get('langue', ''), (rf.text or '').strip()
        if code not in LANG_CODES or not text or text == '\u2014':
            continue
        node = lemme.find(f'FormePhonétique[@langue="{code}"]')
        if node is not None and _text_of(node):
            continue
        known = (_SEED_IPA.get(eid) or {}).get(code)
        confirmed = bool(known) and _ipa_to_orth(known) == text      # the entry still has the author's own form
        ipa = known if confirmed else _orth_to_ipa(text)
        if node is None:
            node = etree.Element('FormePhonétique', langue=code)
            anchor = tail()
            lemme.insert(list(lemme).index(anchor) + 1 if anchor is not None else 0, node)
        node.text = ipa
        if confirmed:
            node.attrib.pop('statut', None)
        else:
            node.set('statut', 'auto')
        added += 1
    return added

def _rederive_auto(tree):
    """Re-derive the phonetic forms still marked statut="auto" from the CURRENT table. A form the
    author wrote or confirmed is never touched. Returns how many changed."""
    n = 0
    for el in tree.getroot().findall('.//EntréeLexicale'):
        lemme = el.find('Lemme')
        if lemme is None:
            continue
        for fp in lemme.findall('FormePhonétique'):
            if fp.get('statut') != 'auto':
                continue
            rf = lemme.find(f'ReprésentationDeForme[@langue="{fp.get("langue", "")}"]')
            text = _text_of(rf) if rf is not None else ''
            if not text or text == '\u2014':
                continue
            new = _orth_to_ipa(text)
            if new != _text_of(fp):
                fp.text = new; n += 1
    return n

def _backup_dictionary(tag=''):
    import shutil, datetime
    bdir = os.path.join(UPLOAD_FOLDER, 'backups'); os.makedirs(bdir, exist_ok=True)
    path = os.path.join(bdir, 'dictionary-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + tag + '.xml')
    shutil.copyfile(_dict_path(), path)
    return path

def _auto_ipa():
    """On start-up (and after a dictionary upload): every entry gets its IPA, and the provisional
    ones are kept in line with the correspondence table. Backed up first."""
    try:
        if not os.path.exists(_dict_path()):
            return
        tree = _read_dict()
        added = sum(_ensure_ipa(el) for el in tree.getroot().findall('.//EntréeLexicale'))
        refreshed = _rederive_auto(tree)
        if added or refreshed:
            backup = _backup_dictionary('-ipa')
            _write_dict(tree)
            print(f"[dictionary] phonetic forms: {added} added, {refreshed} provisional one(s) re-derived "
                  f"from the correspondence table. Backup: {backup}")
    except Exception as e:
        print(f"[dictionary] automatic IPA step skipped: {e}")

@app.route('/api/dictionary/ipa-suggest', methods=['POST'])
def ipa_suggest():
    """IPA suggested for orthographic forms: {code: 'ron̄', …} -> {code: 'rɔŋ', …}."""
    forms = (request.get_json(silent=True) or {}).get('forms') or {}
    if not _corr()['orth_syms']:
        return jsonify({})
    return jsonify({c: _orth_to_ipa(f) for c, f in forms.items()
                    if c in LANG_CODES and (f or '').strip() not in ('', '\u2014')})

@app.route('/api/dictionary/entry/<entry_id>/ipa', methods=['POST'])
def ipa_confirm(entry_id):
    """Confirm (or un-confirm) the derived phonetic form of one language of an entry."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    code = data.get('lang', '')
    try:
        tree = _read_dict()
        node = tree.getroot().find(f'.//EntréeLexicale[@identifiant="{entry_id}"]/Lemme/FormePhonétique[@langue="{code}"]')
        if node is None:
            return jsonify({'error': 'Phonetic form not found'}), 404
        if data.get('confirmed', True):
            node.attrib.pop('statut', None)
        else:
            node.set('statut', 'auto')
        _write_dict(tree)
        return jsonify({'ok': True, 'auto': node.get('statut') == 'auto'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/colors.js')
def colors_js():
    """The language colours, as a script every page loads first: JS maps + CSS variables (--c-<language code> …)."""
    from flask import Response
    c = _colors_current()
    by_name = {_COLOR_NAMES[k]: v for k, v in c.items()}
    css = ':root{' + ''.join(f'--c-{k}:{v};' for k, v in c.items()) + '}'
    js = (f"window.DBT_COLORS={json.dumps(c)};window.DBT_COLORS_BY_NAME={json.dumps(by_name)};"
          f"(function(){{var s=document.createElement('style');s.textContent={json.dumps(css)};document.head.appendChild(s);}})();")
    return Response(js, mimetype='application/javascript', headers={'Cache-Control': 'no-cache'})

@app.route('/api/dictionary/settings', methods=['GET', 'POST'])
def dictionary_settings():
    """The orthography <-> IPA correspondence table of the dictionary (author only)."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    if request.method == 'GET':
        cfg, custom = _cfg_current()
        return jsonify({'correspondences': cfg, 'defaults': _DEFAULT_CORR, 'custom': custom,
                        'colors': _colors_current(), 'default_colors': _DEFAULT_COLORS, 'color_names': _COLOR_NAMES})
    data = request.get_json(silent=True) or {}
    cfg, err = _clean_corr(data.get('correspondences'))
    if err:
        return jsonify({'error': err}), 400
    cols, err = _clean_colors(data.get('colors') if 'colors' in data else _colors_current())
    if err:
        return jsonify({'error': err}), 400
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        tmp = _SETTINGS_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'correspondences': cfg, 'colors': cols}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _SETTINGS_PATH)
        _corr_cache['compiled'] = None
        rederived = 0
        if data.get('rederive') and os.path.exists(_dict_path()):
            tree = _read_dict()
            rederived = _rederive_auto(tree)
            if rederived:
                _backup_dictionary('-settings')
                _write_dict(tree)
        return jsonify({'ok': True, 'rederived': rederived})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dictionary/settings/test', methods=['POST'])
def dictionary_settings_test():
    """Try a (not yet saved) table on a word: {correspondences, orth, ipa} -> {ipa, orth}."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    corr = data.get('correspondences') if isinstance(data.get('correspondences'), dict) else {}
    # while the author is still typing, a half-filled row is simply ignored (saving does refuse it)
    corr = dict(corr, rows=[r for r in (corr.get('rows') or []) if isinstance(r, dict)
                            and str(r.get('orth') or '').strip() and str(r.get('ipa') or '').strip()])
    cfg, err = _clean_corr(corr)
    if err:
        return jsonify({'error': err}), 400
    c = _compile_corr(cfg)
    return jsonify({'ipa': _orth_to_ipa(data.get('orth', ''), c), 'orth': _ipa_to_orth(data.get('ipa', ''), c)})

def _ortho_collect(tree, strict=False):
    """The Lemme forms of the dictionary that are written in IPA: (changes, already-fine, entries)."""
    changes, kept, total = [], 0, 0
    for el in tree.getroot().findall('.//EntréeLexicale'):
        total += 1
        for node in el.findall('Lemme/ReprésentationDeForme'):
            code, text = node.get('langue', ''), (node.text or '').strip()
            if code not in LANG_CODES or not text or text == '\u2014':
                continue
            new = _ipa_to_orth(text) if _looks_ipa(text, strict) else text
            if new != text:
                changes.append({'id': el.get('identifiant', ''), 'lang': code, 'from': text, 'to': new, '_n': node})
            else:
                kept += 1
    return changes, kept, total

def _ortho_apply(tree, changes):
    """Back the dictionary file up, then write the converted forms. Returns the backup's path."""
    import shutil, datetime
    bdir = os.path.join(UPLOAD_FOLDER, 'backups')
    os.makedirs(bdir, exist_ok=True)
    backup = os.path.join(bdir, 'dictionary-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S') + '.xml')
    shutil.copyfile(_dict_path(), backup)
    for c in changes:
        c['_n'].text = c['to']
    _write_dict(tree)
    return backup

@app.route('/api/dictionary/orthography', methods=['GET', 'POST'])
def dictionary_orthography():
    """GET: preview which forms of the ACTIVE dictionary would be converted from IPA to
    orthography. POST: do it (the file is backed up first)."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        tree = _read_dict()
        changes, kept, total = _ortho_collect(tree)
        if request.method == 'GET':
            return jsonify({'entries': total, 'unchanged': kept,
                            'changes': [{k: v for k, v in c.items() if k != '_n'} for c in changes]})
        if not changes:
            return jsonify({'ok': True, 'converted': 0, 'backup': None})
        return jsonify({'ok': True, 'converted': len(changes), 'backup': _ortho_apply(tree, changes)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _auto_orthography():
    """On start-up, write any form that is plainly IPA in the orthography, so the dictionary is
    orthographic without anyone having to remember a button. The file is backed up first, and
    only forms with unmistakable IPA symbols are touched (the button previews the rest)."""
    lock = os.path.join(UPLOAD_FOLDER, '.ortho.lock')
    try:
        if not os.path.exists(_dict_path()):
            return
        try:                                   # several workers may start together: one converts
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL))
        except FileExistsError:
            if os.path.getmtime(lock) > __import__('time').time() - 60:
                return
        try:
            tree = _read_dict()
            changes, _kept, _total = _ortho_collect(tree, strict=True)
            if changes:
                backup = _ortho_apply(tree, changes)
                print(f"[dictionary] {len(changes)} form(s) written in IPA were converted to the "
                      f"orthography. Backup: {backup}")
        finally:
            try: os.remove(lock)
            except OSError: pass
    except Exception as e:                     # never stop the site from starting
        print(f"[dictionary] automatic orthography conversion skipped: {e}")

# ── Dictionary CRUD ───────────────────────────────────────────

@app.route('/api/dictionary/xml')
def dictionary_xml():
    """Serve the ACTIVE dictionary XML - the very file the add/edit/delete routes write to
    (an uploaded dictionary if there is one, otherwise dbt_dictionary.xml). The pages load
    the dictionary from here instead of guessing which file is current."""
    from flask import Response
    p = _dict_path()
    if not os.path.exists(p):
        return jsonify({'error': 'Dictionary XML not found'}), 404
    with open(p, 'rb') as f:
        data = f.read()
    return Response(data, mimetype='application/xml',
                    headers={'Cache-Control': 'no-store'})

@app.route('/api/dictionary/entry', methods=['POST'])
def add_dict_entry():
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    try:
        tree = _read_dict()
        root = tree.getroot()
        existing = {el.get('identifiant','') for el in root.findall('.//EntréeLexicale')}
        dictionnaire = root.find('Dictionnaire')
        if dictionnaire is None:
            return jsonify({'error': 'No <Dictionnaire> element'}), 500
        el, eid = _build_entry_el(data, existing_ids=existing)
        dictionnaire.append(el)
        _number_homonyms(root, el)
        _write_dict(tree)
        return jsonify({'ok': True, 'id': eid})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dictionary/entry/<entry_id>', methods=['PUT'])
def update_dict_entry(entry_id):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    try:
        tree = _read_dict()
        root = tree.getroot()
        old  = root.find(f'.//EntréeLexicale[@identifiant="{entry_id}"]')
        if old is None:
            return jsonify({'error': 'Entry not found'}), 404
        _apply_entry_data(old, entry_id, data)      # in place: nothing else in the entry is lost
        _number_homonyms(root, old)
        _write_dict(tree)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dictionary/entry/<entry_id>', methods=['DELETE'])
def delete_dict_entry(entry_id):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        tree = _read_dict()
        root = tree.getroot()
        el   = root.find(f'.//EntréeLexicale[@identifiant="{entry_id}"]')
        if el is None:
            return jsonify({'error': 'Entry not found'}), 404
        el.getparent().remove(el)
        _write_dict(tree)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Text examples for dictionary entries ─────────────────────────────────────
# An entry's examples are the sentences, in texts whose glosses the author has
# CONFIRMED, that contain one of its forms. Computed on the fly, so they stay in
# sync with confirmations and also work for entries added earlier.

# Language code used in a transcription XML (xml:lang) -> the project's language code (_TX_LANG_TO_CODE,
# from the languages' "aliases" in project.json). A text in a language the project does not describe is simply absent.

def _clean_form(s):
    """Lower-case a form and strip morpheme-boundary and punctuation marks."""
    s = unicodedata.normalize('NFC', (s or '').strip())     # ō typed as o + macron == ō
    return re.sub(r'^[-=]+|[-=.,;!?]+$', '', s).lower()

def _entry_forms_clean(el):
    forms = {}
    for node in el.findall('Lemme/ReprésentationDeForme'):
        code, c = node.get('langue', ''), _clean_form(node.text)
        if code in LANG_CODES and c and c != '\u2014':
            forms[code] = c
    return forms

def _cited_example(key, ef):
    """{{cite: key}} -> the example object the dictionary page draws (as in /api/dictionary/examples), or None if it does not exist.
    `ef` = the entry's cleaned forms {code: form}: the columns that hold the entry's word are marked."""
    def parallel(typ, idx, title, sid, tokens, glosses, transl):
        n_cols = max((len(tokens.get(c, [])) for c in LANG_CODES), default=0)
        cols = []
        for ci in range(n_cols):
            col = {c: _clean_form(tokens.get(c, [])[ci] if ci < len(tokens.get(c, [])) else '') for c in LANG_CODES}
            if ef and sum(1 for c, v in ef.items() if col.get(c) == v) >= min(2, len(ef)):
                cols.append(ci)
        return {'type': typ, 'index': idx, 'title': title, 'sentence_id': sid, 'tokens': tokens,
                'glosses': glosses, 'translation': transl, 'match_cols': cols}
    if key.startswith('papers#'):
        sid = key.split('#', 1)[1].strip()
        ex = _paper_example(sid)
        if ex is None:
            return None
        tokens, glosses, _n, transl = _paper_state(ex)
        return parallel('papers', 0, PAPERS_TITLE, sid, tokens, glosses, transl)
    if key.startswith('fieldnotes#'):
        parts = key.split('#', 2)
        xml = get_fieldnotes_xml()
        if xml is None or len(parts) < 3 or not parts[1].isdigit():
            return None
        tgs = xml.findall('.//tiGroup')
        idx, sid = int(parts[1]), parts[2].strip()
        if idx >= len(tgs):
            return None
        rfg = next((r for r in tgs[idx].findall('rfGroup') if (r.findtext('rf') or '').strip() == sid), None)
        if rfg is None:
            return None
        grp = rfg.find('bslGroup') if rfg.find('bslGroup') is not None else rfg.find('frGroup')
        prompt = (grp.findtext('bsl') or grp.findtext('fr') or '').strip() if grp is not None else ''
        stored = _load_stored_glosses(f'fieldnotes_{idx}').get(sid)
        if isinstance(stored, dict) and isinstance(stored.get('tokens'), dict) and stored.get('tokens'):
            tokens, glosses = stored['tokens'], stored.get('glosses', [])
        else:
            tokens = {}
            for code in LANG_CODES:
                vals = [nd.text.strip() for nd in (grp.findall(code) if grp is not None else []) if nd.text and nd.text.strip()]
                tokens[code] = _tokenize_form(' '.join(vals)) if vals else []
            glosses = []
        transl = stored.get('translation') if isinstance(stored, dict) and stored.get('translation') is not None else prompt
        return parallel('fieldnotes', idx, (tgs[idx].findtext('ti') or '').strip(), sid, tokens, glosses, transl)
    if '#' in key:
        fn, sid = (x.strip() for x in key.split('#', 1))
        path = os.path.join(TRANSCRIPTIONS_FOLDER, os.path.basename(fn))
        if not os.path.isfile(path):
            return None
        try:
            data = _parse_tx(path)
        except Exception:
            return None
        sent = next((s for s in data['sentences'] if s['id'] == sid), None)
        code = _TX_LANG_TO_CODE.get((data.get('lang') or '').strip())
        if sent is None or not code:
            return None
        stored = _load_stored_glosses(os.path.basename(fn)).get(sid)
        if isinstance(stored, dict) and stored.get('tokens'):
            toks, glosses = _stored_tokens(stored, code), stored.get('glosses', [])
            transl = stored.get('translation') if stored.get('translation') is not None else sent['transl']
        else:
            toks, glosses, transl = _tokenize_form(sent['form']), [], sent['transl']
        cols = [i for i, t in enumerate(map(_clean_form, toks)) if code in ef and t == ef[code]]
        return {'type': 'narrative', 'file': os.path.basename(fn), 'title': data['title'], 'lang': code, 'sentence_id': sid,
                'tokens': toks, 'glosses': glosses, 'translation': transl, 'match_cols': cols}
    return None

@app.route('/api/dictionary/cited-examples')
def dictionary_cited_examples():
    """The examples the author chose for senses: {"entry id|sense position": {examples: [...], missing: [keys that do not exist]}}."""
    d = get_dict_xml()
    out = {}
    if d is None:
        return jsonify(out)
    for el in d.findall('.//EntréeLexicale'):
        ef = None
        for ref, sn in enumerate(el.findall('Sens')):
            keys = _example_keys(_text_of(sn.find('Exemples')))
            if not keys:
                continue
            ef = _entry_forms_clean(el) if ef is None else ef
            found, missing = [], []
            for k in keys:
                obj = _cited_example(k, ef)
                (found if obj else missing).append(obj if obj else k)
            out[f"{el.get('identifiant', '')}|{ref}"] = {'examples': found, 'missing': missing}
    return jsonify(out)

@app.route('/api/dictionary/examples')
def dictionary_examples():
    try:
        d = get_dict_xml()
        if d is None:
            return jsonify({})
        entry_forms = {}
        for el in d.findall('.//EntréeLexicale'):
            forms = {}
            for node in el.findall('Lemme/ReprésentationDeForme'):
                code = node.get('langue', '')
                c = _clean_form(node.text)
                if code in LANG_CODES and c and c != '\u2014':
                    forms[code] = c
            if forms:
                entry_forms[el.get('identifiant', '')] = forms
        result = {eid: [] for eid in entry_forms}
        # the glosses of each entry's senses: they decide WHICH homonym an attestation belongs to
        entry_glosses = {}
        for el in d.findall('.//EntréeLexicale'):
            entry_glosses[el.get('identifiant', '')] = {
                _clean_form(_text_of(sn.find('gloss')) or _text_of(sn.find('Glose[@langue="eng"]')))
                for sn in el.findall('Sens')} - {''}

        def narrow(cands, gloss):
            """Several entries match one word: keep those that have a sense glossed like the word
            was glossed in the text. If none does (or it is unglossed) the word stays ambiguous."""
            g = _clean_form(gloss)
            if len(cands) > 1 and g:
                keep = [c for c in cands if g in entry_glosses.get(c, set())]
                if keep:
                    return keep
            return cands

        # ---- fieldwork-style texts (fieldnotes + examples from papers): parallel languages ----
        fx = get_fieldnotes_xml()
        groups = fx.findall('.//tiGroup') if fx is not None else []
        sources = []   # (type, index, gloss-store key, title, {sentence id: default translation})
        for fname in sorted(os.listdir(GLOSSES_FOLDER)):
            m = re.fullmatch(r'fieldnotes_(\d+)\.json', fname)
            if not m:
                continue
            idx = int(m.group(1))
            title, prompts = '', {}
            if idx < len(groups):
                title = (groups[idx].findtext('ti') or '').strip()
                for rfg in groups[idx].findall('rfGroup'):
                    grp = rfg.find('bslGroup')
                    if grp is None:
                        grp = rfg.find('frGroup')
                    if grp is not None:
                        prompts[(rfg.findtext('rf') or '').strip()] = (
                            grp.findtext('bsl') or grp.findtext('fr') or '').strip()
            sources.append(('fieldnotes', idx, f'fieldnotes_{idx}', title, prompts))
        sources.append(('papers', 0, 'papers_0', PAPERS_TITLE,
                        {x.get('id'): (x.findtext('Translation[@lang="eng"]') or '').strip()
                         for x in _paper_examples()}))
        for typ, idx, key, title, prompts in sources:
            stored = _load_stored_glosses(key)
            for sid, g in stored.items():
                if not (isinstance(g, dict) and g.get('confirmed') is True
                        and isinstance(g.get('tokens'), dict)):
                    continue
                tokens = g['tokens']
                n_cols = max((len(tokens.get(c, [])) for c in LANG_CODES), default=0)
                matched = {}   # entry id -> [column indexes]
                for ci in range(n_cols):
                    col = {c: _clean_form(tokens.get(c, [])[ci]
                                          if ci < len(tokens.get(c, [])) else '')
                           for c in LANG_CODES}
                    cands = [eid for eid, ef in entry_forms.items()
                             if sum(1 for c, v in ef.items() if col.get(c) == v) >= min(2, len(ef))]
                    col_gloss = g.get('glosses', [])[ci] if ci < len(g.get('glosses', [])) else ''
                    for eid in narrow(cands, col_gloss):
                        matched.setdefault(eid, []).append(ci)
                for eid, cols in matched.items():
                    transl = (g.get('translation') if g.get('translation') is not None
                              else prompts.get(sid, ''))
                    result[eid].append({
                        'type': typ, 'index': idx, 'title': title,
                        'sentence_id': sid, 'tokens': tokens,
                        'glosses': g.get('glosses', []),
                        'translation': transl, 'match_cols': cols})

        # ---- transcribed narratives: a single language per sentence ----
        for fn in sorted(os.listdir(TRANSCRIPTIONS_FOLDER)):
            if not fn.endswith('.xml'):
                continue
            stored = _load_stored_glosses(fn)
            confirmed = {sid: g for sid, g in stored.items()
                         if isinstance(g, dict) and g.get('confirmed') is True
                         and isinstance(g.get('tokens'), (list, dict))}
            if not confirmed:
                continue
            try:
                data = _parse_tx(os.path.join(TRANSCRIPTIONS_FOLDER, fn))
            except Exception:
                continue
            code = _TX_LANG_TO_CODE.get((data.get('lang') or '').strip())
            if not code:
                continue
            sent_transl = {s['id']: s['transl'] for s in data['sentences']}
            for sid, g in confirmed.items():
                raw_toks = _stored_tokens(g, code)
                toks = [_clean_form(t) for t in raw_toks]
                col_glosses = g.get('glosses', [])
                hit_cols = {eid: [i for i, t in enumerate(toks) if t == ef[code]]
                            for eid, ef in entry_forms.items() if code in ef}
                for i in sorted({i for v in hit_cols.values() for i in v}):
                    owners = narrow([eid for eid, v in hit_cols.items() if i in v],
                                    col_glosses[i] if i < len(col_glosses) else '')
                    for eid in hit_cols:
                        if eid not in owners and i in hit_cols[eid]:
                            hit_cols[eid].remove(i)
                for eid, cols in hit_cols.items():
                    if cols:
                        transl = (g.get('translation') if g.get('translation') is not None
                                  else sent_transl.get(sid, ''))
                        result[eid].append({
                            'type': 'narrative', 'file': fn, 'title': data['title'],
                            'lang': code, 'sentence_id': sid,
                            'tokens': raw_toks, 'glosses': g.get('glosses', []),
                            'translation': transl, 'match_cols': cols})
        return jsonify({k: v for k, v in result.items() if v})
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/dictionary/entries')
def dictionary_entries():
    """Return all entries with their 5-language forms and the glosses of ALL their senses.
    Used by the viewer and the grammar page to suggest glosses, show previews and link words."""
    d = get_dict_xml()
    if d is None:
        return jsonify({'entries': []})
    entries = []
    for el in d.findall('.//EntréeLexicale'):
        senses = []
        for i, sn in enumerate(el.findall('Sens'), 1):
            cur = _sense_current(sn)
            # <gloss> (short interlinear label) is preferred over the full definition
            short = _text_of(sn.find('gloss')) or _text_of(sn.find('Glose[@langue="eng"]'))
            if short:
                s = {'n': i, 'gloss': short, 'definition': cur['definition']}
                if _langs_attr(sn):
                    s['langs'] = _langs_attr(sn)
                senses.append(s)
        if not senses:
            continue
        forms = {}
        for node in el.findall('Lemme/ReprésentationDeForme'):
            lang = node.get('langue', '')
            if lang and node.text:
                forms[lang] = node.text.strip()
        hom = (el.findtext('NuméroDHomonyme') or '').strip()
        entries.append({
            'id':       el.get('identifiant', ''),
            'gloss':    senses[0]['gloss'],                  # first sense (kept for older callers)
            'glosses':  [s['gloss'] for s in senses],        # every sense
            'senses':   senses,
            'homonym':  hom if hom.isdigit() else '',
            'forms':    forms,
        })
    return jsonify({'entries': entries})

# ══════════════════════════════════════════════════════════════
#  LATEX EXPORT
# ══════════════════════════════════════════════════════════════

# Characters that must be escaped in LaTeX prose (not in math/verbatim)
_LATEX_ESC = str.maketrans({
    '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
    '_': r'\_', '{': r'\{', '}': r'\}',
    '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
    '\\': r'\textbackslash{}',
})

def _le(s):
    """Escape a plain-text string for LaTeX."""
    return str(s).translate(_LATEX_ESC)

# ── Shortcode → LaTeX ─────────────────────────────────────────

def _example_latex(ex_id, n):
    ex = _paper_example(ex_id)
    if ex is None:
        return f'\\textit{{[Example {_le(ex_id)} not found]}}'
    glosses_raw = (ex.findtext('Glosses') or '').split()
    translation = (ex.findtext('Translation[@lang="eng"]') or '').strip()
    label = (ex.findtext('Label') or '').strip()
    cols = [_le(g) for g in glosses_raw]
    rows = []
    for code in LANG_CODES:
        lang = LANG_MAP[code]
        abbr = LANG_ABBR[lang]
        tier = ex.find(f'Tier[@lang="{code}"]')
        if tier is None or not tier.text:
            continue
        forms = [_le(f) for f in tier.text.strip().split()]
        rows.append(f'\\textit{{{_le(abbr)}}} & ' + ' & '.join(forms) + r' \\')
    sep = 'l' * (len(cols) + 1)
    gloss_row = ' & '.join([''] + cols) + r' \\'
    tabular = (
        f'\\begin{{tabular}}[t]{{@{{}}{sep}@{{}}}}\n'
        + '\n'.join(rows) + '\n'
        + r'\midrule' + '\n'
        + gloss_row + '\n'
        + r'\end{tabular}'
    )
    transl = _le(translation)
    label_tex = f'\\textit{{{_le(label)}}}\\\\\n' if label else ''
    return (f'\\begin{{exe}}\n\\ex\\label{{ex:{_le(ex_id)}}}\n'
            f'{label_tex}{tabular}\\\\\n'
            f'\\trans `{transl}\'\n'
            f'\\end{{exe}}')

def _entry_latex(entry_id):
    d = get_dict_xml()
    if d is None:
        return f'\\textit{{{_le(entry_id)}}}'
    el = d.find(f'.//EntréeLexicale[@identifiant="{entry_id}"]')
    if el is None:
        return f'\\textit{{{_le(entry_id)}}}'
    gloss = (el.findtext('Sens/Glose[@langue="eng"]') or entry_id).strip()
    parts = []
    shown = _chip_forms(el)                            # the same forms as the chip in the grammar page
    for code in LANG_CODES:
        lang = LANG_MAP[code]
        abbr = LANG_ABBR[lang]
        form = shown.get(code, '')
        if form:
            parts.append(f'{_le(abbr)}.~\\textit{{{_le(form)}}}')
    forms_str = ', '.join(parts)
    return f'\\textit{{{_le(gloss)}}} [{forms_str}]'

def _cite_fieldnotes_latex(group_index, sent_id, n):
    xml = get_fieldnotes_xml()
    if xml is None:
        return f'\\textit{{[Fieldnotes not loaded]}}'
    tgs = xml.findall('.//tiGroup')
    if group_index >= len(tgs):
        return f'\\textit{{[Group {group_index} not found]}}'
    tg  = tgs[group_index]
    rfg = next((r for r in tg.findall('rfGroup')
                if (r.findtext('rf') or '').strip() == sent_id), None)
    if rfg is None:
        return f'\\textit{{[{_le(sent_id)} not found]}}'
    grp    = rfg.find('bslGroup') or rfg.find('frGroup')
    prompt = (grp.findtext('bsl') or grp.findtext('fr') or '').strip() if grp else ''
    stored = _load_stored_glosses(f'fieldnotes_{group_index}').get(sent_id)
    display_transl = (stored.get('translation') if stored and isinstance(stored, dict)
                      and stored.get('translation') is not None else prompt)
    if stored and isinstance(stored, dict) and stored.get('tokens'):
        tokens     = stored['tokens']
        col_glosses = stored.get('glosses', [])
        n_cols = max((len(tokens.get(c, [])) for c, _, _ in _FN_LANGS), default=0)
    else:
        tokens = {}; n_cols = 0
        for code, _, _ in _FN_LANGS:
            toks = _tokenize_form((grp.findall(code)[0].text or '') if grp and grp.findall(code) else '')
            tokens[code] = toks; n_cols = max(n_cols, len(toks))
        col_glosses = [''] * n_cols
        for code, _, _ in _FN_LANGS:
            while len(tokens[code]) < n_cols: tokens[code].append('')
    rows = []
    for code, abbr, _ in _FN_LANGS:
        cells = [_le(tokens[code][i] if i < len(tokens[code]) else '---') for i in range(n_cols)]
        rows.append(f'\\textit{{{_le(abbr)}}} & ' + ' & '.join(cells) + r' \\')
    gloss_cells = [_le(col_glosses[i] if i < len(col_glosses) else '') for i in range(n_cols)]
    sep      = 'l' * (n_cols + 1)
    gloss_row = ' & '.join([''] + gloss_cells) + r' \\'
    tabular = (f'\\begin{{tabular}}[t]{{@{{}}{sep}@{{}}}}\n'
               + '\n'.join(rows) + '\n'
               + r'\midrule' + '\n'
               + gloss_row + '\n'
               + r'\end{tabular}')
    return (f'\\begin{{exe}}\n\\ex\\label{{ex:{n}}}\n'
            f'{tabular}\\\\\n'
            f'\\trans `{_le(display_transl)}\'\n'
            f'\\end{{exe}}')

def _cite_narrative_latex(filename, sent_id, n):
    path = os.path.join(TRANSCRIPTIONS_FOLDER, filename)
    if not os.path.exists(path):
        return f'\\textit{{[{_le(filename)} not found]}}'
    try:
        data = _parse_tx(path)
    except Exception:
        return f'\\textit{{[Parse error in {_le(filename)}]}}'
    sent = next((s for s in data['sentences'] if s['id'] == sent_id), None)
    if not sent:
        return f'\\textit{{[{_le(sent_id)} not found]}}'
    stored = _load_stored_glosses(filename).get(sent_id)
    transl = (stored.get('translation') if stored and isinstance(stored, dict)
              and stored.get('translation') is not None else sent['transl'])
    lang_code = data.get('lang', '')
    if isinstance(stored, dict) and stored.get('tokens'):
        toks = _stored_tokens(stored, _TX_LANG_TO_CODE.get(lang_code) or lang_code)
        gl = stored.get('glosses', [])
        form_cells  = ' & '.join(_le(t) for t in toks)
        gloss_cells = ' & '.join(_le(gl[i] if i < len(gl) else '') for i in range(len(toks)))
        body = (f'\\begin{{tabular}}[t]{{@{{}}{"l" * len(toks)}@{{}}}}\n'
                f'{form_cells}\\\\\n{gloss_cells}\\\\\n\\end{{tabular}}')
    elif sent['has_gloss'] and sent['words']:
        form_cells  = ' & '.join(_le(w['form'])  for w in sent['words'])
        gloss_cells = ' & '.join(_le(w['gloss'] or '') for w in sent['words'])
        sep = 'l' * len(sent['words'])
        body = (f'\\begin{{tabular}}[t]{{@{{}}{sep}@{{}}}}\n'
                f'{form_cells}\\\\\n{gloss_cells}\\\\\n\\end{{tabular}}')
    else:
        manual = (stored if isinstance(stored, str) else '')
        body = f'\\gll {_le(sent["form"])} \\\\\n     {_le(manual)} \\\\'
    return (f'\\begin{{exe}}\n\\ex\\label{{ex:{n}}}\n'
            f'{body}\\\\\n'
            f'\\trans `{_le(transl)}\'\n'
            f'\\end{{exe}}')

# ── Markdown → LaTeX ──────────────────────────────────────────

def _cite_papers_latex(example_id, n):
    ex = _paper_example(example_id)
    if ex is None:
        return f'\\textit{{[{_le(example_id)} not found]}}'
    tokens, col_glosses, n_cols, transl = _paper_state(ex)
    rows = []
    for code, abbr, _ in _FN_LANGS:
        cells = [_le((tokens.get(code, [])[i] if i < len(tokens.get(code, [])) else '') or '---')
                 for i in range(n_cols)]
        rows.append(f'\\textit{{{_le(abbr)}}} & ' + ' & '.join(cells) + r' \\')
    gloss_row = ' & '.join([''] + [_le(col_glosses[i] if i < len(col_glosses) else '') for i in range(n_cols)]) + r' \\'
    label = (ex.findtext('Label') or '').strip()
    label_tex = f'\\textit{{{_le(label)}}}\\\\\n' if label else ''
    tabular = (f'\\begin{{tabular}}[t]{{@{{}}{"l" * (n_cols + 1)}@{{}}}}\n'
               + '\n'.join(rows) + '\n' + r'\midrule' + '\n' + gloss_row + '\n' + r'\end{tabular}')
    return (f'\\begin{{exe}}\n\\ex\\label{{ex:{n}}}\n{label_tex}{tabular}\\\\\n'
            f'\\trans `{_le(transl)}\'\n\\end{{exe}}')

def _md_to_latex_body(source, cited=None):
    """Convert grammar Markdown (with shortcodes) to a LaTeX body string. `cited` collects the keys of the
    references cited with {{source: …}} (they make the References section)."""
    cited = cited if cited is not None else set()
    counter = [0]

    def resolve_cite(m):
        counter[0] += 1; spec = m.group(1).strip(); n = counter[0]
        try:
            if spec.startswith('papers#'):
                return _cite_papers_latex(spec.split('#', 1)[1].strip(), n)
            if spec.startswith('fieldnotes#'):
                parts = spec.split('#', 2)
                return _cite_fieldnotes_latex(int(parts[1]), parts[2].strip(), n)
            elif '#' in spec:
                fn, sid = spec.split('#', 1)
                return _cite_narrative_latex(fn.strip(), sid.strip(), n)
        except Exception as e:
            return f'\\textit{{[cite error: {_le(str(e))}]}}'
        return f'\\textit{{[invalid cite]}}'

    def resolve_example(m):
        counter[0] += 1
        return _example_latex(m.group(1).strip(), counter[0])

    # 1. Resolve shortcodes
    src = re.sub(r'\{\{\s*cite\s*:\s*([^\}]+)\}\}',    resolve_cite,    source)
    src = re.sub(r'\{\{\s*example\s*:\s*([^\}]+)\}\}', resolve_example, src)
    src = re.sub(r'\{\{\s*entry\s*:\s*([^\}]+)\}\}',
                 lambda m: _entry_latex(m.group(1).strip()), src)
    src = _SOURCE_RE.sub(lambda m: _source_latex(_html.unescape(m.group(1)).strip(), cited), src)

    lines = src.split('\n')
    out   = []
    in_table = False
    table_rows = []

    def flush_table():
        nonlocal in_table, table_rows
        if not table_rows:
            in_table = False; return
        # Find separator row (--|--|--)
        header = table_rows[0] if table_rows else []
        data   = [r for r in table_rows[1:] if not all(c.strip().replace('-','') == '' for c in r)]
        ncols  = max(len(header), max((len(r) for r in data), default=0))
        sep    = 'l' * ncols
        hcells = ' & '.join(_le(c) for c in header) + r' \\'
        rows   = '\n'.join(' & '.join(_le(c) for c in row) + r' \\' for row in data)
        out.append(f'\\begin{{tabular}}{{@{{}}{sep}@{{}}}}\n\\toprule\n{hcells}\n\\midrule\n{rows}\n\\bottomrule\n\\end{{tabular}}\n')
        in_table = False; table_rows.clear()

    for line in lines:
        # Table row
        if line.strip().startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            # Skip separator rows
            if not all(c.replace('-','').replace(':','').strip() == '' for c in cells):
                if not in_table: in_table = True
                table_rows.append(cells)
            continue
        else:
            if in_table: flush_table()

        # ATX headings
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            depth = len(m.group(1))
            title = _apply_inline(m.group(2))
            cmd   = {1:'section',2:'section',3:'subsection',4:'subsubsection'}[depth]
            out.append(f'\\{cmd}{{{title}}}'); continue

        # Horizontal rule
        if re.match(r'^---+$', line.strip()):
            out.append(r'\medskip\noindent\rule{\linewidth}{0.4pt}\medskip'); continue

        # Blank line
        if not line.strip():
            out.append(''); continue

        # Already a LaTeX block (shortcode output)
        if line.strip().startswith('\\begin{') or line.strip().startswith('\\end{'):
            out.append(line); continue

        # Normal prose line
        out.append(_apply_inline(line))

    if in_table: flush_table()

    # Merge consecutive prose lines into paragraphs
    result = '\n'.join(out)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result

def _apply_inline(text):
    """Apply inline Markdown formatting and escape for LaTeX."""
    # Bold before italic to handle **...**
    text = re.sub(r'\*\*(.+?)\*\*', lambda m: f'\\textbf{{{_le(m.group(1))}}}', text)
    text = re.sub(r'\*(.+?)\*',     lambda m: f'\\textit{{{_le(m.group(1))}}}', text)
    text = re.sub(r'`(.+?)`',       lambda m: f'\\texttt{{{_le(m.group(1))}}}', text)
    # Escape remaining plain text (not already inside \command{})
    # Simple heuristic: escape & % $ # _ outside braces — already done by _le above
    # for the portions not inside LaTeX commands. For inline-converted text we just
    # escape the literal parts between commands.
    return text

_LATEX_DOC = r"""\documentclass[12pt, a4paper]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{gb4e}}\noautomath
\usepackage{{booktabs}}
\usepackage{{microtype}}
\usepackage{{hyperref}}
\usepackage{{xcolor}}
{latex_colors}
\title{{{latex_title}\\
\large {latex_subtitle}}}
\author{{{latex_author}}}
\date{{\today}}
\begin{{document}}
\maketitle
\tableofcontents
\newpage

{body}

\end{{document}}
"""

@app.route('/api/grammar/export/latex')
def export_grammar_latex():
    """Render all grammar sections as a single downloadable .tex file."""
    sections_latex, cited = [], set()
    for fname in sorted(os.listdir(GRAMMAR_FOLDER)):
        if not fname.endswith('.md'):
            continue
        path = os.path.join(GRAMMAR_FOLDER, fname)
        with open(path, encoding='utf-8') as f:
            source = f.read()
        try:
            sections_latex.append(_md_to_latex_body(source, cited))
        except Exception as e:
            sections_latex.append(f'% ERROR in {fname}: {e}')

    body = '\n\n'.join(sections_latex)
    used = [r for r in _refs_load() if r['id'] in cited]                      # the works cited in the grammar
    if used:
        body += ('\n\n\\section*{References}\\addcontentsline{toc}{section}{References}\n'
                 + refs_lib.latex_list(used, _le, refs_lib.Context(_refs_load())))
    lx   = PROJECT['latex']
    tex  = _LATEX_DOC.format(body=body, latex_title=lx.get('title', 'Comparative Grammar'),
                             latex_subtitle=lx.get('subtitle', ''), latex_author=lx.get('author', ''),
                             latex_colors='\n'.join(
                                 '\\definecolor{%sColor}{HTML}{%s}' % (re.sub('[^A-Za-z]', '', l['name']) or l['code'].upper(),
                                                                       _colors_current()[l['code']].lstrip('#'))
                                 for l in _LANGS))

    from flask import Response
    return Response(
        tex,
        mimetype='text/plain; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="grammar.tex"'}
    )

# ── List available sections ───────────────────────────────────

@app.route('/api/grammar')
def list_sections():
    sections = []
    for fname in sorted(os.listdir(GRAMMAR_FOLDER)):
        if fname.endswith('.md'):
            sections.append({'id': fname[:-3]})
    return jsonify({'sections': sections})


# ── Transcription helpers ─────────────────────────────────────

# xml:lang="en" uses the XML namespace
_XMLLANG = '{http://www.w3.org/XML/1998/namespace}lang'
# Parse without downloading DTD (Pangloss DTD referenced in files)
_XML_PARSER = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)

def _tx_index():
    if os.path.exists(TRANSCRIPTIONS_INDEX):
        with open(TRANSCRIPTIONS_INDEX, encoding='utf-8') as f:
            return json.load(f)
    return {}

def _tx_path(text_key):
    idx = _tx_index()
    fn  = idx.get(text_key)
    if not fn:
        return None
    p = os.path.join(TRANSCRIPTIONS_FOLDER, fn)
    return p if os.path.exists(p) else None

def _gloss_path(text_key):
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', text_key)
    return os.path.join(GLOSSES_FOLDER, f'{safe}.json')

_TRANSL_PREFS = ('en', 'fr', 'it', 'de', 'es', 'nl')

def _best_transl(el):
    """Return (text, lang_code) of the most preferred translation on an element."""
    found = {}
    for t in el.findall('TRANSL'):
        lv  = t.get(_XMLLANG, '') or t.get('xml:lang', '')
        txt = (t.text or '').strip()
        if txt:
            found[lv] = txt
    for pref in _TRANSL_PREFS:
        if pref in found:
            return found[pref], pref
    # Fallback: any available
    for lv, txt in found.items():
        return txt, lv
    return '', ''

def _extract_words(s_el):
    """
    Extract word-aligned gloss from <W><M> elements.
    Returns a list of {'form': str, 'gloss': str} — one entry per <W>.
    Returns [] if no W elements or none have M children with content.
    """
    words = []
    for w in s_el.findall('W'):
        morphs_form  = []
        morphs_gloss = []
        for m in w.findall('M'):
            mf = (m.findtext('FORM')  or '').strip()
            mg = (m.findtext('TRANSL') or '').strip()
            if mf:
                morphs_form.append(mf)
            if mg:
                morphs_gloss.append(mg)
        if morphs_form:
            words.append({
                'form':  '-'.join(morphs_form),
                'gloss': '-'.join(morphs_gloss) if morphs_gloss else '',
            })
    return words

def _parse_tx(path):
    xml  = etree.parse(path, _XML_PARSER)
    root = xml.getroot()
    lang_code = (root.get(_XMLLANG) or root.get('xml:lang', '')).strip()
    text_id   = root.get('id', '')

    # Titles — prefer English, fall back to French or first available
    titles = {}
    for t in root.findall('HEADER/TITLE'):
        lv = (t.get(_XMLLANG) or t.get('xml:lang', '')).strip()
        if t.text: titles[lv] = t.text.strip()
    title = titles.get('en') or titles.get('fr') or next(iter(titles.values()), '')

    # Sentences
    sentences = []
    for s in root.findall('S'):
        sid  = s.get('id', '')
        form = (s.findtext('FORM') or '').strip()
        if not form:
            continue
        transl, transl_lang = _best_transl(s)
        audio_el = s.find('AUDIO')
        audio    = {'start': audio_el.get('start', ''),
                    'end':   audio_el.get('end', '')} if audio_el is not None else None
        words     = _extract_words(s)
        has_gloss = bool(words and any(w['gloss'] for w in words))
        sentences.append({
            'id': sid, 'form': form,
            'transl': transl, 'transl_lang': transl_lang,
            'audio': audio,
            'words': words,          # word-aligned gloss from W/M
            'has_gloss': has_gloss,  # True = gloss already in XML
        })

    return {
        'id': text_id, 'lang': lang_code,
        'title': title,
        'sentences': sentences,
    }

# ── Transcription API routes ──────────────────────────────────

@app.route('/api/transcriptions/list')
def tx_list():
    """Return metadata for every XML in transcribed_narratives/ — drives the recordings tab."""
    items = []
    for fn in sorted(os.listdir(TRANSCRIPTIONS_FOLDER)):
        if not fn.endswith('.xml'):
            continue
        path = os.path.join(TRANSCRIPTIONS_FOLDER, fn)
        if _is_examples_file(path):          # examples from papers, not a recording
            continue
        try:
            xml  = etree.parse(path, _XML_PARSER)
            root = xml.getroot()
            lang = (root.get(_XMLLANG) or root.get('xml:lang', '')).strip()
            tx_id = root.get('id', fn[:-4])
            titles = {}
            for t in root.findall('HEADER/TITLE'):
                lv = (t.get(_XMLLANG) or t.get('xml:lang', '')).strip()
                if t.text: titles[lv] = t.text.strip()
            title = (titles.get('en') or titles.get('fr')
                     or next(iter(titles.values()), fn[:-4]))
            items.append({
                'filename': fn,
                'id': tx_id,
                'lang': lang,
                'title': title,
                'n_sentences': len(root.findall('S')),
            })
        except Exception:
            continue
    return jsonify({'transcriptions': items})

@app.route('/api/transcription/<string:text_key>')
def get_transcription(text_key):
    # text_key is the XML filename (e.g. crdo-WWO_FARFADETS.xml)
    path = os.path.join(TRANSCRIPTIONS_FOLDER, text_key)
    if not os.path.exists(path):
        return jsonify({'error': 'Transcription not found'}), 404
    try:
        data = _parse_tx(path)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(data)

@app.route('/api/transcription/<string:text_key>/glosses', methods=['GET'])
def get_glosses(text_key):
    # text_key is the XML filename; gloss stored by sanitised filename key
    return jsonify(_load_stored_glosses(text_key))

@app.route('/api/transcription/<string:text_key>/glosses', methods=['POST'])
def save_gloss(text_key):
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    data    = request.get_json(silent=True) or {}
    sent_id = data.get('sentence_id', '')
    gloss   = data.get('gloss', '')
    if not sent_id:
        return jsonify({'error': 'No sentence_id'}), 400
    p       = _gloss_path(text_key)
    glosses = _load_stored_glosses(text_key)   # robust: handles corrupted files
    glosses[sent_id] = gloss
    # Atomic write: temp file + rename prevents corruption on interrupted saves
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(glosses, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return jsonify({'ok': True})

@app.route('/api/upload/transcription', methods=['POST'])
def upload_transcription():
    """Save a transcription XML to transcribed_narratives/.
    The title and language are read from the XML itself — no manual linking needed."""
    if not session.get('author'):
        return jsonify({'error': 'Unauthorized'}), 401
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No file provided'}), 400
    try:
        etree.parse(f, _XML_PARSER)
    except etree.XMLSyntaxError as e:
        return jsonify({'error': f'Invalid XML: {e}'}), 400
    f.seek(0)
    safe_fn = re.sub(r'[^a-zA-Z0-9._-]', '_', f.filename or 'transcription.xml')
    f.save(os.path.join(TRANSCRIPTIONS_FOLDER, safe_fn))
    return jsonify({'ok': True, 'filename': safe_fn})

# ── Static file serving ───────────────────────────────────────

# ── Home page and "about" page: the layout is code, the content is the project's ──────────────
# project/pages/home.json and about.json hold the prose, as lists of paragraphs written in inline HTML
# (<strong>, <em>, links). {languages.count} and {languages.list} stand for the number of the project's languages
# in words and for the list of their names. A page whose file is missing is simply left out.
def _load_page(name):
    try:
        with open(os.path.join(PROJECT['files']['pagesDir'], name + '.json'), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

HOME, ABOUT = _load_page('home'), _load_page('about')

_NUMBER_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
                 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty']

def _prose(s):
    names = [_esc(l['name']) for l in _LANGS]
    n = len(names)
    if n == 1:
        lst = f'<strong>{names[0]}</strong>'
    elif n == 2:
        lst = f'<strong>{names[0]}</strong> and <strong>{names[1]}</strong>'
    else:
        lst = f"<strong>{', '.join(names[:-1])}</strong>, and <strong>{names[-1]}</strong>"
    return (str(s).replace('{languages.count}', _NUMBER_WORDS[n] if n < len(_NUMBER_WORDS) else str(n))
                  .replace('{languages.list}', lst).replace('{n}', str(n)))

def _anchor(l):
    from urllib.parse import quote
    return re.sub(r'[^a-z0-9]+', '-', l['name'].lower()).strip('-') or l['code']

_DEFAULT_CARDS = {
    'grammar': 'A systematic comparative description of grammatical structures. Every claim is illustrated with interlinear glossed examples; every morpheme links to the dictionary.',
    'texts': 'A curated index of natural language texts, each linking to its archived item.',
    'dictionary': 'A comparative lexicon giving each form in every language, with part of speech, semantic gloss, usage notes, and bidirectional links to the glossed grammatical examples.',
}

_MORE_LINK_STYLE = """
        display:inline-block; margin-top:1.2rem;
        font-family:'Crimson Pro',serif; font-size:0.9rem; font-weight:600;
        letter-spacing:0.06em; color:#c9a458; text-decoration:none;
        border:1px solid rgba(201,164,88,0.4); border-radius:3px;
        padding:5px 18px 6px; transition:background 0.15s, color 0.15s;
      """

def _block_home_langstrip():
    from urllib.parse import quote
    cells = []
    for l in _LANGS:
        href = f"about.html#{_anchor(l)}" if ABOUT else f"dictionary.html?lang={quote(l['name'])}"
        cells.append(f'  <a class="lang-cell" href="{_esc(href)}" style="text-decoration:none;">\n'
                     f'    <span class="ldot" style="background:var(--c-{l["code"]});"></span>\n'
                     f'    <span class="lname">{_esc(l["name"])}</span>\n  </a>')
    return '\n'.join(cells)

def _block_home_map():
    m = (HOME or {}).get('map')
    if not m:
        return ''
    paras = ''.join(f'      <p class="map-desc">\n        {_prose(p)}\n      </p>\n' for p in m.get('text', []))
    credit = f'      <p class="map-credit">{m["credit"]}</p>\n' if m.get('credit') else ''
    more = (f'      <a href="about.html" style="{_MORE_LINK_STYLE}" onmouseover="this.style.background=\'rgba(201,164,88,0.12)\'"\n'
            f'         onmouseout="this.style.background=\'\'"\n      >{m.get("moreLabel", "More →")}</a>\n') if ABOUT else ''
    img = (f'    <div class="map-img-wrap">\n      <img src="{_esc(m["image"])}" alt="{_esc(m.get("imageAlt", ""))}" class="map-img">\n    </div>\n'
           ) if m.get('image') else ''
    return ('<section class="map-section">\n  <div class="map-inner">\n    <div class="map-text">\n'
            f'      <h2 class="map-title">{m.get("title", "")}</h2>\n{paras}{credit}{more}    </div>\n{img}  </div>\n</section>')

def _lang_section_html(l):
    from urllib.parse import quote
    c = (ABOUT or {}).get('languages', {}).get(l['code'], {})
    badge = f' <span class="speaker-badge">{c["badge"]}</span>' if c.get('badge') else ''
    meta = ''.join(f'        <span>{x}</span>\n' for x in c.get('meta', []))
    meta = f'      <div class="lang-meta">\n{meta}      </div>\n' if meta else ''
    paras = ''.join(f'      <p>{_prose(p)}</p>\n' for p in c.get('text', []))
    st = f'style="background:var(--c-{l["code"]});"'
    return (f'    <div class="lang-section" id="{_anchor(l)}" style="border-color:var(--c-{l["code"]});">\n'
            f'      <h3 style="color:var(--c-{l["code"]});">{_esc(l["name"])}{badge}</h3>\n{meta}{paras}'
            f'      <div class="lang-links">\n        <a class="lang-link" href="grammar.html" {st}>Grammar →</a>\n'
            f'        <a class="lang-link" href="dictionary.html?lang={quote(l["name"])}" {st}>Dictionary →</a>\n'
            f'        <a class="lang-link" href="texts.html" {st}>Texts →</a>\n      </div>\n    </div>\n')

def _block_about_sections():
    out = []
    for s in (ABOUT or {}).get('sections', []):
        out.append(f'    <h2 id="{_esc(s["id"])}">{s["title"]}</h2>\n\n')
        ib = ABOUT.get('infobox')
        if s.get('infobox') and ib:
            rows = ''.join(f'        <tr><td>{a}</td><td>{b}</td></tr>\n' for a, b in ib.get('rows', []))
            out.append(f'    <div class="infobox">\n      <table>\n        <caption>{ib.get("caption", "")}</caption>\n{rows}      </table>\n    </div>\n\n')
        for p in s.get('text', []):
            out.append(f'    <p>{_prose(p)}</p>\n\n')
        if s.get('languageSections'):
            out.extend(_lang_section_html(l) + '\n' for l in _LANGS)
    return ''.join(out)

def _block_about_toc():
    out = []
    for s in (ABOUT or {}).get('sections', []):
        out.append(f'      <li><a href="#{_esc(s["id"])}">{s.get("tocLabel", s["title"])}</a></li>\n')
        if s.get('languageSections'):
            out.extend(f'      <li class="sub"><a href="#{_anchor(l)}">{_esc(l["name"])}</a></li>\n' for l in _LANGS)
    return ''.join(out)

def _page_blocks():
    """{{block:name}} in a page: HTML generated from the project's languages and page content."""
    h, ab = HOME or {}, ABOUT or {}
    cards = dict(_DEFAULT_CARDS, **(h.get('cards') or {}))
    intro = h.get('intro') or ['The {languages.count} languages documented here: {languages.list}.']
    footer = PROJECT['footer']
    return {
        'home.byline': h.get('byline', ''),
        'home.intro': '\n'.join(f'<p style="margin-top:1rem;">{_prose(p)}</p>' for p in intro),
        'home.card.grammar': _prose(cards['grammar']), 'home.card.texts': _prose(cards['texts']),
        'home.card.dictionary': _prose(cards['dictionary']),
        'home.langstrip': _block_home_langstrip(), 'home.map': _block_home_map(),
        'about.toc': _block_about_toc(), 'about.sections': _block_about_sections(),
        'about.sidebarmap': (f'<div class="sidebar-map">\n      <img src="{_esc(ab["sidebarImage"])}" alt="{_esc(ab.get("sidebarImageAlt", ""))}">\n    </div>'
                             if ab.get('sidebarImage') else ''),
        'footer': f'<footer>\n  {footer}\n</footer>' if footer else '',
    }

# ── The project's wording, and what the pages are told about it ──────────────
def _page_tokens():
    """{{project.name}} and the like, filled in when an HTML page is served."""
    n = len(PROJECT['languages'])
    t = {'project.name': PROJECT['name'], 'project.titleSuffix': PROJECT['titleSuffix'],
         'project.homeTitle': PROJECT['homeTitle'], 'project.orthographyName': _DEFAULT_CORR['name']}
    for k, v in PROJECT['nav'].items():
        t[f'project.nav.{k}'] = str(v).replace('{languages}', f"{n} Language{'s' if n != 1 else ''}").replace('{n}', str(n))
    t.setdefault('project.nav.references', 'References')
    ab = ABOUT or {}
    t['project.about.tabTitle'] = ab.get('tabTitle', 'About')
    return t

def _serve_page(filename):
    with open(filename, encoding='utf-8') as f:
        text = f.read()
    for k, v in _page_blocks().items():
        text = text.replace('{{block:' + k + '}}', v)
    for k, v in _page_tokens().items():
        text = text.replace('{{' + k + '}}', _esc(v, quote=False))
    for k in ('title', 'subtitle'):                       # the about page's heading (HTML allowed)
        text = text.replace('{{project.about.' + k + '}}', (ABOUT or {}).get(k, ''))
    return Response(text, mimetype='text/html')

@app.route('/project.js')
def project_js():
    """What every page needs to know about the project: its name and its languages (with the colours currently in
    force). Loaded first, like /colors.js. The pages build their language lists from it."""
    colors = _colors_current()
    pub = {'id': PROJECT.get('id', ''), 'name': PROJECT['name'], 'headwordLanguage': PROJECT['headwordLanguage'],
           'recordings': PROJECT['recordings'],
           'languages': [{'code': l['code'], 'name': l['name'], 'abbr': l['abbr'], 'color': colors[l['code']],
                          'aliases': l['aliases']} for l in _LANGS]}
    js = ('window.DBT_PROJECT=' + json.dumps(pub, ensure_ascii=False) + ';\n'
          '(function(P){var L=P.languages;window.DBT={project:P,langs:L,codes:L.map(function(l){return l.code}),'
          'names:L.map(function(l){return l.name}),byCode:{},byName:{},nameByCode:{},codeByName:{},abbrByName:{},abbrByCode:{},'
          'colorByName:{},colorByCode:{},nameFromFileCode:{},codeFromFileCode:{}};'
          'L.forEach(function(l){var D=window.DBT;D.byCode[l.code]=l;D.byName[l.name]=l;D.nameByCode[l.code]=l.name;D.codeByName[l.name]=l.code;'
          'D.abbrByName[l.name]=l.abbr;D.abbrByCode[l.code]=l.abbr;D.colorByName[l.name]=l.color;D.colorByCode[l.code]=l.color;'
          '[l.code].concat(l.aliases).forEach(function(c){D.nameFromFileCode[c]=l.name;D.codeFromFileCode[c]=l.code;});});'
          'if(L.length===1)document.documentElement.classList.add("one-language");})(window.DBT_PROJECT);\n')
    return Response(js, mimetype='application/javascript', headers={'Cache-Control': 'no-cache'})

# ── Static files: only the site's own pages and images, never code or data ────
_PUBLIC_EXT = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.woff', '.woff2', '.ttf'}

@app.route('/')
def index():
    return _serve_page('index.html')


@app.route('/<path:filename>')
def static_files(filename):
    target = PROJECT['redirects'].get(filename)          # an old page name that now lives under another one
    if target:
        return redirect('/' + target, code=301)
    if filename == 'about.html' and ABOUT is None:      # a project without an about page
        abort(404)
    if filename == 'setup.html':                        # reached only through /setup, and only before the setup
        abort(404)
    # Files directly in the site folder, with a public extension. Not source code (.py), not data (.xml, .json,
    # .md), not the data folders (uploads, project, ...), not hidden files.
    if '/' in filename or filename.startswith('.') or os.path.splitext(filename)[1].lower() not in _PUBLIC_EXT:
        abort(404)
    if not os.path.isfile(filename):
        abort(404)
    if filename.endswith('.html'):
        return _serve_page(filename)
    return send_from_directory('.', filename)


# ── First-run setup ────────────────────────────────────────────────────────────
# A new linguist starts here: no code to edit. The page asks for the project's name, its languages (or the small
# starter example) and the author's password, then writes project/project.json and restarts the server.
# It is protected by a one-time code printed in the server's console, so that nobody who reaches the site
# before its owner can take it over.
SETUP_CODE = None
if SETUP_MODE:
    import secrets as _secrets
    SETUP_CODE = _secrets.token_urlsafe(9)
    print("\n  ┌─────────────────────────────────────────────────────────────────────┐\n"
          "  │  This DBT has not been set up yet.                                  │\n"
          "  │  Open the site in your browser and fill in the setup page.          │\n"
          f"  │  Setup code (asked there):  {SETUP_CODE:<39}│\n"
          "  └─────────────────────────────────────────────────────────────────────┘\n", flush=True)

STARTER_DIR = 'starter'
_PALETTE = ['#2e5c8a', '#c07820', '#922810', '#267040', '#5c2878', '#0e7c86', '#a0407a', '#6b6b1a', '#b04a2a', '#3a5f3a']

@app.before_request
def _setup_gate():
    if not SETUP_MODE or request.path in ('/setup', '/api/setup'):
        return None
    if request.path.startswith('/api/'):
        return jsonify({'setup': True, 'error': 'This DBT has not been set up yet.'}), 503
    return redirect('/setup')

@app.route('/setup')
def setup_page():
    if not SETUP_MODE:
        abort(404)
    return send_from_directory('.', 'setup.html')

def _clean_setup(data):
    """Validate what the setup page sent. Returns (name, languages, mode, error)."""
    name = str(data.get('name') or '').strip()
    if not name or len(name) > 80:
        return None, None, None, 'Give the project a name (up to 80 characters).'
    mode = 'starter' if data.get('mode') == 'starter' else 'own'
    langs = []
    if mode == 'own':
        raw = data.get('languages')
        if not isinstance(raw, list) or not 1 <= len(raw) <= 40:
            return None, None, None, 'Add at least one language.'
        seen = set()
        for i, l in enumerate(raw, 1):
            lname = str(l.get('name') or '').strip()
            code = str(l.get('code') or '').strip().lower()
            abbr = str(l.get('abbr') or '').strip() or lname[:3]
            color = str(l.get('color') or '').strip().lower()
            if not lname:
                return None, None, None, f'Language {i} needs a name.'
            if not re.fullmatch(r'[a-z][a-z0-9_-]{0,11}', code):
                return None, None, None, f'The code of "{lname}" must be lower case letters and digits, starting with a letter (e.g. "mwo").'
            if code in seen:
                return None, None, None, f'The code "{code}" is used for two languages.'
            seen.add(code)
            if not re.fullmatch(r'#[0-9a-f]{6}', color):
                color = _PALETTE[(i - 1) % len(_PALETTE)]
            langs.append({'code': code, 'name': lname, 'abbr': abbr[:8], 'color': color, 'aliases': []})
    problem = security.validate_new_password(data.get('password'))
    if problem:
        return None, None, None, problem
    return name, langs, mode, None

def _restart_soon():
    """Restart the server so that it starts with the new project. Returns 'auto', or 'manual' when this
    server was not started with `python app.py` (a WSGI server: the owner restarts it)."""
    if __name__ != '__main__':
        return 'manual'
    import threading, time
    def go():
        time.sleep(1.2)
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':      # the debug reloader restarts when a source file changes
            os.utime(os.path.abspath(sys.argv[0]), None)
        else:
            for fd in range(3, 256):                          # the listening socket must not survive the restart
                try:
                    os.set_inheritable(fd, False)
                except OSError:
                    pass
            os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=go, daemon=True).start()
    return 'auto'

@app.route('/api/setup', methods=['POST'])
def api_setup():
    if not SETUP_MODE:
        abort(404)
    import hmac, shutil
    data = request.get_json(silent=True) or {}
    key = 'setup:' + (request.remote_addr or '?')
    refused = _too_many(key)
    if refused:
        return refused
    if not hmac.compare_digest(str(data.get('setupCode') or '').strip().encode(), SETUP_CODE.encode()):
        _LOGIN_LIMITER.fail(key)
        return jsonify({'ok': False, 'error': 'The setup code is not right. It is printed in the console of the server when it starts.'}), 403
    name, langs, mode, error = _clean_setup(data)
    if error:
        return jsonify({'ok': False, 'error': error}), 400
    try:
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'project'
        if mode == 'starter':
            with open(os.path.join(STARTER_DIR, 'project.json'), encoding='utf-8') as f:
                proj = json.load(f)
        else:
            proj = {'schema': 1, 'languages': langs, 'headwordLanguage': langs[0]['code'], 'recordings': {},
                    'nav': {'home': '', 'about': '', 'dictionary': 'Dictionary · {languages}', 'grammar': 'Grammar · {languages}', 'texts': 'Texts'},
                    'latex': {'title': f'Grammar of {name}', 'subtitle': '', 'author': ''}, 'footer': '', 'redirects': {}}
        proj.update({'id': slug, 'name': name, 'titleSuffix': name, 'homeTitle': f'Digital Boasian Trilogy: {name}'})
        if mode == 'starter':
            proj['latex']['title'] = f'Grammar of {name}'
        for d in ('grammar', 'texts', 'images', 'pages'):
            os.makedirs(os.path.join('project', d), exist_ok=True)
        with open(os.path.join('project', 'orthography.json'), 'w', encoding='utf-8') as f:
            json.dump({'name': '', 'longVowelDoubling': True, 'rows': [], 'previousDefaults': []}, f, indent=1)
        if mode == 'own':                                          # an empty dictionary, ready for the first entry
            src = ''.join(f'      <Langue rôle="source" code="{l["code"]}">{_esc(l["name"])}</Langue>\n' for l in langs)
            with open(os.path.join('project', 'dictionary.xml'), 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<RessourceLexicale>\n  <InformationsGlobales>\n'
                        f'    <Titre>{_esc(name)}</Titre>\n    <Auteurs></Auteurs>\n    <Langues>\n{src}'
                        '      <Langue rôle="cible" code="eng">English</Langue>\n    </Langues>\n  </InformationsGlobales>\n'
                        '  <Dictionnaire>\n  </Dictionnaire>\n</RessourceLexicale>\n')
        if mode == 'starter':
            shutil.copyfile(os.path.join(STARTER_DIR, 'dictionary.xml'), os.path.join('project', 'dictionary.xml'))
            for sub_dir in ('grammar', 'texts', 'pages'):
                for fn in os.listdir(os.path.join(STARTER_DIR, sub_dir)):
                    shutil.copyfile(os.path.join(STARTER_DIR, sub_dir, fn), os.path.join('project', sub_dir, fn))
            shutil.copyfile(os.path.join(STARTER_DIR, 'references.json'), os.path.join('project', 'references.json'))
        else:                                                      # an empty list of references, ready for the first one
            with open(os.path.join('project', 'references.json'), 'w', encoding='utf-8') as f:
                json.dump({'references': []}, f, indent=1)
        security.set_password(data['password'])
        with open(PROJECT_PATH, 'w', encoding='utf-8') as f:       # written last: it is what ends the setup
            json.dump(proj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Could not write the project: {e}'}), 500
    return jsonify({'ok': True, 'restart': _restart_soon()})

_auto_orthography()
_auto_ipa()

if not SETUP_MODE and not security.password_configured():
    print("\n  !! No author password is set, so nobody can log in as the author.\n"
          "     Set one (it is stored hashed in instance/, never in the code):   python app.py --set-password\n")
elif security.password_source() == 'environment':
    print("  Author password: read from the AUTHOR_PASSWORD environment variable.")

# ── Dev entry point ───────────────────────────────────────────

if __name__ == '__main__':
    # PORT and DBT_DEBUG=0 let the test harness (tests/run_tests.py) start the site on a free port without the reloader
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DBT_DEBUG', '1') != '0'
    print(f"{PROJECT['name']} — starting on http://localhost:{port}")
    app.run(debug=debug, port=port, host='0.0.0.0')
