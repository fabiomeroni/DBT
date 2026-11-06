"""
References: the logic of the DBT's bibliography, independent of any language or project.

    - validation of a reference typed in the form
    - APA 7th edition reference-list entries (following the templates of the UTS "APA 7th referencing guide")
    - APA in-text citations: parenthetical (Smith & Jones, 2016, p. 4) and narrative Smith and Jones (2016, p. 4)
    - the order of the list, and the a / b letters that tell apart works by the same author in the same year
    - export to BibTeX and to the EndNote tagged format

A reference is a plain dict (see `clean`). Formatted text is built as "rich text": a list of (text, style) pieces,
style '' (plain), 'i' (italic) or 'u' (a URL), so that punctuation can be decided on the plain text and the result
turned into HTML (with <em> and links) or into plain text.
"""
import html as _html
import re
import unicodedata

TYPES = [
    ('article', 'Journal article'), ('book', 'Book'), ('edited', 'Edited book'), ('chapter', 'Chapter in an edited book'),
    ('conference', 'Conference paper'), ('thesis', 'Thesis or dissertation'), ('report', 'Report'), ('web', 'Web page'),
    ('dataset', 'Data set'), ('unpublished', 'Unpublished manuscript'), ('other', 'Other'),
]
TYPE_IDS = [t for t, _ in TYPES]
_ITALIC_TITLE = {'book', 'edited', 'report', 'thesis', 'web', 'dataset', 'unpublished'}   # types whose title is in italics

_TEXT_FIELDS = ['title', 'container', 'volume', 'issue', 'pages', 'edition', 'publisher', 'place', 'number', 'level',
                'institution', 'descriptor', 'dateText', 'accessed', 'note', 'doi', 'url']


# ───────────────────────── small helpers ─────────────────────────
def _fold(s):
    """Lower case without accents, for sorting and keys."""
    return ''.join(c for c in unicodedata.normalize('NFKD', str(s or '')) if not unicodedata.combining(c)).lower()


def _clip(v, n=2000):
    return str(v or '').strip()[:n]


def _ordinal(n):
    n = int(n)
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def initials(given):
    """'Alexandre' -> 'A.'   'Jean-Pierre' -> 'J.-P.'   'Mary Ann' -> 'M. A.'   'A. J.' / 'AJ' stay initials.
    A hyphenated part whose second half is lower case ('Lee-ann') counts as one name."""
    g = str(given or '').strip()
    if not g:
        return ''
    out = []
    for part in g.replace('.', ' ').split():
        if len(part) <= 3 and part.isupper() and part.isalpha() and '-' not in part and len(part) > 1:
            out.extend(f'{c}.' for c in part)                 # AJ -> A. J.
            continue
        pieces = part.split('-')
        if len(pieces) > 1 and pieces[1][:1].isupper():
            out.append('-'.join(f'{p[0].upper()}.' for p in pieces if p))
        else:
            out.append(f'{pieces[0][0].upper()}.')
    return ' '.join(out)


# ───────────────────────── rich text ─────────────────────────
def T(s):  return [(s, '')] if s else []
def I(s):  return [(s, 'i')] if s else []
def U(s):  return [(s, 'u')] if s else []
def cat(*parts):
    out = []
    for p in parts:
        out.extend(p)
    return out
def plain(r):  return ''.join(t for t, _ in r)
def _end(r):
    """Close an element of a reference with a full stop, unless it ends with . ? or !"""
    s = plain(r).rstrip()
    return r if not s or s[-1] in '.?!' else r + T('.')
def to_text(r):  return plain(r)
def to_html(r):
    out = []
    for t, st in r:
        e = _html.escape(t, quote=False)
        if st == 'i':   out.append(f'<em>{e}</em>')
        elif st == 'u': out.append(f'<a href="{_html.escape(t, quote=True)}" target="_blank" rel="noopener">{e}</a>')
        else:           out.append(e)
    return ''.join(out)


# ───────────────────────── names ─────────────────────────
def _inverted(p):
    """Reference list form: 'Family, A. B.' (an organisation, or a single name, as it is)."""
    if p.get('org'):
        return p['org']
    ini = initials(p.get('given'))
    s = f"{p.get('family', '')}, {ini}" if ini else p.get('family', '')
    return f"{s}, {p['suffix']}" if p.get('suffix') and ini else s


