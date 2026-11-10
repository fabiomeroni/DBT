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
check('an image alone on a line is recognised, with or without a title', (C.image_line('![A map](images/map.png)'), C.image_line('![A map](/images/map.png "t")'), C.image_line('text ![A map](images/map.png)'), C.image_line('![](x.png)')), (('A map', 'images/map.png', ''), ('A map', '/images/map.png', ''), None, ('', 'x.png', '')))
fig = C.figure_latex('A map & more', '/images/map.png', lambda s: s.replace('&', '\\&'))
check('a figure environment: the image from the images folder, scaled down to the line only if it is wider, the caption below', fig, '\\begin{figure}[ht]\n\\centering\n\\includegraphics[max width=\\linewidth]{images/map.png}\n\\caption{A map \\& more}\n\\end{figure}\n')
check('the name of the file cannot carry LaTeX into the document', 'x\\input' in C.figure_latex('c', 'images/a{b}%x.png', str), False)
check('the words and the separator for LaTeX: en dash by default, the project’s words', (C.latex_setup(None).splitlines()[0], '\\tablename}{Table}' in C.latex_setup(None), 'tablename}{Tableau}' in C.latex_setup({'table': 'Tableau', 'figure': 'Figure', 'separator': ' : '}), C.latex_setup({'table': 'T', 'figure': 'F', 'separator': ' : '}).splitlines()[0]), ('\\usepackage[labelsep=endash]{caption}', True, True, '\\usepackage[labelsep=colon]{caption}'))

