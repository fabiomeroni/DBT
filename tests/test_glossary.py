"""
Direct tests of glossary.py (no server): the id and the term of an entry, the tooltip made of its definition, the order, and the {{glossary: …}} shortcode
in HTML and in LaTeX.   Run alone with:  python tests/test_glossary.py
"""
import re
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import glossary as G

ok = bad = 0
def check(name, got, want):
    global ok, bad
    if got == want: ok += 1
    else:
        bad += 1; print(f"✗ {name}\n    got : {got!r}\n    want: {want!r}")

check('an id keeps lower case letters, digits, - and _; anything else becomes _; capitals are lowered; nothing valid left is empty', [G.clean_id(x) for x in ('predicate', ' Case Marking! ', 'a/b\\c', '--x--', '$$$', None, 'x' * 90)], ['predicate', 'case_marking', 'a_b_c', 'x', '', '', 'x' * 60])
check('the id made from a term drops the accents', (G.slug_id('Case marking'), G.slug_id('Évidentialité'), G.slug_id('ŋ and ō')), ('case_marking', 'evidentialite', 'and_o'))
check('the term is the first heading, without its markup; without a heading, the id as words', (G.term_of('## Predicate\n\ntext'), G.term_of('\n### *Case* marking {#cm}\n'), G.term_of('no heading here', 'case_marking'), G.term_of('', 'sub-ject')), ('Predicate', 'Case marking', 'Case marking', 'Sub ject'))
md = '## Predicate\n\nThe predicate makes a **statement** about the [subject](http://x.org/a) {{ref: tab1}} — see *this*.\n\n```\ncode here\n```\n\n[see in the Grammaticon](https://g.org/25) ![Logo](logo.png){.small}\n'
check('the tooltip is the definition as plain text: no heading, no shortcode, no image, no code, no link address, no emphasis', G.snippet(md), 'The predicate makes a statement about the subject — see this. see in the Grammaticon')
check('a long definition is cut at a word, with …', (len(G.snippet('## T\n\n' + 'word ' * 100, 50)) <= 51, G.snippet('## T\n\n' + 'word ' * 100, 50).endswith('…')), (True, True))
check('a snippet is made from the source: an entry that refers to itself cannot loop', G.snippet('## A\n\nSee {{glossary: a}} again.'), 'See again.')
check('the order is by term, accents and case ignored', [G.sort_key(t) for t in ('Évidence', 'evidence', 'Zeta', 'alpha')], ['evidence', 'evidence', 'zeta', 'alpha'])
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / 'predicate.md').write_text(md, encoding='utf-8'); (d / 'case_marking.md').write_text('## Case marking\n\nx', encoding='utf-8'); (d / 'Bad Name.md').write_text('## Bad\n', encoding='utf-8'); (d / 'notes.txt').write_text('x')
    lst, by = G.entry_index(str(d))
    check('the entries of a folder: the .md files with a valid id (not other files, not a bad name), sorted by term, with their term and tooltip', ([e['id'] for e in lst], lst[1]['term'], lst[1]['snippet'][:30], sorted(by)), (['case_marking', 'predicate'], 'Predicate', 'The predicate makes a statemen', ['case_marking', 'predicate']))
    (d / 'predicate.md').write_text('## Predicate (changed)\n\nnew', encoding='utf-8')
    check('a file that changed is read again', G.entry_index(str(d))[1]['predicate']['term'], 'Predicate (changed)')
    check('a folder that does not exist has no entry', G.entry_index(str(d / 'nope')), ([], {}))
BY = {'predicate': {'id': 'predicate', 'term': 'Predicate', 'snippet': 'The predicate makes a "statement" & more'}, 'case_marking': {'id': 'case_marking', 'term': 'Case marking', 'snippet': 'x'}}
check('{{glossary: id}} is a link that reads as the term, to the entry, with the beginning of the definition as its tooltip (escaped)', G.expand('<p>See {{glossary: predicate}}.</p>', BY), '<p>See <a class="gloss-link" href="glossary.html#predicate" title="The predicate makes a &quot;statement&quot; &amp; more">Predicate</a>.</p>')
check('{{glossary: id | words}} shows your own words (escaped); the id is found whatever its case and spaces', (re.sub(r'<[^>]+>', '', G.expand('{{glossary: Predicate | the "predicates" & co}}', BY)), re.sub(r'<[^>]+>', '', G.expand('{{glossary:CASE_MARKING}}', BY)), re.sub(r'<[^>]+>', '', G.expand('{{ glossary : predicate }}', BY))), ('the &quot;predicates&quot; &amp; co', 'Case marking', 'Predicate'))
check('the page the links go to can be changed (on the glossary page itself, #id)', 'href="#predicate"' in G.expand('{{glossary: predicate}}', BY, ''), True)
check('an entry that does not exist is a visible error (escaped)', G.expand('{{glossary: x&y}}', BY), '<span class="shortcode-error">Glossary entry not found: x&amp;y</span>')
ex = G.expand('<p><img alt="{{glossary: predicate}}" src="a.png" /></p><pre>{{glossary: predicate}}</pre><p><code>{{glossary: predicate}}</code> and {{glossary: predicate}}</p>', BY)
check('inside a tag (an attribute), in <pre> and in <code> the shortcode is left as written; elsewhere it is a link', ('alt="{{glossary: predicate}}"' in ex, '<pre>{{glossary: predicate}}</pre>' in ex, '<code>{{glossary: predicate}}</code> and <a class="gloss-link"' in ex), (True, True, True))
check('a text with no shortcode is returned as it is', G.expand('<p>a {b} text</p>', BY), '<p>a {b} text</p>')
esc = lambda s: s.replace('&', '\\&')
check('LaTeX: the term, or the words shown, as plain text; ?? if the entry does not exist', (G.latex_text('A {{glossary: predicate}} and {{glossary: case_marking | the case system}} & {{glossary: nope}}', BY, esc),), ('A Predicate and the case system & \\textbf{??}',))
print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
