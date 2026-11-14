"""
Phonological charts for the grammar: one chart of consonants and one of vowels, whose rows and columns the author decides, and
an inventory for each language of the project, merged in a single chart.

In a grammar section a chart is a fenced block that the editor writes (the author never has to type it):

    ```phonotable
    {"kind": "consonants", "caption": "The consonant phonemes",
     "columns": ["Bilabial", "Alveolar", "Velar"], "rows": ["Plosive", "Nasal"],
     "inventory": {"drg": {"Plosive": {"Bilabial": "p b", "Alveolar": "t d"}, "Nasal": {"Bilabial": "m"}}}}
    ```

Each sound is followed by a small coloured tag with the abbreviation of the language(s) that have it (NUM, DRG ...), and the background of
each cell takes the colour(s) of the languages involved. A sound found in every language shown has no tag. Over a sound the reader sees
a box with its description (place and manner of articulation, as the author typed it), a button that plays it and a link to PHOIBLE: they
are in the optional "segments" of the definition ({"p": {"description": "...", "audio": "p.mp3", "phoible": "https://phoible.org/..."}}).
A chart of vowels with long vowels (iː) is two tables, short and long, under one caption and one legend.
In LaTeX the chart is split into one plain table for each language.

A third kind, "lexical", is a comparative table of words (the independent personal pronouns, the numerals ...): the same rows and columns, and in each
cell the word of each language. A word found in every language of the table is shown in black, one found in only some is followed by the tags of
those languages, exactly as for the sounds (but no cell is tinted). A tilde separates a word from its variant (`ni ~ nē`); each part is a link to
its entry of the dictionary, as {{entry: ID}} is (`na@ID` links to that entry when the word alone is not enough).

Nothing here knows a language or the web framework: the languages (code, name, colour) are given.
"""
import html as _html
import json
import re
import unicodedata
from urllib.parse import quote as _urlquote

import captions as _cap

KINDS = ('consonants', 'vowels', 'lexical')

# What the author starts from (and may change: add, remove, reorder). The IPA order of places and manners.
DEFAULT_AXES = {
    'consonants': {
        'columns': ['Bilabial', 'Labiodental', 'Dental', 'Alveolar', 'Postalveolar', 'Retroflex', 'Palatal', 'Velar', 'Uvular', 'Pharyngeal', 'Glottal'],
        'rows': ['Plosive', 'Nasal', 'Trill', 'Tap or flap', 'Fricative', 'Lateral fricative', 'Approximant', 'Lateral approximant'],
    },
    'vowels': {
        'columns': ['Front', 'Central', 'Back'],
        'rows': ['Close', 'Near-close', 'Close-mid', 'Mid', 'Open-mid', 'Near-open', 'Open'],
    },
    'lexical': {'columns': [], 'rows': []},              # the author's own: nothing is suggested
}
MAX_AXIS, MAX_LABEL, MAX_PHONEMES, MAX_PHONEME, MAX_BLOCK = 40, 60, 24, 16, 200_000
MAX_SEGMENTS, MAX_DESCRIPTION, MAX_LINK = 400, 200, 400
MAX_FORM, MAX_PARTS, MAX_UNITS = 60, 4, 6                       # a word, the parts of a word with its variants, the words of a cell (lexical tables)
_ENTRY_ID = re.compile(r'[A-Za-z0-9_.:\-]{1,80}')
AUDIO_BASE = 'audio/'                                       # where the page asks for an audio file (the server serves project/audio there)
_AUDIO_FILE = re.compile(r'[^\s\\/:*?"<>|][^\s\\:*?"<>|]*\.(?:mp3|ogg|oga|opus|wav|m4a|aac|flac|webm)', re.I)
_URL = re.compile(r'https?://[^\s<>"\']+', re.I)

BLOCK_RE = re.compile(r'^[ \t]*```[ \t]*phonotable[ \t]*\r?\n(.*?)\r?\n[ \t]*```[ \t]*\r?$', re.S | re.M)


def _nfc(s):
    return unicodedata.normalize('NFC', str(s if s is not None else ''))


