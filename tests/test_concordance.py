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

print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
