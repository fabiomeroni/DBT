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
print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
