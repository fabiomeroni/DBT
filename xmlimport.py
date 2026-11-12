"""
Import of any XML dictionary into the DBT's own format (LEXICA XML: <EntréeLexicale>, <Lemme>, <Sens> …).

The logic is that of LExport (https://lexport-anonymous.streamlit.app/), which converts lexical XML dictionaries into other formats: the file is
read without being told its schema; the author says, once, which XML node is what (the entry, the headword, the part of speech, the definition …) and
the dictionary is converted. Here the target is the DBT.

A field is described by a small dictionary:
    {'path': './sense/gloss', 'value': './text', 'filterAttr': 'lang', 'filterValue': 'en'}
  path         the elements, relative to the entry (or to the sense): a bare tag (anywhere below) or a path such as ./lexical-unit/form
  value        what is read from each element: '' its text, '@attr' one of its attributes, 'text' (or any path) the text of a descendant
  filterAttr / filterValue   keep only the elements whose attribute has that value (the language of a gloss, the type of a note)
The language of the forms is a fixed language of the project, or an attribute of the headword element mapped to the project's languages.

This module knows no web framework and no particular project: the languages of the project are passed in.
"""
import re
import unicodedata
from collections import OrderedDict

from lxml import etree

EXAMPLES_TITLE = 'Examples from pre-existent dictionary'           # the text the examples of an imported dictionary go to (like "Examples from papers")
MAX_BYTES = 60 * 1024 * 1024
MAX_ENTRIES = 300000
SAMPLE_ENTRIES = 3000                        # entries looked at to list the paths (the counts are those of the sample)

_PARSER_ARGS = dict(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False, remove_comments=True, remove_pis=True)