def _label(s):
    return re.sub(r'\s+', ' ', _nfc(s)).strip()[:MAX_LABEL]


def _axis(values):
    """A list of labels: stripped, no empty one, no two the same (the case does not count), at most MAX_AXIS."""
    out, seen = [], set()
    for v in (values if isinstance(values, list) else []):
        if not isinstance(v, str):
            continue
        l = _label(v)
        if l and l.lower() not in seen and len(out) < MAX_AXIS:
            seen.add(l.lower()); out.append(l)
    return out


def phonemes(text):
    """The sounds written in a cell: separated by spaces (or commas), each at most MAX_PHONEME characters, no repeat."""
    out = []
    for p in re.split(r'[\s,;]+', _nfc(text)):
        if p and len(p) <= MAX_PHONEME and p not in out and len(out) < MAX_PHONEMES:
            out.append(p)
    return out


def lex_parts(unit):
    """The parts of a word of a lexical table: [(text, entry id or '')]. The first is the entry, the others its variants (`ni ~ nē`);
    `form@ID` names the entry of the dictionary by its identifier."""
    out = []
    for raw in _nfc(unit).split('~'):
        text, _at, ident = raw.partition('@')
        text, ident = re.sub(r'\s+', ' ', text).strip()[:MAX_FORM], ident.strip()
        if text and len(out) < MAX_PARTS:
            out.append((text, ident if _ENTRY_ID.fullmatch(ident) else ''))
    return out


def lex_unit(unit):
    """A word as it is kept: its parts, joined with ' ~ ' (the identifier, if any, after the part it belongs to)."""
    return ' ~ '.join(t + ('@' + i if i else '') for t, i in lex_parts(unit))


def lex_text(unit):
    """A word as the reader reads it (no identifiers)."""
    return ' ~ '.join(t for t, _i in lex_parts(unit))


def lex_units(text):
    """The words written in a cell of a lexical table: separated by semicolons, at most MAX_UNITS, no repeat."""
    out = []
    for u in _nfc(text).split(';'):
        u = lex_unit(u)
        if u and u not in out and len(out) < MAX_UNITS:
            out.append(u)
    return out


def units(kind, text):
    """What a cell holds: the sounds (consonants, vowels) or the words (lexical)."""
    return lex_units(text) if kind == 'lexical' else phonemes(text)


def entries_of(spec):
    """[(row, column, language code, word, identifier)]: the ENTRY of every word of a lexical table (the first part: a variant is not an entry)."""
    out = []
    for code, by_row in spec.get('inventory', {}).items():
        for r in spec['rows']:
            for c in spec['columns']:
                for u in lex_units(by_row.get(r, {}).get(c, '')):
                    t, i = lex_parts(u)[0]
                    out.append((r, c, code, t, i))
    return out


def _link(value):
    """A PHOIBLE address: http(s) only ("phoible.org/…" gets https://); anything else is not kept."""
    v = str(value or '').strip()
    if re.match(r'(?i)(www\.)?phoible\.org(/|$)', v):
        v = 'https://' + v
    return v[:MAX_LINK] if len(v) <= MAX_LINK and _URL.fullmatch(v) else ''


def _audio(value):
    """An audio file: the name of a file of the audio folder (an audio extension, no .. and no hidden part), or an http(s) address."""
    v = str(value or '').strip()
    if len(v) > MAX_LINK:
        return ''
    if _URL.fullmatch(v):
        return v
    parts = v.split('/')
    if v and _AUDIO_FILE.fullmatch(parts[-1]) and all(x and not x.startswith('.') for x in parts):
        return v
    return ''


def audio_url(value):
    """The address the page uses for the audio of a sound ('' if none)."""
    v = _audio(value)
    return v if _URL.fullmatch(v) or not v else AUDIO_BASE + _urlquote(v, safe='/')


