"""
Concordancing: search a corpus for a string and show every occurrence in its context (KWIC: key word in context).

The corpus is a list of *lines* (one sentence in one language). A line is a plain dict:

    {'src': 'fieldnotes', 'lang': 'drg', 'sid': 'd01.Road:02', 'label': 'D01 · d01.Road:02', 'link': 'transcription.html?…',
     'text': 'Qōn̄ va-wē.',                       # the sentence as written
     'translation': 'Good afternoon.',
     'tokens': [{'form': 'Qōn̄', 'gloss': 'afternoon'}, {'form': 'va-', 'gloss': 'LOC'}, …]}   # the word-by-word annotation

The tokens are the *annotation layer*: every word can carry a gloss, and the application adds an entry and a part of speech
(see `search(…, annotate=…)`). A search is by string for now; searching those layers (a part of speech, a gloss pattern …) is
a matter of adding a query on the tokens: the index already has them, aligned with the characters of the sentence.

Nothing here knows a language or the web framework, so it can be tested alone and reused.
"""
import re
import unicodedata

SCOPES = ('forms', 'glosses', 'translation')
MATCHES = ('anywhere', 'word', 'morpheme', 'phrase')
MAX_QUERY = 200

# characters that end a word / a morpheme (an apostrophe is not one: it can be a letter of the orthography)
_WORD_STOP = set(' \t\r\n.,;:!?…"“”«»()[]{}')
_MORPH_STOP = _WORD_STOP | set('-=')


def nfc(text):
    return unicodedata.normalize('NFC', str(text or ''))


def prepare_line(line):
    """A line with its texts in NFC, the form in which the search compares them."""
    out = dict(line)
    out['text'], out['translation'] = nfc(line.get('text')), nfc(line.get('translation'))
    out['tokens'] = [{'form': nfc(t.get('form')), 'gloss': nfc(t.get('gloss'))} for t in line.get('tokens', [])]
    return out


def _piece(ch, ignore_case, ignore_diacritics):
    """What one character of the text counts as when searching: lower case, and no combining marks if diacritics are ignored."""
    if ignore_diacritics:
        ch = ''.join(c for c in unicodedata.normalize('NFD', ch) if unicodedata.category(c) != 'Mn')
    return ch.lower() if ignore_case else ch


def fold(text, ignore_case=True, ignore_diacritics=False):
    """(folded text, owner, pieces): `owner[k]` is the index, in `text`, of the character folded text[k] came from.
    A combining mark that is ignored folds to nothing; `pieces[i] == ''` tells so. Folding keeps matches mappable back to
    the original characters, so that what is highlighted is exactly what was found (a final combining mark included)."""
    pieces = [_piece(ch, ignore_case, ignore_diacritics) for ch in text]
    owner = [i for i, p in enumerate(pieces) for _ in p]
    return ''.join(pieces), owner, pieces


def _bounded(text, s, e, query, match):
    """Does text[s:e] stand alone, as a whole word / a whole morpheme?"""
    if match == 'anywhere':
        return True
    stops = _WORD_STOP if match == 'word' else _MORPH_STOP
    edge = set('-=') if match == 'morpheme' else set()          # a query that starts or ends with - or = is itself bounded there
    left = s == 0 or text[s - 1] in stops or query[:1] in edge
    right = e >= len(text) or text[e] in stops or query[-1:] in edge
    return left and right


def find_spans(text, query, match='anywhere', ignore_case=True, ignore_diacritics=False):
    """Every occurrence of `query` in `text`, as (start, end) offsets in `text`, left to right, not overlapping.
    The query is a plain string (never a pattern: a dot is a dot). Both are normalised (NFC), so a letter and its
    combining-mark spelling are the same."""
    text, query = nfc(text), nfc(query).strip()
    if not query:
        return []
    if match == 'phrase':
        return _phrase_spans(text, query, ignore_case, ignore_diacritics)
    ftext, owner, pieces = fold(text, ignore_case, ignore_diacritics)
    fq = fold(re.sub(r'\s+', ' ', query), ignore_case, ignore_diacritics)[0]
    if not fq:
        return []
    spans, pos = [], 0
    while True:
        k = ftext.find(fq, pos)
        if k < 0:
            break
        s = owner[k]
        e = owner[k + len(fq) - 1] + 1
        while e < len(text) and pieces[e] == '':               # a combining mark that is ignored belongs to the letter before it
            e += 1
        if e < len(text) and unicodedata.category(text[e]) == 'Mn':
            pos = k + 1                                         # a match may not end between a letter and its mark (n is not n̄)
            continue
        if _bounded(text, s, e, query, match):
            spans.append((s, e))
            pos = k + len(fq)
        else:
            pos = k + 1
    return spans


