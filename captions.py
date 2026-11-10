"""
Captions numbered through the whole grammar: "Table 3 – …" above a table (a phonological chart), "Figure 2 – …" below a figure (an image).

The author writes only the text of the caption (the alt text of an image, the caption box of a chart); the number is given automatically,
in the order of the grammar: the sections in their order, the tables and the figures in theirs, each kind counted by itself. A section is
rendered alone, so it is told how many tables and figures come before it (see `count_figures` and phonotable.count_valid).

A figure is an image alone in its paragraph (`![the caption](images/map.png)` on a line of its own). An image inside a line of text is just an
image: it has no caption and no number.

The words ("Table", "Figure") and the separator (" – ") come from the project (`captions` in project.json), so that a grammar in another language
has its own. Nothing here knows a language of the project or the web framework.
"""
import html as _html
import re

DEFAULTS = {'table': 'Table', 'figure': 'Figure', 'separator': ' – '}
MAX_WORD, MAX_SEP = 30, 8


def labels(settings=None):
    """The words of the captions: the defaults, changed by what the project says (short plain strings only)."""
    out = dict(DEFAULTS)
    for k, limit in (('table', MAX_WORD), ('figure', MAX_WORD), ('separator', MAX_SEP)):
        v = (settings or {}).get(k) if isinstance(settings, dict) else None
        if isinstance(v, str) and 0 < len(v.strip() if k != 'separator' else v) <= limit:
            out[k] = v.strip() if k != 'separator' else v
    return out


def caption_text(text):
    """The text of a caption as it is kept: spaces collapsed, at most 400 characters."""
    return re.sub(r'\s+', ' ', str(text or '')).strip()[:400].rstrip()


def caption_html(kind, number, text, lab=None):
    """<figcaption> for a 'table' or a 'figure': the label and the number, then the separator and the text (if there is one)."""
    lab = lab or DEFAULTS
    e = _html.escape
    name = lab[kind] + (f' {number}' if number is not None else '')
    text = caption_text(text)
    rest = f'<span class="cap-text">{e(lab["separator"])}{e(text)}</span>' if text else ''
    return f'<figcaption class="caption caption-{kind}"><span class="cap-label">{e(name)}</span>{rest}</figcaption>'


# an image alone in a paragraph, as Markdown writes it: <p><img alt="…" src="…" /></p>
_FIGURE = re.compile(r'<p>\s*(<img\b[^>]*?>)\s*</p>')
_ALT = re.compile(r'\balt="([^"]*)"')


def count_figures(html):
    """How many figures there are in some rendered Markdown."""
    return len(_FIGURE.findall(html))


def number_figures(html, start=0, lab=None):
    """Each image alone in a paragraph becomes a numbered figure, the caption (its alt text) below it. Returns (html, how many)."""
    n = [0]
    def fig(m):
        n[0] += 1
        alt = _ALT.search(m.group(1))
        text = _html.unescape(alt.group(1)) if alt else ''
        return f'<figure class="grammar-figure">{m.group(1)}{caption_html("figure", start + n[0], text, lab)}</figure>'
    out = _FIGURE.sub(fig, html)
    return out, n[0]


# ── LaTeX: the figures and the words of the captions ──
_IMAGE_LINE = re.compile(r'^\s*!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+"[^"]*")?\s*\)\s*$')


def image_line(line):
    """('the caption', 'images/map.png') if the line is an image alone, else None."""
    m = _IMAGE_LINE.match(line)
    return (m.group(1), m.group(2)) if m else None


def figure_latex(alt, src, escape):
    """A figure environment: the image from the images folder (next to the .tex), the caption below it. LaTeX numbers it."""
    name = src.rstrip('/').rsplit('/', 1)[-1]
    return ('\\begin{figure}[ht]\n\\centering\n\\includegraphics[max width=\\linewidth]{images/%s}\n\\caption{%s}\n\\end{figure}\n'
            % (name.replace('\\', '').replace('{', '').replace('}', '').replace('%', '').replace('#', ''), escape(caption_text(alt))))


def latex_setup(lab=None):
    """The lines of the preamble that give LaTeX the project's words and separator for its own numbering."""
    lab = lab or DEFAULTS
    sep = lab['separator'].strip()
    labelsep = {'.': 'period', ':': 'colon', '–': 'endash', '-': 'endash', '—': 'endash'}.get(sep, 'endash')
    word = lambda s: s.replace('\\', '').replace('{', '').replace('}', '').replace('%', '').replace('#', '').replace('&', '\\&').replace('_', '\\_')
    return ('\\usepackage[labelsep=%s]{caption}\n\\AtBeginDocument{\\renewcommand{\\tablename}{%s}\\renewcommand{\\figurename}{%s}}'
            % (labelsep, word(lab['table']), word(lab['figure'])))
