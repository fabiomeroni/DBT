"""
Direct tests of references.py (no server): the APA 7 formatting, in-text citations, ordering, validation and the exports.

The expected reference-list lines are those of the UTS "APA 7th referencing guide" (templates and worked examples), plus a
chapter in an edited volume. Run it alone with:  python tests/test_references.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import references as R
ok = bad = 0
def check(name, got, want):
    global ok, bad
    if got == want: ok += 1
    else:
        bad += 1; print(f"✗ {name}\n    got : {got!r}\n    want: {want!r}")
def P(f, g=''): return {'family': f, 'given': g} if g else {'family': f}
def ref(i, ty, **kw): return dict({'id': i, 'type': ty, 'authors': [], 'editors': [], 'year': '2000'}, **kw)
def text(r, rs=None): ctx = R.Context(rs or [r]); return R.apa(r, ctx)[1]
def html(r, rs=None): ctx = R.Context(rs or [r]); return R.apa(r, ctx)[0]

# ── the user's example ──
fr = ref('francois2026b', 'chapter', authors=[P('François', 'Alexandre')], editors=[P('Miestamo', 'M.'), P('Veselinova', 'L.')], year='2026b',
         title='Negation in Dorig', container='Negation in the world’s languages III: Papunesia, Australia, and the Americas',
         pages='73-128', publisher='Language Science Press', doi='10.5281/zenodo.18234067')
check('user example', text(fr), "François, A. (2026b). Negation in Dorig. In M. Miestamo & L. Veselinova (Eds.), Negation in the world’s languages III: Papunesia, Australia, and the Americas (pp. 73–128). Language Science Press. https://doi.org/10.5281/zenodo.18234067")
check('user example, italics', '<em>Negation in the world’s languages III: Papunesia, Australia, and the Americas</em>' in html(fr), True)
c = R.Context([fr])
check('in-text parenthetical', R.intext([(fr, 'p. 128')], c)[0], '(François, 2026b, p. 128)')
check('in-text narrative', R.intext([(fr, '128')], c, narrative=True)[0], 'François (2026b, p. 128)')

# ── the guide's templates ──
check('1.10 chapter', text(ref('c', 'chapter', authors=[P('Coleman', 'S.')], year='2003', title='Democracy in an e-connected world', editors=[P('Davidson', 'R.')], container='The e-connected world: Risks and opportunities', edition='2', pages='125–132', publisher='McGill Queens University Press')),
      'Coleman, S. (2003). Democracy in an e-connected world. In R. Davidson (Ed.), The e-connected world: Risks and opportunities (2nd ed., pp. 125–132). McGill Queens University Press.')
check('1.10 chapter, volume, title with ?', text(ref('c', 'chapter', authors=[P('Slee', 'R.')], year='2014', title='Inclusive schooling as an apprenticeship in democracy?', editors=[P('Florian', 'L.')], container='The SAGE handbook of special education', edition='2', volume='1', pages='217-229', publisher='SAGE Publications')),
      'Slee, R. (2014). Inclusive schooling as an apprenticeship in democracy? In L. Florian (Ed.), The SAGE handbook of special education (2nd ed., Vol. 1, pp. 217–229). SAGE Publications.')
check('1.08 edited book', text(ref('e', 'edited', authors=[P('Hamilton', 'P.')], year='2005', title='Visual research methods', edition='4', publisher='Sage')), 'Hamilton, P. (Ed.). (2005). Visual research methods (4th ed.). Sage.')
check('1.09 edited, two editors', text(ref('e', 'edited', authors=[P('Burley', 'J.'), P('Harris', 'J.')], year='2008', title='A companion to genetics', edition='2', publisher='John Wiley & Sons')), 'Burley, J., & Harris, J. (Eds.). (2008). A companion to genetics (2nd ed.). John Wiley & Sons.')
check('1.01 book', text(ref('b', 'book', authors=[P('O’Sullivan', 'A.')], year='2019', title='Urban economics', edition='9', publisher='McGraw-Hill Education')), 'O’Sullivan, A. (2019). Urban economics (9th ed.). McGraw-Hill Education.')
check('1.02 book, two authors', text(ref('b', 'book', authors=[P('Oshima', 'A.'), P('Hogue', 'A.')], year='2004', title='Writing academic English', edition='4', publisher='Pearson Longman')), 'Oshima, A., & Hogue, A. (2004). Writing academic English (4th ed.). Pearson Longman.')
art = ref('a1', 'article', authors=[P('Alderton', 'Z.')], year='2014', title='“Snapewives” and “Snapeism”: A fiction-based religion within the Harry Potter fandom', container='Religions', volume='5', issue='1', pages='219-267', doi='10.3390/rel5010219')
check('2.01 article', text(art), 'Alderton, Z. (2014). “Snapewives” and “Snapeism”: A fiction-based religion within the Harry Potter fandom. Religions, 5(1), 219–267. https://doi.org/10.3390/rel5010219')
check('2.01 italics: journal and volume, not the issue', '<em>Religions</em>, <em>5</em>(1), 219–267.' in html(art), True)
check('2.02 two authors', text(ref('a', 'article', authors=[P('O’Toole', 'J.'), P('Vogel', 'D.')], year='2011', title='Two and a half cheers for conscious capitalism', container='California Management Review', volume='53', issue='3', pages='60-76', doi='https://doi.org/10.1525/cmr.2011.53.3.60')),
      'O’Toole, J., & Vogel, D. (2011). Two and a half cheers for conscious capitalism. California Management Review, 53(3), 60–76. https://doi.org/10.1525/cmr.2011.53.3.60')
gu = ref('g', 'article', authors=[P('Gursoy', 'A.'), P('Wickett', 'K.'), P('Feinberg', 'M.')], year='2018', title='Understanding tag functions in a moderated, user-generated metadata ecosystem', container='Journal of Documentation', volume='74', issue='3', pages='490-508', doi='10.1108/JD-09-2017-0134')
check('2.03 three authors', text(gu), 'Gursoy, A., Wickett, K., & Feinberg, M. (2018). Understanding tag functions in a moderated, user-generated metadata ecosystem. Journal of Documentation, 74(3), 490–508. https://doi.org/10.1108/JD-09-2017-0134')
check('2.03 in-text et al.', (R.intext([(gu, '')], R.Context([gu]))[0], R.intext([(gu, '')], R.Context([gu]), True)[0]), ('(Gursoy et al., 2018)', 'Gursoy et al. (2018)'))
names = ['Kalnay', 'Kanamitsu', 'Kistler', 'Collins', 'Deaven', 'Gandin', 'Iredell', 'Saha', 'White', 'Woollen', 'Zhu', 'Chelliah', 'Ebisuzaki', 'Higgins', 'Janowial', 'Mo', 'Ropelewski', 'Wang', 'Leetmaa', 'Reynolds', 'Jenne', 'Joseph']
kal = ref('k', 'article', authors=[P(n, n[0]) for n in names], year='1996', title='The NCEP/NCAR 40-year reanalysis project', container='Bulletin of the American Meteorological Society', volume='77', issue='3', pages='437-471')
t = text(kal)
check('21+ authors: first 19, an ellipsis, the last', t.startswith('Kalnay, K., Kanamitsu, K., ') and 'Leetmaa, L., … Joseph, J. (1996).' in t and 'Reynolds' not in t and 'Jenne' not in t, True)
check('7.07 thesis, publication number', text(ref('t', 'thesis', authors=[P('Hollander', 'M.')], year='2017', title='Resistance to authority: Methodological innovations and new lessons from the Milgram experiment', number='Publication No. 10289373', level='Doctoral dissertation', institution='University of Wisconsin-Madison', publisher='ProQuest Dissertations and Theses Global')),
      'Hollander, M. (2017). Resistance to authority: Methodological innovations and new lessons from the Milgram experiment (Publication No. 10289373) [Doctoral dissertation, University of Wisconsin-Madison]. ProQuest Dissertations and Theses Global.')
check('7.07 thesis, URL', text(ref('t', 'thesis', authors=[P('Hutcheson', 'V. H.')], year='2012', title='Dealing with dual differences: Social coping strategies of gifted and lesbian, gay, bisexual, transgender, and queer adolescents', level='Master’s thesis', institution='The College of William & Mary', publisher='William & Mary Digital Archive', url='https://digitalarchive.wm.edu/bitsream/handle/10288/16594/HutchesonVirginia2012.pdf')),
      'Hutcheson, V. H. (2012). Dealing with dual differences: Social coping strategies of gifted and lesbian, gay, bisexual, transgender, and queer adolescents [Master’s thesis, The College of William & Mary]. William & Mary Digital Archive. https://digitalarchive.wm.edu/bitsream/handle/10288/16594/HutchesonVirginia2012.pdf')
check('7.09 conference paper', text(ref('cp', 'conference', authors=[P('Campbell', 'K.')], year='2019', dateText='October 28-29', title='An information behaviours view of first in family students before and during university', container='Research Applications in Information and Library Studies', place='Canberra, ACT, Australia')),
      'Campbell, K. (2019, October 28–29). An information behaviours view of first in family students before and during university [Paper presentation]. Research Applications in Information and Library Studies, Canberra, ACT, Australia.')
check('7.16 data set, organisation, retrieved', text(ref('d', 'dataset', authors=[{'org': 'Pew Research Center'}], year='2018', title='American trends panel Wave 26', accessed='October 21, 2019', url='https://www.pewsocialtrends.org/dataset/american-trends-panel-wave-26/')),
      'Pew Research Center. (2018). American trends panel Wave 26 [Data set]. Retrieved October 21, 2019, from https://www.pewsocialtrends.org/dataset/american-trends-panel-wave-26/')
check('6.03 unpublished', text(ref('u', 'unpublished', authors=[P('Yoo', 'J.'), P('Miyamoto', 'Y.'), P('Rigotti', 'A.'), P('Ryff', 'C.')], year='2016', title='Linking positive affect to blood lipids: A cultural perspective', publisher='Department of Psychology, University of Wisconsin-Madison')),
      'Yoo, J., Miyamoto, Y., Rigotti, A., & Ryff, C. (2016). Linking positive affect to blood lipids: A cultural perspective [Unpublished manuscript]. Department of Psychology, University of Wisconsin-Madison.')
check('3.01 web page, individual', text(ref('w', 'web', authors=[P('McLeod', 'S.')], year='2020', dateText='March 20', title='Maslow’s hierarchy of needs', container='Simply Psychology', url='https://www.simplypsychology.org/maslow.html')),
      'McLeod, S. (2020, March 20). Maslow’s hierarchy of needs. Simply Psychology. https://www.simplypsychology.org/maslow.html')
check('3.02 web page, organisation (site name omitted: same as the author)', text(ref('w', 'web', authors=[{'org': 'World Health Organization'}], year='2022', dateText='July 14', title='Immunization coverage', container='World Health Organization', url='https://www.who.int/news-room/fact-sheets/detail/immunization-coverage')),
      'World Health Organization. (2022, July 14). Immunization coverage. https://www.who.int/news-room/fact-sheets/detail/immunization-coverage')
check('1.05 no author: the title takes the author position', text(ref('n', 'book', year='1999', title='Maximum Linux security: A hacker’s guide to protecting your Linux server and workstation', publisher='Sams')),
      'Maximum Linux security: A hacker’s guide to protecting your Linux server and workstation. (1999). Sams.')
check('11.04 two organisations: no comma', text(ref('o', 'report', authors=[{'org': 'Australian Government'}, {'org': 'Productivity Commission'}], year='2020', title='A report', publisher='Canberra')), 'Australian Government & Productivity Commission. (2020). A report. Canberra.')

# ── initials (guide 11.06) ──
for given, want in [('Alexandre', 'A.'), ('Jean-Pierre', 'J.-P.'), ('Ai-Jun', 'A.-J.'), ('Lee-ann', 'L.'), ('Mary Ann', 'M. A.'), ('A. J.', 'A. J.'), ('AJ', 'A. J.'), ('A.J.', 'A. J.'), ('Émile', 'É.'), ('', '')]:
    check(f'initials {given!r}', R.initials(given), want)
check('single name author (Plato.)', text(ref('p', 'book', authors=[P('Plato')], year='2017', title='Republic', publisher='Penguin')), 'Plato. (2017). Republic. Penguin.')

# ── year letters, same surname, ordering ──
c1 = ref('c1', 'article', authors=[P('Collier', 'K.'), P('McManus', 'J.')], year='2005', title='Setting up learning partnerships in vocational education and training: Lessons learnt', container='The Journal of Vocational Education and Training', volume='57', issue='3', pages='251-273')
c2 = ref('c2', 'article', authors=[P('Collier', 'K.'), P('McManus', 'J.')], year='2005', title='Bridging the gap: The use of learning partnerships to enhance workplace learning', container='Asia Pacific Journal of Cooperative Education', volume='6', issue='2', pages='7-16')
ctx = R.Context([c1, c2])
check('same authors, same year: letters follow the titles alphabetically', (ctx.year(c2), ctx.year(c1)), ('2005a', '2005b'))
check('…and show in the in-text citation', R.intext([(c1, ''), (c2, '')], ctx)[0], '(Collier & McManus, 2005a, 2005b)')
mA = ref('mA', 'conference', authors=[P('McManus', 'A.')], year='2019', title='Tag! You’re it', container='Conf', place='X')
mJ = ref('mJ', 'article', authors=[P('McManus', 'J.'), P('Hansford', 'A.'), P('Hasseldine', 'J.'), P('Walpole', 'M.')], year='2007', title='VAT and GST', container='British Tax Review', volume='40')
cc = R.Context([mA, mJ])
check('same first-author surname, other initials: initials in the text', R.intext([(mJ, ''), (mA, '')], cc)[0], '(A. McManus, 2019; J. McManus et al., 2007)')
order = [r['id'] for r in R.Context([mJ, c1, c2, mA]).sorted()]
check('alphabetical order of the list', order, ['c2', 'c1', 'mA', 'mJ'])
nd = ref('nd', 'book', authors=[P('Zed', 'A.')], year='n.d.', title='B', publisher='P'); y1 = ref('y1', 'book', authors=[P('Zed', 'A.')], year='1990', title='A', publisher='P'); ip = ref('ip', 'book', authors=[P('Zed', 'A.')], year='in press', title='C', publisher='P')
check('n.d. first, in press last', [r['id'] for r in R.Context([ip, y1, nd]).sorted()], ['nd', 'y1', 'ip'])
one = ref('one', 'book', authors=[P('Alfred', 'P.')], year='2019', title='Z', publisher='P'); two = ref('two', 'book', authors=[P('Alfred', 'P.'), P('Zeta', 'L.')], year='2001', title='Y', publisher='P')
check('one author before several, with the same first author', [r['id'] for r in R.Context([two, one]).sorted()], ['one', 'two'])
check('accents sort as letters (François before Fowler? no: Fowler < François)', [r['id'] for r in R.Context([ref('fr', 'book', authors=[P('François', 'A.')], title='T', publisher='P'), ref('fo', 'book', authors=[P('Fowler', 'A.')], title='T', publisher='P')]).sorted()], ['fo', 'fr'])
check('n.d. with two works by the same author: n.d.-a', R.Context([nd, ref('nd2', 'book', authors=[P('Zed', 'A.')], year='n.d.', title='Another first', publisher='P')]).year(nd), 'n.d.-b')

# ── in-text variants ──
check('several sources: alphabetical, semicolons, no &', R.intext([(R.Context([ref('x', 'book', authors=[P('Potter')], year='2018', title='t', publisher='p')]).refs[0], ''), (ref('y', 'book', authors=[P('Black')], year='2017', title='t', publisher='p'), '')], R.Context([ref('x', 'book', authors=[P('Potter')], year='2018', title='t', publisher='p'), ref('y', 'book', authors=[P('Black')], year='2017', title='t', publisher='p')]))[0], '(Black, 2017; Potter, 2018)')
tw = ref('tw', 'article', authors=[P('Smith', 'A.'), P('Jones', 'B.')], year='2016', title='t', container='j')
check('two authors: & in brackets, "and" in the sentence', (R.intext([(tw, 'pp. 3-5')], R.Context([tw]))[0], R.intext([(tw, '')], R.Context([tw]), True)[0]), ('(Smith & Jones, 2016, pp. 3–5)', 'Smith and Jones (2016)'))
org = ref('org', 'web', authors=[{'org': 'World Health Organization'}], year='2022', title='t', container='x', url='https://x.org')
check('group author in the text', R.intext([(org, 'Key strategies section')], R.Context([org]))[0], '(World Health Organization, 2022, Key strategies section)')
check('no author: the title in italics or in quotes', (R.author_text(ref('a', 'book', year='2019', title='Interpersonal Skills', publisher='P'), R.Context([])), R.author_text(ref('a', 'article', year='2019', title='Interpersonal Skills', container='J'), R.Context([]))), ('Interpersonal Skills', '“Interpersonal Skills”'))
check('shortcode spec', R.parse_source_spec('francois2026b, p. 128; Miestamo2020, narrative'), [('francois2026b', 'p. 128', False), ('miestamo2020', '', True)])

# ── citing by author and year, as one writes it in a text ──
def found(what, refs):
    r, why = R.find_reference(what, refs, R.Context(refs))
    return r['id'] if r else why
sm   = ref('smith2020', 'book', authors=[P('Smith', 'Jane')], year='2020', title='One', publisher='P')
smj  = ref('smithjones2016', 'book', authors=[P('Smith', 'Jane'), P('Jones', 'Bob')], year='2016', title='Two', publisher='P')
gur  = gu
mxA  = ref('mxa', 'book', authors=[P('McManus', 'A.')], year='2019', title='A', publisher='P')
mxJ  = ref('mxj', 'book', authors=[P('McManus', 'J.')], year='2019', title='B', publisher='P')
allr = [fr, sm, smj, gur, mxA, mxJ, c1, c2, nd]
check('François 2026b', found('François 2026b', allr), 'francois2026b')
check('François, 2026b (with a comma)', found('François, 2026b', allr), 'francois2026b')
check('case and accents do not matter', found('FRANCOIS 2026B', allr), 'francois2026b')
check('no letter: the only year of that author', found('François 2026', allr), 'francois2026b')
check('the wrong letter is not found', found('François 2026a', allr), 'not found')
check('an unknown author is not found', found('Nobody 2000', allr), 'not found')
check('an author without a year is not a citation', found('François', allr), 'not found')
check('a key still works', found('smith2020', allr), 'smith2020')
check('two authors with &', found('Smith & Jones 2016', allr), 'smithjones2016')
check('two authors with and, and a comma', found('Smith and Jones, 2016', allr), 'smithjones2016')
check('the first author only, when that is enough', found('Smith 2016', allr), 'smithjones2016')
check('but the one-author work wins when there is one', found('Smith 2020', allr), 'smith2020')
check('three authors: et al.', found('Gursoy et al. 2018', allr), 'g')
check('same surname, different people: ambiguous', found('McManus 2019', allr).startswith('ambiguous'), True)
check('…told apart by the initial', (found('A. McManus 2019', allr), found('J. McManus 2019', allr)), ('mxa', 'mxj'))
check('two works of one year: ambiguous, naming the letters', found('Collier & McManus 2005', allr), 'ambiguous: 2005a, 2005b')
check('…and fine with the letter', (found('Collier & McManus 2005a', allr), found('Collier & McManus 2005b', allr)), ('c2', 'c1'))
check('n.d.', found('Zed n.d.', allr), 'nd')
check('a surname with particles', found('van der Berg 2001', [ref('vdb', 'book', authors=[P('van der Berg', 'H.')], year='2001', title='T', publisher='P')]), 'vdb')
keys = {'smith2020', 'francois2026b'}
check('parse: author, comma, year, locator', R.parse_source_spec('François, 2026b, p. 128', keys), [('François 2026b', 'p. 128', False)])
check('parse: author year, narrative', R.parse_source_spec('Smith 2020, narrative', keys), [('Smith 2020', '', True)])
check('parse: several, mixing forms', R.parse_source_spec('Lee, 2018; smith2020, p. 3; Kim 2019', keys), [('Lee 2018', '', False), ('smith2020', 'p. 3', False), ('Kim 2019', '', False)])
check('parse: a key followed by a number keeps its locator (the number is not taken for a year)', R.parse_source_spec('smith2020, 2021', keys), [('smith2020', '2021', False)])

# ── validation and keys ──
r, e = R.clean({'type': 'article', 'title': 'T', 'year': '2020', 'authors': [{'family': 'Doe', 'given': 'J'}, {'family': ''}], 'url': 'ftp://x'})
check('a URL must be http(s)', e is not None, True)
r, e = R.clean({'type': 'article', 'title': 'T', 'year': 'soon'})
check('a year must look like a year', e is not None, True)
r, e = R.clean({'type': 'article', 'title': 'T', 'year': '', 'authors': [{'family': 'Doe'}, {'family': ' '}]})
check('a missing year becomes n.d.; blank authors are dropped', (r['year'], r['authors']), ('n.d.', [{'family': 'Doe'}]))
check('suggested key', (R.suggest_id(fr), R.suggest_id(fr, taken={'francois2026b'}), R.suggest_id(ref('z', 'web', authors=[{'org': 'World Health Organization'}], year='n.d.', title='x'))), ('francois2026b', 'francois2026b-2', 'worldhealthorganizationnd'))

# ── exports ──
b = R.to_bibtex([fr]); e = R.to_endnote([fr])
check('BibTeX chapter', all(x in b for x in ('@incollection{francois2026b,', 'author = {François, Alexandre}', 'editor = {Miestamo, M. and Veselinova, L.}', 'booktitle = {Negation in the world’s languages III', 'pages = {73--128}', 'year = {2026}', 'publisher = {Language Science Press}', 'doi = {10.5281/zenodo.18234067}')), True)
check('EndNote chapter', all(x in e for x in ('%0 Book Section', '%A François, Alexandre', '%E Miestamo, M.', '%T Negation in Dorig', '%B Negation in the world’s languages III', '%D 2026', '%P 73–128', '%I Language Science Press', '%R 10.5281/zenodo.18234067')), True)

# ═════════ import: BibTeX, EndNote (tagged format) and RIS ═════════
import time
def one(text):
    fmt, items = R.parse_references(text)
    return fmt, items
def imp(text):
    fmt, items = R.parse_references(text)
    return [i['ref'] for i in items]
def apa_of(r, rs=None): return text(r, rs)

# ── the round trip: what the site exports, it reads back as the same references ──
RT = [
    ref('a1', 'article', authors=[P('Smith', 'John A.'), P('Jones', 'Mary')], title='A study of questions & answers: 50% of _cases_', container='Journal of Testing', volume='12', issue='3', pages='45-67', doi='10.1000/xyz123', year='2020'),
    ref('a2', 'article', authors=[{'org': 'World Health Organization'}], title='Annual report on health', container='Bulletin', volume='9', year='in press'),
    ref('a3', 'article', authors=[P('François', 'Alexandre'), P('Müller', 'Hans')], title='Négation en dorig: étude', container='Revue de linguistique', volume='4', pages='1-20', year='2019'),
    ref('b1', 'book', authors=[P('Brown', 'Peter')], title='The language of trees', edition='2nd', publisher='Language Science Press', year='2015'),
    ref('b2', 'book', authors=[P('Brown', 'Peter')], title='Trees again', publisher='Brill', year='n.d.'),
    ref('e1', 'edited', authors=[P('Miestamo', 'Matti'), P('Veselinova', 'Ljuba')], title='Negation in the world’s languages', publisher='Language Science Press', year='2026'),
    ref('c1', 'chapter', authors=[P('François', 'Alexandre')], editors=[P('Miestamo', 'M.'), P('Veselinova', 'L.')], title='Negation in Dorig', container='Negation in the world’s languages III', pages='73-128', publisher='Language Science Press', doi='10.5281/zenodo.18234067', year='2026b'),
    ref('k1', 'conference', authors=[P('Lee', 'Kim')], title='Talking about time', container='Proceedings of the Pacific Conference', place='Honolulu, HI', dateText='June 5–8', year='2018'),
    ref('t1', 'thesis', authors=[P('Nguyen', 'An')], title='Verb serialisation in an Oceanic language', institution='Australian National University', level='Doctoral dissertation', url='https://example.org/thesis', year='2017'),
    ref('t2', 'thesis', authors=[P('Nguyen', 'An')], title='A smaller thesis', institution='University of Sydney', level="Master's thesis", year='2012'),
    ref('r1', 'report', authors=[{'org': 'Vanuatu Cultural Centre'}], title='Language survey of the Banks Islands', publisher='Vanuatu Cultural Centre', number='42', year='2010'),
    ref('w1', 'web', authors=[{'org': 'Ethnologue'}], title='Languages of Vanuatu', container='SIL International', url='https://www.ethnologue.com/country/VU', accessed='May 3, 2024', year='2024'),
    ref('d1', 'dataset', authors=[P('Taylor', 'Sam')], title='Corpus of Banks Islands narratives', edition='2.1', publisher='Zenodo', doi='10.5281/zenodo.1', year='2021'),
    ref('u1', 'unpublished', authors=[P('Ray', 'Ana')], title='Notes on reduplication', descriptor='Unpublished manuscript, University of Paris', year='2023'),
    ref('o1', 'other', authors=[P('Cole', 'Ed')], title='Personal communication topics', note='Fieldwork recording', year='2022'),
]
RTR = {r['id']: r for r in RT}
for fmt_name, export in (('BibTeX', R.to_bibtex), ('EndNote', R.to_endnote)):
    bad_rt = []
    for r in RT:
        r = dict(r, year=R.split_year(r['year'])[0])                      # the formats have no year letters: the site gives them
        ctx = R.Context([r])
        want = R.apa(r, ctx)[1]
        fmt, items = R.parse_references(export([r]))
        got_r = items[0]['ref'] if items else None
        got = R.apa(got_r, R.Context([got_r]))[1] if got_r else None
        if got != want or (got_r and got_r['type'] != r['type']) or (got_r and got_r['id'] != r['id']): bad_rt.append((r['id'], want, got))
    check(f'round trip {fmt_name}: every type is read back as the same reference (same APA text, type and key)', bad_rt, [])
check('round trip: the whole list at once', len([i for i in R.parse_references(R.to_bibtex(RT))[1] if i['ref']]), len(RT))
check('round trip: the formats are recognised', (R.parse_references(R.to_bibtex(RT))[0], R.parse_references(R.to_endnote(RT))[0]), ('bibtex', 'endnote'))

# ── BibTeX as people write it ──
b = imp(r"""
% a comment line
@preamble{ "\newcommand{\noopsort}[1]{}" }
@string{jfl = "Journal of Foo"}
@comment{ @article{ignored, title = {not read}} }
@Article{Smith:2020a,
  Author = {Fran{\c c}ois, Alexandre and M{\"u}ller, Hans and John von Neumann and Doe, Jr., J. and {World Health Organization} and others},
  TITLE = {A {DNA} study of {\'E}mile's ``{T}rees''},
  journal = jfl # " Letters",
  year = {2020}, volume = 12, number = "3", pages = {12--34},
  doi = {https://doi.org/10.1000/abc}
}
@book(plain2001, title = "T", author = "Roe, R.", year = 2001, publisher = {P}) 
""")
a = b[0]
check('BibTeX: accents, names (given family, family given, a particle, a suffix, an organisation, "others"), macros', (
    [(p.get('family'), p.get('given'), p.get('suffix'), p.get('org')) for p in a['authors']]),
    [('François', 'Alexandre', None, None), ('Müller', 'Hans', None, None), ('von Neumann', 'John', None, None), ('Doe', 'J.', 'Jr.', None), (None, None, None, 'World Health Organization')])
check('BibTeX: braces, accents and a macro joined to a string in the title and the journal; pages; DOI; key', (a['title'], a['container'], a['pages'], a['doi'], a['volume'], a['issue'], a['id'], a['year']),
      ('A DNA study of Émile’s “Trees”'.replace('’', "'").replace('“', '``').replace('”', "''") if False else "A DNA study of Émile's ``Trees''", 'Journal of Foo Letters', '12–34', '10.1000/abc', '12', '3', 'smith-2020a', '2020'))
check('BibTeX: parentheses as delimiters, and a number or a string as a value', (b[1]['type'], b[1]['title'], b[1]['year'], b[1]['publisher'], b[1]['id']), ('book', 'T', '2001', 'P', 'plain2001'))
check('BibTeX: comments and @comment are skipped', len(b), 2)
check('BibTeX: a title in double braces and a title that carries a line break', imp('@misc{x, title = {{The {Old} Title}\n   continues}, year={1999}}')[0]['title'], 'The Old Title continues')
t1 = imp('@phdthesis{p, author={A, B}, title={T}, school={ANU}, year={2000}}')[0]; t2 = imp('@mastersthesis{m, author={A, B}, title={T}, school={ANU}, year={2000}}')[0]
check('BibTeX: theses by their level', (t1['type'], t1['level'], t1['institution'], t2['level']), ('thesis', 'Doctoral dissertation', 'ANU', "Master's thesis"))
check('BibTeX: types: a book with editors only is an edited book, @misc with a url is a web page, @misc without is "other", @inproceedings is a conference paper, an unknown type is "other"',
      [imp(s_)[0]['type'] for s_ in ('@book{k, editor={E, A}, title={T}, year=2000}', '@misc{k, title={T}, url={https://x.org/a}, year=2000}', '@misc{k, title={T}, year=2000}',
                                     '@inproceedings{k, title={T}, booktitle={B}, year=2000}', '@whatever{k, title={T}, year=2000}')], ['edited', 'web', 'other', 'conference', 'other'])
check('BibTeX: edited book: the editors are its authors', imp('@book{k, editor={Ed, A and Ee, B}, title={T}, year=2000}')[0]['authors'], [{'family': 'Ed', 'given': 'A'}, {'family': 'Ee', 'given': 'B'}])
check('BibTeX: year from a date, "in press", and none', [imp(f'@misc{{k, title={{T}}, {y}}}')[0]['year'] for y in ('date={2020-05-01}', 'year={in press}', 'author={A, B}')], ['2020', 'in press', 'n.d.'])
check('BibTeX: months as names or numbers (a conference)', [imp(f'@inproceedings{{k, title={{T}}, month={m}, year=2000}}')[0]['dateText'] for m in ('jun', '{3}', '{Spring}')], ['June', 'March', 'Spring'])
check('BibTeX: keys are made safe, or made up', [imp(f'@misc{{{k}, author={{Roe, R.}}, title={{T}}, year=2000}}')[0]['id'] for k in ('Smith:2020/a', '', '  ')], ['smith-2020-a', '', ''])
f_, it = one('@article{k, author={Roe, R.}, year=2000}')
check('BibTeX: an entry with no title is reported, not imported', (it[0]['ref'], it[0]['error']), (None, 'it has no title'))
f_, it = one('@misc{k, title={T}, url={ftp://x.org/f}, doi={doi:10.1/x}, year=2000}')
check('BibTeX: a URL that is not http(s) is left out with a warning, and "doi:" is dropped', (it[0]['ref']['url'], it[0]['ref']['doi'], len(it[0]['warnings'])), ('', '10.1/x', 1))
# junk and hostile input: no crash, no hang
t0 = time.time()
junk = ['@article{a, title = {unclosed', '@article{x,' + '{' * 100000, '{' * 50000 + '@misc{k, title={ok}}', '@' * 30000, '@misc{k,' + 'title = {' + 'a' * 500000 + '}}', '\x00\x01@misc{k, title={T}, year=2000}\x02', '@article{a, title = "x' + '\\' * 1000]
res = [R.parse_references(j) for j in junk]
check('junk and hostile input does not crash nor hang, and what can be read is read', (time.time() - t0 < 5, res[5][1][0]['ref']['title'], res[2][0]), (True, 'T', 'bibtex'))
check('what is not a list of references is not recognised', [R.parse_references(x)[0] for x in ('', 'Hello world', '<html></html>', '{"a": 1}', '\ufeff')], [None] * 5)

# ── EndNote, tagged format ──
enw = """\ufeff%0 Journal Article
%A Smith, John A.
%A Jones, Mary
%A World Health Organization,
%T A study of
 questions
%J Journal of Testing
%D 2020
%V 12
%N 3
%P 45-67
%R 10.1000/xyz123
%F smith2020

%0 Edited Book
%E Ed, Ann
%T Edited things
%I Brill
%D 2019

%0 Book Section
%A Roe, R.
%E Ed, Ann
%E Ee, Bo
%T A chapter
%B The book
%P 5-9
%Z in press

%0 Thesis
%A Pat, Lee
%T A thesis
%I Uni X
%9 Master's thesis
%D 2005

%0 Newspaper Article
%A Nobody
%T No year here
"""
e = imp(enw)
check('EndNote: types and authors (a trailing comma marks an organisation); a title over two lines; the label is the key', (e[0]['type'], [p.get('family') or p.get('org') for p in e[0]['authors']], e[0]['title'], e[0]['id'], e[0]['pages'], e[0]['issue']),
      ('article', ['Smith', 'Jones', 'World Health Organization'], 'A study of questions', 'smith2020', '45–67', '3'))
check('EndNote: an edited book (%E are its authors), a chapter (%A authors, %E editors)', ([p['family'] for p in e[1]['authors']], e[1]['type'], [p['family'] for p in e[2]['authors']], [p['family'] for p in e[2]['editors']]), (['Ed'], 'edited', ['Roe'], ['Ed', 'Ee']))
check('EndNote: "in press" in the notes is the year; a thesis has its level and institution; no year is n.d.', (e[2]['year'], e[3]['level'], e[3]['institution'], e[4]['year'], e[4]['type']), ('in press', "Master's thesis", 'Uni X', 'n.d.', 'article'))
check('EndNote: five references, the first begins after a byte order mark', len(e), 5)

# ── RIS ──
ris = """TY  - JOUR
AU  - Smith, John
AU  - Jones, Mary
TI  - On things
JO  - Journal of Things
PY  - 2020///
VL  - 5
IS  - 2
SP  - 10
EP  - 20
DO  - 10.1/abc
UR  - https://example.org/x
ID  - sm20
ER  - 

TY  - THES
AU  - Lee, Pat
TI  - A thesis
PB  - Uni X
M3  - PhD thesis
PY  - 2001/05/01
ER  - 
"""
r_ = imp(ris)
check('RIS: an article (authors, journal, year with slashes, pages from SP and EP, DOI, URL, key)', (r_[0]['type'], [p['family'] for p in r_[0]['authors']], r_[0]['container'], r_[0]['year'], r_[0]['pages'], r_[0]['doi'], r_[0]['url'], r_[0]['id']),
      ('article', ['Smith', 'Jones'], 'Journal of Things', '2020', '10–20', '10.1/abc', 'https://example.org/x', 'sm20'))
check('RIS: a thesis with its level and institution', (r_[1]['type'], r_[1]['level'], r_[1]['institution'], r_[1]['year']), ('thesis', 'PhD thesis', 'Uni X', '2001'))
check('the format is found from what is in the file, not from its name', [R.detect_format(x) for x in ('@book{a,}', ris, enw, 'xx\n@article {k, title={T}}')], ['bibtex', 'ris', 'endnote', 'bibtex'])

# ── setting them beside the references that exist ──
have = [dict(RTR['a1'], id='smith2020'), dict(RTR['b1'], id='brown2015')]
new_text = ('@article{smith2020, author={Smith, John A. and Jones, Mary}, title={A study of questions & answers: 50% of _cases_}, journal={Journal of Testing}, year={2020}}\n'       # the same, same key
            '@article{other, author={Smith, John A. and Jones, Mary}, title={A study of questions & answers: 50% of _cases_}, journal={Journal of Testing}, year={2020}}\n'    # the same, another key
            '@article{brown2015, author={Brown, Pat}, title={A different paper}, journal={J}, year={2015}}\n'                                                                      # another reference, key taken
            '@article{fresh, author={Fresh, Fay}, title={Fresh}, journal={J}, year={2022}}\n'
            '@misc{, author={Nokey, Ned}, title={No key}, year={2021}}\n'
            '@article{fresh2, author={Fresh, Fay}, title={Fresh}, journal={J}, year={2022}}\n'                                                                                     # a duplicate in the file
            '@article{notitle, author={Bad, Bo}, year={2022}}\n')
f_, items = R.parse_references(new_text)
add, rep = R.merge_import(have, items)
check('merge: the statuses', [x['status'] for x in rep], ['duplicate', 'duplicate', 'renamed', 'new', 'new', 'duplicate', 'rejected'])
check('merge: a taken key is replaced by a free one; a missing key is made from author and year; the duplicates name what they duplicate', ([r['id'] for r in add], rep[0]['id'], rep[1]['id'], rep[5]['id']), (['brown2015-2', 'fresh', 'nokey2021'], 'smith2020', 'smith2020', 'fresh'))
check('merge: what exists is not touched', [r['id'] for r in have], ['smith2020', 'brown2015'])
check('merge: all of them, in a second import, are duplicates', set(x['status'] for x in R.merge_import(have + add, R.parse_references(new_text)[1])[1]), {'duplicate', 'rejected'})

print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
