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


_YEAR = r'\d{4}[a-z]?|n\.\s?d\.(?:-[a-z])?|in press(?:-[a-z])?'


def parse_source_spec(spec, keys=None):
    """'smith2020, p. 12; Jones 2019, narrative; Lee, 2018' -> [(what, locator, narrative)].
    `what` is a key, or the author(s) and year as written in the text ('Jones 2019', 'Lee, 2018'). `keys` are the keys that
    exist: a first word that is a key is never taken for an author."""
    keys = {str(k).lower() for k in (keys or ())}
    items = []
    for chunk in str(spec or '').split(';'):
        toks = [t.strip() for t in chunk.split(',') if t.strip()]
        if not toks:
            continue
        what, rest = toks[0], toks[1:]
        if what.lower() not in keys and rest and re.fullmatch(_YEAR, rest[0], re.I):      # "Lee, 2018": author, then year
            what, rest = f'{what} {rest[0]}', rest[1:]
        narrative = any(t.lower() == 'narrative' for t in rest)
        loc = ', '.join(t for t in rest if t.lower() != 'narrative')
        items.append((what.lower() if (what.lower() in keys or ' ' not in what) else what, loc, narrative))
    return items


def find_reference(what, refs, ctx):
    """Find the reference a citation points to. `what` is a key, or the author(s) and year as one writes them in a text:
    'Smith 2020b', 'Smith & Jones 2016', 'Lee et al. 2018', 'A. Young 2019', 'Smith 2020' (when only one year
    of that author matches). Returns (reference, None), or (None, 'not found') or (None, 'ambiguous: 2005a, 2005b')."""
    t = str(what or '').strip()
    for r in refs:
        if r['id'] == t.lower():
            return r, None
    m = re.fullmatch(r'(.+?)[\s,]+(' + _YEAR + r')', t, re.I)
    if not m:
        return None, 'not found'
    who, year = m.group(1).strip(), m.group(2).lower()
    year = 'n.d.' + year[year.index('.', 2) + 1:] if year.startswith('n') else year
    ini = ''
    mi = re.match(r'^((?:[^\W\d_]\.\s*)+)(\S.*)$', who)                      # "A. McManus": initials before the surname
    if mi:
        ini, who = _fold(mi.group(1)).replace('.', '').replace(' ', ''), mi.group(2).strip()
    et_al = bool(re.search(r'\s+et\s+al\.?$', who, re.I))
    who = re.sub(r'\s+et\s+al\.?$', '', who, flags=re.I)
    names = [_fold(x).strip() for x in re.split(r'\s*&\s*|\s+and\s+', who) if x.strip()]
    exact, loose = [], []
    for r in refs:
        au = r.get('authors') or []
        have = [_fold(a.get('org') or a.get('family')) for a in au]
        if not names or len(names) > len(have) or have[:len(names)] != names:
            continue
        if ini and not _fold(initials(au[0].get('given'))).replace('.', '').replace(' ', '').startswith(ini):
            continue
        shown = ctx.year(r)
        if (shown != year) if (year[-1:].isalpha() and not year.startswith(('n.d.', 'in press')) or '-' in year) else (split_year(shown)[0] != year):
            continue
        (exact if (len(have) == len(names) or (et_al and len(have) > len(names))) else loose).append(r)
    for found in (exact, loose):
        if len(found) == 1:
            return found[0], None
        if len(found) > 1:
            return None, 'ambiguous: ' + ', '.join(sorted(ctx.year(r) for r in found))
    return None, 'not found'


# ───────────────────────── same authors, same year: the author chooses the letters ─────────────────────────
# APA tells apart works by the same authors in the same year with letters (2026a, 2026b ...), and the letter must be the same in the
# reference list and in every citation. When a reference is saved that shares its authors and year with another, the author decides
# which is which (the engine suggests an order); the choice is stored in the year, and the citations in the grammar follow.
LETTERS = 'abcdefghijklmnopqrstuvwxyz'