def _natural(p):
    """'A. B. Family' (for editors, in a chapter's 'In …' part)."""
    if p.get('org'):
        return p['org']
    ini = initials(p.get('given'))
    return f"{ini} {p.get('family', '')}".strip()


def _people_ref(people):
    names = [_inverted(p) for p in people]
    n = len(names)
    if n == 0:
        return ''
    if n == 1:
        return names[0]
    if n == 2:
        return f'{names[0]} & {names[1]}' if all(p.get('org') for p in people) else f'{names[0]}, & {names[1]}'
    if n <= 20:
        return ', '.join(names[:-1]) + ', & ' + names[-1]
    return ', '.join(names[:19]) + ', … ' + names[-1]          # 21 or more: the first 19, an ellipsis, the last


def _editors_in(eds):
    names = [_natural(e) for e in eds]
    n = len(names)
    if n == 1:
        s = names[0]
    elif n == 2:
        s = f'{names[0]} & {names[1]}'
    else:
        s = ', '.join(names[:-1]) + ', & ' + names[-1]
    return f"{s} ({'Ed.' if n == 1 else 'Eds.'})"


# ───────────────────────── years, pages, editions, links ─────────────────────────
def split_year(y):
    """'2026b' -> ('2026', 'b'); 'n.d.-a' -> ('n.d.', 'a'); 'in press' -> ('in press', '')."""
    y = str(y or '').strip()
    m = re.fullmatch(r'(\d{4})([a-z]?)', y)
    if m:
        return m.group(1), m.group(2)
    m = re.fullmatch(r'(n\.?\s?d\.?|in press)(?:-([a-z]))?', y, re.I)
    if m:
        base = 'in press' if m.group(1).lower().startswith('in') else 'n.d.'
        return base, (m.group(2) or '')
    return y, ''


def _dashes(s):
    """A range of numbers takes an en dash: 73-128 -> 73–128, October 28-29 -> October 28–29."""
    return re.sub(r'(?<=\d)\s*[-–—]\s*(?=\d)', '–', str(s or '').strip())


def _pages(p):
    return re.sub(r'\s*[-–—]\s*', '–', str(p or '').strip())


def _edition(e):
    e = str(e or '').strip()
    if not e:
        return ''
    if e.isdigit():
        return f'{_ordinal(e)} ed.'
    return e if e.lower().endswith(('ed.', 'edition')) else f'{e} ed.'


def _doi_url(ref):
    doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', str(ref.get('doi') or ''), flags=re.I).strip()
    return f'https://doi.org/{doi}' if doi else str(ref.get('url') or '').strip()


# ───────────────────────── validation ─────────────────────────
def _clean_people(raw):
    out = []
    for p in (raw if isinstance(raw, list) else [])[:60]:
        if not isinstance(p, dict):
            continue
        org, fam, giv = _clip(p.get('org'), 300), _clip(p.get('family'), 120), _clip(p.get('given'), 120)
        if org:
            out.append({'org': org})
        elif fam:
            q = {'family': fam}
            if giv: q['given'] = giv
            if _clip(p.get('suffix'), 12): q['suffix'] = _clip(p.get('suffix'), 12)
            out.append(q)
    return out


def clean(data, existing_ids=()):
    """Validate a reference typed in the form. Returns (reference, error): one of them is None."""
    if not isinstance(data, dict):
        return None, 'No reference was sent.'
    ty = data.get('type')
    if ty not in TYPE_IDS:
        return None, 'Choose the type of the reference.'
    ref = {'type': ty, 'authors': _clean_people(data.get('authors')), 'editors': _clean_people(data.get('editors'))}
    for k in _TEXT_FIELDS:
        ref[k] = _clip(data.get(k), 600 if k not in ('title', 'container', 'note') else 2000)
    if not ref['title']:
        return None, 'The reference needs a title.'
    year = _clip(data.get('year'), 20)
    ref['year'] = year if split_year(year)[0] and (re.fullmatch(r'\d{4}[a-z]?', year) or split_year(year)[0] in ('n.d.', 'in press')) else ('n.d.' if not year else year)
    if year and not (re.fullmatch(r'\d{4}[a-z]?', year) or re.fullmatch(r'(n\.?\s?d\.?|in press)(-[a-z])?', year, re.I)):
        return None, 'The year must look like 2026, 2026b, n.d. or in press.'
    if ref['url'] and not re.match(r'^https?://\S+$', ref['url'], re.I):
        return None, 'The URL must start with http:// or https://.'
    rid = _clip(data.get('id'), 80).lower()
    if rid and not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', rid):
        return None, 'The key may only use lower case letters, digits, - and _.'
    ref['id'] = rid
    return ref, None