def clean_segments(raw, sounds):
    """{sound: {description, audio, phoible}} for the sounds in `sounds` only; empty fields and entries are left out."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for p, d in raw.items():
        p = _nfc(p)
        if p not in sounds or not isinstance(d, dict) or len(out) >= MAX_SEGMENTS:
            continue
        desc = re.sub(r'\s+', ' ', _nfc(d.get('description') if isinstance(d.get('description'), str) else '')).strip()[:MAX_DESCRIPTION]
        item = {k: v for k, v in (('description', desc), ('audio', _audio(d.get('audio'))), ('phoible', _link(d.get('phoible')))) if v}
        if item:
            out[p] = item
    return out


def segment_problems(raw, cleaned):
    """Messages about what the author typed in the sounds that was not kept (an address that is not one, a file that is not audio)."""
    out = []
    if not isinstance(raw, dict):
        return out
    for p, d in raw.items():
        if p not in cleaned.get('segments', {}) and not (isinstance(d, dict) and any(str(d.get(k) or '').strip() for k in ('audio', 'phoible'))):
            continue
        if not isinstance(d, dict) or _nfc(p) not in {s for by_row in cleaned['inventory'].values() for by_col in by_row.values() for t in by_col.values() for s in t.split(' ')}:
            continue
        kept = cleaned.get('segments', {}).get(_nfc(p), {})
        if str(d.get('audio') or '').strip() and 'audio' not in kept:
            out.append('%s: the audio must be the name of a file (ending in .mp3, .ogg, .wav …) or an address that starts with http:// or https://.' % p)
        if str(d.get('phoible') or '').strip() and 'phoible' not in kept:
            out.append('%s: the PHOIBLE link must be an address that starts with https:// (or phoible.org/…).' % p)
    return out


def clean(spec, language_codes=None):
    """A definition as it will be kept: (spec, None), or (None, why not). Rows, columns and sounds are normalised; an inventory of a
    language that is not one of `language_codes`, or in a row or column that does not exist, is dropped."""
    if not isinstance(spec, dict):
        return None, 'The definition of the table is not an object.'
    kind = spec.get('kind')
    if kind not in KINDS:
        return None, 'The kind of the table must be "consonants" or "vowels".'
    cols, rows = _axis(spec.get('columns')), _axis(spec.get('rows'))
    if not cols or not rows:
        return None, 'The table needs at least one row and one column.'
    inv = {}
    raw = spec.get('inventory') if isinstance(spec.get('inventory'), dict) else {}
    cmap, rmap = {c.lower(): c for c in cols}, {r.lower(): r for r in rows}
    for code, by_row in raw.items():
        if not isinstance(code, str) or not isinstance(by_row, dict) or (language_codes is not None and code not in language_codes):
            continue
        for r, by_col in by_row.items():
            r2 = rmap.get(_label(r).lower()) if isinstance(r, str) else None
            if r2 is None or not isinstance(by_col, dict):
                continue
            for c, text in by_col.items():
                c2 = cmap.get(_label(c).lower()) if isinstance(c, str) else None
                ph = units(kind, text) if isinstance(text, str) else []
                if c2 is not None and ph:
                    inv.setdefault(code, {}).setdefault(r2, {})[c2] = '; '.join(ph) if kind == 'lexical' else ' '.join(ph)
    sounds = {p for by_row in inv.values() for by_col in by_row.values() for t in by_col.values() for p in t.split(' ')} if kind != 'lexical' else set()
    segments = clean_segments(spec.get('segments'), sounds)          # (a lexical table has none)
    # the caption is the text shown after "Table 3 –": there is no title (an old block's title is read as its caption)
    caption = _cap.caption_text(spec['caption'] if isinstance(spec.get('caption'), str) else spec.get('title') if isinstance(spec.get('title'), str) else '')
    # the label is the short name that lets the text refer to the chart: {{ref: name}}
    out = {'kind': kind, 'caption': caption, 'label': _cap.clean_label(spec['label'] if isinstance(spec.get('label'), str) else ''), 'columns': cols, 'rows': rows, 'inventory': inv, 'segments': segments}
    if kind == 'lexical':                                   # the part of speech of the entries the words are links to (so that na, the pronoun, is not the article na)
        out['pos'] = re.sub(r'\s+', ' ', _nfc(spec.get('pos') if isinstance(spec.get('pos'), str) else '')).strip()[:30]
    return out, None


def parse_block(text):
    """The definition in a fenced block -> (spec, None) or (None, why not)."""
    if len(text) > MAX_BLOCK:
        return None, 'The table is too large.'
    try:
        return json.loads(text), None
    except ValueError as e:
        return None, 'The definition of the table could not be read (%s).' % str(e).split(':')[0]


def merge(spec, languages):
    """The chart as it is shown: {'languages': the codes that have an inventory, 'cells': {row: {column: [{'p': sound, 'langs': [codes]}]}}}.
    Within a cell the sounds are in the order in which they were typed, language after language (the project's order of languages)."""
    order = [l['code'] for l in languages]
    inv = spec['inventory']
    present = [c for c in order if c in inv]
    cells = {}
    for r in spec['rows']:
        for c in spec['columns']:
            seen, found = [], {}
            for code in present:
                for p in units(spec['kind'], inv[code].get(r, {}).get(c, '')):
                    if p not in found:
                        seen.append(p); found[p] = []
                    found[p].append(code)
            if seen:
                cells.setdefault(r, {})[c] = [{'p': p, 'langs': found[p]} for p in seen]
    return {'languages': present, 'cells': cells}


def present_languages(spec, languages):
    """The languages (as the project lists them, in its order) that have at least one sound in the chart."""
    inv = spec.get('inventory', {})
    return [l for l in languages if any(units(spec['kind'], cell) for row in inv.get(l['code'], {}).values() for cell in row.values())]


def caption_names(spec, languages):
    """The names that {language} stands for on the website: the languages of the chart (all the project's if the chart has no sound yet)."""
    return [l['name'] for l in (present_languages(spec, languages) or languages)]


def _hex(color):
    c = str(color or '').strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', c):
        return c.lower()
    if re.fullmatch(r'#[0-9a-fA-F]{3}', c):
        return '#' + ''.join(ch * 2 for ch in c[1:]).lower()
    return '#808080'


SHORT_LABEL, LONG_LABEL = 'Short', 'Long'                   # the corner of the two tables of a chart of vowels that has long ones


def is_long(sound):
    """A long vowel: written with the length mark (iː)."""
    return sound.endswith('\u02d0')


def _stripes(colors, alpha='2e'):
    """The background of a cell: the colours of the languages involved, side by side, light enough for the text to stay readable."""
    n = len(colors)
    return 'linear-gradient(90deg,' + ','.join('%s%s %g%% %g%%' % (c, alpha, round(100 * i / n, 2), round(100 * (i + 1) / n, 2)) for i, c in enumerate(colors)) + ')'


def render_html(spec, languages, number=None, lab=None, anchors=True, resolver=None):
    """The chart as HTML, with its caption above it ("Table 3 – …"; the number is given by the caller). The text of the table is escaped;
    the colours and the tags come from the languages of the project, never from the table. With one language there are no tags and no tints.
    For a lexical table `resolver(code, word, id, pos)` -> (entry id, title) or None says where a word is in the dictionary (each part of a word is a link
    to its entry); without it nothing is a link."""
    e = _html.escape
    m = merge(spec, languages)
    present, by_code = m['languages'], {l['code']: l for l in languages}
    several = len(present) > 1
    seg = spec.get('segments') or {}
    def tag(code, hidden):
        l = by_code[code]
        abbr = str(l.get('abbr') or l['code']).upper()
        return (f'<span class="ph-tag" data-lang="{e(code)}" style="--tag:{_hex(l.get("color"))}" title="{e(l["name"])}"{" hidden" if hidden else ""}>{e(abbr)}</span>')
    lexical = spec['kind'] == 'lexical'
    def word(item):
        """A word of a lexical table: its parts (a link where the dictionary has the entry), separated by a tilde, then the tags."""
        langs = item['langs']
        shared = len(langs) == len(present)
        shown = []
        for k, (text, ident) in enumerate(lex_parts(item['p'])):
            hit = None
            for code in langs:                                     # a word shared by several languages: the first in which it is an entry
                hit = resolver(code, text, ident, spec.get('pos', '')) if resolver else None
                if hit:
                    break
            if hit:
                shown.append(f'<a class="lx-link" href="dictionary.html#{e(hit[0])}"' + (f' title="{e(hit[1])}"' if hit[1] else '') + f'>{e(text)}</a>')
            else:
                shown.append(f'<span class="lx-plain">{e(text)}</span>')
        tags = ''.join(tag(c, shared) for c in langs) if several else ''
        return f'<span class="ph" data-langs="{e(" ".join(langs))}"><span class="lx-form">{' <span class="lx-tilde">~</span> '.join(shown)}</span>{tags}</span>'
    def sound(item):
        if lexical:
            return word(item)
        langs, s = item['langs'], seg.get(item['p'], {})
        shared = len(langs) == len(present)                     # a sound of every language needs no tag
        tags = ''.join(tag(c, shared) for c in langs) if several else ''
        attrs = f'data-seg="{e(item["p"])}" data-desc="{e(s.get("description", ""))}" data-audio="{e(audio_url(s.get("audio")))}" data-phoible="{e(s.get("phoible", ""))}"'
        return f'<span class="ph" data-langs="{e(" ".join(langs))}"><span class="ph-seg" {attrs}>{e(item["p"])}</span>{tags}</span>'
    def table(label, keep):
        """One table: `keep` says which sounds of a cell belong to it. A cell is tinted only with the languages of the sounds that NOT every
        language has: where everything is shared there is nothing to tell apart, so the cell stays plain."""
        head = ''.join(f'<th scope="col">{e(c)}</th>' for c in spec['columns'])
        body = ''
        for r in spec['rows']:
            tds = ''
            for c in spec['columns']:
                items = [i for i in m['cells'].get(r, {}).get(c, []) if keep(i['p'])]
                used = [code for code in present if any(code in i['langs'] for i in items if len(i['langs']) < len(present))]
                style = f' style="--cell-bg:{_stripes([_hex(by_code[x].get("color")) for x in used])}"' if several and used and not lexical else ''
                tds += f'<td class="{"lx-cell" if lexical else "ph-cell"}" data-langs="{e(" ".join(used))}"{style}>' + ' '.join(sound(i) for i in items) + '</td>'
            body += f'<tr><th scope="row">{e(r)}</th>{tds}</tr>'
        return f'<div class="phono-scroll"><table class="phono"><thead><tr><th class="corner">{e(label)}</th>{head}</tr></thead><tbody>{body}</tbody></table></div>'
    # a chart of vowels that has long vowels (a sound ending in the length mark) is two tables, short on the left and long on the right, with one legend
    has_long = spec['kind'] == 'vowels' and any(is_long(i['p']) for cells in m['cells'].values() for items in cells.values() for i in items)
    tables = (f'<div class="phono-pair">{table(SHORT_LABEL, lambda s: not is_long(s))}{table(LONG_LABEL, is_long)}</div>' if has_long else table('', lambda s: True))
    legend = ''
    if several and lexical:
        boxes = ' '.join(f'<label class="lg"><input type="checkbox" checked data-lang="{e(c)}" data-color="{_hex(by_code[c].get("color"))}">'
                         f'<span class="lg-name">{e(by_code[c]["name"])}</span> <span class="lg-tag" style="--tag:{_hex(by_code[c].get("color"))}">{e(str(by_code[c].get("abbr") or c).upper())}</span></label>' for c in present)
        legend = (f'<div class="phono-legend"><span class="pl-title">Languages shown:</span> {boxes}'
                  '<div class="pl-note">The tag after a word says which language has it; a word without a tag is the same in all the languages shown. A tilde separates a word from its variant. '
                  'Untick a language to leave its words out. Click a word to go to its entry of the dictionary.</div></div>')
    elif several:                                             # the legend is a set of check boxes: the reader chooses the languages to show
        boxes = ' '.join(f'<label class="lg"><input type="checkbox" checked data-lang="{e(c)}" data-color="{_hex(by_code[c].get("color"))}">'
                         f'<span class="lg-name">{e(by_code[c]["name"])}</span> <span class="lg-tag" style="--tag:{_hex(by_code[c].get("color"))}">{e(str(by_code[c].get("abbr") or c).upper())}</span></label>' for c in present)
        legend = (f'<div class="phono-legend"><span class="pl-title">Languages shown:</span> {boxes}'
                  '<div class="pl-note">The tag after a sound says which language has it; a cell that holds a sound not found in all the languages shown is tinted with the colours of the languages that have it, and what all of them share stays plain; '
                  'a sound without a tag is found in all the languages shown. Untick a language to leave its sounds out. Hover over a sound to read about it.</div></div>')
    ident = f' id="{e(_cap.anchor("table", spec["label"]))}" data-label="{e(spec["label"])}"' if spec.get('label') and anchors else ''   # a preview has no anchor: the page must not have the id twice
    return (f'<figure class="phonotable" data-kind="{e(spec["kind"])}"{ident}>{_cap.caption_html("table", number, _cap.fill_language(spec["caption"], caption_names(spec, languages), lab), lab)}'
            f'{tables}{legend}</figure>')


_LATEX_SPECIAL = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}