def with_letter(base, letter):
    """('2026', 'a') -> '2026a'; ('n.d.', 'a') -> 'n.d.-a'; ('in press', 'a') -> 'in press-a'"""
    return base if not letter else (f'{base}-{letter}' if not str(base).isdigit() else f'{base}{letter}')


def _group_key(r):
    return (_authors_key(r) or ('~' + _title_key(r),), split_year(r.get('year'))[0])


def groups_needing_choice(before, after, touched):
    """The groups of two or more references with the same authors and year, in `after`, that the author has to give letters to: those that
    contain a reference of `touched` (added, or edited), whose membership is not what it was in `before`, and in which some
    reference has no letter of its own (or two have the same). Returns [(key, [references in the order of `after`])]."""
    def groups(refs):
        g = {}
        for r in refs:
            g.setdefault(_group_key(r), []).append(r['id'])
        return g
    gb, ga, byid, out = groups(before), groups(after), {r['id']: r for r in after}, []
    for key, ids in ga.items():
        if len(ids) < 2 or not any(i in touched for i in ids) or set(gb.get(key, [])) == set(ids):
            continue
        letters = [split_year(byid[i].get('year'))[1] for i in ids]
        if all(letters) and len(set(letters)) == len(letters):
            continue
        out.append((key, [byid[i] for i in ids]))
    return out


def suggest_letters(members, cited):
    """{id: letter}. The ones that already have a letter keep it. The others get the free letters in this order: those the grammar
    cites already, in the order it first cites them (the first cited is a); then the rest, the older ones first, the new one last
    (the author will say which will be cited first). `cited` is {id: position of its first citation in the grammar}."""
    taken = {split_year(r.get('year'))[1] for r in members} - {''}
    free = iter(c for c in LETTERS if c not in taken)
    out = {r['id']: split_year(r.get('year'))[1] for r in members if split_year(r.get('year'))[1]}
    order = sorted((i for i, r in enumerate(members) if not split_year(r.get('year'))[1]),
                   key=lambda i: (0, cited[members[i]['id']]) if members[i]['id'] in cited else (1, i))
    for i in order:
        out[members[i]['id']] = next(free)
    return out


def apply_letters(refs, groups, letters):
    """Give each reference of the groups the letter chosen. Returns (the references, None) or (None, why not): every reference of a
    group needs its letter, a letter is one of a-z, and no two of a group share one."""
    letters = letters if isinstance(letters, dict) else {}
    chosen = {}
    for _key, members in groups:
        seen = set()
        for r in members:
            l = letters.get(r['id'])
            if not (isinstance(l, str) and len(l) == 1 and l in LETTERS):
                return None, 'Choose a letter, from a to z, for each of the references.'
            if l in seen:
                return None, f'The letter {l} is given to two references: each needs its own.'
            seen.add(l); chosen[r['id']] = l
    out = []
    for r in refs:
        out.append(dict(r, year=with_letter(split_year(r.get('year'))[0], chosen[r['id']])) if r['id'] in chosen else r)
    return out, None


_YEAR_TOKEN = re.compile(r'(?<![\w.])(' + _YEAR + r')(?![\w])', re.I)


def rewrite_source_spec(spec, old_refs, new_refs):
    """The text of a {{source: …}} with the year of each citation that was written by author and year (Smith 2026) made the year the
    reference now has (Smith 2026a): the citation is read in the references as they were and written for the references as they are.
    Citations by key, and those that did not find a reference, are left as they were. Returns (spec, [(old, new)])."""
    old_ctx, new_ctx = Context(old_refs), Context(new_refs)
    keys, new_by = {r['id'] for r in old_refs}, {r['id']: r for r in new_refs}
    out, changes = [], []
    for chunk in str(spec).split(';'):
        items = parse_source_spec(chunk, keys)
        ref = find_reference(items[0][0], old_refs, old_ctx)[0] if len(items) == 1 else None
        if ref and ref['id'] in new_by and items[0][0].lower() != ref['id']:
            now = new_ctx.year(new_by[ref['id']])
            m = _YEAR_TOKEN.search(chunk)
            if m and m.group(1).lower() != now.lower():
                changes.append((m.group(1), now))
                chunk = chunk[:m.start(1)] + now + chunk[m.end(1):]
        out.append(chunk)
    return ';'.join(out), changes


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