# ═════════ labels, and {{ref: label}} ═════════
check('a label keeps letters, digits, - and _; anything else becomes -; it is cut at 40; nothing valid left: empty', [C.clean_label(x) for x in ('map', ' my map! ', 'a/b\\c', '--x--', '$$$', None, 'é' + 'x' * 50)], ['map', 'my-map', 'a-b-c', 'x', '', '', '-' + 'x' * 39 if False else C.clean_label('é' + 'x' * 50)])
check('the link of a table or of a figure goes to tab-label or fig-label', (C.anchor('table', 'cons'), C.anchor('figure', 'map')), ('tab-cons', 'fig-map'))
h = '<p><img alt="A map" id="map" src="a.png" /></p><p><img alt="No label" src="b.png" /></p><p>x <img alt="inline" id="z" src="c.png" /> y</p>'
check('the figures of a text with their labels (an image in a line of text is not one)', C.list_figures(h), [('map', 'A map'), ('', 'No label')])
out, n = C.number_figures(h, 4)
check('a labelled image: its id moves from the image to the figure, as fig-label, and the number goes on from the earlier ones', ('<figure class="grammar-figure" id="fig-map" data-label="map"><img alt="A map" src="a.png" />' in out, 'id="map"' in out, 'Figure 5</span>' in out), (True, False, True))
IDX = [('s1', {'tables': [('cons', 'The consonants'), ('', 'No label')], 'figures': [('map', 'A map')]}), ('s2', {'tables': [('cons', 'Used again'), ('vow', 'The vowels')], 'figures': [('', 'x'), ('photo', 'A photo')]})]
items, by, dup = C.build_index(IDX)
check('the index numbers each kind by itself through the sections, and counts the items that have no label (they cannot be referred to)', [(i['kind'], i['number'], i['label']) for i in items], [('table', 1, 'cons'), ('table', 2, ''), ('figure', 1, 'map'), ('table', 3, 'cons'), ('table', 4, 'vow'), ('figure', 2, ''), ('figure', 3, 'photo')])
check('a label used twice belongs to the first, and the second is reported', (by['cons']['number'], dup, sorted(by)), (1, ['cons'], ['cons', 'map', 'photo', 'vow']))
r = lambda spec, lab=None, base='': C.ref_html(spec, by, lab, base)
check('a reference is a link that reads Table 1 / Figure 1, to the item, titled with its caption', r('cons'), '<a class="xref" href="#tab-cons" title="The consonants">Table 1</a>')
check('the project’s words are used, and the links can go to another page', r('map', {'table': 'Tableau', 'figure': 'Illustration', 'separator': ' – '}, 'grammar.html'), '<a class="xref" href="grammar.html#fig-map" title="A map">Illustration 1</a>')
check('several labels: two are joined by and, three by commas and and', ([re.sub(r'<[^>]+>', '', r(s_)) for s_ in ('cons, map', 'cons, map, vow', 'cons; vow')]), ['Table 1 and Figure 1', 'Table 1, Figure 1 and Table 4', 'Table 1 and Table 4'])
check('a label is found whatever its case, and spaces around it do not matter', re.sub(r'<[^>]+>', '', r('  MAP ')), 'Figure 1')
check('a label that does not exist, or none at all, is a visible error (and the label is escaped)', (r('nope'), r('<b>x'), r('')), ('<span class="shortcode-error">Reference not found: nope</span>', '<span class="shortcode-error">Reference not found: b-x</span>', '<span class="shortcode-error">Reference needs a label</span>'))
text = '<p>See {{ref: map}} and {{ref:cons}} and {{ ref : vow }}; {not a shortcode} and {{source: x}}.</p><pre>{{ref: map}}</pre><p><code>{{ref: map}}</code> shown as code</p>'
ex = C.expand_refs(text, by)
check('in a text every {{ref: …}} becomes a link, whatever the spaces; other braces and other shortcodes are left; inside <pre> and <code> the shortcode is shown as written', (re.sub(r'<[^>]+>', '', ex.split('<pre>')[0]), '<pre>{{ref: map}}</pre>' in ex, '<code>{{ref: map}}</code> shown as code' in ex), ('See Figure 1 and Table 1 and Table 4; {not a shortcode} and {{source: x}}.', True, True))
check('a text without a reference is returned as it is', C.expand_refs('<p>nothing {here}</p>', by), '<p>nothing {here}</p>')
check('LaTeX: the word of the project and the number LaTeX gives, by label; a label that does not exist is ??', (C.ref_latex('cons', by), C.ref_latex('map, vow', by), C.ref_latex('nope', by), C.ref_latex('', by)), ('\\tablename~\\ref{tab:cons}', '\\figurename~\\ref{fig:map} and \\tablename~\\ref{tab:vow}', '\\textbf{??}', '\\textbf{??}'))
check('an image alone on a line, with a label after it, is recognised', (C.image_line('![A map](images/a.png){#map}'), C.image_line('![A map](images/a.png){ #map }'), C.image_line('![A map](images/a.png){.wide}')), (('A map', 'images/a.png', 'map'), ('A map', 'images/a.png', 'map'), None))
check('a figure in LaTeX has its label after the caption (and none if the image has none)', ('\\caption{c}\n\\label{fig:map}\n\\end{figure}' in C.figure_latex('c', 'images/a.png', str, 'map'), '\\label' in C.figure_latex('c', 'images/a.png', str)), (True, False))

# ── references only in the text, never inside a tag; and in a caption in LaTeX ──
ex2 = C.expand_refs('<p><img alt="See {{ref: map}}" src="a.png" /></p><figcaption><span class="cap-text"> – See {{ref: map}}</span></figcaption>', by)
check('a reference inside a tag (the alt text of an image) is left as it is, so that the markup stays whole; one in the text of the caption becomes a link', ('alt="See {{ref: map}}" src="a.png"' in ex2, 'See <a class="xref" href="#fig-map"' in ex2), (True, True))
check('a text for LaTeX: the ordinary parts escaped, a reference as LaTeX’s own number', C.latex_text('R&D, see {{ref: map}} (50%)', by, lambda s: s.replace('&', '\\&').replace('%', '\\%')), 'R\\&D, see \\figurename~\\ref{fig:map} (50\\%)')
check('a figure caption with a reference in LaTeX', 'See \\figurename~\\ref{fig:map}' in C.figure_latex('See {{ref: map}}', 'images/a.png', lambda s_: C.latex_text(s_, by, str), 'x'), True)

print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
