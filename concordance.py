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
MATCHES = ('anywhere', 'word', 'morpheme')
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