def _tex(s):
    return ''.join(_LATEX_SPECIAL.get(ch, ch) for ch in str(s))


def _latex_table(caption, columns, rows, cells, extra=''):
    """One LaTeX table: the caption above, then `extra` (labels), then the sounds in the IPA font (\\ipafont is in the preamble of the export)."""
    cols = 'l|' + '|'.join('c' for _ in columns)
    body = [f'{_tex(r)} & ' + ' & '.join(cells.get((r, c), '') for c in columns) + r' \\' for r in rows]
    head = ' & ' + ' & '.join(_tex(c) for c in columns) + r' \\'
    return ('\\begin{table}[ht]\n\\centering\n\\caption{%s}\n%s{\\ipafont\\resizebox{\\linewidth}{!}{%%\n\\begin{tabular}{%s}\n\\toprule\n%s\n\\midrule\n%s\n\\bottomrule\n\\end{tabular}}}\n\\end{table}\n'
            % (caption, extra, cols, head, '\n'.join(body)))


def render_latex(spec, languages, render_text=None, lab=None):
    """The chart for LaTeX. A chart with the sounds of several languages is split into one table for each language (black, the rows and columns
    that are empty for it left out): they share the number of the chart and are lettered, Table 1a, 1b ... The caption of each has its language:
    {language} is replaced by its name, or, if the caption has no {language}, " (name)" is added. A chart with one language is one table, numbered
    as usual. `render_text` makes a caption safe for LaTeX (default: escaping), so that a caption can hold references."""
    render_text = render_text or _tex
    present = present_languages(spec, languages)
    label = spec.get('label') or ''
    lexical = spec['kind'] == 'lexical'
    sound = (lambda p: _tex(lex_text(p))) if lexical else (lambda p: _tex(p))
    sep = '; ' if lexical else ' '
    if len(present) <= 1:                                        # not split: as it is, with the name of its language if the caption asks for it
        caption = _cap.fill_language(spec['caption'], [l['name'] for l in (present or languages)], lab)
        cells = {}
        for l in present:
            for r in spec['rows']:
                for c in spec['columns']:
                    cells[(r, c)] = sep.join(sound(p) for p in units(spec['kind'], spec['inventory'][l['code']].get(r, {}).get(c, '')))
        return _latex_table(render_text(caption), spec['columns'], spec['rows'], cells, ('\\label{tab:%s}\n' % label) if label else '')
    out = ['\\tabgroupstart']
    for k, l in enumerate(present):
        inv = spec['inventory'][l['code']]
        rows = [r for r in spec['rows'] if any(units(spec['kind'], inv.get(r, {}).get(c, '')) for c in spec['columns'])]
        cols = [c for c in spec['columns'] if any(units(spec['kind'], inv.get(r, {}).get(c, '')) for r in rows)]
        cells = {(r, c): sep.join(sound(p) for p in units(spec['kind'], inv.get(r, {}).get(c, ''))) for r in rows for c in cols}
        base = spec['caption']
        caption = base.replace(_cap.LANGUAGE, l['name']) if _cap.LANGUAGE in base else (f"{base} ({l['name']})" if base.strip() else l['name'])
        extra = ''
        if label:                                                # tab:L:code is this table, tab:L (the number) and tab:L:first / tab:L:last the group
            extra += '\\label{tab:%s:%s}\n' % (label, _cap.clean_label(l['code']))
            if k == 0:
                extra += '\\labelas{tab:%s}{\\arabic{table}}\n\\label{tab:%s:first}\n' % (label, label)
            if k == len(present) - 1:
                extra += '\\labelas{tab:%s:last}{\\alph{tabpart}}\n' % label
        if k:
            out.append('\\tabgroupnext')
        out.append(_latex_table(render_text(caption), cols, rows, cells, extra))
    out.append('\\tabgroupend')
    return '\n'.join(out) + '\n'


