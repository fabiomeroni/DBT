"""
Direct tests of captions.py (no server): the words of the captions, the HTML of a caption, the numbering of the figures of a section, and the
LaTeX of a figure and of the caption words.   Run alone with:  python tests/test_captions.py
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import captions as C

ok = bad = 0
def check(name, got, want):
    global ok, bad
    if got == want: ok += 1
    else:
        bad += 1; print(f"✗ {name}\n    got : {got!r}\n    want: {want!r}")

# ── the words ──
check('the defaults are Table, Figure and an en dash', C.labels(None), {'table': 'Table', 'figure': 'Figure', 'separator': ' – '})
check('a project can say its own words and separator', C.labels({'table': 'Tableau', 'figure': 'Figure', 'separator': ' : '}), {'table': 'Tableau', 'figure': 'Figure', 'separator': ' : '})
check('a word that is empty, too long, or not a text, is ignored: the default stays', C.labels({'table': '', 'figure': 'x' * 40, 'separator': 5}), C.DEFAULTS)
check('what is not a settings object is ignored', (C.labels('Table'), C.labels([1])), (C.DEFAULTS, C.DEFAULTS))
check('the caption text: spaces collapsed, cut at 400 without a trailing space', (C.caption_text('  a   b \n c '), len(C.caption_text('x ' * 300)), C.caption_text(None)), ('a b c', 399, ''))

# ── the HTML of a caption ──
check('Table 3, then the separator and the text', C.caption_html('table', 3, 'Consonants'), '<figcaption class="caption caption-table"><span class="cap-label">Table 3</span><span class="cap-text"> – Consonants</span></figcaption>')
check('a figure caption is the same with its own word and class', C.caption_html('figure', 12, 'A map'), '<figcaption class="caption caption-figure"><span class="cap-label">Figure 12</span><span class="cap-text"> – A map</span></figcaption>')
check('no text: only the label and the number', C.caption_html('figure', 1, ''), '<figcaption class="caption caption-figure"><span class="cap-label">Figure 1</span></figcaption>')
check('the text is escaped, and so are the words of the project', ('<b>' in C.caption_html('table', 1, '<b>x</b>'), 'Tab&lt;b&gt;' in C.caption_html('table', 1, 'x', {'table': 'Tab<b>', 'figure': 'F', 'separator': ' – '})), (False, True))

# ── the figures of a section ──
md_html = '<p>Before.</p>\n<p><img alt="A map of the island" src="/images/map.png" /></p>\n<p>Text with <img alt="an icon" src="/images/i.png" /> inside.</p>\n<p><img alt="" src="/images/b.png" /></p>\n<p><img alt="Two &amp; three" src="/images/c.png" /><em>old style caption</em></p>'
out, n = C.number_figures(md_html, start=2)
check('an image alone in its paragraph is a figure: numbered from the number after the earlier ones, its caption (the alt text) below it', (n, re.findall(r'Figure (\d+)</span>(?:<span class="cap-text"> – ([^<]*))?', out)), (2, [('3', 'A map of the island'), ('4', '')]))
check('the caption comes after the image', out.index('<img alt="A map') < out.index('Figure 3'), True)
check('an image in a line of text is only an image: no caption, no number; nor is an image followed by an old-style italic caption in the same paragraph', ('an icon" src="/images/i.png" /> inside' in out, 'old style caption</em></p>' in out, out.count('<figure')), (True, True, 2))
check('the figures are counted the same way', C.count_figures(md_html), 2)
check('the alt text is kept as the alt of the image, and its entities are not doubled in the caption', ('Two &amp; three' in C.number_figures('<p><img alt="Two &amp; three" src="a.png" /></p>')[0], C.number_figures('<p><img alt="Two &amp; three" src="a.png" /></p>')[0].count('&amp;amp;')), (True, 0))

# ── LaTeX ──
check('an image alone on a line is recognised, with or without a title', (C.image_line('![A map](images/map.png)'), C.image_line('![A map](/images/map.png "t")'), C.image_line('text ![A map](images/map.png)'), C.image_line('![](x.png)')), (('A map', 'images/map.png'), ('A map', '/images/map.png'), None, ('', 'x.png')))
fig = C.figure_latex('A map & more', '/images/map.png', lambda s: s.replace('&', '\\&'))
check('a figure environment: the image from the images folder, scaled down to the line only if it is wider, the caption below', fig, '\\begin{figure}[ht]\n\\centering\n\\includegraphics[max width=\\linewidth]{images/map.png}\n\\caption{A map \\& more}\n\\end{figure}\n')
check('the name of the file cannot carry LaTeX into the document', 'x\\input' in C.figure_latex('c', 'images/a{b}%x.png', str), False)
check('the words and the separator for LaTeX: en dash by default, the project’s words', (C.latex_setup(None).splitlines()[0], '\\tablename}{Table}' in C.latex_setup(None), 'tablename}{Tableau}' in C.latex_setup({'table': 'Tableau', 'figure': 'Figure', 'separator': ' : '}), C.latex_setup({'table': 'T', 'figure': 'F', 'separator': ' : '}).splitlines()[0]), ('\\usepackage[labelsep=endash]{caption}', True, True, '\\usepackage[labelsep=colon]{caption}'))
print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