# ───────────────────────── import: BibTeX, EndNote (tagged format) and RIS ─────────────────────────
# parse_references(text) reads a list of references in any of these formats and gives, for each, either a reference as the form
# would make it (validated by clean()) or the reason why it could not be read. merge_import() then sets them beside the references
# that exist: those that are already there are skipped, a key that is taken is replaced by a free one.
MAX_IMPORT_CHARS = 2_000_000
MAX_IMPORT_ENTRIES = 5000

_ACCENTS = {"'": '\u0301', '`': '\u0300', '^': '\u0302', '"': '\u0308', '~': '\u0303', '=': '\u0304', '.': '\u0307',
            'u': '\u0306', 'v': '\u030c', 'c': '\u0327', 'H': '\u030b', 'k': '\u0328', 'r': '\u030a'}
_LETTERS = {'ss': 'ß', 'o': 'ø', 'O': 'Ø', 'aa': 'å', 'AA': 'Å', 'ae': 'æ', 'AE': 'Æ', 'oe': 'œ', 'OE': 'Œ', 'l': 'ł', 'L': 'Ł',
            'i': 'i', 'j': 'j', 'dh': 'ð', 'DH': 'Ð', 'th': 'þ', 'TH': 'Þ', 'ng': 'ŋ', 'NG': 'Ŋ'}
_PARTICLES = {'von', 'van', 'de', 'der', 'den', 'del', 'della', 'di', 'da', 'du', 'la', 'le', 'ter', 'ten', 'al', 'el', 'bin', 'ibn',
              'dos', 'das', 'do', 'zu', 'af', "d'", 'des', 'los', 'las'}
_ORG_WORDS = re.compile(r'\b(university|universit\w+|institute|institut|association|organi[sz]ation|society|press|committee|council|department|'
                        r'ministry|bureau|group|project|agency|cent(?:re|er)|foundation|commission|survey|office|board|library|museum|school|'
                        r'college|academy|inc|ltd|company|consortium|network|program(?:me)?|team|laboratory)\b', re.I)


def unlatex(s):
    """A BibTeX value as plain text: LaTeX accents and special letters become the letters, escaped characters become themselves,
    protective braces go."""
    s = str(s or '')
    if '\\' in s or '{' in s or '~' in s or '$' in s or '--' in s:
        s = re.sub(r'\\([&%$#_{}])', lambda m: m.group(1), s)
        s = re.sub(r"\\(['`^\"~=.])\s*(?:\{\s*\\?([A-Za-z])\s*\}|\\?([A-Za-z]))", lambda m: (m.group(2) or m.group(3)) + _ACCENTS[m.group(1)], s)
        s = re.sub(r'\\([uvcHkr])(?:\s*\{\s*\\?([A-Za-z])\s*\}|\s+\\?([A-Za-z]))', lambda m: (m.group(2) or m.group(3)) + _ACCENTS[m.group(1)], s)
        s = re.sub(r'\\([A-Za-z]+)(?![A-Za-z])\s?', lambda m: _LETTERS.get(m.group(1), ''), s)
        s = s.replace('$', '').replace('{', '').replace('}', '').replace('\\', '')
        s = s.replace('~', ' ').replace('---', '—').replace('--', '–')
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', s)).strip()


def _key_of(s):
    k = re.sub(r'[^a-z0-9_-]+', '-', str(s or '').strip().lower()).strip('-_')
    return k[:80]


def _top_split(s, sep_re):
    """Split at the places that match sep_re and are not inside braces."""
    out, depth, start = [], 0, 0
    for m in re.finditer(r'[{}]|' + sep_re, s):
        t = m.group(0)
        if t == '{': depth += 1
        elif t == '}': depth = max(0, depth - 1)
        elif depth == 0:
            out.append(s[start:m.start()]); start = m.end()
    out.append(s[start:])
    return [x.strip() for x in out if x.strip()]