# ── in a section: lift the blocks out before Markdown, put the charts in after ──
def extract(md_text):
    """The Markdown with each fenced chart replaced by a marker on a line of its own, and the texts of the blocks."""
    blocks = []
    def take(m):
        blocks.append(m.group(1))
        return '\n\nPHONOTABLEXZ%dZX\n\n' % (len(blocks) - 1)
    return BLOCK_RE.sub(take, md_text), blocks


def render_block(text, languages, fmt='html', number=None, lab=None, render_text=None, resolver=None):
    """One fenced block -> its chart; if it cannot be read, a message in its place (never an exception)."""
    spec, err = parse_block(text)
    if spec is not None:
        spec, err = clean(spec, {l['code'] for l in languages})
    if spec is None:
        return ('<div class="shortcode-error">Phonological table: %s</div>' % _html.escape(err)) if fmt == 'html' else '%% phonological table: %s\n' % err.replace('\n', ' ')
    return render_html(spec, languages, number, lab, resolver=resolver) if fmt == 'html' else render_latex(spec, languages, render_text, lab)


def list_charts(blocks, languages):
    """[(label, caption, parts)] of the blocks that are charts that can be shown, in order: what the grammar can refer to. The caption is the one
    the website shows ({language} filled); the parts are the codes of the languages that the exports give a table of their own, none if the chart
    is not split (fewer than two languages)."""
    codes, out = {l['code'] for l in languages}, []
    for b in blocks:
        spec = parse_block(b)[0]
        spec = clean(spec, codes)[0] if spec is not None else None
        if spec is not None:
            present = present_languages(spec, languages)
            out.append((spec['label'], _cap.fill_language(spec['caption'], caption_names(spec, languages)), [l['code'] for l in present] if len(present) > 1 else []))
    return out


