"""
Captions numbered through the whole grammar: "Table 3 – …" above a table (a phonological chart), "Figure 2 – …" below a figure (an image).

The author writes only the text of the caption (the alt text of an image, the caption box of a chart); the number is given automatically,
in the order of the grammar: the sections in their order, the tables and the figures in theirs, each kind counted by itself. A section is
rendered alone, so it is told how many tables and figures come before it (see `count_figures` and phonotable.count_valid).

A figure is an image alone in its paragraph (`![the caption](images/map.png)` on a line of its own). An image inside a line of text is just an
image: it has no caption and no number.

To refer to a table or a figure the author gives it a label (a short name: letters, digits, - and _): a chart has a Label box, a figure has it after
the image, `![the caption](images/map.png){#map}`. `{{ref: map}}` then becomes a link that reads "Figure 3" (or "Table 2": the words are the
project's), with the number it has now; `{{ref: a, b}}` refers to several. The labels of tables and figures are one set of names (the first
one to use a name keeps it). The same shortcode works in the grammar and in the dictionary.

The words ("Table", "Figure") and the separator (" – ") come from the project (`captions` in project.json), so that a grammar in another language
has its own. Nothing here knows a language of the project or the web framework.
"""
import html as _html
import re

DEFAULTS = {'table': 'Table', 'figure': 'Figure', 'separator': ' – ', 'tables': 'Tables', 'figures': 'Figures', 'and': 'and'}
MAX_WORD, MAX_SEP, MAX_LABEL = 30, 8, 40


def labels(settings=None):
    """The words of the captions: the defaults, changed by what the project says (short plain strings only). The plural forms ("Tables 1a–e")
    are the singular with an s unless the project gives them; `and` is the word between the last two items of a list."""
    out = dict(DEFAULTS)
    for k, limit in (('table', MAX_WORD), ('figure', MAX_WORD), ('separator', MAX_SEP), ('tables', MAX_WORD), ('figures', MAX_WORD), ('and', MAX_WORD)):
        v = (settings or {}).get(k) if isinstance(settings, dict) else None
        if isinstance(v, str) and 0 < len(v.strip() if k != 'separator' else v) <= limit:
            out[k] = v.strip() if k != 'separator' else v
    for one, many in (('table', 'tables'), ('figure', 'figures')):
        given = isinstance(settings, dict) and isinstance(settings.get(many), str) and settings.get(many).strip()
        if out[one] != DEFAULTS[one] and not given:
            out[many] = out[one] + 's'
    return out


def caption_text(text):
    """The text of a caption as it is kept: spaces collapsed, at most 400 characters."""
    return re.sub(r'\s+', ' ', str(text or '')).strip()[:400].rstrip()


def clean_label(s):
    """A label as it is kept: letters, digits, - and _ (anything else becomes -), at most 40 characters; '' if nothing is left."""
    return re.sub(r'[^A-Za-z0-9_-]+', '-', str(s or '').strip()).strip('-_')[:MAX_LABEL]


def anchor(kind, label):
    """The id of the table or the figure in the page, and what a link goes to."""
    return ('tab-' if kind == 'table' else 'fig-') + label


LANGUAGE = '{language}'


def join_names(names, lab=None):
    """['Alpha', 'Beta', 'Gamma'] -> 'Alpha, Beta and Gamma' (the word between the last two is the project's)."""
    names = [str(n) for n in names if str(n)]
    word = f" {labels(lab)['and']} "
    return names[0] if len(names) == 1 else (', '.join(names[:-1]) + word + names[-1]) if names else ''


def fill_language(text, names, lab=None):
    """The caption of a chart with {language} replaced by the names of the languages (all of them on the website, one for each table in the exports)."""
    return str(text or '').replace(LANGUAGE, join_names(names, lab))


def caption_html(kind, number, text, lab=None):
    """<figcaption> for a 'table' or a 'figure': the label and the number, then the separator and the text (if there is one)."""
    lab = labels(lab)
    e = _html.escape
    name = lab[kind] + (f' {number}' if number is not None else '')
    text = caption_text(text)
    rest = f'<span class="cap-text">{e(lab["separator"])}{e(text)}</span>' if text else ''
    return f'<figcaption class="caption caption-{kind}"><span class="cap-label">{e(name)}</span>{rest}</figcaption>'


# an image alone in a paragraph, as Markdown writes it: <p><img alt="…" src="…" /></p>
_FIGURE = re.compile(r'<p>\s*(<img\b[^>]*?>)\s*</p>')
_ALT = re.compile(r'\balt="([^"]*)"')


_ID = re.compile(r'\sid="([^"]*)"')


