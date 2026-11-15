"""
Splitting a parallel sentence of the fieldnotes (questionnaire) into several, one per group of languages.

A sentence of the questionnaire is one <rfGroup> (its id in <rf>) holding the prompt and one element per language. The author may split it, for
example d01.Road:10 into d01.Road:10a (Nume, Dorig) and d01.Road:10b (Koro, Olrat, Lakon): each part is then a sentence of its own, with its own
alignment and glosses. This module knows no web framework: it changes the XML tree and the stored glosses it is given.
"""
import copy

PROMPT_TAGS = ('bsl', 'fr')                                # the stimulus sentence: kept in every part
GROUP_TAGS = ('bslGroup', 'frGroup')
LETTERS = 'abcdefghijklmnopqrstuvwxyz'


class SplitError(ValueError):
    pass


def _is_empty(v):
    return v is None or str(v).strip() in ('', '—')


def find_sentence(tiGroup, sid):
    for rfg in tiGroup.findall('rfGroup'):
        if (rfg.findtext('rf') or '').strip() == sid:
            return rfg
    return None


def present_codes(rfg, codes):
    """The languages that have a form in this sentence (a sentence already split holds only some of them)."""
    grp = next((g for g in (rfg.find(t) for t in GROUP_TAGS) if g is not None), None)
    return [c for c in codes if grp is not None and (grp.findtext(c) or '').strip()]


def check_parts(parts, codes):
    """The groups must share the sentence's languages out: every language in exactly one group, no group empty, at least two groups."""
    if not isinstance(parts, list) or len(parts) < 2:
        raise SplitError('Choose at least two groups.')
    if len(parts) > len(LETTERS):
        raise SplitError('Too many groups.')
    seen = []
    for p in parts:
        if not isinstance(p, list) or not p:
            raise SplitError('Each group needs at least one language.')
        seen += p
    if sorted(seen) != sorted(codes):
        raise SplitError('Each language must be in exactly one group.')


def new_ids(sid, n, taken):
    ids = [sid + LETTERS[i] for i in range(n)]
    clash = [i for i in ids if i in taken]
    if clash:
        raise SplitError('Already used: ' + ', '.join(clash))
    return ids


def split_sentence(root, tiGroup, sid, parts, codes):
    """Replace the sentence `sid` of the tiGroup by one sentence per group. Returns the new ids (in the order of the groups)."""
    rfg = find_sentence(tiGroup, sid)
    if rfg is None:
        raise SplitError('Sentence not found.')
    codes = present_codes(rfg, codes)                      # a language with no form goes with the first group
    check_parts(parts, codes)
    taken = {(r.text or '').strip() for r in root.iter('rf')}
    ids = new_ids(sid, len(parts), taken)
    parent = tiGroup
    at = list(parent).index(rfg)
    first_tail = rfg.tail
    parent.remove(rfg)
    for k, (part, nid) in enumerate(zip(parts, ids)):
        c = copy.deepcopy(rfg)
        c.find('rf').text = nid
        c.set('part', '1')                                  # a part shows only the languages it holds
        grp = next((g for g in (c.find(t) for t in GROUP_TAGS) if g is not None), None)
        if grp is not None:
            for el in list(grp):
                if el.tag in PROMPT_TAGS:
                    continue
                mine = (el.tag in part) if el.tag in codes else (k == 0)      # a language outside the project, or with no form, stays with the first group
                if not mine:
                    tail = el.tail
                    prev = el.getprevious()
                    grp.remove(el)
                    if prev is not None:
                        prev.tail = tail if prev.tail is None or not prev.tail.strip() else prev.tail
                    else:
                        grp.text = tail
        c.tail = first_tail
        parent.insert(at + k, c)
    return ids


def split_gloss(gloss, part, codes, first):                # codes: the languages that were split (present_codes)
    """The stored gloss of the old sentence, cut for one group: only its languages, and only the columns where one of them has a word."""
    if not isinstance(gloss, dict):
        return copy.deepcopy(gloss)
    g = copy.deepcopy(gloss)
    toks = g.get('tokens')
    if isinstance(toks, dict):
        toks = {c: v for c, v in toks.items() if (c in part) or (c not in codes and first)}
        n = max([len(v) for v in toks.values()] + [len(g.get('glosses') or [])] + [0])
        keep = [i for i in range(n) if any(i < len(v) and not _is_empty(v[i]) for v in toks.values())]
        if keep:
            toks = {c: [v[i] if i < len(v) else '' for i in keep] for c, v in toks.items()}
            if isinstance(g.get('glosses'), list):
                g['glosses'] = [g['glosses'][i] if i < len(g['glosses']) else '' for i in keep]
        g['tokens'] = toks
        g['confirmed'] = False
    return g
