"""
Direct tests of xmlimport.py (no server): reading any XML dictionary, the inventory the wizard shows, the fields (paths, attributes, filters),
the suggestions for LIFT and TEI, the coverage report, the validation of a mapping, the conversion into the DBT's format, and files that attack the reader.
Run alone with:  python tests/test_xmlimport.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lxml import etree
import xmlimport as X

ok = bad = 0
def check(name, got, want):
    global ok, bad
    if got == want: ok += 1
    else:
        bad += 1; print(f"✗ {name}\n    got : {got!r}\n    want: {want!r}")

CODES = ['num', 'drg', 'kro']
LIFT = '''<?xml version="1.0" encoding="UTF-8"?>
<lift version="0.13">
 <entry id="mōrōs_1" guid="a1">
  <lexical-unit><form lang="nme"><text>mōrōs</text></form><form lang="drg"><text>morus</text></form></lexical-unit>
  <pronunciation><form lang="nme-fonipa"><text>moːɾos</text></form></pronunciation>
  <sense id="s1"><grammatical-info value="Noun"/>
    <gloss lang="en"><text>house</text></gloss><gloss lang="fr"><text>maison</text></gloss>
    <definition><form lang="en"><text>a building where people live</text></form></definition>
    <note><form lang="en"><text>very common</text></form></note>
    <subsense id="s1a"><gloss lang="en"><text>hut</text></gloss></subsense>
  </sense>
  <sense id="s2"><grammatical-info value="Noun"/><gloss lang="en"><text>family</text></gloss></sense>
  <etymology type="proto" source="POc"><form lang="x"><text>*rumaq</text></form><gloss lang="en"><text>house</text></gloss></etymology>
 </entry>
 <entry id="nir_2" guid="a2">
  <lexical-unit><form lang="nme"><text>nir</text></form></lexical-unit>
  <sense id="s3"><grammatical-info value="Pronoun"/><gloss lang="en"><text>3PL</text></gloss></sense>
 </entry>
 <entry id="x_3" guid="a3"><lexical-unit><form lang="zzz"><text>other language</text></form></lexical-unit><sense><gloss lang="en"><text>skipped</text></gloss></sense></entry>
 <entry id="mōrōs_4" guid="a4"><lexical-unit><form lang="nme"><text>mōrōs</text></form></lexical-unit><sense><gloss lang="en"><text>to lie down</text></gloss></sense></entry>
</lift>'''
TEI = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body>
 <entry xml:id="e1"><form type="lemma"><orth xml:lang="nme">nir</orth><pron>nir</pron></form><gramGrp><pos>pro.</pos></gramGrp><sense><def>3PL</def></sense></entry>
 <entry xml:id="e2"><form type="lemma"><orth xml:lang="nme">ron̄</orth></form><gramGrp><pos>n.</pos></gramGrp><sense><def>voice</def></sense></entry>
</body></text></TEI>'''
FLAT = '<dict><rec><lx>nir</lx><ps>pro</ps><ge>3PL</ge><nt>a note</nt></rec><rec><lx>ron</lx><ps>n</ps><ge>voice</ge></rec><rec><ps>n</ps><ge>no headword</ge></rec></dict>'

# ── reading the file ──
root, ns = X.parse(LIFT.encode('utf-8'))
check('a LIFT file is read, it has no namespace to strip, and it is not in the DBT format', (root.tag, ns, X.is_native(root)), ('lift', False, False))
troot, tns = X.parse(TEI.encode('utf-8'))
check('a TEI file: the namespace is stripped (the wizard shows plain tag names), xml:lang becomes lang', (tns, troot.find('.//entry') is not None, troot.find('.//orth').get('lang')), (True, True, 'nme'))
native, _ = X.parse(Path(__file__).resolve().parents[1].joinpath('project', 'dictionary.xml').read_bytes())
check('the DBT’s own dictionary is recognised as native (no wizard needed)', X.is_native(native), True)
def err(data):
    try: X.parse(data); return None
    except ValueError as e: return str(e)[:40]
check('what is not XML is refused with a message', (err(b'not xml at all').startswith('Invalid XML:'), err(b'').startswith('Invalid XML:')), (True, True))
xxe = b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]><d><entry>&x;</entry></d>'
r_, _ = X.parse(xxe)
check('an external entity is not read (no file of the server is included), nothing is fetched', 'root:' in etree.tostring(r_, encoding='unicode'), False)
bomb = b'<?xml version="1.0"?><!DOCTYPE b [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]><b><e>&c;</e></b>'
rb, _ = X.parse(bomb)
check('an entity bomb is not expanded', len(etree.tostring(rb, encoding='unicode')) < 500, True)
check('a file that is too large is refused', X.MAX_BYTES > 1000 and 'too large' in (err(b'<a>' + b'x' * (X.MAX_BYTES + 1) + b'</a>') or ''), True)

# ── the inventory ──
cands = X.entry_candidates(root)
check('the likeliest entry node comes first and is flagged, with its count', (cands[0]['tag'], cands[0]['count'], cands[0]['likely']), ('entry', 4, True))
paths, sampled = X.describe_paths(root, 'entry')
byp = {p['path']: p for p in paths}
check('every path below the entry is listed in document order with its count, a sample of its text and its attributes', (paths[0]['path'], byp['./sense']['count'], byp['./sense/gloss']['attrs']['lang'], byp['./lexical-unit/form/text']['sample'], byp['./sense/grammatical-info']['attrs']['value']), ('./lexical-unit', 5, ['en', 'fr'], 'mōrōs', ['Noun', 'Pronoun']))
check('the entries seen are counted (the counts are those of the sample)', sampled, 4)
check('a tag used at two positions gives two paths (the wizard asks which one)', sorted(p for p in byp if p.endswith('/gloss')), ['./etymology/gloss', './sense/gloss', './sense/subsense/gloss'])
check('the first entries are shown as XML', 'lexical-unit' in X.sample_xml(root, 'entry', 1)[0], True)

# ── fields ──
e1 = X.entries(root, 'entry')[0]
check('a field: the text of a descendant (LIFT: form/text), an attribute (@value), the filtered ones (English glosses)', (X.field_values(e1, {'path': './sense/gloss', 'value': 'text', 'filterAttr': 'lang', 'filterValue': 'en'}), X.field_values(e1, {'path': './sense/grammatical-info', 'value': '@value'}), X.field_values(e1, {'path': './sense/gloss', 'value': 'text', 'filterAttr': 'lang', 'filterValue': 'fr'})), (['house', 'family'], ['Noun', 'Noun'], ['maison']))
check('a bare tag is looked for anywhere below the entry; a path from the entry; no path means the element itself', (X.field_values(e1, {'path': 'note', 'value': 'text'}), X.field_values(e1, {'path': './etymology', 'value': '@source'}), X.field_values(e1, {'path': '', 'value': '@guid'})), (['very common'], ['POc'], ['a1']))
check('a path that leaves the entry, or is not a path, is refused', ([X.rel_xpath(p) for p in ('sense', './a/b', 'a/b')], [type(_e).__name__ for _e in [_try for _try in []]]), (['.//sense', './a/b', './a/b'], []))
def refused(p):
    try: X.rel_xpath(p); return False
    except ValueError: return True
check('…//etc, parent paths and unions are refused', [refused(p) for p in ('/etc/passwd', '../x', 'a|b')], [True, True, True])
check('the values of a field over the dictionary, the commonest first (the table where the POS is mapped)', X.unique_values(root, 'entry', {'path': './sense/grammatical-info', 'value': '@value'}), [('Noun', 2), ('Pronoun', 1)])

# ── suggestions ──
sg = X.suggest(root, 'entry', paths)
check('LIFT: the mapping starts filled in (headword, IPA, part of speech, senses, glosses, definitions, notes, etymology)', (sg['lemma']['path'], sg['langAttr'], sg['pos']['value'], sg['sense']['path'], sg['gloss']['value'], sg['definition']['path'], sg['notes']['path'], sg['etymology']['path']), ('./lexical-unit/form', 'lang', '@value', './sense', './text', './definition/form', './note/form', './etymology'))
tpaths, _ = X.describe_paths(troot, 'entry')
tg = X.suggest(troot, 'entry', tpaths)
check('TEI: orth, pron, pos, sense and def are suggested', (tg['lemma']['path'], tg['ipa']['path'], tg['pos']['path'], tg['sense']['path'], tg['definition']['path']), ('./form/orth', './form/pron', './gramGrp/pos', './sense', './def'))
fpaths, _ = X.describe_paths(X.parse(FLAT.encode())[0], 'rec')
check('another schema has no suggestion: the author maps it by hand', X.suggest(X.parse(FLAT.encode())[0], 'rec', fpaths), None)

# ── validation ──
CFG = {'entryTag': 'entry', 'lemma': {'path': './lexical-unit/form', 'value': 'text'}, 'language': {'mode': 'attr', 'attr': 'lang', 'map': {'nme': 'num', 'drg': 'drg'}},
       'ipa': {'path': './pronunciation/form', 'value': 'text'}, 'pos': {'path': './sense/grammatical-info', 'value': '@value'}, 'posMap': {'Noun': 'n.', 'Pronoun': 'pro.'},
       'sense': {'path': './sense'}, 'subsense': {'path': './subsense'},
       'definition': {'path': './definition/form', 'value': 'text', 'filterAttr': 'lang', 'filterValue': 'en'},
       'gloss': {'path': './gloss', 'value': 'text', 'filterAttr': 'lang', 'filterValue': 'en'}, 'notes': {'path': './note/form', 'value': 'text'},
       'etymology': {'path': './etymology', 'form': {'path': './form', 'value': 'text'}, 'lang': {'path': '', 'value': '@source'}, 'gloss': {'path': './gloss', 'value': 'text'}}}
check('a complete mapping has no problem', X.validate_config(root, CFG, CODES), [])
check('a mapping without entry node, headword or language says what is missing', (X.validate_config(root, {}, CODES), X.validate_config(root, {'entryTag': 'nope'}, CODES), X.validate_config(root, {'entryTag': 'entry', 'lemma': {}, 'language': {'mode': 'fixed', 'code': 'num'}}, CODES), X.validate_config(root, {'entryTag': 'entry', 'lemma': {'path': 'x'}, 'language': {'mode': 'fixed', 'code': 'zzz'}}, CODES)), (['Choose the node that wraps each entry.'], ['Choose the node that wraps each entry.'], ['Headword: choose the node.'], ['Languages: choose the language of the headwords.']))
check('languages mapped to something that is not a language of the project are refused; so is a path that leaves the entry', (X.validate_config(root, dict(CFG, language={'mode': 'attr', 'attr': 'lang', 'map': {'nme': 'xxx'}}), CODES), X.validate_config(root, dict(CFG, pos={'path': '/etc', 'value': ''}), CODES)), (['Languages: xxx is not a language of the project.'], ['Part of speech: the path is not valid (Not a path below the entry: /etc).']))

# ── conversion ──
els, rep = X.convert(root, CFG, CODES)
xml = [etree.tostring(e, encoding='unicode') for e in els]
e0 = els[0]
check('three entries are imported; the one whose headword is in no language of the project is skipped and reported', (rep['total'], rep['imported'], rep['skipped']), (4, 3, [{'reason': 'no headword in a language of the project', 'count': 1, 'sample': ['other language']}]))
check('the headword is in each language of the project that has one (the language read from the attribute and mapped), in the project’s order, with the IPA of its language', ([(f.get('langue'), f.text) for f in e0.findall('Lemme/ReprésentationDeForme')], [(f.get('langue'), f.text) for f in e0.findall('Lemme/FormePhonétique')]), ([('num', 'mōrōs'), ('drg', 'morus')], [('num', 'moːɾos')]))
_tei_cfg = dict(CFG, lemma={'path': './form/orth', 'value': ''}, ipa={'path': './form/pron', 'value': ''}, language={'mode': 'attr', 'attr': 'lang', 'map': {'nme': 'num'}}, pos=None, sense={'path': ''}, subsense={}, definition=None, gloss=None, notes=None, etymology=None)
_tei_first = X.convert(troot, _tei_cfg, CODES)[0][0]
check('LIFT’s nme-fonipa is the IPA of nme (see the next check); TEI’s pron, which says no language, is the IPA of the only language of its entry', [(f.get('langue'), f.text) for f in _tei_first.findall('Lemme/FormePhonétique')], [('num', 'nir')])
check('the part of speech goes through the author’s table', e0.findtext('ClasseGrammaticale'), 'n.')
check('senses: the sense, its subsense as a sense of its own, then the next; numbered; definition and short gloss in English, notes', ([(s.get('identifiant'), s.findtext('NuméroDeSens'), s.findtext('Glose'), s.findtext('gloss')) for s in e0.findall('Sens')], e0.findtext('Sens/Notes/ReprésentationDeTexte')), ([('morosⓢ1', '1', 'a building where people live', 'house'), ('morosⓢ2', '2', 'hut', 'hut'), ('morosⓢ3', '3', 'family', 'family')], 'very common'))
check('the language of the glosses is written as eng (what the DBT shows)', {s.get('langue') for s in e0.findall('Sens/Glose')}, {'eng'})
check('etymology: the form, the language read from the attribute of the wrapper, the gloss', [(n.findtext('Langue'), n.findtext('Forme'), n.findtext('Glose')) for n in e0.findall('Étymologie/Étymon')], [('POc', '*rumaq', 'house')])
check('identifiers come from the headword (diacritics dropped); two entries with the same headword get _2', [e.get('identifiant') for e in els], ['moros', 'nir', 'moros_2'])
check('an entry without IPA has no phonetic form', els[1].find('Lemme/FormePhonétique'), None)
_els2, _ = X.convert(root, CFG, CODES, existing_ids={'moros', 'nir'})
check('when the entries are added to a dictionary, the identifiers already there are not reused', [e.get('identifiant') for e in _els2], ['moros_2', 'nir_2', 'moros_3'])
check('keeping the identifiers of the source: the attribute of the entry, as an ASCII identifier', [e.get('identifiant') for e in X.convert(root, dict(CFG, idAttr='@id'), CODES)[0]], ['moros_1', 'nir_2', 'moros_4'])
_f, rp = X.convert(root, dict(CFG, language={'mode': 'fixed', 'code': 'kro'}), CODES)
check('a fixed language: every headword is in it, whatever the attribute says (the first form of an entry is kept, and the file is told)', ([(e.get('identifiant'), [f.get('langue') for f in e.findall('Lemme/ReprésentationDeForme')]) for e in _f], rp['warnings'][:1]), ([('moros', ['kro']), ('nir', ['kro']), ('other_language', ['kro']), ('moros_2', ['kro'])], ['1 headword(s) had several forms for the same language: the first one is kept.']))
check('only part of the file can be converted (the wizard’s preview)', len(X.convert(root, CFG, CODES, limit=2)[0]), 2)
check('the converted entry is well-formed XML in the DBT’s tags', all(t in xml[0] for t in ('<EntréeLexicale identifiant="moros">', '<Lemme>', '<ClasseGrammaticale>n.</ClasseGrammaticale>', '<Étymologie>', '<Sens identifiant=')), True)
# ── a flat file and a TEI file, mapped by hand ──
froot = X.parse(FLAT.encode())[0]
fcfg = {'entryTag': 'rec', 'lemma': {'path': 'lx', 'value': ''}, 'language': {'mode': 'fixed', 'code': 'num'}, 'pos': {'path': 'ps', 'value': ''}, 'posMap': {'pro': 'pro.', 'n': 'n.'},
        'sense': {'path': ''}, 'gloss': {'path': 'ge', 'value': ''}, 'notes': {'path': 'nt', 'value': ''}}
fe, fr = X.convert(froot, fcfg, CODES)
check('a flat dictionary (no sense node: the entry is the sense) is converted; the record without a headword is skipped', ([(e.findtext('Lemme/ReprésentationDeForme'), e.findtext('ClasseGrammaticale'), e.findtext('Sens/gloss'), e.findtext('Sens/Notes/ReprésentationDeTexte')) for e in fe], fr['imported'], fr['skipped'][0]['count']), ([('nir', 'pro.', '3PL', 'a note'), ('ron', 'n.', 'voice', None)], 2, 1))
tcfg = {'entryTag': 'entry', 'lemma': {'path': './form/orth', 'value': ''}, 'language': {'mode': 'attr', 'attr': 'lang', 'map': {'nme': 'num'}}, 'ipa': {'path': './form/pron', 'value': ''}, 'pos': {'path': './gramGrp/pos', 'value': ''}, 'sense': {'path': './sense'}, 'definition': {'path': './def', 'value': ''}}
te, tr = X.convert(troot, tcfg, CODES)
check('TEI: orth with xml:lang, pron, pos, def', [(e.findtext('Lemme/ReprésentationDeForme'), e.findtext('Lemme/FormePhonétique'), e.findtext('ClasseGrammaticale'), e.findtext('Sens/Glose')) for e in te], [('nir', 'nir', 'pro.', '3PL'), ('ron̄', None, 'n.', 'voice')])
# ── coverage ──
cov = X.coverage(root, 'entry', [('Headword', CFG['lemma'], True), ('English gloss', CFG['gloss'] | {'path': './sense/gloss'}, True), ('Notes', {'path': './sense/note/form', 'value': 'text'}, False)], CFG['lemma'])
check('the coverage report says how many entries lack a field and gives examples', [(c['label'], c['present'], c['missing'], c['missingPct']) for c in cov] + [cov[2]['sample'][:2]], [('Headword', 4, 0, 0.0), ('English gloss', 4, 0, 0.0), ('Notes', 1, 3, 75.0), ['nir', 'other language']])
# ── a dictionary of the size the wizard has to carry ──
big = '<d>' + ''.join('<e><h>w%d</h><g>g%d</g></e>' % (i, i) for i in range(20000)) + '</d>'
br = X.parse(big.encode())[0]
bp, bs = X.describe_paths(br, 'e')
check('a large dictionary: the inventory looks at a sample, the conversion at everything', (bs, [p['count'] for p in bp], X.convert(br, {'entryTag': 'e', 'lemma': {'path': 'h'}, 'language': {'mode': 'fixed', 'code': 'num'}, 'gloss': {'path': 'g'}}, CODES)[1]['imported']), (X.SAMPLE_ENTRIES, [X.SAMPLE_ENTRIES, X.SAMPLE_ENTRIES], 20000))
# ── a third schema, French tags: the DBT's own dictionary, mapped by hand, comes back with the same forms, parts of speech and senses ──
_orig = native
_ALL = ['num', 'drg', 'kro', 'olr', 'lkn']
_rt = {'entryTag': 'EntréeLexicale', 'lemma': {'path': './Lemme/ReprésentationDeForme', 'value': ''}, 'language': {'mode': 'attr', 'attr': 'langue', 'map': {c: c for c in _ALL}},
       'pos': {'path': './ClasseGrammaticale', 'value': ''}, 'domain': {'path': './DomaineSémantique', 'value': ''}, 'sense': {'path': './Sens'},
       'definition': {'path': './Glose', 'value': '', 'filterAttr': 'langue', 'filterValue': 'eng'}, 'gloss': {'path': './gloss', 'value': ''},
       'notes': {'path': './Notes/ReprésentationDeTexte', 'value': ''},
       'etymology': {'path': './Étymologie/Étymon', 'form': {'path': './Forme', 'value': ''}, 'lang': {'path': './Langue', 'value': ''}, 'gloss': {'path': './Glose', 'value': ''}}}
check('the DBT’s own dictionary, mapped by hand as if it were a foreign schema, validates', X.validate_config(_orig, _rt, _ALL), [])
_els, _rep = X.convert(_orig, _rt, _ALL)
_o = X.entries(_orig, 'EntréeLexicale')
_forms = lambda es: [[(f.get('langue'), f.text) for f in e.findall('Lemme/ReprésentationDeForme')] for e in es]
check('…and comes back entry for entry: the same number, the same forms in each language', (_rep['imported'], _rep['total'], _forms(_els)), (len(_o), len(_o), _forms(_o)))
check('…the same parts of speech and semantic domains', ([e.findtext('ClasseGrammaticale') for e in _els], [e.findtext('DomaineSémantique') for e in _els]), ([e.findtext('ClasseGrammaticale') for e in _o], [e.findtext('DomaineSémantique') for e in _o]))
_sn = lambda es, g: [[(s.findtext(g), s.findtext('gloss') or s.findtext(g), s.findtext('Notes/ReprésentationDeTexte')) for s in e.findall('Sens') if s.findtext(g)] for e in es]      # without a short gloss the definition is used, as in the editor
check('…the same senses (English definitions, short glosses; the definition where there is none) and notes', _sn(_els, 'Glose'), _sn(_o, 'Glose[@langue="eng"]'))
_et = lambda es: [[(n.findtext('Langue'), n.findtext('Forme')) for n in e.findall('Étymologie/Étymon')] for e in es]
check('…and the same etymologies', _et(_els), _et(_o))

# ═════════ examples (into a text) and semantic relations (resolved after all the entries are converted) ═════════
LIFT2 = '''<lift version="0.13">
 <entry id="a_1" guid="g1"><lexical-unit><form lang="nme"><text>nir</text></form></lexical-unit>
  <sense id="s1"><gloss lang="en"><text>they</text></gloss>
   <example><form lang="nme"><text>nir vitis gil</text></form><translation type="Free translation"><form lang="en"><text>They do not know</text></form><form lang="fr"><text>Ils ne savent pas</text></form></translation></example>
   <example><form lang="nme"><text>nir mi</text></form></example>
   <example><form lang="zzz"><text>a sentence in a language that is not in the project</text></form></example>
   <relation type="Synonyms" ref="s3"/></sense></entry>
 <entry id="b_2" guid="g2"><lexical-unit><form lang="nme"><text>ron</text></form></lexical-unit>
  <sense id="s2"><gloss lang="en"><text>voice</text></gloss><relation type="Antonyms" ref="g3"/></sense>
  <sense id="s2b"><gloss lang="en"><text>speak</text></gloss><example><form lang="drg"><text>drg sentence</text></form><translation><form lang="en"><text>he speaks</text></form></translation></example>
   <example><form lang="nme"><text>nir vitis gil</text></form><translation><form lang="en"><text>They do not know</text></form></translation></example></sense></entry>
 <entry id="c_3" guid="g3"><lexical-unit><form lang="nme"><text>vis</text></form></lexical-unit>
  <sense id="s3"><gloss lang="en"><text>know</text></gloss><relation type="Hypernym" ref="g1"/><relation type="Synonyms" ref="missing"/></sense></entry>
</lift>'''
r2 = X.parse(LIFT2.encode())[0]
CFG2 = {'entryTag': 'entry', 'lemma': {'path': './lexical-unit/form', 'value': './text'}, 'language': {'mode': 'attr', 'attr': 'lang', 'map': {'nme': 'num', 'drg': 'drg'}}, 'sense': {'path': './sense'},
        'gloss': {'path': './gloss', 'value': './text', 'filterAttr': 'lang', 'filterValue': 'en'},
        'examples': {'path': './sense/example', 'text': {'path': './form', 'value': './text'}, 'translation': {'path': './translation/form', 'value': './text', 'filterAttr': 'lang', 'filterValue': 'en'}},
        'relations': {'path': './sense/relation', 'type': {'path': '', 'value': '@type'}, 'typeMap': {}, 'target': {'path': '', 'value': '@ref'}, 'by': 'id', 'entryKey': '@guid', 'senseKey': '@id'}}
check('a mapping with examples and relations validates', X.validate_config(r2, CFG2, CODES), [])
els2, rep2 = X.convert(r2, CFG2, CODES)
ids2 = {e.get('identifiant'): e for e in els2}
texts2 = rep2['_texts']
check('the examples go into a text for each language of the project (a text has one language): the sentence, its translation in the language chosen; an example in no language of the project is left out; the same sentence in two senses is one sentence', ({c: [(i['id'], i['form'], i['transl']) for i in v] for c, v in texts2.items()}, rep2['examples']), ({'num': [('ex1', 'nir vitis gil', 'They do not know'), ('ex2', 'nir mi', '')], 'drg': [('ex1', 'drg sentence', 'he speaks')]}, {'num': 2, 'drg': 1}))
check('each sense cites its examples, in the text of their language: one {{cite: file#id}} per line (the key every sense of the DBT uses)', ([s.findtext('Exemples') for s in ids2['nir'].findall('Sens')], [s.findtext('Exemples') for s in ids2['ron'].findall('Sens')]), (['{{cite: Examples_from_pre-existent_dictionary_num.xml#ex1}}\n{{cite: Examples_from_pre-existent_dictionary_num.xml#ex2}}'], [None, '{{cite: Examples_from_pre-existent_dictionary_drg.xml#ex1}}\n{{cite: Examples_from_pre-existent_dictionary_num.xml#ex1}}']))
check('in a dictionary that is added to another, the numbering of the sentences goes on from the text that is already there', [i['id'] for i in X.convert(r2, CFG2, CODES, example_start={'num': 5})[1]['_texts']['num']], ['ex6', 'ex7'])
rl = [(e.get('identifiant'), [(r.findtext('Type'), r.find('Cible').get('cible'), r.findtext('Cible')) for r in s.findall('RelationSémantique')]) for e in els2 for s in e.findall('Sens')]
check('relations: by the identifier of a sense (ref="s3"), or of an entry (ref="g3": its first sense); the type read from the file (Synonyms, Antonyms); each is written on the sense where it stood and points to a sense, with the headword of its target', rl, [('nir', [('synonym', 'visⓢ1', 'vis')]), ('ron', [('antonym', 'visⓢ1', 'vis')]), ('ron', []), ('vis', [])])
check('relations of another type (Hypernym) are not imported, and one that points to nothing is skipped: both are reported', (rep2['relations'], [w for w in rep2['warnings'] if 'relation' in w]), ({'unresolved': 1, 'ignored': 1, 'imported': 2}, ['1 relation(s) point to an entry or sense that is not among the imported ones: skipped.', '1 relation(s) of another type than synonym or antonym were not imported.']))
byhw = dict(CFG2, relations={'path': './sense/relation', 'type': {'path': '', 'value': '@type'}, 'typeMap': {}, 'target': {'path': '', 'value': '@ref'}, 'by': 'headword'})
r3 = X.parse(LIFT2.replace('ref="s3"', 'ref="Vis"').replace('ref="g3"', 'ref="nir"').encode())[0]
e3 = X.convert(r3, byhw, CODES)[0]
check('relations by headword: the target is found by its headword (case ignored), in any of the forms of the entry', [[(r.findtext('Type'), r.find('Cible').get('cible')) for r in s.findall('RelationSémantique')] for e in e3 for s in e.findall('Sens')][:2], [[('synonym', 'visⓢ1')], [('antonym', 'nirⓢ1')]])
tm = dict(CFG2, relations=dict(CFG2['relations'], typeMap={'Synonyms': 'antonym', 'Antonyms': '', 'Hypernym': 'synonym'}))
check('the author’s table decides what each type of the file is: synonym, antonym, or not imported', [[r.findtext('Type') for r in s.findall('RelationSémantique')] for e in X.convert(r2, tm, CODES)[0] for s in e.findall('Sens')], [['antonym'], [], [], ['synonym']] if False else [['antonym'], [], [], ['synonym']])
check('a mapping with relations needs a type, a target, a way to find it, and a type table that says synonym or antonym', (X.validate_config(r2, dict(CFG2, relations=dict(CFG2['relations'], by='nothing')), CODES), X.validate_config(r2, dict(CFG2, relations=dict(CFG2['relations'], entryKey='', senseKey='')), CODES), X.validate_config(r2, dict(CFG2, relations=dict(CFG2['relations'], typeMap={'x': 'hypernym'})), CODES), X.validate_config(r2, dict(CFG2, examples=dict(CFG2['examples'], text={})), CODES)), (['Relations: say how a relation points to its target (by identifier, or by headword).'], ['Relations: say which attribute holds the identifier of an entry or of a sense.'], ['Relations: hypernym is not synonym or antonym.'], ['Examples: text: choose the node.']))
txt = etree.tostring(X.build_examples_text('num', texts2['num'], X.EXAMPLES_TITLE), encoding='unicode')
check('the text made of the examples has the format of every text of the Texts page: its language, its title, a sentence with its form and its translation', ('xml:lang="num"' in txt and '<TITLE xml:lang="en">Examples from pre-existent dictionary</TITLE>' in txt and '<S id="ex1"><FORM>nir vitis gil</FORM><TRANSL xml:lang="en">They do not know</TRANSL></S>' in txt and '<S id="ex2"><FORM>nir mi</FORM></S>' in txt), True)
check('without examples or relations in the mapping nothing of them is produced', ('_texts' in X.convert(r2, dict(CFG2, examples=None, relations=None), CODES)[1], 'relations' in X.convert(r2, dict(CFG2, examples=None, relations=None), CODES)[1], [e.findall('.//Exemples') for e in X.convert(r2, dict(CFG2, examples=None, relations=None), CODES)[0]][0]), (False, False, []))
sg2 = X.suggest(X.parse(LIFT2.encode())[0], 'entry', X.describe_paths(r2, 'entry')[0])
check('LIFT: examples and relations are suggested too (the relation as an attribute type, the target the attribute ref, found by identifier)', (sg2['examples']['path'], sg2['examples']['translation']['path'], sg2['relations']['path'], sg2['relations']['type']['value'], sg2['relations']['target']['value'], sg2['relations']['by']), ('./sense/example', './translation/form', './sense/relation', '@type', '@ref', 'id'))

print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
