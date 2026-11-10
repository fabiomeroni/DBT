"""
Direct tests of phonotable.py (no server): the definition of a chart, the merging of the languages' inventories, and its HTML and LaTeX.
Run alone with:  python tests/test_phonotable.py
"""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import phonotable as PT

ok = bad = 0
def check(name, got, want):
    global ok, bad
    if got == want: ok += 1
    else:
        bad += 1; print(f"✗ {name}\n    got : {got!r}\n    want: {want!r}")

LANGS = [{'code': 'aaa', 'name': 'Alpha', 'color': '#2e5c8a'}, {'code': 'bbb', 'name': 'Beta', 'color': '#c07820'}, {'code': 'ccc', 'name': 'Gamma', 'color': '#2f7a3a'}]
CODES = {l['code'] for l in LANGS}
def spec(inv, cols=('Bilabial', 'Alveolar'), rows=('Plosive', 'Nasal'), kind='consonants', caption='T'):
    s, err = PT.clean({'kind': kind, 'caption': caption, 'columns': list(cols), 'rows': list(rows), 'inventory': inv}, CODES)
    assert err is None, err
    return s
def html(inv, langs=LANGS, **kw): return PT.render_html(spec(inv, **kw), langs)

# ── what the author starts from ──
check('suggested columns of the consonants, in the order of the IPA chart', PT.DEFAULT_AXES['consonants']['columns'], ['Bilabial', 'Labiodental', 'Dental', 'Alveolar', 'Postalveolar', 'Retroflex', 'Palatal', 'Velar', 'Uvular', 'Pharyngeal', 'Glottal'])
check('suggested rows of the consonants', PT.DEFAULT_AXES['consonants']['rows'], ['Plosive', 'Nasal', 'Trill', 'Tap or flap', 'Fricative', 'Lateral fricative', 'Approximant', 'Lateral approximant'])
check('suggested columns and rows of the vowels', (PT.DEFAULT_AXES['vowels']['columns'], PT.DEFAULT_AXES['vowels']['rows']), (['Front', 'Central', 'Back'], ['Close', 'Near-close', 'Close-mid', 'Mid', 'Open-mid', 'Near-open', 'Open']))

# ── the definition ──
s, err = PT.clean({'kind': 'vowels', 'columns': [' Front ', 'front', 'Back', '', 5, 'Labial-velar'], 'rows': ['Close', 'close', 'Open'], 'inventory': {}}, CODES)
check('columns and rows are stripped, the empty and the repeated (case ignored) are dropped, anything the author invents is kept, and the order is the author’s', (s['columns'], s['rows'], s['caption']), (['Front', 'Back', 'Labial-velar'], ['Close', 'Open'], ''))
check('an unknown kind, no rows, no columns, not an object: refused with a reason', [PT.clean(x, CODES)[1] is not None for x in ({'kind': 'tones', 'columns': ['a'], 'rows': ['b']}, {'kind': 'vowels', 'columns': ['a'], 'rows': []}, {'kind': 'vowels', 'columns': [], 'rows': ['a']}, [], 'x')], [True] * 5)
s = spec({'aaa': {'Plosive': {'Bilabial': ' p,  b  p ɓ ', 'Velar': 'k'}, 'Nasal': {'Alveolar': 'n'}, 'Trill': {'Bilabial': 'r'}}, 'zzz': {'Plosive': {'Bilabial': 'x'}}})
check('an inventory in a row or column that does not exist, or of a language that is not in the project, is dropped; sounds are split at spaces and commas, no repeats', s['inventory'], {'aaa': {'Plosive': {'Bilabial': 'p b ɓ'}, 'Nasal': {'Alveolar': 'n'}}})
check('rows and columns of the inventory are found whatever their case', spec({'aaa': {'plosive': {'BILABIAL': 'p'}}})['inventory'], {'aaa': {'Plosive': {'Bilabial': 'p'}}})
check('limits: a sound longer than 16 characters is dropped, at most 24 to a cell and 40 rows or columns', (PT.phonemes('a ' + 'x' * 17 + ' b'), len(PT.phonemes(' '.join(f's{i}' for i in range(40)))), len(spec({}, cols=[f'c{i}' for i in range(60)])['columns'])), (['a', 'b'], 24, 40))
check('a chart has a caption, not a title: the caption is kept as written (spaces collapsed), and there is none unless the author gives one', (spec({}, caption='  My  table ')['caption'], spec({}, caption='')['caption'], 'title' in spec({}), spec({}, kind='vowels', caption=None)['caption']), ('My table', '', False, ''))
check('an old block that has a title (before captions) keeps its text, as its caption; a caption wins over a title', (PT.clean({'kind': 'vowels', 'title': 'Old title', 'columns': ['a'], 'rows': ['b']}, CODES)[0]['caption'], PT.clean({'kind': 'vowels', 'title': 'Old', 'caption': 'New', 'columns': ['a'], 'rows': ['b']}, CODES)[0]['caption']), ('Old title', 'New'))
check('a caption can be a sentence (400 characters), not a label (the axes are cut at 60)', len(spec({}, caption='x ' * 300)['caption']), 399)
check('the two spellings of a letter are one sound', PT.phonemes('n\u0304 ' + 'n\u0304'), ['n\u0304'])
check('a block that is not JSON is refused with a reason, and a huge one too', (PT.parse_block('{oops')[1] is not None, PT.parse_block('x' * 300000)[1]), (True, 'The table is too large.'))