def list_figures(html):
    """[(label, alt text)] of the figures of some rendered Markdown, in order (the label is '' if the image has none)."""
    out = []
    for m in _FIGURE.finditer(html):
        i, a = _ID.search(m.group(1)), _ALT.search(m.group(1))
        out.append((clean_label(i.group(1)) if i else '', _html.unescape(a.group(1)) if a else ''))
    return out


def count_figures(html):
    """How many figures there are in some rendered Markdown."""
    return len(_FIGURE.findall(html))


def number_figures(html, start=0, lab=None):
    """Each image alone in a paragraph becomes a numbered figure, the caption (its alt text) below it; the label of the image, if it has one, becomes
    the id of the figure (fig-label) that links go to. Returns (html, how many)."""
    n = [0]
    def fig(m):
        n[0] += 1
        img = m.group(1)
        i, a = _ID.search(img), _ALT.search(img)
        label = clean_label(i.group(1)) if i else ''
        img = _ID.sub('', img, count=1) if i else img
        attrs = f' id="{anchor("figure", label)}" data-label="{label}"' if label else ''
        text = _html.unescape(a.group(1)) if a else ''
        return f'<figure class="grammar-figure"{attrs}>{img}{caption_html("figure", start + n[0], text, lab)}</figure>'
    out = _FIGURE.sub(fig, html)
    return out, n[0]


# ── references: what can be referred to, and {{ref: label}} ──
def build_index(sections):
    """sections = [(section id, {'tables': [(label, caption)], 'figures': [(label, caption)]})] in the order of the grammar.
    Returns (items, by_label, duplicates): every table and figure with its number (each kind counted by itself), the items that have a label by
    that label (lower case; the first to use a name keeps it) and the labels that were used more than once."""
    items, by_label, dup, counters = [], {}, [], {'table': 0, 'figure': 0}
    for sid, found in sections:
        for kind, key in (('table', 'tables'), ('figure', 'figures')):
            for k, entry in enumerate(found.get(key, [])):
                label, text = entry[0], entry[1]
                counters[kind] += 1
                it = {'kind': kind, 'number': counters[kind], 'label': label, 'text': text, 'section': sid, 'kindIndex': k,
                      'anchor': anchor(kind, label) if label else '', 'parts': list(entry[2]) if len(entry) > 2 else []}
                items.append(it)
                if label:
                    if label.lower() in by_label: dup.append(label)
                    else: by_label[label.lower()] = it
    return items, by_label, dup


_REF = re.compile(r'\{\{\s*ref\s*:\s*([^}]*)\}\}')
_CODE = re.compile(r'(<pre\b.*?</pre>|<code\b.*?</code>)', re.S)


def _labels_of(spec):
    """[(label, part)] of a {{ref: …}}: `cons` or `cons#drg` (a part is one language's table of a chart in the exports: the website ignores it)."""
    out = []
    for x in re.split(r'[,;]', spec):
        if x.strip():
            l, _, p = x.strip().partition('#')
            out.append((clean_label(l), clean_label(p)))
    return out


def _join(parts, last=' and '):
    return parts[0] if len(parts) == 1 else ', '.join(parts[:-1]) + last + parts[-1]


def ref_html(spec, by_label, lab=None, base=''):
    """The text of one {{ref: …}}: a link for each label, "Table 2" or "Figure 3" with the number it has now. `base` is the page the links go to
    ('' on the page that has the item)."""
    lab, e = labels(lab), _html.escape
    labels_ = _labels_of(spec)
    if not labels_:
        return '<span class="shortcode-error">Reference needs a label</span>'
    parts = []
    for l, _part in labels_:
        it = by_label.get(l.lower())
        parts.append(f'<a class="xref" href="{e(base)}#{e(it["anchor"])}" title="{e(caption_text(it["text"]))}">{e(lab[it["kind"]])} {it["number"]}</a>' if it
                     else f'<span class="shortcode-error">Reference not found: {e(l)}</span>')
    return _join(parts, f" {lab['and']} ")


_TAG = re.compile(r'(<[^>]*>)')


def expand_refs(text, by_label, lab=None, base=''):
    """{{ref: …}} in a text made of HTML become links, in the text between the tags only (never inside a tag: an attribute such as alt="…" stays
    as it is); inside <pre> and <code> they are left as written (the author is showing the shortcode)."""
    out = []
    for part in _CODE.split(text):
        if _CODE.fullmatch(part):
            out.append(part)
        else:
            out.append(''.join(tok if tok.startswith('<') and tok.endswith('>') else _REF.sub(lambda m: ref_html(m.group(1), by_label, lab, base), tok)
                               for tok in _TAG.split(part)))
    return ''.join(out)