def _person_from_words(words):
    """['John', 'von', 'Neumann'] -> {'family': 'von Neumann', 'given': 'John'}"""
    if not words:
        return None
    i = len(words) - 1
    while i > 0 and words[i - 1][:1].islower() and words[i - 1].lower() in _PARTICLES:
        i -= 1
    fam, giv = ' '.join(words[i:]), ' '.join(words[:i])
    return {'family': fam, 'given': giv} if giv else {'family': fam}


def _split_name(raw, comma_is_org=False):
    """One name as written in a list of references -> a person {'family', 'given'}, an organisation {'org'}, or None."""
    raw = raw.strip()
    if not raw or raw.lower() in ('others', 'et al', 'et al.'):
        return None
    if raw.startswith('{') and raw.endswith('}') and _balanced_group(raw):             # {World Health Organization}: one name, not to be split
        return {'org': unlatex(raw[1:-1])}
    parts = _top_split(raw, r'\s*,\s*')
    if len(parts) == 1 and raw.rstrip().endswith(','):                          # "Name,": an organisation, or a family name alone
        n = unlatex(parts[0])
        return {'org': n} if (' ' in n or _ORG_WORDS.search(n)) else {'family': n}
    if len(parts) >= 2:
        fam, giv = unlatex(parts[0]), unlatex(parts[-1])
        p = {'family': fam}
        if giv: p['given'] = giv
        if len(parts) == 3 and unlatex(parts[1]): p['suffix'] = unlatex(parts[1])
        return p
    words = _top_split(raw, r'\s+')
    n = unlatex(raw)
    if _ORG_WORDS.search(n) and len(words) > 1:
        return {'org': n}
    return _person_from_words([unlatex(w) for w in words])


def _balanced_group(raw):
    depth = 0
    for i, c in enumerate(raw):
        depth += (c == '{') - (c == '}')
        if depth == 0 and i < len(raw) - 1:
            return False
    return depth == 0


def _names_bibtex(raw):
    return [p for p in (_split_name(x) for x in _top_split(raw, r'\s+and\s+')) if p]


# ── BibTeX ──
_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
_BRACE = re.compile(r'[{}\\]')


def _read_braced(s, i):
    """s[i] == '{': the text up to the matching brace, and the position after it (an unclosed brace takes the rest)."""
    depth, j, n = 0, i, len(s)
    while True:
        m = _BRACE.search(s, j)
        if not m:
            return s[i + 1:], n
        c = m.group(0)
        if c == '\\': j = m.end() + 1; continue
        depth += 1 if c == '{' else -1
        j = m.end()
        if depth == 0:
            return s[i + 1:m.start()], j


def _read_quoted(s, i):
    depth, j, n = 0, i + 1, len(s)
    while j < n:
        c = s[j]
        if c == '\\': j += 2; continue
        if c == '{': depth += 1
        elif c == '}': depth = max(0, depth - 1)
        elif c == '"' and depth == 0:
            return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], n


def _bib_value(s, i, macros):
    parts, n = [], len(s)
    while i < n:
        while i < n and s[i] in ' \t\r\n': i += 1
        if i >= n: break
        c = s[i]
        if c == '{': v, i = _read_braced(s, i)
        elif c == '"': v, i = _read_quoted(s, i)
        else:
            m = re.compile(r'[A-Za-z0-9_:.+/-]+').match(s, i)
            if not m: break
            word = m.group(0); i = m.end()
            v = word if word.isdigit() else macros.get(word.lower(), word)
        parts.append(v)
        while i < n and s[i] in ' \t\r\n': i += 1
        if i < n and s[i] == '#': i += 1; continue
        break
    return ''.join(parts), i


