"""
The Glossary: the concepts that the grammar and the dictionary can refer to.

One Markdown file for each entry, in the folder of the glossary (project/glossary/predicate.md). The file name (without .md) is the id of the entry, the
first heading is its term, and the whole file is written with the markup of the grammar (every shortcode of the grammar works in an entry).

A text refers to an entry with  {{glossary: predicate}}  (a link that reads as the term, with the beginning of the definition as a tooltip) or
{{glossary: predicate | the words shown}}. Nothing here knows the web framework or a particular project.
"""
import html as _html
import os
import re
import unicodedata

import captions as _cap

ID_MAX = 60
_ID = re.compile(r'[a-z0-9][a-z0-9_-]*')


def clean_id(s):
    """An entry id as it is kept: lower case letters, digits, - and _ (anything else becomes _), at most 60 characters; '' if nothing is left."""
    return re.sub(r'[^a-z0-9_-]+', '_', str(s or '').strip().lower()).strip('_-')[:ID_MAX]


def slug_id(term):
    """The id made from a term (accents dropped): 'Case marking' -> 'case_marking'."""
    s = unicodedata.normalize('NFKD', str(term or ''))
    return clean_id(''.join(c for c in s if not unicodedata.combining(c)))


def term_of(md, fallback=''):
    """The term of an entry: its first heading (the markup of the heading removed); the id as words if there is none."""
    for line in str(md or '').split('\n'):
        m = re.match(r'^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$', line)
        if m:
            t = re.sub(r'\{[^}]*\}', '', m.group(1))                       # {#id} attributes
            t = re.sub(r'[*_`]+', '', t).strip()
            if t:
                return t
    return (fallback or '').replace('_', ' ').replace('-', ' ').strip().capitalize()


def snippet(md, n=300):
    """The beginning of the definition as plain text, from the source (so that an entry that refers to itself cannot loop): no heading, code, image,
    shortcode, link address or emphasis."""
    s = re.sub(r'```.*?```', ' ', str(md or ''), flags=re.S)
    s = re.sub(r'^\s{0,3}#{1,6}\s+.*$', '', s, count=1, flags=re.M)             # the term itself
    s = re.sub(r'!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?', ' ', s)                      # images
    s = re.sub(r'\{\{[^}]*\}\}', ' ', s)                                         # shortcodes
    s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)                               # links: their text
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'[*_`>|#]+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0].rstrip(',;:') + '…'


def sort_key(term):
    s = unicodedata.normalize('NFKD', str(term or ''))
    return ''.join(c for c in s if not unicodedata.combining(c)).casefold()


_CACHE = {}


def entry_index(folder):
    """([{'id', 'term', 'snippet'}] sorted by term, {id: entry}) for the entries of the folder. A file is read again only when it changed."""
    try:
        names = sorted(n for n in os.listdir(folder) if n.endswith('.md') and _ID.fullmatch(n[:-3]))
    except OSError:
        return [], {}
    out = []
    for name in names:
        path = os.path.join(folder, name)
        try:
            st = os.stat(path)
            key = (path, st.st_mtime_ns, st.st_size)
            if key not in _CACHE:
                with open(path, encoding='utf-8') as f:
                    src = f.read()
                _CACHE[key] = {'id': name[:-3], 'term': term_of(src, name[:-3]), 'snippet': snippet(src)}
            out.append(_CACHE[key])
        except OSError:
            continue
    out.sort(key=lambda e: (sort_key(e['term']), e['id']))
    return out, {e['id']: e for e in out}


# ── the shortcode ──
_SHORTCODE = re.compile(r'\{\{\s*glossary\s*:\s*([^}|]*?)\s*(?:\|\s*([^}]*?)\s*)?\}\}')


def link_html(spec_id, shown, by_id, base='glossary.html'):
    e = by_id.get(clean_id(spec_id))
    if not e:
        return '<span class="shortcode-error">Glossary entry not found: %s</span>' % _html.escape(str(spec_id).strip() or '(empty)')
    return '<a class="gloss-link" href="%s#%s" title="%s">%s</a>' % (_html.escape(base), e['id'], _html.escape(e['snippet']), _html.escape(shown or e['term']))


def expand(text, by_id, base='glossary.html'):
    """{{glossary: …}} in a text made of HTML become links, in the text between the tags only; inside <pre> and <code> they are left as written."""
    out = []
    for part in _cap._CODE.split(text):
        if _cap._CODE.fullmatch(part):
            out.append(part)
        else:
            out.append(''.join(tok if tok.startswith('<') and tok.endswith('>') else _SHORTCODE.sub(lambda m: link_html(m.group(1), m.group(2), by_id, base), tok)
                               for tok in _cap._TAG.split(part)))
    return ''.join(out)


def latex_text(line, by_id, escape):
    """{{glossary: …}} in a line for LaTeX: the words shown, or the term, as plain text (the Glossary is a page of the site); ?? if the entry does not exist."""
    def one(m):
        e = by_id.get(clean_id(m.group(1)))
        return escape(m.group(2) or e['term']) if e else '\\textbf{??}'
    return _SHORTCODE.sub(one, line)