def suggest_id(ref, taken=()):
    """smith2020 from the first author's name and the year (the key used in {{source: …}})."""
    a = (ref.get('authors') or [{}])[0]
    word = re.sub(r'[^a-z0-9]', '', _fold(a.get('family') or a.get('org') or (ref.get('title') or '').split(' ')[0]))[:24] or 'ref'
    base_year, letter = split_year(ref.get('year'))
    year = (base_year if re.fullmatch(r'\d{4}', base_year) else 'nd' if base_year == 'n.d.' else 'inpress') + letter
    key, n = word + year, 2
    while key in taken:
        key, n = f'{word}{year}-{n}', n + 1
    return key


# ───────────────────────── the context: year letters, ambiguous names, order ─────────────────────────
def _title_key(r):
    return re.sub(r'^(?:a|an|the)\s+', '', _fold(r.get('title')).strip())


def _authors_key(r):
    return tuple((_fold(p.get('org') or p.get('family')), _fold(initials(p.get('given')))) for p in r.get('authors') or [])


class Context:
    """What the formatting of one reference needs to know about all the others."""

    def __init__(self, refs):
        self.refs = list(refs)
        self.letter = {}
        groups = {}
        for r in self.refs:
            base, expl = split_year(r.get('year'))
            groups.setdefault((_authors_key(r) or ('~' + _title_key(r),), base), []).append((r, expl))
        for items in groups.values():
            if len(items) < 2:
                continue
            used = {e for _, e in items if e}
            free = (c for c in 'abcdefghijklmnopqrstuvwxyz' if c not in used)
            for r, e in sorted((i for i in items if not i[1]), key=lambda i: _title_key(i[0])):
                self.letter[r['id']] = next(free)
        seen = {}
        for r in self.refs:
            a = (r.get('authors') or [None])[0]
            if a and a.get('family'):
                seen.setdefault(_fold(a['family']), set()).add(_fold(initials(a.get('given'))))
        self.ambiguous = {s for s, ini in seen.items() if len(ini) > 1}

    def year(self, r):
        base, expl = split_year(r.get('year'))
        letter = expl or self.letter.get(r.get('id'), '')
        return base if not letter else (f'{base}-{letter}' if not base.isdigit() else f'{base}{letter}')

    def sorted(self):
        def key(r):
            base, expl = split_year(r.get('year'))
            yk = (0, 0) if base == 'n.d.' else (2, 0) if base == 'in press' else (1, int(base) if base.isdigit() else 9999)
            who = [(a, b) for a, b in _authors_key(r)]
            return (who or [(_title_key(r), '')], yk, self.year(r), _title_key(r))
        return sorted(self.refs, key=key)


# ───────────────────────── a reference-list entry (APA 7) ─────────────────────────
def _paren(*bits):
    bits = [b for b in bits if b]
    return f" ({', '.join(bits)})" if bits else ''


