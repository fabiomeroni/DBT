"""
Phonological charts for the grammar: one chart of consonants and one of vowels, whose rows and columns the author decides, and
an inventory for each language of the project, merged in a single chart.

In a grammar section a chart is a fenced block that the editor writes (the author never has to type it):

    ```phonotable
    {"kind": "consonants", "caption": "The consonant phonemes",
     "columns": ["Bilabial", "Alveolar", "Velar"], "rows": ["Plosive", "Nasal"],
     "inventory": {"drg": {"Plosive": {"Bilabial": "p b", "Alveolar": "t d"}, "Nasal": {"Bilabial": "m"}}}}
    ```

A sound found in every language that has an inventory is shown in black; a sound found in only some is shown in the colours of
those languages (one character split into as many coloured parts as there are languages; in LaTeX, once for each language).

Nothing here knows a language or the web framework: the languages (code, name, colour) are given.
"""
import html as _html
import json
import re
import unicodedata

import captions as _cap

KINDS = ('consonants', 'vowels')

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
}
MAX_AXIS, MAX_LABEL, MAX_PHONEMES, MAX_PHONEME, MAX_BLOCK = 40, 60, 24, 16, 200_000

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
                ph = phonemes(text) if isinstance(text, str) else []
                if c2 is not None and ph:
                    inv.setdefault(code, {}).setdefault(r2, {})[c2] = ' '.join(ph)
    # the caption is the text shown after "Table 3 –": there is no title (an old block's title is read as its caption)
    caption = _cap.caption_text(spec['caption'] if isinstance(spec.get('caption'), str) else spec.get('title') if isinstance(spec.get('title'), str) else '')
    # the label is the short name that lets the text refer to the chart: {{ref: name}}
    return {'kind': kind, 'caption': caption, 'label': _cap.clean_label(spec['label'] if isinstance(spec.get('label'), str) else ''), 'columns': cols, 'rows': rows, 'inventory': inv}, None


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
                for p in phonemes(inv[code].get(r, {}).get(c, '')):
                    if p not in found:
                        seen.append(p); found[p] = []
                    found[p].append(code)
            if seen:
                cells.setdefault(r, {})[c] = [{'p': p, 'langs': found[p]} for p in seen]
    return {'languages': present, 'cells': cells}


def _hex(color):
    c = str(color or '').strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', c):
        return c.lower()
    if re.fullmatch(r'#[0-9a-fA-F]{3}', c):
        return '#' + ''.join(ch * 2 for ch in c[1:]).lower()
    return '#808080'


def _grad(colors):
    n = len(colors)
    return 'linear-gradient(90deg,' + ','.join('%s %g%% %g%%' % (c, round(100 * i / n, 2), round(100 * (i + 1) / n, 2)) for i, c in enumerate(colors)) + ')'


def render_html(spec, languages, number=None, lab=None, anchors=True):
    """The chart as HTML, with its caption above it ("Table 3 – …"; the number is given by the caller). The text of the table is escaped;
    the colours come from the languages of the project, never from the table."""
    e = _html.escape
    m = merge(spec, languages)
    present, by_code = m['languages'], {l['code']: l for l in languages}
    def sound(item):
        langs = item['langs']
        names = ', '.join(e(by_code[c]['name']) for c in langs)
        data = f'data-langs="{e(" ".join(langs))}"'
        if len(langs) == len(present):
            return f'<span class="ph ph-all" {data}>{e(item["p"])}</span>'
        cols = [_hex(by_code[c].get('color')) for c in langs]
        if len(cols) == 1:
            return f'<span class="ph ph-one" style="color:{cols[0]}" title="{names}" {data}>{e(item["p"])}</span>'
        return f'<span class="ph ph-mix" style="--ph-c1:{cols[0]};--ph-grad:{_grad(cols)}" title="{names}" {data}>{e(item["p"])}</span>'
    head = ''.join(f'<th scope="col">{e(c)}</th>' for c in spec['columns'])
    body = ''
    for r in spec['rows']:
        tds = ''.join('<td>' + ' '.join(sound(i) for i in m['cells'].get(r, {}).get(c, [])) + '</td>' for c in spec['columns'])
        body += f'<tr><th scope="row">{e(r)}</th>{tds}</tr>'
    legend = ''
    if len(present) > 1:                                    # the legend is a set of check boxes: the reader chooses the languages to show
        boxes = ' '.join(f'<label class="lg"><input type="checkbox" checked data-lang="{e(c)}" data-color="{_hex(by_code[c].get("color"))}">'
                         f'<span style="color:{_hex(by_code[c].get("color"))}">{e(by_code[c]["name"])}</span></label>' for c in present)
        legend = (f'<div class="phono-legend"><span class="pl-title">Languages shown:</span> {boxes}'
                  '<div class="pl-note">In black: sounds found in all the languages shown. In colour: sounds found only in some of them, in the colour of the language; '
                  'a sound found in several of them, but not in all, shows their colours together. Untick a language to leave its sounds out.</div></div>')
    ident = f' id="{e(_cap.anchor("table", spec["label"]))}" data-label="{e(spec["label"])}"' if spec.get('label') and anchors else ''   # a preview has no anchor: the page must not have the id twice
    return (f'<figure class="phonotable" data-kind="{e(spec["kind"])}"{ident}>{_cap.caption_html("table", number, spec["caption"], lab)}'
            f'<div class="phono-scroll"><table class="phono"><thead><tr><th class="corner"></th>{head}</tr></thead><tbody>{body}</tbody></table></div>{legend}</figure>')