# ── the merge ──
m = PT.merge(spec({'bbb': {'Plosive': {'Bilabial': 'p b'}}, 'aaa': {'Plosive': {'Bilabial': 'p ɓ'}, 'Nasal': {'Alveolar': 'n'}}, 'ccc': {}}), LANGS)
check('only the languages that have an inventory count; the sounds of a cell are in the order typed, language after language (the project’s order)', (m['languages'], [(i['p'], i['langs']) for i in m['cells']['Plosive']['Bilabial']]), (['aaa', 'bbb'], [('p', ['aaa', 'bbb']), ('ɓ', ['aaa']), ('b', ['bbb'])]))
check('an empty cell is not in the chart', 'Alveolar' in m['cells'].get('Plosive', {}), False)

# ── HTML: black for what the languages share, the colour of the language for what is its own ──
h = html({'aaa': {'Plosive': {'Bilabial': 'p b'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}})
check('a sound of all the languages is black: no colour at all (it says which languages have it)', '<span class="ph ph-all" data-langs="aaa bbb">p</span>' in h, True)
check('a sound of one language only is in its colour (and says which language)', '<span class="ph ph-one" style="color:#2e5c8a" title="Alpha" data-langs="aaa">b</span>' in h, True)
h3 = html({'aaa': {'Plosive': {'Bilabial': 'p t'}}, 'bbb': {'Plosive': {'Bilabial': 'p t'}}, 'ccc': {'Plosive': {'Bilabial': 'p'}}})
check('a sound of two of three languages shows both colours in one character: the first half in the first colour, the second in the second', ('ph-mix' in h3, '--ph-c1:#2e5c8a' in h3, '--ph-grad:linear-gradient(90deg,#2e5c8a 0% 50%,#c07820 50% 100%)' in h3), (True, True, True))
check('three colours split the character in thirds', PT._grad(['#111111', '#222222', '#333333']), 'linear-gradient(90deg,#111111 0% 33.33%,#222222 33.33% 66.67%,#333333 66.67% 100%)')
h5 = html({'aaa': {'Plosive': {'Bilabial': 't'}}, 'bbb': {'Plosive': {'Bilabial': 't'}}, 'ccc': {'Plosive': {'Bilabial': 't'}}, 'xxx': {}}, langs=LANGS + [{'code': 'xxx', 'name': 'X', 'color': '#111'}])
check('with a language that has no inventory the others still share in black', '<span class="ph ph-all" data-langs="aaa bbb ccc">t</span>' in h5, True)
h1 = html({'aaa': {'Plosive': {'Bilabial': 'p b'}}}, langs=LANGS[:1])
check('one language: everything is black and there is no legend', ('ph-all' in h1, 'ph-one' in h1, 'phono-legend' in h1), (True, False, False))
check('with several languages and something not shared, a legend says what the colours mean, naming the languages that have an inventory', ('phono-legend' in h and 'Alpha' in h.split('phono-legend')[1] and 'Beta' in h.split('phono-legend')[1] and 'Gamma' not in h.split('phono-legend')[1]), True)
hs = html({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}})
check('with two languages the legend is there even when every sound is shared (the reader may still choose the languages to show)', ('phono-legend' in hs, hs.count('<input type="checkbox" checked data-lang='), 'phono-legend' in html({'aaa': {'Plosive': {'Bilabial': 'p'}}}, langs=LANGS[:1])), (True, 2, False))
check('the legend is a check box for each language that has an inventory, ticked, in the order of the project, each with its colour', re.findall(r'data-lang="(\w+)" data-color="(#[0-9a-f]{6})"', h), [('aaa', '#2e5c8a'), ('bbb', '#c07820')])
check('…and says what black and colour mean, and that a language can be unticked', ('In black: sounds found in all the languages shown' in h, 'Untick a language' in h), (True, True))
check('every sound says which languages have it, whatever its colour', all('data-langs="' in m for m in re.findall(r'<span class="ph [^>]*>', h3)) and len(re.findall(r'<span class="ph [^>]*>', h3)) == 2, True)
check('the table has the columns and rows as defined, in that order, and the author’s own', (lambda hh: (hh.index('Alveolar') > hh.index('Bilabial'), hh.index('Nasal') > hh.index('Plosive')))(html({}, cols=('Bilabial', 'Alveolar'))), (True, True))
hv = html({'aaa': {'Close': {'Front': 'i y', 'Back': 'u'}}}, cols=('Front', 'Central', 'Back', 'Labial-velar'), rows=('Close', 'Open'), kind='vowels')
check('a vowel chart is a chart of its own, with its own axes', ('data-kind="vowels"' in hv, 'Labial-velar' in hv, hv.count('<tr>')), (True, True, 3))
bad_h = html({'aaa': {'Plosive': {'Bilabial': '<img src=x onerror=alert(1)> p'}}}, caption='<b>x</b>', rows=('<i>row</i>', 'Plosive'))
check('everything typed is escaped: no element is made', ('<img' in bad_h, '<b>' in bad_h, '<i>' in bad_h, '&lt;img' in bad_h), (False, False, False, True))
hc = html({'aaa': {'Plosive': {'Bilabial': 'p'}}}, langs=[{'code': 'aaa', 'name': 'A', 'color': 'red;background:url(//evil)'}, {'code': 'bbb', 'name': 'B', 'color': '#abc'}]).replace('\n', '')
hc2 = html({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Bilabial': 'k'}}}, langs=[{'code': 'aaa', 'name': 'A', 'color': 'red;background:url(//evil)'}, {'code': 'bbb', 'name': 'B', 'color': '#abc'}])
check('a colour that is not a hex colour is replaced by grey, so nothing can be slipped into the style; #abc becomes #aabbcc', ('evil' in hc2, '#808080' in hc2, '#aabbcc' in hc2), (False, True, True))
check('a colour that is not a hex colour never reaches the check boxes either', ('evil' in hc2, 'data-color="#808080"' in hc2, 'data-color="#aabbcc"' in hc2), (False, True, True))

# ── the caption: above the table, numbered by the caller, in the words of the project ──
hc = PT.render_html(spec({'aaa': {'Plosive': {'Bilabial': 'p'}}}, caption='The consonants of Alpha'), LANGS, number=3)
check('the caption is above the table: “Table 3 – The consonants of Alpha”, in a caption element that comes before the table', ('<figcaption class="caption caption-table"><span class="cap-label">Table 3</span><span class="cap-text"> – The consonants of Alpha</span></figcaption>' in hc, hc.index('<figcaption') < hc.index('<table')), (True, True))
check('without a caption text only the label and the number are shown', '<figcaption class="caption caption-table"><span class="cap-label">Table 7</span></figcaption>' in PT.render_html(spec({}, caption=''), LANGS, number=7), True)
check('there is no title anywhere in the chart (no heading, no title element before the caption)', ('<h' in hc, hc.count('<figcaption')), (False, 1))
hl = PT.render_html(spec({}, caption='Les consonnes'), LANGS, number=2, lab={'table': 'Tableau', 'figure': 'Figure', 'separator': ' : '})
check('the words and the separator are the project’s: “Tableau 2 : Les consonnes”', 'Tableau 2</span><span class="cap-text"> : Les consonnes' in hl, True)
check('the caption text is escaped', ('<b>' in PT.render_html(spec({}, caption='<b>x</b>'), LANGS, number=1), '&lt;b&gt;x' in PT.render_html(spec({}, caption='<b>x</b>'), LANGS, number=1)), (False, True))

# ── the numbers through a section ──
VALID = lambda cap: '{"kind":"vowels","caption":"%s","columns":["Front"],"rows":["Close"],"inventory":{}}' % cap
blocks = [VALID('one'), '{broken', VALID('two'), '{"kind":"nope"}', VALID('three')]
out = PT.put_back(''.join(f'<p>PHONOTABLEXZ{i}ZX</p>' for i in range(5)), blocks, LANGS, start=4)
check('the charts are numbered in the order of the text, from the number after those of the earlier sections; a block that cannot be shown has a message and takes no number', re.findall(r'Table (\d+)</span><span class="cap-text"> – (\w+)', out), [('5', 'one'), ('6', 'two'), ('7', 'three')])
check('…and how many charts a section has is counted the same way (the readable ones)', (PT.count_valid(blocks, LANGS), PT.count_valid([], LANGS)), (3, 0))
check('the LaTeX table has the caption and no number of its own (LaTeX numbers it)', ('\\caption{two}' in PT.put_back('PHONOTABLEXZ0ZX', [VALID('two')], LANGS, 'latex', start=9), 'Table 10' in PT.put_back('PHONOTABLEXZ0ZX', [VALID('two')], LANGS, 'latex', start=9)), (True, False))

# ── the label: how the text refers to a chart ──
check('a chart may have a label (letters, digits, - and _: the rest becomes -), and has none unless the author gives one', (PT.clean({'kind': 'vowels', 'label': ' my chart! ', 'columns': ['a'], 'rows': ['b']}, CODES)[0]['label'], PT.clean({'kind': 'vowels', 'columns': ['a'], 'rows': ['b']}, CODES)[0]['label'], PT.clean({'kind': 'vowels', 'label': 5, 'columns': ['a'], 'rows': ['b']}, CODES)[0]['label']), ('my-chart', '', ''))
hl = PT.render_html(spec({}, caption='x') | {'label': 'cons'}, LANGS, number=2)
check('a chart with a label has the anchor that links go to (tab-label); one without has none', ('id="tab-cons" data-label="cons"' in hl, 'id="tab-' in PT.render_html(spec({}, caption='x'), LANGS, number=2)), (True, False))
check('a preview has no anchor (the page would have the id twice)', 'id="tab-' in PT.render_html(spec({}, caption='x') | {'label': 'cons'}, LANGS, number=2, anchors=False), False)
check('in LaTeX the label comes after the caption', '\\caption{x}\n\\label{tab:cons}\n' in PT.render_latex(spec({}, caption='x') | {'label': 'cons'}, LANGS), True)
LBL = lambda lab, cap: '{"kind":"vowels","label":"%s","caption":"%s","columns":["Front"],"rows":["Close"],"inventory":{}}' % (lab, cap)
check('the charts of a section that can be referred to, in order: label and caption (a block that cannot be read is not one)', PT.list_charts([LBL('a', 'One'), '{broken', LBL('', 'Two'), LBL('c', 'Three')], LANGS), [('a', 'One'), ('', 'Two'), ('c', 'Three')])

# ── LaTeX ──
tex = PT.render_latex(spec({'aaa': {'Plosive': {'Bilabial': 'p b'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}, 'Nasal': {'Alveolar': 'n_#'}}}, caption='A & B'), LANGS)
check('LaTeX: a table with the caption, the columns and the rows, in booktabs style, scaled to the line', ('\\caption{A \\& B}' in tex, '\\resizebox{\\linewidth}' in tex, '\\toprule' in tex, ' & Bilabial & Alveolar \\\\' in tex, 'Plosive & ' in tex), (True,) * 5)
check('LaTeX: a shared sound is plain, a sound of one language is in its colour, special characters are escaped', ('p' in tex, '\\textcolor[HTML]{2E5C8A}{b}' in tex, '\\textcolor[HTML]{C07820}{n\\_\\#}' in tex), (True, True, True))
tex3 = PT.render_latex(spec({'aaa': {'Plosive': {'Bilabial': 't'}}, 'bbb': {'Plosive': {'Bilabial': 't'}}, 'ccc': {'Plosive': {'Bilabial': 'k'}}}), LANGS)
check('LaTeX: a sound of two of three languages is printed once for each, in each colour', '\\textcolor[HTML]{2E5C8A}{t}\\,\\textcolor[HTML]{C07820}{t}' in tex3, True)

# ── in a section ──
src = 'Intro.\n\n```phonotable\n{"kind":"vowels","columns":["Front"],"rows":["Close"],"inventory":{"aaa":{"Close":{"Front":"i"}}}}\n```\n\nBetween.\n\n```phonotable\n{"kind":"consonants","columns":["Bilabial"],"rows":["Plosive"],"inventory":{}}\n```\n\nEnd with *markdown*.\n'
md, blocks = PT.extract(src)
check('each block is lifted out and marked on a line of its own; the rest of the text is untouched', (len(blocks), md.count('PHONOTABLEXZ'), 'Intro.' in md and 'Between.' in md and 'End with *markdown*.' in md, '```' in md), (2, 2, True, False))
out = PT.put_back('<p>Intro.</p>\n<p>PHONOTABLEXZ0ZX</p>\n<p>Between.</p>\n<p>PHONOTABLEXZ1ZX</p>', blocks, LANGS)
check('the charts come back in place, not inside a paragraph', (out.count('<figure class="phonotable"'), '<p><figure' in out, out.index('data-kind="vowels"') < out.index('data-kind="consonants"')), (2, False, True))
check('a block that cannot be read becomes a message, never an error, and the message is escaped', PT.render_block('{<b>', LANGS).startswith('<div class="shortcode-error">Phonological table: ') and '<b>' not in PT.render_block('{<b>', LANGS), True)
check('a text with no block is not touched', PT.extract('Just *text*.\n\n```python\nx = 1\n```\n'), ('Just *text*.\n\n```python\nx = 1\n```\n', []))
check('an unclosed block is left as it is', PT.extract('```phonotable\n{"kind"')[1], [])
check('Windows line ends are fine', len(PT.extract(src.replace('\n', '\r\n'))[1]), 2)
check('LaTeX of a block that cannot be read is a comment, not an error', PT.render_block('{oops', LANGS, 'latex').startswith('% phonological table:'), True)

print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