def parse_bibtex(text):
    """-> [{'type', 'key', 'fields': {lower case name: raw value}}]; @string macros are expanded, @comment and @preamble skipped."""
    s, n, i, out = str(text or ''), len(str(text or '')), 0, []
    macros = {m[:3].lower(): m for m in _MONTHS}
    head = re.compile(r'@\s*([A-Za-z]+)\s*([{(])')
    while len(out) < MAX_IMPORT_ENTRIES:
        i = s.find('@', i)
        if i < 0: break
        m = head.match(s, i)
        if not m: i += 1; continue
        kind, close = m.group(1).lower(), ('}' if m.group(2) == '{' else ')')
        i = m.end()
        if kind in ('comment', 'preamble'):
            if m.group(2) == '{': _v, i = _read_braced(s, i - 1)
            continue
        key = ''
        if kind != 'string':
            mk = re.compile(r'\s*([^,\s{}()="]*)\s*(,|' + re.escape(close) + ')').match(s, i)
            if not mk: continue
            key, i = mk.group(1), mk.end()
            if mk.group(2) == close:
                continue
        fields = {}
        while i < n:
            while i < n and s[i] in ' \t\r\n,': i += 1
            if i >= n or s[i] == close: i += 1; break
            if s[i] == '@': break                                    # a missing closing brace: the next entry begins
            mf = re.compile(r'([^\s=,{}()"#]+)\s*=').match(s, i)
            if not mf:
                nxt = re.compile(r'[,' + re.escape(close) + r']').search(s, i + 1)
                i = nxt.start() if nxt else n
                continue
            name = mf.group(1).lower(); i = mf.end()
            val, i = _bib_value(s, i, macros)
            if kind == 'string': macros[name] = val
            else: fields[name] = val
        if kind != 'string':
            out.append({'type': kind, 'key': key, 'fields': fields})
    return out


def _clean_year(v):
    v = unlatex(v)
    if re.fullmatch(r'\d{4}[a-z]?', v): return v
    if re.fullmatch(r'(?i)(in press|forthcoming|accepted|to appear)', v): return 'in press'
    if re.fullmatch(r'(?i)n\.?\s?d\.?', v): return 'n.d.'
    m = re.search(r'(?<!\d)(\d{4})(?!\d)', v)
    return m.group(1) if m else ''


def _pages_in(v):
    return re.sub(r'\s*(?:--|—|–|-)+\s*', '–', unlatex(v)) if v else ''


def _month_text(v):
    v = unlatex(v)
    if re.fullmatch(r'0?([1-9]|1[0-2])', v): return _MONTHS[int(v) - 1]
    return v


_BIB_KIND = {'article': 'article', 'book': 'book', 'mvbook': 'book', 'inbook': 'chapter', 'incollection': 'chapter', 'inreference': 'chapter',
             'bookinbook': 'chapter', 'suppbook': 'chapter', 'inproceedings': 'conference', 'conference': 'conference', 'proceedings': 'edited',
             'collection': 'edited', 'mvcollection': 'edited', 'mvproceedings': 'edited', 'phdthesis': 'thesis', 'mastersthesis': 'thesis', 'thesis': 'thesis',
             'techreport': 'report', 'report': 'report', 'manual': 'report', 'unpublished': 'unpublished', 'online': 'web', 'electronic': 'web',
             'www': 'web', 'dataset': 'dataset'}