def word_spans(text, ignore_case=True, ignore_diacritics=False, quotes=False):
    """[(key, start, end)]: each word of a text and where it stands in it (the punctuation at its edges left out)."""
    edge = _EDGE + ('‘’' if quotes else '')
    out = []
    for m in re.finditer(r'\S+', text):
        raw = m.group()
        w = raw.strip(edge)
        if w and w != '\u2014':
            s = m.start() + len(raw) - len(raw.lstrip(edge))
            out.append((fold(w, ignore_case, ignore_diacritics)[0], s, s + len(w)))
    return out


def _phrase_spans(text, query, ignore_case, ignore_diacritics):
    """The query as a sequence of whole words: they must follow each other, with only spaces and punctuation between them."""
    qk = [k for k, _ in words(query, ignore_case, ignore_diacritics)]
    ws = word_spans(text, ignore_case, ignore_diacritics)
    spans, i, k = [], 0, len(qk)
    while qk and i + k <= len(ws):
        if [w[0] for w in ws[i:i + k]] == qk:
            spans.append((ws[i][1], ws[i + k - 1][2]))
            i += k
        else:
            i += 1
    return spans


def align_tokens(text, tokens):
    """The (start, end) of each token in the sentence, found in order. A token that cannot be found (the sentence was edited
    after it was aligned) gets None, and simply has no position."""
    text, spans, cursor = nfc(text), [], 0
    for tok in tokens:
        form = nfc(tok.get('form', ''))
        k = text.find(form, cursor) if form else -1
        if k < 0:
            spans.append(None)
        else:
            spans.append((k, k + len(form)))
            cursor = k + len(form)
    return spans


def _words_before(text, width):
    parts = re.findall(r'\S+|\s+', text)
    out, n = [], 0
    for p in reversed(parts):
        if p.strip():
            if n == width:
                return ''.join(reversed(out)).lstrip(), True
            n += 1
        out.append(p)
    return ''.join(reversed(out)).lstrip(), False


def _words_after(text, width):
    parts = re.findall(r'\S+|\s+', text)
    out, n = [], 0
    for p in parts:
        if p.strip():
            if n == width:
                return ''.join(out).rstrip(), True
            n += 1
        out.append(p)
    return ''.join(out).rstrip(), False


def context(text, span, width):
    """(left, match, right, left_cut, right_cut): the matched characters and `width` words on each side, without the spaces
    between them and the match (`touches` tells where the match is inside a word)."""
    s, e = span
    left, lcut = _words_before(text[:s], width)
    right, rcut = _words_after(text[e:], width)
    return left.rstrip(), text[s:e], right.lstrip(), lcut, rcut


def touches(text, span):
    """(left, right): is the match attached to the character before it / after it (no space between)?"""
    s, e = span
    return s > 0 and not text[s - 1].isspace(), e < len(text) and not text[e].isspace()


def _scope_text(line, scope):
    if scope == 'translation':
        return nfc(line.get('translation', ''))
    if scope == 'glosses':
        return ' '.join(t.get('gloss', '') for t in line.get('tokens', []) if t.get('gloss'))
    return nfc(line.get('text', ''))