# ── reading the file ─────────────────────────────────────────────────────────────────────────────
def parse(data):
    """(root, namespaces_were_stripped) for the bytes of an XML file. Entities are not expanded and nothing is fetched. Raises ValueError."""
    if len(data) > MAX_BYTES:
        raise ValueError('The file is too large (more than %d MB).' % (MAX_BYTES // 1024 // 1024))
    try:
        root = etree.fromstring(data, etree.XMLParser(**_PARSER_ARGS))
    except etree.XMLSyntaxError as e:
        raise ValueError('Invalid XML: %s' % e)
    return root, strip_namespaces(root)


def strip_namespaces(root):
    """Plain tag and attribute names (TEI's xmlns, xml:lang becomes lang), so that the wizard shows names as the author knows them."""
    had = False
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]; had = True
        if any('}' in k for k in el.attrib):
            items = [(k.split('}', 1)[1] if '}' in k else k, v) for k, v in el.attrib.items()]
            el.attrib.clear()
            for k, v in items:
                el.set(k, v)
    return had


def is_native(root):
    """True if the file is already in the DBT's own format (LEXICA XML), which needs no wizard."""
    return root.tag == 'RessourceLexicale' and root.find('.//EntréeLexicale') is not None


def _elements(root):
    return (e for e in root.iter() if isinstance(e.tag, str))


# ── the inventory the wizard shows ───────────────────────────────────────────────────────────────
_ENTRY_NAME = re.compile(r'entry|entr[eé]e|lexical|record|article|lemma|^lx$|item|word|head|vedette|lemme', re.I)


def entry_candidates(root):
    """[{'tag', 'count', 'children', 'likely'}]: the tags that could be the entry, the likeliest first (many occurrences, children, a name that says it)."""
    counts, withchild = OrderedDict(), {}
    for e in _elements(root):
        counts[e.tag] = counts.get(e.tag, 0) + 1
        if len(e):
            withchild[e.tag] = withchild.get(e.tag, 0) + 1
    out = []
    for tag, n in counts.items():
        if tag == root.tag:
            continue
        score = (3 if _ENTRY_NAME.search(tag) else 0) + (2 if withchild.get(tag, 0) > n * 0.8 else 0) + (1 if n > 1 else 0) + min(n, 1000) / 1000.0
        out.append({'tag': tag, 'count': n, 'children': withchild.get(tag, 0), 'score': score})
    out.sort(key=lambda d: -d['score'])
    for i, d in enumerate(out):
        d['likely'] = i == 0 and d['count'] > 1 and d['score'] >= 3
        d.pop('score')
    return out


def entries(root, entry_tag):
    return [e for e in root.iter(entry_tag) if isinstance(e.tag, str)]


def describe_paths(root, entry_tag, limit=SAMPLE_ENTRIES, max_paths=400):
    """The structure of an entry as the wizard lists it: every distinct path below the entry, in document order, with how many times it occurs,
    a sample of its text, and its attributes with sample values. [{'path': './sense/gloss', 'count', 'depth', 'sample', 'attrs': {'lang': ['en', 'fr']}}]"""
    info = OrderedDict()
    n = 0
    def walk(el, prefix):
        for ch in el:
            if not isinstance(ch.tag, str):
                continue
            path = prefix + '/' + ch.tag
            d = info.get(path)
            if d is None:
                if len(info) >= max_paths:
                    continue
                d = info[path] = {'path': path, 'count': 0, 'depth': path.count('/'), 'sample': '', 'attrs': OrderedDict()}
            d['count'] += 1
            if not d['sample']:
                t = (ch.text or '').strip()
                if t:
                    d['sample'] = t[:60]
            for k, v in ch.attrib.items():
                vs = d['attrs'].setdefault(k, [])
                if v and v not in vs and len(vs) < 8:
                    vs.append(v)
            walk(ch, path)
    for entry in entries(root, entry_tag):
        n += 1
        if n > limit:
            break
        walk(entry, '.')
    out = list(info.values())
    for d in out:
        d['attrs'] = dict(d['attrs'])
    return out, min(n, limit)


def entry_attrs(root, entry_tag, limit=300):
    """The attributes of the entry elements themselves, with sample values: {'id': ['maison_1', …], 'guid': [...]} (where a relation's target identifier is found)."""
    out = {}
    for e in entries(root, entry_tag)[:limit]:
        for k, v in e.attrib.items():
            vs = out.setdefault(k, [])
            if v and v not in vs and len(vs) < 4:
                vs.append(v)
    return out


def sample_xml(root, entry_tag, n=2, maxlen=2500):
    return [etree.tostring(e, encoding='unicode', pretty_print=True)[:maxlen] for e in entries(root, entry_tag)[:n]]


# ── reading a field ──────────────────────────────────────────────────────────────────────────────
def rel_xpath(path):
    """A path as ElementTree can use it from an element: a bare tag is looked for anywhere below, a path starts at the element. None if empty."""
    path = (path or '').strip()
    if not path:
        return None
    if path.startswith('/') or path.startswith('..') or '|' in path:
        raise ValueError('Not a path below the entry: %s' % path)
    if '/' in path:
        return path if path.startswith('.') else './' + path
    return './/' + path


def _flat_text(el):
    return re.sub(r'\s+', ' ', ''.join(el.itertext())).strip()


def field_elements(elem, field):
    """The elements a field selects below `elem` (the element itself if the field has no path), after the attribute filter."""
    if not field:
        return []
    xp = rel_xpath(field.get('path'))
    found = [elem] if xp is None else elem.findall(xp)
    fa, fv = field.get('filterAttr'), field.get('filterValue')
    if fa:
        found = [e for e in found if e.get(fa) == fv]
    return [e for e in found if isinstance(e.tag, str)]


def element_value(el, value):
    """What is read from a selected element: its text, an attribute (@attr), or the text of a descendant (a path)."""
    value = (value or '').strip()
    if not value:
        return _flat_text(el)
    if value.startswith('@'):
        return (el.get(value[1:]) or '').strip()
    xp = rel_xpath(value)
    sub = el.find(xp) if xp else None
    return _flat_text(sub) if sub is not None else ''


def field_values(elem, field):
    """All the (non-empty) values of a field below `elem`, in document order."""
    out = []
    for el in field_elements(elem, field):
        v = element_value(el, field.get('value'))
        if v:
            out.append(v)
    return out


def first_value(elem, field):
    v = field_values(elem, field)
    return v[0] if v else ''


def unique_values(root, entry_tag, field, limit=300):
    """[(value, count)] of a field over all the entries, the commonest first: the values the POS or the language mapping asks about."""
    counts = {}
    for entry in entries(root, entry_tag):
        for v in field_values(entry, field):
            counts[v] = counts.get(v, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]


# ── suggestions for the schemas everybody uses ───────────────────────────────────────────────────
def suggest(root, entry_tag, paths):
    """A first mapping for LIFT (FLEx, WeSay, Lexique Pro) and TEI dictionaries, so that the wizard starts filled in; None for other schemas.
    Only what exists in the file is suggested."""
    have = {p['path'] for p in paths}
    def pick(*options):
        return next((o for o in options if o in have), None)
    cfg = {}
    if root.tag == 'lift' and entry_tag == 'entry':
        lem = pick('./lexical-unit/form')
        if lem: cfg['lemma'] = {'path': lem, 'value': './text'}; cfg['langAttr'] = 'lang'
        if pick('./pronunciation/form'): cfg['ipa'] = {'path': './pronunciation/form', 'value': './text'}
        if pick('./sense/grammatical-info'): cfg['pos'] = {'path': './sense/grammatical-info', 'value': '@value'}
        if pick('./sense'): cfg['sense'] = {'path': './sense'}
        if pick('./sense/gloss'): cfg['gloss'] = {'path': './gloss', 'value': './text'}
        if pick('./sense/definition/form'): cfg['definition'] = {'path': './definition/form', 'value': './text'}
        if pick('./sense/note/form'): cfg['notes'] = {'path': './note/form', 'value': './text'}
        if pick('./etymology'): cfg['etymology'] = {'path': './etymology', 'form': {'path': './form', 'value': './text'}, 'lang': {'path': '', 'value': '@source'}}
        if pick('./sense/example'): cfg['examples'] = {'path': './sense/example', 'text': {'path': './form', 'value': './text'}, 'translation': {'path': './translation/form', 'value': './text'}}
        rel = pick('./sense/relation', './relation')
        if rel: cfg['relations'] = {'path': rel, 'type': {'path': '', 'value': '@type'}, 'typeMap': {}, 'target': {'path': '', 'value': '@ref'}, 'by': 'id', 'entryKey': '@guid', 'senseKey': '@id'}
    elif root.tag in ('TEI', 'tei') or (root.find('.//body') is not None and entry_tag == 'entry' and pick('./form/orth')):
        lem = pick('./form/orth', './form[@type="lemma"]/orth')
        if lem: cfg['lemma'] = {'path': lem, 'value': ''}
        if pick('./form/pron'): cfg['ipa'] = {'path': './form/pron', 'value': ''}
        pos = pick('./gramGrp/pos', './sense/gramGrp/pos')
        if pos: cfg['pos'] = {'path': pos, 'value': ''}
        if pick('./sense'): cfg['sense'] = {'path': './sense'}
        if pick('./sense/def'): cfg['definition'] = {'path': './def', 'value': ''}
        if pick('./etym'): cfg['etymology'] = {'path': './etym', 'form': {'path': './/mentioned', 'value': ''}, 'lang': {'path': './/lang', 'value': ''}}
        xr = pick('./sense/xr', './xr')
        if xr: cfg['relations'] = {'path': xr, 'type': {'path': '', 'value': '@type'}, 'typeMap': {}, 'target': {'path': './/ref', 'value': ''}, 'by': 'headword'}
    return cfg or None


# ── checking that a mapping is populated across the dictionary (LExport's coverage report) ───────
def coverage(root, entry_tag, specs, lemma_field=None):
    """[{'label', 'total', 'present', 'missing', 'missingPct', 'sample'}] for fields given as (label, field, required)."""
    ents = entries(root, entry_tag)
    out = []
    for label, field, required in specs:
        present, sample = 0, []
        for e in ents:
            if first_value(e, field):
                present += 1
            elif lemma_field and len(sample) < 5:
                v = first_value(e, lemma_field)
                if v:
                    sample.append(v)
        out.append({'label': label, 'total': len(ents), 'present': present, 'missing': len(ents) - present,
                    'missingPct': round(100.0 * (len(ents) - present) / len(ents), 1) if ents else 0.0, 'sample': sample, 'required': required})
    return out


def output_coverage(els, cfg):
    """LExport's coverage report, counted on the converted entries (what the dictionary will hold): for each field the author mapped, how many
    entries lack it, with examples. [{'label', 'total', 'present', 'missing', 'missingPct', 'sample'}]"""
    rows = [('A definition or a gloss', lambda e: e.find('Sens') is not None, True)]
    if cfg.get('pos'): rows.append(('Part of speech', lambda e: bool(e.findtext('ClasseGrammaticale')), True))
    if cfg.get('domain'): rows.append(('Semantic domain', lambda e: bool(e.findtext('DomaineSémantique')), False))
    if cfg.get('ipa'): rows.append(('IPA', lambda e: e.find('Lemme/FormePhonétique') is not None, False))
    if (cfg.get('etymology') or {}).get('path'): rows.append(('Etymology', lambda e: e.find('Étymologie') is not None, False))
    out = []
    for label, has, required in rows:
        miss = [e for e in els if not has(e)]
        out.append({'label': label, 'total': len(els), 'present': len(els) - len(miss), 'missing': len(miss), 'required': required,
                    'missingPct': round(100.0 * len(miss) / len(els), 1) if els else 0.0,
                    'sample': [e.findtext('Lemme/ReprésentationDeForme') or e.get('identifiant') for e in miss[:5]]})
    return out


# ── the mapping and the conversion ───────────────────────────────────────────────────────────────
def validate_config(root, cfg, project_codes):
    """The problems of a mapping, as texts for the author ([] if it can be used)."""
    errs = []
    if not isinstance(cfg, dict):
        return ['No mapping given.']
    tag = cfg.get('entryTag')
    if not isinstance(tag, str) or not tag or not entries(root, tag):
        return ['Choose the node that wraps each entry.']
    def check_field(name, f, required=False):
        if not f or (not (f.get('path') or '').strip() and not (f.get('value') or '').strip()):      # an element itself read through an attribute (@type) is a field
            if required:
                errs.append('%s: choose the node.' % name)
            return
        if not isinstance(f.get('path'), str) or len(f['path']) > 300 or len(str(f.get('value') or '')) > 300:
            errs.append('%s: the path is not valid.' % name); return
        try:
            for e in entries(root, tag)[:1]:
                field_elements(e, f); element_value(e, f.get('value'))
        except (ValueError, SyntaxError, KeyError) as ex:
            errs.append('%s: the path is not valid (%s).' % (name, ex))
    check_field('Headword', cfg.get('lemma'), True)
    for name, key in (('IPA', 'ipa'), ('Part of speech', 'pos'), ('Semantic domain', 'domain'), ('Homonym number', 'homonym')):
        check_field(name, cfg.get(key))
    lang = cfg.get('language') or {}
    if lang.get('mode') == 'attr':
        if not lang.get('attr'):
            errs.append('Languages: say which attribute of the headword gives the language.')
        mapped = [v for v in (lang.get('map') or {}).values() if v]
        if not mapped:
            errs.append('Languages: map at least one value of the attribute to a language of the project.')
        errs += ['Languages: %s is not a language of the project.' % v for v in mapped if v not in project_codes]
    else:
        if lang.get('code') not in project_codes:
            errs.append('Languages: choose the language of the headwords.')
    sense = cfg.get('sense') or {}
    if sense.get('path'):
        check_field('Senses', sense)
    ex = cfg.get('examples')
    if ex and (ex.get('path') or '').strip():
        check_field('Examples', ex)
        check_field('Examples: text', ex.get('text'), True)
        check_field('Examples: translation', ex.get('translation'))
    rl = cfg.get('relations')
    if rl and (rl.get('path') or '').strip():
        check_field('Relations', rl)
        check_field('Relations: type', rl.get('type'), True)
        check_field('Relations: target', rl.get('target'), True)
        if rl.get('by') not in ('id', 'headword'):
            errs.append('Relations: say how a relation points to its target (by identifier, or by headword).')
        elif rl.get('by') == 'id' and not (rl.get('entryKey') or rl.get('senseKey')):
            errs.append('Relations: say which attribute holds the identifier of an entry or of a sense.')
        errs += ['Relations: %s is not synonym or antonym.' % v for v in (rl.get('typeMap') or {}).values() if v not in ('synonym', 'antonym', '')]
    for name, key in (('Definition', 'definition'), ('Short gloss', 'gloss'), ('Notes', 'notes')):
        f = cfg.get(key)
        if f and (f.get('path') or '').strip():
            try:
                rel_xpath(f['path']); element_value(entries(root, tag)[0], f.get('value'))
            except (ValueError, SyntaxError) as ex:
                errs.append('%s: the path is not valid (%s).' % (name, ex))
    return errs


_IPA_SUFFIX = re.compile(r'-(fon[a-z]+|x-.*)$', re.I)


_REL_ALIASES = {'synonym': 'synonym', 'synonyme': 'synonym', 'synonymie': 'synonym', 'synonymy': 'synonym', 'synonyms': 'synonym', 'syn': 'synonym',
                'antonym': 'antonym', 'antonyme': 'antonym', 'antonymie': 'antonym', 'antonymy': 'antonym', 'antonyms': 'antonym', 'ant': 'antonym'}


def rel_type(text):
    """'synonym' or 'antonym' for what a dictionary may call them (Synonyms, syn, antonymie …); None for any other relation."""
    return _REL_ALIASES.get(re.sub(r'[\s.]+', '', (text or '').strip().lower()))


def examples_filename(code):
    """The text file of the examples in one language of the project (a text has one language)."""
    return 'Examples_from_pre-existent_dictionary_%s.xml' % re.sub(r'[^A-Za-z0-9_-]', '_', code)


def build_examples_text(code, items, title, text_lang='en'):
    """The XML of a text (the format of every text of the Texts page) made of dictionary examples: [{'id', 'form', 'transl'}]."""
    root = etree.Element('TEXT', id='examples-from-pre-existent-dictionary-' + code)
    root.set('{http://www.w3.org/XML/1998/namespace}lang', code)
    head = etree.SubElement(root, 'HEADER')
    t = etree.SubElement(head, 'TITLE'); t.text = title; t.set('{http://www.w3.org/XML/1998/namespace}lang', 'en')
    for it in items:
        s = etree.SubElement(root, 'S', id=it['id'])
        etree.SubElement(s, 'FORM').text = it['form']
        if it.get('transl'):
            tr = etree.SubElement(s, 'TRANSL'); tr.text = it['transl']; tr.set('{http://www.w3.org/XML/1998/namespace}lang', text_lang)
    return root


def _norm(s):
    return unicodedata.normalize('NFC', str(s or '')).strip().lower()


def slug_id(s):
    """ASCII identifier from a form: diacritics dropped, anything else becomes _."""
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-zA-Z0-9]+', '_', s).strip('_').lower()[:20]