def bib_to_form(e):
    """A parsed BibTeX entry -> (the data of a reference as the form gives it, [warnings])."""
    f, kind, warn = e['fields'], e['type'], []
    g = lambda *names: next((unlatex(f[k]) for k in names if f.get(k) and unlatex(f[k])), '')
    ty = _BIB_KIND.get(kind, 'other')
    authors, editors = _names_bibtex(f.get('author', '')), _names_bibtex(f.get('editor', ''))
    if ty == 'book' and editors and not authors: ty = 'edited'
    if ty == 'other' and kind in ('misc',) and g('url') and not g('publisher', 'howpublished'): ty = 'web'
    if ty == 'edited': authors, editors = authors or editors, []
    dataset_note = next((m for m in (re.fullmatch(r'(?i)data ?set(?:,\s*version\s+(.+))?', p.strip()) for p in re.split(r'\.\s+', g('note'))) if m), None)
    if ty == 'other' and dataset_note:                                         # what the site writes for a data set
        ty = 'dataset'
    title = g('title')
    if title and g('subtitle'): title += ': ' + g('subtitle')
    form = {'type': ty, 'authors': authors, 'editors': editors if ty == 'chapter' else [], 'title': title, 'id': _key_of(e['key'])}
    year = _clean_year(f.get('year', '')) or _clean_year(f.get('date', ''))
    if not year and re.search(r'(?i)in press|forthcoming', f.get('note', '')):
        year = 'in press'
    form['year'] = year
    if ty == 'article': form['container'] = g('journal', 'journaltitle', 'journal-title')
    elif ty in ('chapter', 'conference'): form['container'] = g('booktitle', 'maintitle')
    elif ty == 'web': form['container'] = g('organization', 'website')
    form['volume'] = g('volume')
    if ty == 'article': form['issue'] = g('number', 'issue')
    if ty in ('report', 'thesis'): form['number'] = g('number')
    form['pages'] = _pages_in(f.get('pages')) or g('eid', 'articleno')
    form['edition'] = g('edition', 'version') or ((dataset_note.group(1) or '').strip() if dataset_note else '')
    if ty == 'report': form['publisher'] = g('institution', 'publisher', 'organization')
    elif ty == 'thesis': form['institution'] = g('school', 'institution', 'publisher')
    else: form['publisher'] = g('publisher')
    form['place'] = g('address', 'location')
    if ty in ('conference', 'web') and f.get('month'): form['dateText'] = _month_text(f['month'])
    if ty == 'thesis': form['level'] = g('type') or ("Master's thesis" if kind == 'mastersthesis' else 'Doctoral dissertation')
    note = g('note', 'howpublished')
    if ty == 'unpublished': form['descriptor'] = note
    elif ty == 'other': form['note'] = note
    elif ty == 'dataset': form['note'] = ''
    elif ty == 'web':
        m = re.match(r'(?i)accessed\s+(.*)', note)
        if m: form['accessed'] = m.group(1)
    if g('urldate'): form['accessed'] = g('urldate')
    doi = g('doi')
    form['doi'] = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', doi, flags=re.I)
    url = g('url')
    if url and not re.match(r'^https?://\S+$', url, re.I):
        warn.append('the URL was left out (it does not start with http:// or https://)'); url = ''
    form['url'] = url
    if f.get('author', '').lower().rstrip().endswith('others'): warn.append('"and others" was left out')
    return form, warn


# ── EndNote, tagged format (.enw / Refer) ──
_ENW_KIND = {'journal article': 'article', 'magazine article': 'article', 'newspaper article': 'article', 'book': 'book', 'edited book': 'edited',
             'book section': 'chapter', 'conference paper': 'conference', 'conference proceedings': 'conference', 'thesis': 'thesis',
             'report': 'report', 'web page': 'web', 'electronic source': 'web', 'online multimedia': 'web', 'dataset': 'dataset',
             'manuscript': 'unpublished', 'unpublished work': 'unpublished'}


def parse_endnote(text):
    """-> [{'tags': {tag character: [values]}}]: the entries of a file in EndNote's tagged format (a line per tag, %0 begins an entry)."""
    out, cur, last = [], None, None
    for raw in str(text or '').lstrip('\ufeff').splitlines():
        line = raw.rstrip('\r\n')
        m = re.match(r'^%(\S)(?:\s+(.*))?$', line)
        if m:
            tag, val = m.group(1), (m.group(2) or '').strip()
            if tag == '0' or cur is None:
                if len(out) >= MAX_IMPORT_ENTRIES: break
                cur = {}; out.append({'tags': cur})
            cur.setdefault(tag, []).append(val); last = (tag, len(cur[tag]) - 1)
        elif not line.strip():
            cur, last = None, None
        elif cur is not None and last:
            cur[last[0]][last[1]] = (cur[last[0]][last[1]] + ' ' + line.strip()).strip()
    return [e for e in out if e['tags']]