def apa_rich(r, ctx):
    ty = r['type']
    authors, editors = r.get('authors') or [], r.get('editors') or []
    title = r.get('title', '').strip()
    year = ctx.year(r)
    date = f"({year}{', ' + _dashes(r['dateText']) if r.get('dateText') else ''})"
    tseg = I(title) if ty in _ITALIC_TITLE else T(title)
    vol, ed = (f"Vol. {r['volume']}" if r.get('volume') else ''), _edition(r.get('edition'))

    # the title slot, with what follows the title in parentheses and brackets
    after = ''
    if ty in ('book', 'edited'):
        after = _paren(ed, vol)
    elif ty == 'report':
        after = _paren(r.get('number'))
    elif ty == 'dataset':
        after = _paren(f"Version {r['edition']}" if r.get('edition') else '') + ' [Data set]'
    elif ty == 'thesis':
        lvl = ', '.join(x for x in (r.get('level') or 'Doctoral dissertation', r.get('institution')) if x)
        after = _paren(r.get('number')) + f' [{lvl}]'
    elif ty == 'conference':
        after = f" [{r.get('descriptor') or 'Paper presentation'}]"
    elif ty == 'unpublished':
        after = f" [{r.get('descriptor') or 'Unpublished manuscript'}]"
    title_slot = cat(tseg, T(after))

    # the source slot
    container, publisher = r.get('container', ''), r.get('publisher', '')
    source, extra = [], []
    if ty == 'article':
        bits = []
        if container: bits.append(I(container))
        v = cat(I(r.get('volume', '')), T(f"({r['issue']})" if r.get('issue') else ''))
        if v: bits.append(v)
        if r.get('pages'): bits.append(T(_pages(r['pages'])))
        for i, b in enumerate(bits):
            source += (T(', ') if i else []) + b
    elif ty == 'chapter':
        pg = _pages(r.get('pages'))
        inner = ', '.join(x for x in (ed, vol, (f"{'pp.' if '–' in pg else 'p.'} {pg}" if pg else '')) if x)
        src = T('In ' + (_editors_in(editors) + ', ' if editors else '')) + I(container) + T(f' ({inner})' if inner else '')
        source, extra = src, [T(publisher)] if publisher else []
    elif ty == 'conference':
        source = T(', '.join(x for x in (container, r.get('place')) if x))
    elif ty == 'web':
        same = authors and _fold(container) == _fold(plain(T(_people_ref(authors))))
        source = [] if same else T(container)
    elif ty == 'other':
        source = T(r.get('note', ''))
    else:
        source = T(publisher)

    link = _doi_url(r)
    if ty in ('web', 'dataset') and r.get('accessed') and link:
        link_r = T(f"Retrieved {r['accessed']}, from ") + U(link)
    else:
        link_r = U(link)

    # who: the authors, or the title when there is no author
    if ty == 'edited':
        who = T(_people_ref(authors) + (f" ({'Ed.' if len(authors) == 1 else 'Eds.'})" if authors else ''))
    else:
        who = T(_people_ref(authors))
    if who:
        head = [_end(who), T(date + '.'), _end(title_slot)]
    else:
        head = [_end(title_slot), T(date + '.')]
    parts = head + [_end(source)] + [_end(e) for e in extra] + [link_r]
    out = []
    for p in parts:
        if plain(p).strip():
            out += (T(' ') if out else []) + p
    return out


def apa(r, ctx):
    """(html, text) of a reference-list entry."""
    rich = apa_rich(r, ctx)
    return to_html(rich), to_text(rich)


# ───────────────────────── in-text citations ─────────────────────────
def _locator(s):
    s = str(s or '').strip()
    if not s:
        return ''
    if re.fullmatch(r'\d+', s):
        return f'p. {s}'
    if re.fullmatch(r'\d+\s*[-–—]\s*\d+', s):
        return 'pp. ' + re.sub(r'\s*[-–—]\s*', '–', s)
    return _dashes(s)


def author_text(r, ctx, narrative=False):
    authors = r.get('authors') or []
    if not authors:
        t = r.get('title', '')
        return t if r['type'] in _ITALIC_TITLE else f'“{t}”'
    def name(p, first=False):
        if p.get('org'):
            return p['org']
        ini = initials(p.get('given'))
        return f"{ini} {p['family']}" if first and ini and _fold(p['family']) in ctx.ambiguous else p['family']
    names = [name(p, i == 0) for i, p in enumerate(authors)]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} {'and' if narrative else '&'} {names[1]}"
    return f'{names[0]} et al.'


def intext(items, ctx, narrative=False):
    """items: [(reference, locator)]. Returns [(text, reference)] pieces and the joiner, as one plain text and a list of
    (text, id) parts for linking. Parenthetical: (A, 2000, p. 3; B, 2001). Narrative: A (2000, p. 3)."""
    if narrative and len(items) == 1:
        r, loc = items[0]
        loc = _locator(loc)
        inside = ctx.year(r) + (f', {loc}' if loc else '')
        return f'{author_text(r, ctx, True)} ({inside})', [(f'{author_text(r, ctx, True)} ({inside})', r['id'])]
    rows = sorted(items, key=lambda it: (_fold(author_text(it[0], ctx)), ctx.year(it[0])))
    parts = []                                        # merge works by the same author: (Smith, 2000, 2001)
    for r, loc in rows:
        a, y, loc = author_text(r, ctx), ctx.year(r), _locator(loc)
        if parts and parts[-1]['a'] == a and not loc and not parts[-1]['loc']:
            parts[-1]['y'].append(y); parts[-1]['ids'].append(r['id'])
        else:
            parts.append({'a': a, 'y': [y], 'loc': loc, 'ids': [r['id']]})
    texts = [(f"{p['a']}, {', '.join(p['y'])}" + (f", {p['loc']}" if p['loc'] else ''), p['ids'][0]) for p in parts]
    return '(' + '; '.join(t for t, _ in texts) + ')', texts


