"""
Direct tests of concordance.py (no server): the search of strings in sentences and their context.
Run alone with:  python tests/test_concordance.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import concordance as C

ok = bad = 0
def check(name, got, want):
    global ok, bad
    if got == want: ok += 1
    else:
        bad += 1; print(f"✗ {name}\n    got : {got!r}\n    want: {want!r}")
def spans(text, q, **kw): return C.find_spans(text, q, **kw)
def found(text, q, **kw): return [text[s:e] for s, e in C.find_spans(text, q, **kw)]

COMPOSED, COMBINING = 'Q\u014dn\u0304 va-w\u0113.', 'Qo\u0304n\u0304 va-we\u0304.'
S = C.nfc(COMPOSED)                                                  # Qōn̄ va-wē.   (n̄ has no single-character form)

# ── Unicode: the same letter spelled two ways is the same letter ──
check('composed text, composed query', len(spans(COMPOSED, 'Q\u014dn\u0304')), 1)
check('combining text, composed query', len(spans(COMBINING, 'Q\u014dn\u0304')), 1)
check('composed text, combining query', len(spans(COMPOSED, 'Qo\u0304n\u0304')), 1)
check('the highlight covers the final combining mark', found(COMPOSED, 'q\u014dn\u0304', ignore_case=True), ['Q\u014dn\u0304'])
check('n is not n̄: a match may not end between a letter and its mark', (found('Q\u014dn\u0304 Q\u014dn', 'q\u014dn'), found('Q\u014dn\u0304', 'Q\u014dn')), (['Q\u014dn'], []))
check('…also when diacritics are ignored', found(COMPOSED, 'qon', ignore_diacritics=True), ['Q\u014dn\u0304'])
check('diacritics count by default', found(COMPOSED, 'qon'), [])
check('case is ignored by default', found(COMPOSED, 'QŌN̄'), ['Q\u014dn\u0304'])
check('…and can be respected', found(COMPOSED, 'qōn̄', ignore_case=False), [])
check('…the right case then matches', found(COMPOSED, 'Qōn̄', ignore_case=False), ['Q\u014dn\u0304'])
check('a letter that is not the same letter does not match (n and n̄)', found('nir n\u0304ir', 'n\u0304'), ['n\u0304'])
check('…unless diacritics are ignored', found('nir n\u0304ir', 'nir', ignore_diacritics=True), ['nir', 'n\u0304ir'])

# ── a plain string, never a pattern ──
check('a dot is a dot', (found('abc a.c', 'a.c'), found('abc', 'a.c')), (['a.c'], []))
check('brackets, stars and backslashes are characters', (found('x (a)* y', '(a)*'), found('a\\b', '\\')), (['(a)*'], ['\\']))
check('a space in the query is a space', found('Qōn̄ va-wē.', 'n̄ va'), ['n\u0304 va'])
check('several spaces in the query count as one', found('a b', 'a   b'), ['a b'])

# ── whole words and morphemes ──
T = 'Qōn̄ va-wē.'
check('anywhere: inside a word', found(T, 'a-w'), ['a-w'])
check('word: va is not a word (the word is va-wē)', found(T, 'va', match='word'), [])
check('word: the whole word va-wē is', found(T, 'va-wē', match='word'), ['va-wē'])
check('word: the full stop does not belong to the word', found(T, 'wē', match='word'), [])
check('morpheme: va is a morpheme of va-wē', found(T, 'va', match='morpheme'), ['va'])
check('morpheme: so is wē', found(T, 'wē', match='morpheme'), ['wē'])
check('morpheme: a-w is not', found(T, 'a-w', match='morpheme'), [])
check('morpheme: va- is one (its hyphen is its boundary)', found(T, 'va-', match='morpheme'), ['va-'])
check('morpheme: -wē is one', found(T, '-wē', match='morpheme'), ['-wē'])
check('an apostrophe is a letter, not the end of a word', found("ma'a ko", "ma'a", match='word'), ["ma'a"])
check('non-overlapping occurrences', len(spans('aaaa', 'aa')), 2)
check('an empty query finds nothing', spans('abc', '   '), [])

# ── context ──
sent = 'one two three four five six seven'
l, m, r, lc, rc = C.context(sent, spans(sent, 'four')[0], 2)
check('two words on each side', (l, m, r, lc, rc), ('two three', 'four', 'five six', True, True))
l, m, r, lc, rc = C.context(sent, spans(sent, 'four')[0], 10)
check('nothing cut when the sentence is short', (l, r, lc, rc), ('one two three', 'five six seven', False, False))
l, m, r, lc, rc = C.context('two three four', spans('two three four', 'hre')[0], 5)
check('a match inside a word keeps the rest of the word next to it', (l, m, r), ('two t', 'hre', 'e four'))
check('the first word: nothing on its left', C.context(sent, (0, 3), 3)[:3], ('', 'one', 'two three four'))
check('a match inside a word touches its neighbours, one between words does not', (C.touches('two three four', (5, 8)), C.touches('two three four', (4, 9))), ((True, True), (False, False)))
check('…and the hit says so', [(h['leftAdj'], h['rightAdj']) for h in C.search([{'text': 'two three four', 'lang': 'x', 'src': 's'}], 'hre')['hits']], [(True, True)])

# ── tokens and glosses ──
toks = [{'form': 'Qōn̄', 'gloss': 'afternoon'}, {'form': 'va-', 'gloss': 'LOC'}, {'form': 'wē', 'gloss': 'good'}]
check('tokens are placed in the sentence', C.align_tokens(S, toks), [(0, 4), (5, 8), (8, 10)])
check('a token that is no longer in the sentence has no place and breaks nothing', C.align_tokens(S, toks + [{'form': 'zzz'}])[-1], None)
line = {'src': 'fieldnotes', 'lang': 'drg', 'sid': 's1', 'label': 'L', 'link': 'l', 'text': S, 'translation': 'Good afternoon.', 'tokens': toks}
res = C.search([line], 'wē')
check('the gloss of the word found', res['hits'][0]['gloss'], 'good')
check('a match across two words gives both glosses', C.search([line], 'a-w')['hits'][0]['gloss'], 'LOC good')
check('the hit carries the sentence, the translation and where it is', (res['hits'][0]['sentence'], res['hits'][0]['translation'], res['hits'][0]['link'], res['hits'][0]['sid']), (S, 'Good afternoon.', 'l', 's1'))
ann = C.search([line], 'wē', annotate=lambda ln, tok: {'entry': 'good1', 'pos': 'adj.', 'secret': 'x'})['hits'][0]
check('the application can add an entry and a part of speech (and nothing else)', (ann['entry'], ann['pos'], 'secret' in ann), ('good1', 'adj.', False))
check('the glosses can be searched', [(h['left'], h['match'], h['right']) for h in C.search([line], 'LOC', scope='glosses')['hits']], [('afternoon', 'LOC', 'good')])
check('the translation can be searched', C.search([line], 'afternoon', scope='translation')['hits'][0]['match'], 'afternoon')

# ── filters, counts, limit ──
lines = [dict(line, lang='drg', src='fieldnotes'), dict(line, lang='kro', src='fieldnotes'), dict(line, lang='drg', src='recording', text='wē wē wē', tokens=[])]
r = C.search(lines, 'wē')
check('every occurrence is a hit, in corpus order, with its counts', (r['total'], r['sentences'], r['byLang'], r['bySource']), (5, 3, {'drg': 4, 'kro': 1}, {'fieldnotes': 2, 'recording': 3}))
check('a language filter', C.search(lines, 'wē', lang='kro')['total'], 1)
check('a source filter', C.search(lines, 'wē', sources=['recording'])['total'], 3)
r = C.search(lines, 'wē', limit=2)
check('a limit shows the first hits and still counts them all', (r['shown'], r['total'], r['truncated']), (2, 5, True))
for bad_q, kw in ((' ', {}), ('x' * 300, {}), ('x', {'scope': 'nope'}), ('x', {'match': 'nope'})):
    try: C.search(lines, bad_q, **kw); outcome = 'accepted'
    except ValueError: outcome = 'refused'
    check(f'refused: {bad_q[:6]!r} {kw}', outcome, 'refused')

# ── a sequence of whole words, punctuation between them ignored ──
PT = 'Wē, tē mi. Tē mi!'
check('phrase: the words follow each other, a comma between them does not matter', found(PT, 'wē tē', match='phrase'), ['Wē, tē'])
check('phrase: whole words only', found('wēs tē', 'wē tē', match='phrase'), [])
check('phrase: the same words as the n-gram counts them (two hits of tē mi)', found(PT, 'tē mi', match='phrase'), ['tē mi', 'Tē mi'])
check('phrase: a sentence boundary is only punctuation, so n-grams and this agree', found('a b. c d', 'b c', match='phrase'), ['b. c'])
check('phrase: case and diacritics follow the options', (found(PT, 'tē mi', match='phrase', ignore_case=False), found('Qōn̄ va', 'qon va', match='phrase', ignore_diacritics=True)), (['tē mi'], ['Qōn̄ va']))
check('phrase: the hit has no punctuation at its edges', found('(wē tē)', 'wē tē', match='phrase'), ['wē tē'])
ph = C.search([{'text': 'Wē, tē mi.', 'lang': 'x', 'src': 's', 'tokens': []}], 'wē tē', match='phrase')['hits'][0]
check('phrase: a hit in context', (ph['left'], ph['match'], ph['right']), ('', 'Wē, tē', 'mi.'))

# ── words ──
check('words: spaces, punctuation stripped at the edges, a hyphen stays inside', C.words('Qōn̄ va-wē.'), [('qōn̄', 'Qōn̄'), ('va-wē', 'va-wē')])
check('words: a dash on its own is nothing', [k for k, _ in C.words('a — b')], ['a', 'b'])
check('words: both spellings of a letter are one word', C.words('Qo\u0304n\u0304')[0][0] == C.words('Q\u014dn\u0304')[0][0], True)
check('words: case ignored by default, respected on request', ([k for k, _ in C.words('The Cat')], [k for k, _ in C.words('The Cat', ignore_case=False)]), (['the', 'cat'], ['The', 'Cat']))
check('words: diacritics can be ignored', [k for k, _ in C.words('Qōn̄', ignore_diacritics=True)], ['qon'])

# ── n-grams, on a corpus small enough to count by eye ──
def L(text, lang='x', src='s', **kw): return dict({'text': text, 'lang': lang, 'src': src, 'label': text, 'link': '#', 'tokens': []}, **kw)
corp = [L('a b c a b d', 'x'), L('a b c', 'y')]
g = C.ngrams(corp, 'b', n=2)
check('bigrams with b: counts', {x['text']: x['count'] for x in g['grams']}, {'a b': 3, 'b c': 2, 'b d': 1})
check('…the most frequent first, then alphabetical', [x['text'] for x in g['grams']], ['a b', 'b c', 'b d'])
check('…the occurrences, the distinct n-grams and the count of b itself', (g['occurrences'], g['distinct'], g['queryCount']), (6, 3, 3))
check('…sentences, and counts by language', ({x['text']: x['sentences'] for x in g['grams']}, g['grams'][0]['byLang']), ({'a b': 2, 'b c': 2, 'b d': 1}, {'x': 2, 'y': 1}))
g3 = C.ngrams(corp, 'b', n=3)
check('trigrams with b, where b stands in each', {x['text']: (x['count'], x['hl']) for x in g3['grams']}, {'a b c': (2, [1]), 'a b d': (1, [1]), 'b c a': (1, [0]), 'c a b': (1, [2])})
g2 = C.ngrams(corp, 'a b', n=3)
check('a query of two words: trigrams that contain them one after the other', {x['text']: x['hl'] for x in g2['grams']}, {'a b c': [0, 1], 'a b d': [0, 1], 'c a b': [1, 2]})
check('a query of two words as bigrams: just that bigram', [(x['text'], x['count']) for x in C.ngrams(corp, 'a b', n=2)['grams']], [('a b', 3)])
check('n-grams do not cross sentences', 'c a' in {x['text'] for x in C.ngrams([L('a b'), L('c d')], 'b', n=2)['grams']}, False)
check('…nor does a short sentence give any', C.ngrams([L('a b')], 'a', n=3)['grams'], [])
check('case: ignored by default, the first spelling is shown (and cat The also contains the)', [(x['text'], x['count']) for x in C.ngrams([L('The cat. The CAT')], 'the', n=2)['grams']], [('The cat', 2), ('cat The', 1)])
check('…and respected on request', C.ngrams([L('The cat. The CAT')], 'the', n=2, ignore_case=False)['grams'], [])
check('punctuation is not part of a word (equal counts: alphabetical order)', [x['text'] for x in C.ngrams([L('wē, tē mi.')], 'tē', n=2)['grams']], ['tē mi', 'wē tē'])
check('diacritics can be ignored in the query and the text', [x['text'] for x in C.ngrams([L('Qōn̄ va-wē')], 'qon', n=2, ignore_diacritics=True)['grams']], ['Qōn̄ va-wē'])
check('…or respected', C.ngrams([L('Qōn̄ va-wē')], 'qon', n=2)['grams'], [])
for bad_kw in (dict(n=1), dict(n=9), dict(scope='nope'), dict(unit='nope'), dict(query='a b c d', n=3), dict(query='  ')):
    kw = dict(query='b', n=2); kw.update(bad_kw)
    try: C.ngrams(corp, kw.pop('query'), **kw); outcome = 'accepted'
    except ValueError: outcome = 'refused'
    check(f'refused: {bad_kw}', outcome, 'refused')
check('filters: a language and a source', (C.ngrams(corp, 'b', n=2, lang='y')['occurrences'], C.ngrams([L('a b', src='s'), L('a b', src='t')], 'b', n=2, sources=['t'])['occurrences']), (2, 1))
check('a minimum count and a limit', ([x['text'] for x in C.ngrams(corp, 'b', n=2, min_count=2)['grams']], C.ngrams(corp, 'b', n=2, limit=1)['truncated'], len(C.ngrams(corp, 'b', n=2, limit=1)['grams'])), (['a b', 'b c'], True, 1))
# glosses: a gap (an unglossed word) cannot be spanned
gl = L('x y z w', tokens=[{'form': 'x', 'gloss': 'A'}, {'form': 'y', 'gloss': ''}, {'form': 'z', 'gloss': 'B'}, {'form': 'w', 'gloss': 'A'}])
check('glosses: n-grams of glosses never span a word that has none', [(x['text'], x['count']) for x in C.ngrams([gl], 'A', n=2, scope='glosses')['grams']], [('B A', 1)])
# morphemes: the tokens of a line, joined without a space where a marker joins them
mo = L('Qōn̄ va-wē.', tokens=[{'form': 'Qōn̄', 'gloss': ''}, {'form': 'va-', 'gloss': ''}, {'form': 'wē', 'gloss': ''}])
check('morphemes: va finds the token va-, and the gram is written as the word', [(x['text'], x['tokens'], x['hl']) for x in C.ngrams([mo], 'va', n=2, unit='morpheme')['grams']], [('Qōn̄ va-', ['Qōn̄', 'va-'], [1]), ('va-wē', ['va-', 'wē'], [0])])
check('translations: the words of the translation, quotes and full stops left out', [x['text'] for x in C.ngrams([L('x', translation='‘Good afternoon.’')], 'afternoon', n=2, scope='translation')['grams']], ['Good afternoon'])

# ── lexical statistics ──
check('tokens, types, TTR and Root TTR', C.lexical_stats([['a', 'b', 'a'], ['c']]), {'tokens': 4, 'types': 3, 'ttr': 0.75, 'rttr': 1.5})
check('all different: TTR is 1', C.lexical_stats([['a', 'b', 'c', 'd']])['ttr'], 1.0)
check('Root TTR is types divided by the square root of the tokens', C.lexical_stats([['a'] * 8 + ['b']])['rttr'], round(2 / 9 ** 0.5, 3))
check('nothing to measure', C.lexical_stats([[], []]), {'tokens': 0, 'types': 0, 'ttr': None, 'rttr': None})

# ── the statistics of a corpus: by source, by text, by language ──
cs = C.corpus_stats([L('a b a', 'x', 'fn', tkey='fn:0', ttitle='One'), L('a c', 'y', 'fn', tkey='fn:0', ttitle='One'), L('d d d d', 'x', 'fn', tkey='fn:1', ttitle='Two'), L('The the', 'x', 'rec', tkey='rec:f', ttitle='Rec')])
check('a source as a whole: all the languages, then each language', (cs['collections']['fn']['all'], cs['collections']['fn']['byLang']['x'], cs['collections']['fn']['byLang']['y']),
      ({'tokens': 9, 'types': 4, 'ttr': 0.4444, 'rttr': 1.333}, {'tokens': 7, 'types': 3, 'ttr': 0.4286, 'rttr': 1.134}, {'tokens': 2, 'types': 2, 'ttr': 1.0, 'rttr': 1.414}))
check('a text: its own tokens only, its title and its source', (cs['texts']['fn:0']['all']['tokens'], cs['texts']['fn:0']['all']['types'], cs['texts']['fn:0']['title'], cs['texts']['fn:0']['src']), (5, 3, 'One', 'fn'))
check('a text in one language has one language', list(cs['texts']['fn:1']['byLang']), ['x'])
check('case is ignored in counting types (The the is one type)', cs['texts']['rec:f']['all'], {'tokens': 2, 'types': 1, 'ttr': 0.5, 'rttr': 0.707})
check('counted by morpheme, from the aligned tokens', C.corpus_stats([L('Qōn̄ va-wē', tokens=[{'form': 'Qōn̄'}, {'form': 'va-'}, {'form': 'wē'}, {'form': '-wē'}], tkey='t')], unit='morpheme')['texts']['t']['all'], {'tokens': 4, 'types': 3, 'ttr': 0.75, 'rttr': 1.5})

print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