def search(lines, query, scope='forms', match='anywhere', ignore_case=True, ignore_diacritics=False,
           lang=None, sources=None, width=6, limit=1000, annotate=None):
    """Search the lines for a string. Returns {query, total, sentences, shown, truncated, byLang, bySource, hits}.
    `annotate(line, token)` may add information about the token that was found (an entry, a part of speech …) to the hit."""
    query = nfc(query).strip()
    if scope not in SCOPES or match not in MATCHES:
        raise ValueError('unknown scope or match')
    if not query or len(query) > MAX_QUERY:
        raise ValueError('The query must be between 1 and %d characters.' % MAX_QUERY)
    width = max(1, min(int(width), 25))
    limit = max(1, min(int(limit), 5000))
    srcs = set(sources) if sources else None
    hits, total, sentences, by_lang, by_src = [], 0, 0, {}, {}
    for line in lines:
        if lang and line.get('lang') != lang:
            continue
        if srcs is not None and line.get('src') not in srcs:
            continue
        text = _scope_text(line, scope)
        spans = find_spans(text, query, match, ignore_case, ignore_diacritics)
        if not spans:
            continue
        sentences += 1
        positions = align_tokens(line.get('text', ''), line.get('tokens', [])) if scope == 'forms' else []
        for span in spans:
            total += 1
            by_lang[line.get('lang')] = by_lang.get(line.get('lang'), 0) + 1
            by_src[line.get('src')] = by_src.get(line.get('src'), 0) + 1
            if len(hits) >= limit:
                continue
            left, found, right, lcut, rcut = context(text, span, width)
            hit = {'lang': line.get('lang'), 'src': line.get('src'), 'label': line.get('label', ''), 'link': line.get('link', ''),
                   'sid': line.get('sid', ''), 'left': left, 'match': found, 'right': right, 'leftCut': lcut, 'rightCut': rcut,
                   'leftAdj': touches(text, span)[0], 'rightAdj': touches(text, span)[1],
                   'sentence': nfc(line.get('text', '')), 'translation': nfc(line.get('translation', '')), 'gloss': '', 'entry': '', 'pos': ''}
            if scope == 'forms':                                         # what the words found are glossed as
                toks = [t for t, p in zip(line.get('tokens', []), positions) if p and p[0] < span[1] and p[1] > span[0]]
                hit['gloss'] = ' '.join(t['gloss'] for t in toks if t.get('gloss'))
                if toks and annotate:
                    hit.update({k: v for k, v in (annotate(line, toks[0]) or {}).items() if k in ('entry', 'pos')})
            hits.append(hit)
    return {'query': query, 'scope': scope, 'match': match, 'total': total, 'sentences': sentences, 'shown': len(hits),
            'truncated': total > len(hits), 'byLang': by_lang, 'bySource': by_src, 'hits': hits}


# ───────────────────────── words, n-grams, lexical statistics ─────────────────────────
# A "token" is, by default, a whole word: what is between spaces, without the punctuation at its edges (va-wē is one word). The
# other unit is the morpheme: the aligned tokens of a line (va- wē). Tokens are compared in folded form (case ignored by default).
UNITS = ('word', 'morpheme')
_EDGE = ''.join(c for c in _WORD_STOP if not c.isspace())


def words(text, ignore_case=True, ignore_diacritics=False, quotes=False):
    """[(key, as written)]: the words of a text. `quotes` also strips ‘ ’ at the edges (for a translation)."""
    edge = _EDGE + ('‘’' if quotes else '')
    out = []
    for raw in nfc(text).split():
        w = raw.strip(edge)
        if w and w != '\u2014':
            out.append((fold(w, ignore_case, ignore_diacritics)[0], w))
    return out


def morphemes(tokens, field='form', ignore_case=True, ignore_diacritics=False):
    """[(key, as written) or None]: the aligned tokens of a line. A token with no value (an unglossed word) is None, a gap that no
    n-gram may span. The key has no - or = at its edges, so that a query `va` finds the token `va-`."""
    out = []
    for t in tokens:
        raw = nfc(t.get(field, ''))
        core = raw.strip('-=')
        out.append((fold(core, ignore_case, ignore_diacritics)[0], raw) if core else None)
    return out


def sequence(line, scope='forms', unit='word', ignore_case=True, ignore_diacritics=False):
    """What a line is made of, for counting: its tokens in order, with None where there is a gap."""
    if scope == 'translation':
        return words(line.get('translation', ''), ignore_case, ignore_diacritics, quotes=True)
    if scope == 'glosses':
        return morphemes(line.get('tokens', []), 'gloss', ignore_case, ignore_diacritics)
    if unit == 'morpheme':
        return morphemes(line.get('tokens', []), 'form', ignore_case, ignore_diacritics)
    return words(line.get('text', ''), ignore_case, ignore_diacritics)


def query_keys(query, scope='forms', unit='word', ignore_case=True, ignore_diacritics=False):
    """The tokens of a query, in the same folded form as the tokens of the lines."""
    q = nfc(query).strip()
    if not q or len(q) > MAX_QUERY:
        raise ValueError('The query must be between 1 and %d characters.' % MAX_QUERY)
    if scope == 'translation' or (scope == 'forms' and unit == 'word'):
        keys = [k for k, _ in words(q, ignore_case, ignore_diacritics, quotes=scope == 'translation')]
    else:
        keys = [fold(w.strip('-=' + _EDGE), ignore_case, ignore_diacritics)[0] for w in q.split()]
        keys = [k for k in keys if k]
    if not keys:
        raise ValueError('The query has no word in it.')
    return keys


def _join(parts):
    """The tokens of an n-gram as a string: a space between them, none where a morpheme marker (- or =) joins them."""
    out = ''
    for p in parts:
        out += p if not out or out[-1] in '-=' or p[:1] in '-=' else ' ' + p
    return out