def parse_source_spec(spec):
    """'smith2020, p. 12; jones2019, narrative' -> [(key, locator, narrative)]"""
    items = []
    for chunk in str(spec or '').split(';'):
        toks = [t.strip() for t in chunk.split(',') if t.strip()]
        if not toks:
            continue
        narrative = any(t.lower() == 'narrative' for t in toks[1:])
        loc = ', '.join(t for t in toks[1:] if t.lower() != 'narrative')
        items.append((toks[0].lower(), loc, narrative))
    return items


# ───────────────────────── export: BibTeX ─────────────────────────
def _bib_escape(s):
    s = str(s or '').replace('\\', r'\textbackslash{}')
    for ch in '&%$#_{}':
        s = s.replace(ch, '\\' + ch)
    return s


def _bib_people(people):
    return ' and '.join(f"{{{_bib_escape(p['org'])}}}" if p.get('org') else
                        (f"{_bib_escape(p['family'])}, {_bib_escape(p['given'])}" if p.get('given') else f"{{{_bib_escape(p['family'])}}}")
                        for p in people)


def bibtex_entry(r, ctx):
    ty, base = r['type'], split_year(r.get('year'))[0]
    f = {}
    auth, eds = r.get('authors') or [], r.get('editors') or []
    kind = {'article': 'article', 'book': 'book', 'edited': 'book', 'chapter': 'incollection', 'conference': 'inproceedings',
            'thesis': 'phdthesis', 'report': 'techreport', 'web': 'misc', 'dataset': 'misc', 'unpublished': 'unpublished', 'other': 'misc'}[ty]
    if ty == 'thesis' and 'master' in (r.get('level') or '').lower():
        kind = 'mastersthesis'
    if ty == 'edited':
        if auth: f['editor'] = _bib_people(auth)
    elif auth:
        f['author'] = _bib_people(auth)
    if ty == 'chapter' and eds:
        f['editor'] = _bib_people(eds)
    f['title'] = '{' + _bib_escape(r.get('title')) + '}'
    c = r.get('container')
    if ty == 'article' and c:       f['journal'] = _bib_escape(c)
    if ty in ('chapter', 'conference') and c: f['booktitle'] = _bib_escape(c)
    if base.isdigit():              f['year'] = base
    if r.get('volume'):             f['volume'] = _bib_escape(r['volume'])
    if r.get('issue'):              f['number'] = _bib_escape(r['issue'])
    if r.get('number') and ty in ('report', 'thesis'): f['number'] = _bib_escape(r['number'])
    if r.get('pages'):              f['pages'] = _bib_escape(_pages(r['pages']).replace('–', '--'))
    if r.get('edition') and ty != 'dataset': f['edition'] = _bib_escape(r['edition'])
    if r.get('publisher'):
        f['institution' if ty == 'report' else 'publisher'] = _bib_escape(r['publisher'])
    if ty in ('thesis',) and r.get('institution'): f['school'] = _bib_escape(r['institution'])
    if ty == 'conference' and r.get('place'):       f['address'] = _bib_escape(r['place'])
    if r.get('dateText') and ty in ('conference', 'web'): f['month'] = _bib_escape(_dashes(r['dateText']))
    note = []
    if base == 'in press': note.append('in press')
    if ty == 'dataset': note.append('Data set' + (f", version {r['edition']}" if r.get('edition') else ''))
    if ty == 'unpublished': note.append(r.get('descriptor') or 'Unpublished manuscript')
    if ty == 'other' and r.get('note'): note.append(r['note'])
    if ty == 'web' and r.get('accessed'): note.append('Accessed ' + r['accessed'])
    if ty == 'web' and c: f['organization'] = _bib_escape(c)
    if note: f['note'] = _bib_escape('. '.join(note))
    doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', r.get('doi') or '', flags=re.I).strip()
    if doi: f['doi'] = _bib_escape(doi)
    if r.get('url'): f['url'] = r['url']
    body = ',\n'.join(f'  {k} = {{{v}}}' for k, v in f.items())
    return f"@{kind}{{{r['id']},\n{body}\n}}\n"