def lexical_specs(blocks, languages):
    """The lexical tables among the blocks of a section, cleaned (what the dictionary may be asked about)."""
    codes, out = {l['code'] for l in languages}, []
    for b in blocks:
        spec = parse_block(b)[0]
        spec = clean(spec, codes)[0] if spec is not None else None
        if spec is not None and spec['kind'] == 'lexical':
            out.append(spec)
    return out


def count_valid(blocks, languages):
    """How many of the blocks are charts that can be shown (so that will have a number)."""
    codes = {l['code'] for l in languages}
    return sum(1 for b in blocks if parse_block(b)[0] is not None and clean(parse_block(b)[0], codes)[0] is not None)


def put_back(rendered, blocks, languages, fmt='html', start=0, lab=None, render_text=None, resolver=None):
    """Replace the markers in the converted text by the charts. In HTML each chart that can be shown is numbered, from start + 1, in the
    order of the text (a block that cannot be read has a message and no number); LaTeX numbers its own tables."""
    codes, n = {l['code'] for l in languages}, start
    for i, b in enumerate(blocks):
        spec = parse_block(b)[0]
        ok = spec is not None and clean(spec, codes)[0] is not None
        if ok:
            n += 1
        out = render_block(b, languages, fmt, n if ok else None, lab, render_text, resolver)
        marker = 'PHONOTABLEXZ%dZX' % i
        rendered = rendered.replace('<p>%s</p>' % marker, out).replace(marker, out)
    return rendered
