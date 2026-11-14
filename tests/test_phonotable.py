"""
Direct tests of phonotable.py (no server): the definition of a chart, the merging of the languages' inventories, and its HTML and LaTeX.
Run alone with:  python tests/test_phonotable.py
"""
import json
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

# ── HTML: a tag after each sound, a coloured background for each cell ──
h = html({'aaa': {'Plosive': {'Bilabial': 'p b'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}})
check('a sound of all the languages has its tags hidden (they appear only if the reader unticks a language)', '<span class="ph" data-langs="aaa bbb"><span class="ph-seg" data-seg="p"' in h and '<span class="ph-tag" data-lang="aaa" style="--tag:#2e5c8a" title="Alpha" hidden>AAA</span>' in h, True)
check('a sound of one language only is followed by a tag in the colour of the language, with its abbreviation in capitals, never hidden', '<span class="ph-tag" data-lang="aaa" style="--tag:#2e5c8a" title="Alpha">AAA</span></span>' in h, True)
check('the text of the sound itself carries no colour', 'color:' in re.sub(r'--tag:#[0-9a-f]{6}', '', h.split('<tbody>')[1].split('</tbody>')[0]), False)
LA = [dict(l, abbr=a) for l, a in zip(LANGS, ('Aa', 'Bb', 'Cc'))]
check('the tag is the abbreviation of the language (project.json), in capitals', '>AA</span>' in html({'aaa': {'Plosive': {'Bilabial': 'p b'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}}, langs=LA), True)
h3 = html({'aaa': {'Plosive': {'Bilabial': 'p t'}}, 'bbb': {'Plosive': {'Bilabial': 'p t'}}, 'ccc': {'Plosive': {'Bilabial': 'p'}}})
check('a sound of two of three languages has the tags of both, visible (a sound of all three has them hidden)', (h3.count('data-lang="aaa" style="--tag:#2e5c8a" title="Alpha">'), h3.count('data-lang="bbb" style="--tag:#c07820" title="Beta">'), h3.count('data-lang="ccc" style="--tag:#2f7a3a" title="Gamma" hidden>')), (1, 1, 1))
check('a cell is tinted with the colours of the languages of the sounds that not all the languages have (here t: Alpha and Beta), side by side; the sound all three share does not count', 'style="--cell-bg:linear-gradient(90deg,#2e5c8a2e 0% 50%,#c078202e 50% 100%)"' in h3, True)
check('a cell where every sound is found in all the languages is not tinted at all: everything in common stays plain', html({'aaa': {'Plosive': {'Bilabial': 'p b'}}, 'bbb': {'Plosive': {'Bilabial': 'p b'}}, 'ccc': {'Plosive': {'Bilabial': 'p b'}}}).count('--cell-bg'), 0)
check('the stripes: two colours are halves', PT._stripes(['#111111', '#222222']), 'linear-gradient(90deg,#1111112e 0% 50%,#2222222e 50% 100%)')
check('a cell has the colours of the languages that have something in it, not of the others', 'data-langs="aaa"' in html({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Alveolar': 't'}}}) and '--cell-bg:linear-gradient(90deg,#2e5c8a2e 0% 100%)' in html({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Alveolar': 't'}}}), True)
check('an empty cell has no tint, and a cell of one language alone is tinted with its colour', (html({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}}).count('--cell-bg'), html({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Alveolar': 't'}}}).count('--cell-bg')), (0, 2))
h1 = html({'aaa': {'Plosive': {'Bilabial': 'p b'}}}, langs=LANGS[:1])
check('one language: no tags, no tints, no legend', ('ph-tag' in h1, '--cell-bg' in h1, 'phono-legend' in h1), (False, False, False))
check('with several languages a legend says what the tags and colours mean, naming the languages that have an inventory', ('phono-legend' in h and 'Alpha' in h.split('phono-legend')[1] and 'Beta' in h.split('phono-legend')[1] and 'Gamma' not in h.split('phono-legend')[1]), True)
hs = html({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}})
check('with two languages the legend is there even when every sound is shared (the reader may still choose the languages to show)', ('phono-legend' in hs, hs.count('<input type="checkbox" checked data-lang='), 'phono-legend' in html({'aaa': {'Plosive': {'Bilabial': 'p'}}}, langs=LANGS[:1])), (True, 2, False))
check('the legend is a check box for each language that has an inventory, ticked, in the order of the project, each with its colour and its tag', (re.findall(r'data-lang="(\w+)" data-color="(#[0-9a-f]{6})"', h), h.count('class="lg-tag"')), ([('aaa', '#2e5c8a'), ('bbb', '#c07820')], 2))
check('…and says that a sound without a tag is in all the languages shown, that a language can be unticked, and that the sounds can be hovered over', ('a sound without a tag is found in all the languages shown' in h, 'Untick a language' in h, 'Hover over a sound' in h), (True, True, True))
check('every sound says which languages have it', all('data-langs="' in m for m in re.findall(r'<span class="ph" [^>]*>', h3)) and len(re.findall(r'<span class="ph" [^>]*>', h3)) == 2, True)
check('the table has the columns and rows as defined, in that order, and the author’s own', (lambda hh: (hh.index('Alveolar') > hh.index('Bilabial'), hh.index('Nasal') > hh.index('Plosive')))(html({}, cols=('Bilabial', 'Alveolar'))), (True, True))
hv = html({'aaa': {'Close': {'Front': 'i y', 'Back': 'u'}}}, cols=('Front', 'Central', 'Back', 'Labial-velar'), rows=('Close', 'Open'), kind='vowels')
check('a vowel chart is a chart of its own, with its own axes', ('data-kind="vowels"' in hv, 'Labial-velar' in hv, hv.count('<tr>')), (True, True, 3))
bad_h = html({'aaa': {'Plosive': {'Bilabial': '<img src=x onerror=alert(1)> p'}}}, caption='<b>x</b>', rows=('<i>row</i>', 'Plosive'))
check('everything typed is escaped: no element is made', ('<img' in bad_h, '<b>' in bad_h, '<i>' in bad_h, '&lt;img' in bad_h), (False, False, False, True))
LX = [{'code': 'aaa', 'name': 'A', 'abbr': 'A"><script>', 'color': 'red;background:url(//evil)'}, {'code': 'bbb', 'name': 'B', 'color': '#abc'}]
hc2 = html({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Bilabial': 'k'}}}, langs=LX)
check('a colour that is not a hex colour is replaced by grey, so nothing can be slipped into the style; #abc becomes #aabbcc; the abbreviation is escaped', ('evil' in hc2, '#808080' in hc2, '#aabbcc' in hc2, '<script>' in hc2), (False, True, True, False))
check('a colour that is not a hex colour never reaches the check boxes either', ('evil' in hc2, 'data-color="#808080"' in hc2, 'data-color="#aabbcc"' in hc2), (False, True, True))
check('a language with no abbreviation is tagged with its code', '>BBB</span>' in hc2, True)

# ── vowels: short on the left, long on the right, one legend ──
VI = {'aaa': {'Close': {'Front': 'i', 'Back': 'u'}, 'Open': {'Central': 'a'}}, 'bbb': {'Close': {'Front': 'i iː', 'Back': 'u'}, 'Open': {'Central': 'a aː'}}}
hv2 = html(VI, cols=('Front', 'Central', 'Back'), rows=('Close', 'Open'), kind='vowels')
tabs2 = re.findall(r'<table class="phono">.*?</table>', hv2, re.S)
check('a chart of vowels that has long vowels (a sound ending in ː) is two tables in one figure, short first (left) and long second (right), with one legend and one caption', (len(tabs2), hv2.count('<figure'), hv2.count('phono-legend"'), hv2.count('figcaption class'), 'phono-pair' in hv2, tabs2[0].count('>Short<'), tabs2[1].count('>Long<')), (2, 1, 1, 1, True, 1, 1))
check('the short vowels are in the first table, the long ones in the second, each with its tags', ('data-seg="i"' in tabs2[0] and 'data-seg="a"' in tabs2[0] and 'ː' not in tabs2[0], 'data-seg="iː"' in tabs2[1] and 'data-seg="aː"' in tabs2[1] and 'data-seg="i"' not in tabs2[1]), (True, True))
check('both tables have the same rows and columns', [re.findall(r'<th scope="(?:col|row)">([^<]+)</th>', x) for x in tabs2][0] == [re.findall(r'<th scope="(?:col|row)">([^<]+)</th>', x) for x in tabs2][1], True)
check('a chart of vowels without a long vowel is one table, as before; so is a chart of consonants even with ː in it', (html({'aaa': {'Close': {'Front': 'i'}}}, cols=('Front',), rows=('Close',), kind='vowels').count('<table'), html({'aaa': {'Plosive': {'Bilabial': 'pː'}}}).count('<table')), (1, 1))

# ── comparative tables of words (kind "lexical") ──
check('a word is split at the tilde: the first part is the entry, the others are its variants; the identifier follows @ ; spaces are cleaned; a word keeps its letters (ō)', (PT.lex_parts('  ni~nē '), PT.lex_parts('na@pron_1sg ~ nā'), PT.lex_parts('dō\u0304tōl'), PT.lex_parts('~ ~'), PT.lex_parts('a@')), ([('ni', ''), ('nē', '')], [('na', 'pron_1sg'), ('nā', '')], [('dō\u0304tōl', '')], [], [('a', '')]))
check('an identifier that is not one (spaces, quotes, tags) is dropped, not trusted; a word is cut at 60 characters, a word has at most 4 parts', (PT.lex_parts('x@a b'), PT.lex_parts('x@"><b>'), len(PT.lex_parts('y' * 100)[0][0]), len(PT.lex_parts('a~b~c~d~e~f'))), ([('x', '')], [('x', '')], 60, 4))
check('the words of a cell are separated by semicolons, written in a standard way, without repeats; at most 6', (PT.lex_units('ni ~ nē; ni~nē ;  na'), len(PT.lex_units(';'.join('w%d' % i for i in range(10))))), (['ni ~ nē', 'na'], 6))
LX = lambda inv, **kw: PT.clean(dict({'kind': 'lexical', 'caption': 'P', 'columns': ['sg', 'pl'], 'rows': ['1', '2'], 'inventory': inv}, **kw), CODES)[0]
sl = LX({'aaa': {'1': {'sg': 'na', 'pl': 'ni ~ nē'}}, 'bbb': {'1': {'sg': 'na'}}, 'zzz': {'1': {'sg': 'x'}}, 'ccc': {'3': {'sg': 'x'}}})
check('a lexical table is a table (rows, columns, a language of the project, no segments, no pos unless given), the words in their standard form', (sl['kind'], sl['inventory'], sl['segments'], sl['pos']), ('lexical', {'aaa': {'1': {'sg': 'na', 'pl': 'ni ~ nē'}}, 'bbb': {'1': {'sg': 'na'}}}, {}, ''))
check('the part of speech is kept for a lexical table only (and cut at 30 characters); a chart of sounds has none', (LX({}, pos='  pro. ')['pos'], len(LX({}, pos='x' * 50)['pos']), 'pos' in spec({})), ('pro.', 30, False))
check('a lexical table needs rows and columns like the others, and nothing is suggested for its axes', (PT.clean({'kind': 'lexical', 'columns': [], 'rows': []}, CODES)[1] is not None, PT.DEFAULT_AXES['lexical']), (True, {'columns': [], 'rows': []}))
LL = [{'code': 'aaa', 'name': 'Alpha', 'abbr': 'Al', 'color': '#2e5c8a'}, {'code': 'bbb', 'name': 'Beta', 'abbr': 'Be', 'color': '#c07820'}, {'code': 'ccc', 'name': 'Gamma', 'abbr': 'Ga', 'color': '#2f7a3a'}]
sx = LX({'aaa': {'1': {'sg': 'na', 'pl': 'ni ~ nē'}, '2': {'sg': 'nik'}}, 'bbb': {'1': {'sg': 'na', 'pl': 'ni'}, '2': {'sg': 'nēk'}}})
hx = PT.render_html(sx, LL)
check('a word that all the languages of the table have is plain and its tags are hidden; a word of some has the tags of those languages, visible', ('<span class="ph" data-langs="aaa bbb"><span class="lx-form"><span class="lx-plain">na</span></span><span class="ph-tag" data-lang="aaa" style="--tag:#2e5c8a" title="Alpha" hidden>AL</span>' in hx, '<span class="ph-tag" data-lang="bbb" style="--tag:#c07820" title="Beta">BE</span>' in hx), (True, True))
check('a word and its variant are one word under one tag, with the tilde between them; two words that differ are two words (ni ~ nē is not ni)', ('<span class="lx-form"><span class="lx-plain">ni</span> <span class="lx-tilde">~</span> <span class="lx-plain">nē</span></span><span class="ph-tag" data-lang="aaa"' in hx, hx.count('data-langs="bbb"><span class="lx-form"><span class="lx-plain">ni</span>'), ), (True, 1))
check('no cell of a lexical table is tinted, and the cells are not those of the sounds (the legend script leaves them alone)', ('--cell-bg' in hx, 'ph-cell' in hx, 'class="lx-cell"' in hx), (False, False, True))
check('a lexical table has no hover box on its words (no ph-seg), a legend of the languages and a note that speaks of words', ('ph-seg' in hx, 'phono-legend' in hx, 'The tag after a word' in hx, 'sound' in hx.split('pl-note')[1]), (False, True, True, False))
def resolver(code, word, ident, pos):
    return {'na': ('pro_1sg', '1SG pronoun'), 'ni': ('pro_3sg', '')}.get(word) if not ident else ((ident, 'by id') if ident == 'known' else None)
hr = PT.render_html(LX({'aaa': {'1': {'sg': 'na', 'pl': 'ni ~ nē'}, '2': {'sg': 'nik@known', 'pl': 'x@nope'}}, 'bbb': {'1': {'sg': 'na'}}}), LL, resolver=resolver)
check('a word that is an entry of the dictionary is a link to it (dictionary.html#id), with its gloss as the title; each part of a word on its own; a word that is not is plain text', ('<a class="lx-link" href="dictionary.html#pro_1sg" title="1SG pronoun">na</a>' in hr, '<a class="lx-link" href="dictionary.html#pro_3sg">ni</a> <span class="lx-tilde">~</span> <span class="lx-plain">nē</span>' in hr), (True, True))
check('word@id links to that entry when it exists, and is plain text when it does not; the identifier is never shown', ('href="dictionary.html#known" title="by id">nik</a>' in hr, '<span class="lx-plain">x</span>' in hr, '@' in re.sub(r'<[^>]+>', '', hr)), (True, True, False))
seen = []
PT.render_html(LX({'aaa': {'1': {'sg': 'na'}}}, pos='pro.'), LL, resolver=lambda c, w, i, pos: seen.append((c, w, i, pos)))
check('the resolver is given the language, the word, the identifier and the part of speech of the table', seen, [('aaa', 'na', '', 'pro.')])
hn = PT.render_html(sx, LL)
check('without a resolver nothing is a link; with a link, the href is escaped', ('<a ' in hn, '"' in PT.render_html(LX({'aaa': {'1': {'sg': 'x'}}}), LL, resolver=lambda *a: ('a"><script>', 't"x')).split('href=')[1].split(' title')[0][1:-1]), (False, False))
check('a link made by hand cannot break the page: the identifier of a link is escaped', '<script>' in PT.render_html(LX({'aaa': {'1': {'sg': 'x'}}}), LL, resolver=lambda *a: ('a"><script>', 't')), False)
check('the entries of a table: the first part of each word (a variant is not an entry), with the identifier typed', sorted(PT.entries_of(LX({'aaa': {'1': {'sg': 'ni ~ nē', 'pl': 'na@p1'}}}))), [('1', 'pl', 'aaa', 'na', 'p1'), ('1', 'sg', 'aaa', 'ni', '')])
tx = PT.render_latex(sx, LL)
check('LaTeX: one plain table for each language, the words as they are read (a tilde, no identifier), no link', ('\\textasciitilde{}' in tx, '@' in tx, '\\href' in tx, tx.count('\\begin{table}')), (True, False, False, 2))
chk = PT.list_charts(['{"kind":"lexical","label":"pron","caption":"P","columns":["a"],"rows":["b"],"inventory":{}}'], LL)
check('a lexical table is numbered and can be referred to like the other tables', [(a, b) for a, b, _p in chk], [('pron', 'P')])
check('lexical_specs: the lexical tables of a section, cleaned (the others are not)', [s_['kind'] for s_ in PT.lexical_specs(['{"kind":"vowels","columns":["a"],"rows":["b"],"inventory":{}}', '{"kind":"lexical","columns":["a"],"rows":["b"],"inventory":{}}', '{oops'], LL)], ['lexical'])

# ── the sounds: description, audio, PHOIBLE ──
INV = {'aaa': {'Plosive': {'Bilabial': 'p ᵐb'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}}
def seg(segments): return PT.clean({'kind': 'consonants', 'columns': ['Bilabial'], 'rows': ['Plosive'], 'inventory': INV, 'segments': segments}, CODES)[0]['segments']
check('a sound has a description, an audio file and a PHOIBLE link; a segment with none of them is not kept, nor one of a sound that is not in the chart', seg({'ᵐb': {'description': ' prenasalised  voiced bilabial plosive ', 'audio': 'mb.mp3', 'phoible': 'https://phoible.org/parameters/1'}, 'p': {'description': ''}, 'z': {'description': 'x'}}), {'ᵐb': {'description': 'prenasalised voiced bilabial plosive', 'audio': 'mb.mp3', 'phoible': 'https://phoible.org/parameters/1'}})
check('no segments at all: an empty dictionary (also for anything that is not one)', (seg(None), seg([]), seg('x'), seg({'p': 'x'})), ({}, {}, {}, {}))
check('a PHOIBLE link is http(s) only; “phoible.org/…” and “www.phoible.org/…” get https://; javascript:, data:, a space, an unknown form: nothing', [PT._link(x) for x in ('https://phoible.org/a', 'http://x.org/b', 'phoible.org/c', 'www.phoible.org/d', 'javascript:alert(1)', 'data:text/html,x', 'https://a b', 'ftp://x.org/y', 'phoible', '', None)], ['https://phoible.org/a', 'http://x.org/b', 'https://phoible.org/c', 'https://www.phoible.org/d', '', '', '', '', '', '', ''])
check('an audio is the name of a file with an audio extension (a subfolder is fine) or an http(s) address; no .., no hidden part, no other kind of file', [PT._audio(x) for x in ('p.mp3', 'num/p.OGG', 'https://x.org/p.wav', 'https://x.org/play?id=1', '../p.mp3', 'a/../p.mp3', '.p.mp3', '/etc/p.mp3', 'p.exe', 'p.html', 'p', 'a\\p.mp3', 'javascript:alert(1)', '')], ['p.mp3', 'num/p.OGG', 'https://x.org/p.wav', 'https://x.org/play?id=1', '', '', '', '', '', '', '', '', '', ''])
check('the address the page uses: the audio folder for a file (the name quoted), the address as it is for a URL, nothing for nothing', (PT.audio_url('p.mp3'), PT.audio_url('num/é.mp3'), PT.audio_url('https://x.org/p.wav'), PT.audio_url(''), PT.audio_url('../x.mp3')), ('audio/p.mp3', 'audio/num/%C3%A9.mp3', 'https://x.org/p.wav', '', ''))
check('limits: a description is cut at 200 characters, a link longer than 400 is refused, at most 400 segments', (len(seg({'p': {'description': 'x' * 500}})['p']['description']), PT._link('https://x.org/' + 'a' * 400), PT._audio('a' * 400 + '.mp3')), (200, '', ''))
hs = PT.render_html(PT.clean({'kind': 'consonants', 'columns': ['Bilabial'], 'rows': ['Plosive'], 'inventory': INV, 'segments': {'ᵐb': {'description': 'prenasalised voiced bilabial plosive', 'audio': 'mb.mp3', 'phoible': 'https://phoible.org/x'}}}, CODES)[0], LANGS)
check('each sound is an element carrying what the hover box shows: the sound, the description, the address of the audio, the PHOIBLE link', '<span class="ph-seg" data-seg="ᵐb" data-desc="prenasalised voiced bilabial plosive" data-audio="audio/mb.mp3" data-phoible="https://phoible.org/x">ᵐb</span>' in hs, True)
check('a sound without anything has the same attributes, empty', '<span class="ph-seg" data-seg="p" data-desc="" data-audio="" data-phoible="">p</span>' in hs, True)
he = PT.render_html(PT.clean({'kind': 'consonants', 'columns': ['Bilabial'], 'rows': ['Plosive'], 'inventory': {'aaa': {'Plosive': {'Bilabial': 'p'}}}, 'segments': {'p': {'description': '"><img src=x onerror=1> <b>', 'phoible': 'https://x.org/"><script>'}}}, CODES)[0], LANGS)
check('what the author typed in a segment is escaped (the description) or refused (a link with a quote)', ('<img' in he, '<script' in he, '&lt;img' in he), (False, False, True))
pr = PT.segment_problems({'p': {'audio': 'p.exe', 'phoible': 'javascript:1', 'description': 'ok'}, 'ᵐb': {'audio': 'mb.mp3'}, 'z': {'audio': 'x.exe'}}, PT.clean({'kind': 'consonants', 'columns': ['Bilabial'], 'rows': ['Plosive'], 'inventory': INV, 'segments': {'p': {'audio': 'p.exe'}, 'ᵐb': {'audio': 'mb.mp3'}}}, CODES)[0])
check('what was typed and not kept is reported, for the sounds of the chart only', (len(pr), pr[0].startswith('p: the audio'), pr[1].startswith('p: the PHOIBLE')), (2, True, True))
check('LaTeX does not change: no tags, no segments in it', ('ph-' in PT.render_latex(spec(INV), LANGS), 'prenasalised' in PT.render_latex(PT.clean({'kind': 'consonants', 'columns': ['Bilabial'], 'rows': ['Plosive'], 'inventory': INV, 'segments': {'p': {'description': 'prenasalised'}}}, CODES)[0], LANGS)), (False, False))

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
check('in LaTeX the label comes after the caption (a chart that has no language yet is one table)', '\\caption{x}\n\\label{tab:cons}\n' in PT.render_latex(spec({}, caption='x') | {'label': 'cons'}, LANGS), True)
LBL = lambda lab, cap: '{"kind":"vowels","label":"%s","caption":"%s","columns":["Front"],"rows":["Close"],"inventory":{}}' % (lab, cap)
check('the charts of a section that can be referred to, in order: label and caption (a block that cannot be read is not one)', [(a, b) for a, b, _p in PT.list_charts([LBL('a', 'One'), '{broken', LBL('', 'Two'), LBL('c', 'Three')], LANGS)], [('a', 'One'), ('', 'Two'), ('c', 'Three')])

# ── LaTeX: one table for each language ──
two = spec({'bbb': {'Plosive': {'Bilabial': 'p'}, 'Nasal': {'Alveolar': 'n_#'}}, 'aaa': {'Plosive': {'Bilabial': 'p b'}}}, caption='A & B')
tex = PT.render_latex(two, LANGS)
tabs = tex.split('\\begin{table}')[1:]
check('a chart with the sounds of two languages is two tables, one for each language in the order of the project (not of the typing), as a group: started, next, ended', (len(tabs), tex.startswith('\\tabgroupstart\n'), tex.count('\\tabgroupnext'), tex.rstrip().endswith('\\tabgroupend'), tex.index('Alpha') < tex.index('Beta')), (2, True, 1, True, True))
check('the caption of each has the name of its language added when the caption has no {language}, and the caption is escaped', ('\\caption{A \\& B (Alpha)}' in tex, '\\caption{A \\& B (Beta)}' in tex), (True, True))
check('each table has only the rows and columns of its language (the empty ones are dropped), booktabs style, scaled to the line, the sounds in the IPA font', ('Alveolar' not in tabs[0] and 'Nasal' not in tabs[0] and 'Bilabial' in tabs[0], 'Alveolar' in tabs[1] and 'Nasal' in tabs[1], '\\toprule' in tabs[0], '\\resizebox{\\linewidth}' in tabs[0], '{\\ipafont\\resizebox' in tabs[0]), (True,) * 5)
check('the sounds are plain: no colour, shared or not; special characters are escaped; a sound of one language is only in its table', ('\\textcolor' in tex, 'n\\_\\#' in tabs[1], 'n\\_\\#' in tabs[0], ' & p b ' in tabs[0] or ' & p b' in tabs[0]), (False, True, False, True))
check('the rows of a table end with \\\\ (two backslashes), the header too', (' & Bilabial \\\\' in tabs[0] and '\\\\\\\\' not in tabs[0], ' & Bilabial & Alveolar \\\\' in tabs[1]), (True, True))
ph = PT.render_latex(spec({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}}, caption='Consonants of {language}'), LANGS)
check('{language} in a caption is replaced, in each table, by the name of its language (nothing is added then); an empty caption is the name alone', ('\\caption{Consonants of Alpha}' in ph, '\\caption{Consonants of Beta}' in ph, '(Alpha)' in ph, '\\caption{Alpha}' in PT.render_latex(spec({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}}, caption=''), LANGS)), (True, True, False, True))
one = PT.render_latex(spec({'bbb': {'Plosive': {'Bilabial': 'p'}}}, caption='Sounds of {language}'), LANGS)
check('a chart with one language is not split: one table, no group, the caption as it is (with {language} filled)', (one.count('\\begin{table}'), '\\tabgroup' in one, '\\caption{Sounds of Beta}' in one, '(Beta)' in one), (1, False, True, False))
plain1 = PT.render_latex(spec({'bbb': {'Plosive': {'Bilabial': 'p'}}}, caption='Sounds'), LANGS)
check('…and without the placeholder nothing is added to its caption', '\\caption{Sounds}' in plain1, True)
three = PT.render_latex(spec({'aaa': {'Plosive': {'Bilabial': 't'}}, 'bbb': {'Plosive': {'Bilabial': 't'}}, 'ccc': {'Plosive': {'Bilabial': 'k'}}}), LANGS)
check('three languages: three tables; a sound that two share is in each of their tables', (three.count('\\begin{table}'), three.count(' & t '), three.count(' & k ')), (3, 2, 1))
lab = PT.render_latex(spec({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {'Plosive': {'Bilabial': 'p'}}, 'ccc': {'Plosive': {'Bilabial': 'p'}}}) | {'label': 'cons'}, LANGS)
check('with a label: each table has its own (tab:label:code), the first also the number of the group and tab:label:first, the last the letter of the group (tab:label:last)', ('\\label{tab:cons:aaa}' in lab and '\\label{tab:cons:bbb}' in lab and '\\label{tab:cons:ccc}' in lab, lab.count('\\labelas{tab:cons}{\\arabic{table}}'), lab.count('\\label{tab:cons:first}'), lab.count('\\labelas{tab:cons:last}{\\alph{tabpart}}'), lab.index('tab:cons:first') < lab.index('tab:cons:ccc') < lab.index('tab:cons:last')), (True, 1, 1, 1, True))
check('without a label there are no labels', '\\label' in PT.render_latex(two, LANGS), False)
check('a language that has no sound in the chart gets no table', PT.render_latex(spec({'aaa': {'Plosive': {'Bilabial': 'p'}}, 'bbb': {}, 'ccc': {'Plosive': {'Bilabial': 'k'}}}), LANGS).count('\\begin{table}'), 2)

# ── {language} on the website ──
check('on the website one chart is shown for all: {language} is the names of the languages that have sounds in it, in the order of the project, with “and” before the last', (PT.caption_names(two, LANGS), re.search(r'cap-text"> – ([^<]*)<', PT.render_html(spec({'bbb': {'Plosive': {'Bilabial': 'p'}}, 'aaa': {'Plosive': {'Bilabial': 'p'}}, 'ccc': {'Plosive': {'Bilabial': 'k'}}}, caption='Sounds of {language}'), LANGS, number=1)).group(1)), (['Alpha', 'Beta'], 'Sounds of Alpha, Beta and Gamma'))
check('a chart with no sound yet says all the languages of the project; a caption without the placeholder is as written', (PT.caption_names(spec({}), LANGS), 'Alpha, Beta and Gamma' in PT.render_html(spec({}, caption='All: {language}'), LANGS, number=1), 'Sounds</span>' in PT.render_html(spec({}, caption='Sounds'), LANGS, number=1)), (['Alpha', 'Beta', 'Gamma'], True, True))
lst = PT.list_charts([LBL('a', 'Sounds of {language}'), json.dumps({'kind': 'vowels', 'label': 'b', 'caption': 'Two', 'columns': ['F'], 'rows': ['C'], 'inventory': {'aaa': {'C': {'F': 'i'}}, 'bbb': {'C': {'F': 'u'}}}})], LANGS)
check('what the grammar can refer to: the caption as the site shows it, and the languages that get a table in the exports (none for a chart that is not split)', lst, [('a', 'Sounds of Alpha, Beta and Gamma', []), ('b', 'Two', ['aaa', 'bbb'])])

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