def to_bibtex(refs, ctx=None):
    ctx = ctx or Context(refs)
    return '\n'.join(bibtex_entry(r, ctx) for r in ctx.sorted())


# ───────────────────────── export: EndNote (tagged format, .enw) ─────────────────────────
_ENW_TYPE = {'article': 'Journal Article', 'book': 'Book', 'edited': 'Edited Book', 'chapter': 'Book Section',
             'conference': 'Conference Paper', 'thesis': 'Thesis', 'report': 'Report', 'web': 'Web Page',
             'dataset': 'Dataset', 'unpublished': 'Manuscript', 'other': 'Generic'}


def _enw_person(p):
    if p.get('org'):
        return p['org'] + ','                         # the trailing comma keeps EndNote from splitting the name
    return f"{p['family']}, {p['given']}" if p.get('given') else p['family'] + ','


def enw_entry(r, ctx):
    ty, base = r['type'], split_year(r.get('year'))[0]
    L = [f'%0 {_ENW_TYPE[ty]}']
    auth, eds = r.get('authors') or [], r.get('editors') or []
    for p in auth:
        L.append(f"{'%E' if ty == 'edited' else '%A'} {_enw_person(p)}")
    for p in eds if ty == 'chapter' else []:
        L.append(f'%E {_enw_person(p)}')
    L.append(f"%T {r.get('title')}")
    c = r.get('container')
    if c:
        L.append(f"{'%J' if ty == 'article' else '%B'} {c}")
    L.append(f"%D {base if base.isdigit() else ''}".rstrip())
    if r.get('volume'):  L.append(f"%V {r['volume']}")
    if r.get('issue'):   L.append(f"%N {r['issue']}")
    if r.get('pages'):   L.append(f"%P {_pages(r['pages'])}")
    if r.get('edition'): L.append(f"%7 {r['edition']}")
    pub = r.get('publisher') or (r.get('institution') if ty == 'thesis' else '')
    if pub:              L.append(f'%I {pub}')
    if ty == 'thesis' and r.get('institution') and r.get('publisher'): L.append(f"%Z {r['institution']}")
    if ty == 'thesis':   L.append(f"%9 {r.get('level') or 'Doctoral dissertation'}")
    if ty == 'conference' and r.get('place'): L.append(f"%C {r['place']}")
    if r.get('dateText') and ty in ('conference', 'web'): L.append(f"%8 {r['dateText']}")
    if r.get('number') and ty in ('report', 'thesis'): L.append(f"%@ {r['number']}")
    doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', r.get('doi') or '', flags=re.I).strip()
    if doi:              L.append(f'%R {doi}')
    if r.get('url'):     L.append(f"%U {r['url']}")
    if r.get('accessed'): L.append(f"%[ {r['accessed']}")
    notes = [x for x in (('in press' if base == 'in press' else ''), (r.get('descriptor') if ty in ('unpublished',) else ''), r.get('note')) if x]
    if notes:            L.append('%Z ' + '. '.join(notes))
    L.append(f"%F {r['id']}")
    return '\n'.join(l for l in L if l.strip() not in ('%D',)) + '\n'


def to_endnote(refs, ctx=None):
    ctx = ctx or Context(refs)
    return '\n'.join(enw_entry(r, ctx) for r in ctx.sorted())


# ───────────────────────── LaTeX ─────────────────────────
def latex_list(refs, escape, ctx=None):
    """The reference list for the LaTeX export: one hanging paragraph per entry. `escape` is the exporter's LaTeX escaper."""
    ctx = ctx or Context(refs)
    wanted = {r['id'] for r in refs}
    out = []
    for r in (x for x in ctx.sorted() if x['id'] in wanted):
        rich = apa_rich(r, ctx)
        s = ''.join(f'\\emph{{{escape(t)}}}' if st == 'i' else (f'\\url{{{t}}}' if st == 'u' else escape(t)) for t, st in rich)
        out.append(f'\\hangindent=1.27cm \\hangafter=1 \\noindent {s}\\par\\medskip')
    return '\n'.join(out)