def _names_list(values):
    return [p for p in (_split_name(v) for v in values) if p]


def enw_to_form(e):
    t, warn = e['tags'], []
    first = lambda *tags: next((t[k][0].strip() for k in tags if t.get(k) and t[k][0].strip()), '')
    ty = _ENW_KIND.get(first('0').lower(), 'other')
    authors, editors = _names_list(t.get('A', [])), _names_list(t.get('E', []))
    if ty == 'edited': authors, editors = authors or editors, []
    form = {'type': ty, 'authors': authors, 'editors': editors if ty == 'chapter' else [], 'title': first('T'), 'id': _key_of(first('F'))}
    z = [x.strip() for v in t.get('Z', []) for x in re.split(r'\.\s+', v) if x.strip()]
    year = _clean_year(first('D'))
    if not year and any(x.lower().rstrip('.') == 'in press' for x in z): year = 'in press'
    z = [x for x in z if x.lower().rstrip('.') != 'in press']
    form['year'] = year
    form['container'] = first('J', 'B') if ty == 'article' else first('B', 'J')
    form['volume'], form['issue'], form['pages'], form['edition'] = first('V'), first('N'), _pages_in(first('P')), first('7')
    if ty == 'thesis': form['institution'], form['level'] = first('I'), first('9') or 'Doctoral dissertation'
    else: form['publisher'] = first('I')
    form['place'], form['dateText'] = first('C'), (first('8') if ty in ('conference', 'web') else '')
    if ty in ('report', 'thesis'): form['number'] = first('@')
    form['doi'] = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', first('R'), flags=re.I)
    url = first('U')
    if url and not re.match(r'^https?://\S+$', url, re.I): warn.append('the URL was left out (it does not start with http:// or https://)'); url = ''
    form['url'], form['accessed'] = url, first('[')
    if ty == 'unpublished': form['descriptor'] = '. '.join(z)
    elif ty == 'other': form['note'] = '. '.join(z)
    return form, warn


# ── RIS ──
_RIS_KIND = {'JOUR': 'article', 'MGZN': 'article', 'NEWS': 'article', 'JFULL': 'article', 'BOOK': 'book', 'EBOOK': 'book', 'EDBOOK': 'edited',
             'CHAP': 'chapter', 'ECHAP': 'chapter', 'CONF': 'conference', 'CPAPER': 'conference', 'THES': 'thesis', 'RPRT': 'report',
             'ELEC': 'web', 'WEB': 'web', 'BLOG': 'web', 'DATA': 'dataset', 'UNPB': 'unpublished', 'MANSCPT': 'unpublished'}


def parse_ris(text):
    out, cur = [], None
    for raw in str(text or '').lstrip('\ufeff').splitlines():
        m = re.match(r'^([A-Z][A-Z0-9])  - ?(.*)$', raw.rstrip('\r\n'))
        if not m: continue
        tag, val = m.group(1), m.group(2).strip()
        if tag == 'TY':
            if len(out) >= MAX_IMPORT_ENTRIES: break
            cur = {'TY': [val]}; out.append({'tags': cur})
        elif tag == 'ER': cur = None
        elif cur is not None: cur.setdefault(tag, []).append(val)
    return out