def _sub(parent, tag, text=None, **attrs):
    el = etree.SubElement(parent, tag, **attrs)
    if text is not None:
        el.text = text
    return el


def _mapped(value, mapping):
    return (mapping or {}).get(value, value) if value else ''


def convert(root, cfg, project_codes, existing_ids=None, limit=None, example_start=None):
    """The entries of the dictionary as native <EntréeLexicale> elements. Returns (elements, report).
    report: {'total', 'imported', 'senses', 'skipped': [{'reason', 'sample'}], 'warnings': [texts]}"""
    tag = cfg['entryTag']
    lemma, ipa = cfg['lemma'], cfg.get('ipa')
    lang = cfg.get('language') or {}
    langAttr = lang.get('attr') if lang.get('mode') == 'attr' else None
    langmap = lang.get('map') or {}
    fixed = lang.get('code') if lang.get('mode') != 'attr' else None
    ids = set(existing_ids or ())
    skipped, warnings, out = {}, [], []
    ex_cfg = cfg.get('examples') if (cfg.get('examples') or {}).get('path') else None
    rl_cfg = cfg.get('relations') if (cfg.get('relations') or {}).get('path') else None
    texts, ex_ids, cites, pending, by_entry_key, by_sense_key, by_headword, label_of = {}, {}, {}, [], {}, {}, {}, {}
    ex_start = example_start or {}
    ex_stats = {'unresolved': 0, 'ignored': 0, 'imported': 0}
    stats = {'multiple': 0, 'nosense': 0, 'senses': 0}
    ents = entries(root, tag)
    total = len(ents)
    if total > MAX_ENTRIES:
        raise ValueError('Too many entries (%d).' % total)
    for entry in (ents if limit is None else ents[:limit]):
        forms = {}
        for el in field_elements(entry, lemma):
            code = fixed if fixed else langmap.get(el.get(langAttr) or '')
            v = element_value(el, lemma.get('value'))
            if code in project_codes and v:
                if code in forms:
                    stats['multiple'] += 1
                else:
                    forms[code] = v
        if not forms:
            why = 'no headword in a language of the project'
            skipped.setdefault(why, []).append(first_value(entry, dict(lemma, filterAttr=None)) or '(empty)')
            continue
        first = next(iter(forms.values()))
        base = slug_id(first) or 'entry'
        if cfg.get('idAttr'):                                  # keep the identifiers of the source: an attribute of the entry (@id)
            base = slug_id(first_value(entry, {'path': '', 'value': cfg['idAttr']})) or base
        eid, n = base, 2
        while eid in ids:
            eid = '%s_%d' % (base, n); n += 1
        ids.add(eid)
        el = etree.Element('EntréeLexicale', identifiant=eid)
        lem = _sub(el, 'Lemme')
        for code in project_codes:
            if code in forms:
                _sub(lem, 'ReprésentationDeForme', forms[code], langue=code)
        if ipa:
            for iel in field_elements(entry, ipa):
                raw = iel.get(langAttr) or '' if langAttr else ''
                # the language of an IPA form: LIFT says nme-fonipa for nme; TEI says nothing (then it is the language of the entry, if it has only one)
                code = fixed if fixed else (langmap.get(raw) or langmap.get(_IPA_SUFFIX.sub('', raw)) or (next(iter(forms)) if not raw and len(forms) == 1 else None))
                v = element_value(iel, ipa.get('value'))
                if code in forms and v and lem.find('FormePhonétique[@langue="%s"]' % code) is None:
                    _sub(lem, 'FormePhonétique', v, langue=code)
        if cfg.get('homonym'):
            h = first_value(entry, cfg['homonym'])
            if h.isdigit():
                _sub(el, 'NuméroDHomonyme', h)
        if cfg.get('pos'):
            p = first_value(entry, cfg['pos'])
            if p:
                _sub(el, 'ClasseGrammaticale', _mapped(p, (cfg.get('posMap') or {})))
        if cfg.get('domain'):
            d = first_value(entry, cfg['domain'])
            if d:
                _sub(el, 'DomaineSémantique', _mapped(d, (cfg.get('domainMap') or {})))
        ety = cfg.get('etymology')
        if ety and (ety.get('path') or '').strip():
            ewrap = None
            for eel in field_elements(entry, ety):
                form = first_value(eel, ety.get('form') or {})
                if not form:
                    continue
                if ewrap is None:
                    ewrap = _sub(el, 'Étymologie')
                node = _sub(ewrap, 'Étymon')
                lg = first_value(eel, ety.get('lang')) if ety.get('lang') else ''       # a node below the etymon, or '' + @attr for an attribute of the wrapper
                if lg:
                    _sub(node, 'Langue', lg)
                _sub(node, 'Forme', form)
                g = first_value(eel, ety.get('gloss') or {}) if ety.get('gloss') else ''
                if g:
                    _sub(node, 'Glose', g)
        # ── senses ──
        sense_cfg = cfg.get('sense') or {}
        sense_els = field_elements(entry, sense_cfg) if (sense_cfg.get('path') or '').strip() else [entry]
        subs = (cfg.get('subsense') or {}) if (sense_cfg.get('path') or '').strip() else {}
        flat = []
        for s in sense_els:
            flat.append(s)
            if (subs.get('path') or '').strip():
                flat += field_elements(s, subs)
        k = 0
        sense_out = {}
        for s in flat:
            definition = first_value(s, cfg.get('definition')) if cfg.get('definition') else ''
            short = first_value(s, cfg.get('gloss')) if cfg.get('gloss') else ''
            notes = first_value(s, cfg.get('notes')) if cfg.get('notes') else ''
            if not (definition or short):
                continue
            k += 1
            sn = _sub(el, 'Sens', identifiant='%sⓢ%d' % (eid, k))
            _sub(sn, 'NuméroDeSens', str(k))
            _sub(sn, 'Glose', definition or short, langue='eng')
            _sub(sn, 'gloss', short or definition)
            if notes:
                _sub(_sub(sn, 'Notes'), 'ReprésentationDeTexte', notes, langue='eng')
            sense_out[s] = sn
        stats['senses'] += k
        if not k:
            stats['nosense'] += 1
        out.append(el)
        senses_out = el.findall('Sens')
        first_sens = senses_out[0] if senses_out else None
        label_of[eid] = next(iter(forms.values()))

        def owner_of(node):                               # the converted sense a node of the source belongs to (the first one if it belongs to none)
            p = node
            while p is not None and p is not entry:
                if p in sense_out:
                    return sense_out[p]
                p = p.getparent()
            return first_sens
        if rl_cfg:
            if rl_cfg.get('entryKey') and first_sens is not None:
                key = first_value(entry, {'path': '', 'value': rl_cfg['entryKey']})
                if key: by_entry_key[key] = first_sens.get('identifiant')
            if rl_cfg.get('senseKey'):
                for s_src, sn_out in sense_out.items():
                    key = first_value(s_src, {'path': '', 'value': rl_cfg['senseKey']})
                    if key: by_sense_key[key] = sn_out.get('identifiant')
            if first_sens is not None:
                for v in forms.values():
                    by_headword.setdefault(_norm(v), first_sens.get('identifiant'))
            for rel_el in field_elements(entry, rl_cfg):
                own = owner_of(rel_el)
                tv, tg = first_value(rel_el, rl_cfg.get('type')), first_value(rel_el, rl_cfg.get('target'))
                if own is not None and tg:
                    pending.append((own, tv, tg))
        if ex_cfg:
            for xel in field_elements(entry, ex_cfg):
                own = owner_of(xel)
                if own is None:
                    continue
                tf, trf = ex_cfg.get('text'), ex_cfg.get('translation')
                for tel in field_elements(xel, tf):
                    code = fixed if fixed else langmap.get(tel.get(langAttr) or '')
                    form = element_value(tel, tf.get('value'))
                    if code not in project_codes or not form:
                        continue
                    transl = first_value(xel, trf) if trf else ''
                    k2 = (code, form, transl)
                    if k2 not in ex_ids:
                        n = ex_start.get(code, 0) + len(texts.get(code, [])) + 1
                        ex_ids[k2] = 'ex%d' % n
                        texts.setdefault(code, []).append({'id': ex_ids[k2], 'form': form, 'transl': transl})
                    cite = '{{cite: %s#%s}}' % (examples_filename(code), ex_ids[k2])
                    if cite not in cites.setdefault(own, []):
                        cites[own].append(cite)
    for own, keys in cites.items():                      # the examples of each sense, as the dictionary keeps them: one {{cite: …}} per line
        _sub(own, 'Exemples', '\n'.join(keys))
    if rl_cfg:
        tmap = rl_cfg.get('typeMap') or {}
        seen = set()
        for own, tv, tg in pending:
            kind = tmap[tv] if tv in tmap else rel_type(tv)
            if not kind:
                ex_stats['ignored'] += 1; continue
            target = (by_sense_key.get(tg) or by_entry_key.get(tg)) if rl_cfg.get('by') == 'id' else by_headword.get(_norm(tg))
            if not target or target == own.get('identifiant'):
                ex_stats['unresolved'] += 1; continue
            if (own.get('identifiant'), kind, target) in seen:
                continue
            seen.add((own.get('identifiant'), kind, target))
            tgt_entry = target.split('\u24e2')[0]
            r = _sub(own, 'RelationSémantique')
            _sub(r, 'Type', kind)
            _sub(r, 'Cible', label_of.get(tgt_entry, tgt_entry), cible=target)
            ex_stats['imported'] += 1
    rep = {'total': total, 'imported': len(out), 'senses': stats['senses'],
           'skipped': [{'reason': r, 'count': len(v), 'sample': v[:5]} for r, v in skipped.items()], 'warnings': warnings}
    if stats['multiple']:
        warnings.append('%d headword(s) had several forms for the same language: the first one is kept.' % stats['multiple'])
    if rl_cfg:
        rep['relations'] = dict(ex_stats)
        if ex_stats['unresolved']:
            warnings.append('%d relation(s) point to an entry or sense that is not among the imported ones: skipped.' % ex_stats['unresolved'])
        if ex_stats['ignored']:
            warnings.append('%d relation(s) of another type than synonym or antonym were not imported.' % ex_stats['ignored'])
    if ex_cfg:
        rep['examples'] = {c: len(v) for c, v in texts.items()}
        rep['_texts'] = texts                            # the sentences, for the server to write as texts (not part of the report it sends)
    if stats['nosense']:
        warnings.append('%d entr%s no sense with a definition or a gloss.' % (stats['nosense'], 'y has' if stats['nosense'] == 1 else 'ies have'))
    return out, rep