def ngrams(lines, query, n=3, scope='forms', unit='word', ignore_case=True, ignore_diacritics=False,
           lang=None, sources=None, min_count=1, limit=200):
    """The n-grams (runs of n tokens inside one sentence) that contain the query, most frequent first.
    Returns {query, n, unit, scope, queryCount, occurrences, distinct, shown, truncated, grams}; each gram has its tokens as written,
    the positions of the query in it (`hl`), its count, the number of sentences, the count by language and one example."""
    if scope not in SCOPES or unit not in UNITS:
        raise ValueError('unknown scope or unit')
    n = int(n)
    if not 2 <= n <= 8:
        raise ValueError('n must be between 2 and 8.')
    qk = query_keys(query, scope, unit, ignore_case, ignore_diacritics)
    k = len(qk)
    if k > n:
        raise ValueError('The query has %d words: n must be at least %d.' % (k, k))
    limit, min_count = max(1, min(int(limit), 2000)), max(1, int(min_count))
    srcs = set(sources) if sources else None
    count, sents, by_lang, shown, example, query_count = {}, {}, {}, {}, {}, 0
    for li, line in enumerate(lines):
        if (lang and line.get('lang') != lang) or (srcs is not None and line.get('src') not in srcs):
            continue
        seq = sequence(line, scope, unit, ignore_case, ignore_diacritics)
        keys = [t[0] if t else None for t in seq]
        query_count += sum(1 for i in range(len(keys) - k + 1) if keys[i:i + k] == qk)
        for i in range(len(seq) - n + 1):
            window = keys[i:i + n]
            if None in window or not any(window[j:j + k] == qk for j in range(n - k + 1)):
                continue
            g = tuple(window)
            count[g] = count.get(g, 0) + 1
            sents.setdefault(g, set()).add(li)
            by_lang.setdefault(g, {}).setdefault(line.get('lang'), 0)
            by_lang[g][line.get('lang')] += 1
            if g not in shown:
                shown[g] = [t[1] for t in seq[i:i + n]]
                example[g] = {'label': line.get('label', ''), 'link': line.get('link', ''), 'lang': line.get('lang'), 'sentence': nfc(line.get('text', ''))}
    grams = []
    for g, c in count.items():
        if c < min_count:
            continue
        text = _join(shown[g])
        grams.append({'text': text, 'tokens': shown[g], 'hl': sorted({j + m for j in range(n - k + 1) if list(g[j:j + k]) == qk for m in range(k)}),
                      'count': c, 'sentences': len(sents[g]), 'byLang': by_lang[g], 'example': example[g]})
    grams.sort(key=lambda x: (-x['count'], x['text'].lower()))
    return {'query': nfc(query).strip(), 'n': n, 'unit': unit, 'scope': scope, 'queryCount': query_count, 'occurrences': sum(count.values()),
            'distinct': len(count), 'shown': min(len(grams), limit), 'truncated': len(grams) > limit, 'grams': grams[:limit]}


def lexical_stats(token_lists):
    """Tokens, types, TTR (types / tokens) and Root TTR (Guiraud: types / √tokens) of some lists of token keys."""
    tokens, types = 0, set()
    for keys in token_lists:
        tokens += len(keys)
        types.update(keys)
    t = len(types)
    return {'tokens': tokens, 'types': t, 'ttr': round(t / tokens, 4) if tokens else None, 'rttr': round(t / tokens ** 0.5, 3) if tokens else None}


def corpus_stats(lines, unit='word', ignore_case=True, ignore_diacritics=False):
    """The lexical statistics of the corpus as a whole, by source and by text, each in all languages together and by language:
    {unit, collections: {src: {all, byLang}}, texts: {tkey: {src, title, all, byLang}}}."""
    if unit not in UNITS:
        raise ValueError('unknown unit')
    coll, texts = {}, {}
    for line in lines:
        keys = [t[0] for t in sequence(line, 'forms', unit, ignore_case, ignore_diacritics) if t]
        for bucket, meta in ((coll.setdefault(line.get('src'), {'all': [], 'by': {}}), None),
                             (texts.setdefault(line.get('tkey') or line.get('src'), {'all': [], 'by': {}, 'src': line.get('src'), 'title': line.get('ttitle', '')}), True)):
            bucket['all'].append(keys)
            bucket['by'].setdefault(line.get('lang'), []).append(keys)
    def done(b):
        out = {'all': lexical_stats(b['all']), 'byLang': {lg: lexical_stats(v) for lg, v in b['by'].items()}}
        if 'src' in b:
            out.update(src=b['src'], title=b['title'])
        return out
    return {'unit': unit, 'collections': {k: done(v) for k, v in coll.items()}, 'texts': {k: done(v) for k, v in texts.items()}}