def ref_latex(spec, by_label, lab=None):
    """{{ref: …}} for LaTeX: the word of the project and the number LaTeX gives (\\ref). A chart that the exports split into one table for each
    language is referred to as a group, "Tables 1a–e" (the first part and the letter of the last), or, with {{ref: label#code}}, as one part,
    "Table 1b"; a table that is not split is "Table 1"."""
    lab = labels(lab)
    out = []
    for l, part in _labels_of(spec):
        it = by_label.get(l.lower())
        if not it:
            out.append('\\textbf{??}'); continue
        kind, pre = it['kind'], ('tab' if it['kind'] == 'table' else 'fig')
        parts = it.get('parts') or []
        if kind == 'table' and len(parts) > 1:
            if part and part in parts:
                out.append('\\tablename~\\ref{tab:%s:%s}' % (it['label'], part))
            elif part:
                out.append('\\textbf{??}')
            else:
                out.append('\\tablesname~\\ref{tab:%s:first}--\\ref{tab:%s:last}' % (it['label'], it['label']))
        else:
            out.append('\\%sname~\\ref{%s:%s}' % (kind, pre, it['label']))
    return _join(out, ' ' + lab['and'] + ' ') if out else '\\textbf{??}'


# ── LaTeX: the figures and the words of the captions ──
_IMAGE_LINE = re.compile(r'^\s*!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+"[^"]*")?\s*\)(?:\{\s*#([^}\s]+)\s*\})?\s*$')


def image_line(line):
    """('the caption', 'images/map.png', 'label') if the line is an image alone (the label is '' if it has none), else None."""
    m = _IMAGE_LINE.match(line)
    return (m.group(1), m.group(2), clean_label(m.group(3))) if m else None


def latex_text(text, by_label, escape):
    """A text for LaTeX with {{ref: …}} in it: the ordinary parts escaped, the references as \\tablename~\\ref{…}."""
    out, last = [], 0
    for m in _REF.finditer(text):
        out += [escape(text[last:m.start()]), ref_latex(m.group(1), by_label)]
        last = m.end()
    return ''.join(out) + escape(text[last:])


def figure_latex(alt, src, escape, label=''):
    """A figure environment: the image from the images folder (next to the .tex), the caption below it, the label after the caption. LaTeX numbers it.
    `escape` makes the caption text safe for LaTeX (it may also expand the references of the caption)."""
    name = src.rstrip('/').rsplit('/', 1)[-1]
    return ('\\begin{figure}[ht]\n\\centering\n\\includegraphics[max width=\\linewidth]{images/%s}\n\\caption{%s}\n%s\\end{figure}\n'
            % (name.replace('\\', '').replace('{', '').replace('}', '').replace('%', '').replace('#', ''), escape(caption_text(alt)),
               ('\\label{fig:%s}\n' % label) if label else ''))


def latex_setup(lab=None):
    """The lines of the preamble that give LaTeX the project's words and separator for its own numbering, and the macros that number the tables of a
    chart split by language 1a, 1b … (the counter of tables goes up once for the group)."""
    lab = labels(lab)
    sep = lab['separator'].strip()
    labelsep = {'.': 'period', ':': 'colon', '–': 'endash', '-': 'endash', '—': 'endash'}.get(sep, 'endash')
    word = lambda s: s.replace('\\', '').replace('{', '').replace('}', '').replace('%', '').replace('#', '').replace('&', '\\&').replace('_', '\\_')
    return ('\\usepackage[labelsep=%s]{caption}\n'
            '\\AtBeginDocument{\\renewcommand{\\tablename}{%s}\\renewcommand{\\figurename}{%s}}\n'
            '\\newcommand{\\tablesname}{%s}\\newcommand{\\figuresname}{%s}\n'
            '%% the tables of a chart split by language are numbered 1a, 1b ...: the counter of tables goes up once for the group\n'
            '\\newcounter{tabpart}\n'
            '\\newcommand{\\tabgroupstart}{\\setcounter{tabpart}{1}\\renewcommand{\\thetable}{\\arabic{table}\\alph{tabpart}}}\n'
            '\\newcommand{\\tabgroupnext}{\\addtocounter{table}{-1}\\stepcounter{tabpart}}\n'
            '\\newcommand{\\tabgroupend}{\\renewcommand{\\thetable}{\\arabic{table}}}\n'
            '\\makeatletter\\newcommand{\\labelas}[2]{{\\def\\@currentlabel{#2}\\label{#1}}}\\makeatother'
            % (labelsep, word(lab['table']), word(lab['figure']), word(lab['tables']), word(lab['figures'])))