_LATEX_SPECIAL = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}


def _tex(s):
    return ''.join(_LATEX_SPECIAL.get(ch, ch) for ch in str(s))


def render_latex(spec, languages, render_text=None):
    """The chart as a LaTeX table (needs xcolor and graphicx). A sound found in some of the languages is printed once for each of them,
    in its colour. `render_text` makes the caption safe for LaTeX (default: escaping), so that a caption can hold references."""
    render_text = render_text or _tex
    m = merge(spec, languages)
    present, by_code = m['languages'], {l['code']: l for l in languages}
    def sound(item):
        if len(item['langs']) == len(present):
            return _tex(item['p'])
        return r'\,'.join('\\textcolor[HTML]{%s}{%s}' % (_hex(by_code[c].get('color'))[1:].upper(), _tex(item['p'])) for c in item['langs'])
    cols = 'l|' + '|'.join('c' for _ in spec['columns'])
    rows = []
    for r in spec['rows']:
        cells = [' '.join(sound(i) for i in m['cells'].get(r, {}).get(c, [])) for c in spec['columns']]
        rows.append(f'{_tex(r)} & ' + ' & '.join(cells) + r' \\')
    head = ' & ' + ' & '.join(_tex(c) for c in spec['columns']) + r' \\'
    return ('\\begin{table}[ht]\n\\centering\n\\caption{%s}\n%s\\resizebox{\\linewidth}{!}{%%\n\\begin{tabular}{%s}\n\\toprule\n%s\n\\midrule\n%s\n\\bottomrule\n\\end{tabular}}\n\\end{table}\n'
            % (render_text(spec['caption']), ('\\label{tab:%s}\n' % spec['label']) if spec.get('label') else '', cols, head, '\n'.join(rows)))


# ── in a section: lift the blocks out before Markdown, put the charts in after ──
def extract(md_text):
    """The Markdown with each fenced chart replaced by a marker on a line of its own, and the texts of the blocks."""
    blocks = []
    def take(m):
        blocks.append(m.group(1))
        return '\n\nPHONOTABLEXZ%dZX\n\n' % (len(blocks) - 1)
    return BLOCK_RE.sub(take, md_text), blocks


def render_block(text, languages, fmt='html', number=None, lab=None, render_text=None):
    """One fenced block -> its chart; if it cannot be read, a message in its place (never an exception)."""
    spec, err = parse_block(text)
    if spec is not None:
        spec, err = clean(spec, {l['code'] for l in languages})
    if spec is None:
        return ('<div class="shortcode-error">Phonological table: %s</div>' % _html.escape(err)) if fmt == 'html' else '%% phonological table: %s\n' % err.replace('\n', ' ')
    return render_html(spec, languages, number, lab) if fmt == 'html' else render_latex(spec, languages, render_text)


def list_charts(blocks, languages):
    """[(label, caption)] of the blocks that are charts that can be shown, in order: what the grammar can refer to."""
    codes, out = {l['code'] for l in languages}, []
    for b in blocks:
        spec = parse_block(b)[0]
        spec = clean(spec, codes)[0] if spec is not None else None
        if spec is not None:
            out.append((spec['label'], spec['caption']))
    return out


def count_valid(blocks, languages):
    """How many of the blocks are charts that can be shown (so that will have a number)."""
    codes = {l['code'] for l in languages}
    return sum(1 for b in blocks if parse_block(b)[0] is not None and clean(parse_block(b)[0], codes)[0] is not None)


def put_back(rendered, blocks, languages, fmt='html', start=0, lab=None, render_text=None):
    """Replace the markers in the converted text by the charts. In HTML each chart that can be shown is numbered, from start + 1, in the
    order of the text (a block that cannot be read has a message and no number); LaTeX numbers its own tables."""
    codes, n = {l['code'] for l in languages}, start
    for i, b in enumerate(blocks):
        spec = parse_block(b)[0]
        ok = spec is not None and clean(spec, codes)[0] is not None
        if ok:
            n += 1
        out = render_block(b, languages, fmt, n if ok else None, lab, render_text)
        marker = 'PHONOTABLEXZ%dZX' % i
        rendered = rendered.replace('<p>%s</p>' % marker, out).replace(marker, out)
    return rendered