def ris_to_form(e):
    t, warn = e['tags'], []
    first = lambda *tags: next((t[k][0] for k in tags if t.get(k) and t[k][0]), '')
    ty = _RIS_KIND.get(first('TY').upper(), 'other')
    authors, editors = _names_list(t.get('AU', []) + t.get('A1', [])), _names_list(t.get('A2', []) + t.get('ED', []))
    if ty == 'edited': authors, editors = authors or editors, []
    form = {'type': ty, 'authors': authors, 'editors': editors if ty == 'chapter' else [], 'title': first('TI', 'T1'), 'id': _key_of(first('ID'))}
    form['year'] = _clean_year(first('PY', 'Y1', 'DA'))
    form['container'] = first('JF', 'JO', 'T2', 'BT', 'JA') if ty in ('article', 'chapter', 'conference', 'web') else ''
    form['volume'], form['issue'], form['edition'] = first('VL'), first('IS'), first('ET')
    sp, ep = first('SP'), first('EP')
    form['pages'] = _pages_in(sp + '-' + ep) if sp and ep else sp
    if ty == 'thesis': form['institution'], form['level'] = first('PB'), first('M3') or 'Doctoral dissertation'
    else: form['publisher'] = first('PB')
    form['place'], form['dateText'] = first('CY'), (first('DA') if ty in ('conference', 'web') else '')
    form['doi'] = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', first('DO'), flags=re.I)
    url = first('UR')
    if url and not re.match(r'^https?://\S+$', url, re.I): warn.append('the URL was left out (it does not start with http:// or https://)'); url = ''
    form['url'], form['accessed'] = url, first('Y2')
    if ty == 'unpublished': form['descriptor'] = first('N1')
    elif ty == 'other': form['note'] = first('N1')
    return form, warn


def detect_format(text):
    t = str(text or '').lstrip('\ufeff')
    if re.search(r'(?m)^\s*@\s*[A-Za-z]+\s*[{(]', t) or re.search(r'@\s*(?:article|book|booklet|conference|inbook|incollection|inproceedings|manual|mastersthesis|misc|phdthesis|proceedings|techreport|unpublished|'
                 r'online|report|thesis|string|comment|preamble|dataset|software|collection|inreference|mvbook|electronic|www)\s*[{(]', t, re.I): return 'bibtex'
    if re.search(r'(?m)^TY  - ', t): return 'ris'
    if re.search(r'(?m)^%[0A-Za-z@\[7-9]\s', t): return 'endnote'
    return None


def parse_references(text):
    """-> (format or None, [{'ref': a validated reference or None, 'error': why not, 'warnings': [...], 'what': a short description}])."""
    t = str(text or '')[:MAX_IMPORT_CHARS]
    fmt = detect_format(t)
    if not fmt:
        return None, []
    if fmt == 'bibtex':   raw, conv = parse_bibtex(t), bib_to_form
    elif fmt == 'endnote': raw, conv = parse_endnote(t), enw_to_form
    else:                 raw, conv = parse_ris(t), ris_to_form
    items = []
    for e in raw:
        try:
            form, warn = conv(e)
        except Exception:
            items.append({'ref': None, 'error': 'it could not be read', 'warnings': [], 'what': ''}); continue
        what = (form.get('title') or e.get('key') or '')[:80]
        if not form.get('title'):
            items.append({'ref': None, 'error': 'it has no title', 'warnings': warn, 'what': e.get('key') or what}); continue
        ref, err = clean(form)
        if ref is None:
            items.append({'ref': None, 'error': err, 'warnings': warn, 'what': what}); continue
        items.append({'ref': ref, 'error': None, 'warnings': warn, 'what': what})
    return fmt, items


def _signature(r):
    return (_authors_key(r), _title_key(r), split_year(r.get('year'))[0])


def merge_import(existing, items):
    """Set imported references beside those that exist. Returns (the references to add, a report for each item):
    status 'new', 'renamed' (its key was taken by another reference: it has a free one), 'duplicate' (same authors, year and title:
    skipped) or 'rejected' (it could not be read)."""
    taken, sigs, add, report = {r['id'] for r in existing}, {_signature(r): r['id'] for r in existing}, [], []
    for it in items:
        r = it.get('ref')
        if r is None:
            report.append(dict(it, status='rejected', id='')); continue
        sig = _signature(r)
        if sig in sigs:
            report.append(dict(it, status='duplicate', id=sigs[sig])); continue
        status = 'new'
        if r['id'] and r['id'] in taken:
            r['id'], status = suggest_id(r, taken), 'renamed'
        elif not r['id']:
            r['id'] = suggest_id(r, taken)
        taken.add(r['id']); sigs[sig] = r['id']; add.append(r)
        report.append(dict(it, status=status, id=r['id']))
    return add, report


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
