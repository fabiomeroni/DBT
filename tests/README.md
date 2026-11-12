# DBT regression tests

These tests check that the site still looks and behaves exactly as it did, after any change to the code.
They run on a **private copy** of the repository with clean data. Your dictionary edits, glosses, uploads and
settings on the server are never touched.

## What is checked

| suite | what | how |
|---|---|---|
| `visual` | every page (home, about, grammar, dictionary, Texts, the text viewer ...), at 1280 and 600 px, as a visitor and as the author, plus the Settings and entry-editing dialogs | screenshots compared **pixel by pixel** with the baseline |
| `api` | what the server returns: dictionary, texts, grammar, LaTeX export, colours ...; and what a visitor is refused | responses compared with the baseline |
| `generality` | that the code knows no language: source and data files are not served, no Gaua name is left in the code, and **other projects** run on the same code: different names, abbreviations, colours and title; **one language**; **eight languages**; a language added after data was stored; and codes and names with awkward characters (`Ma'a`, `Lo-Toga`, `A&B`) | scripted, on extra copies of the site, each started with its own `project/project.json` |
| `security` | that no password or signing key is written in any file; that the author's password is stored only as a hash; the lock-out after wrong guesses; that a login cookie forged with the old key in the code is useless; the no-password state, `--set-password`, and changing the password from the Settings | scripted, on extra copies of the site |
| `setup` | the first run of a new project: the setup page, the refusals (wrong code, weak password, bad language codes), and both ways of creating a project (your own languages, the starter example), including the restart and a first login | scripted, on copies of the site with no project |
| `concordance` | searching the texts: counts checked against a plain reading of the XML, Unicode (combining marks), words and morphemes, filters, a corpus that changes, glosses and dictionary entries, the page in a browser, CSV, hostile text, narrow screens, one language | scripted, with `tests/test_concordance.py` (direct tests of `concordance.py`) |
| `textstats` | n-grams of the word typed and tokens, types, TTR and Root TTR of every text, collection and language: all counted again independently from the XML, then the Texts page, the viewers and the n-gram view in a browser, phones, one language | scripted |
| `refimport` | importing BibTeX, EndNote and RIS lists (preview, duplicates, renamed keys, Windows-1252, hostile text, size limit, the site's own export read back) and each reference as a file, for visitors and the author, on phones | scripted, with `tests/test_references.py` (the parsers, direct) |
| `refletters` | references with the same authors and year: the author is asked for the letters (suggestion by the order of the grammar's citations), nothing saved until chosen, the grammar's citations follow, edits, imports, no date, the window in a browser and on a phone | scripted, with `tests/test_references.py` |
| `phonotable` | phonological charts: the tab in the grammar editor, suggested and custom rows and columns, an inventory for each language, black / colours / split colours in the preview and on the page, the legend as check boxes that choose the languages shown, insert, update and remove in the section, LaTeX, visitors, one language, phones | scripted, with `tests/test_phonotable.py` (the engine, direct) |
| `ipafont` | the IPA in Charis SIL: the font files and their license served, nothing else of the folder (path tricks), the stylesheet's character ranges (IPA letters yes, ordinary letters and combining marks no), and the fonts the browser really uses in the charts, the dictionary, the editors and in running text | scripted |
| `captions` | Table N above a chart and Figure N below an image, numbered through the whole grammar: an independent count, the order of sections, edits and deletions that shift the numbers, the preview's number, the LaTeX export, the project's own words, and the editor (a chart, an uploaded figure) in a browser | scripted, with `tests/test_captions.py` |
| `xref` | `{{ref: label}}` to tables and figures: the links and their numbers (an independent count), forward and back across sections, in headings, cells, captions, not in code or tags, the dictionary (definitions, notes, senses list) and the click through to the Grammar page, LaTeX, the editor's Label box and Reference menu, labels already taken, an uploaded image's label | scripted, with `tests/test_captions.py` |
| `latex` | the exports: one table for each language (Table 1a, 1b …), `{language}` in the captions, `Tables 1a–e` and `{{ref: cons#drg}}`, the XeLaTeX preamble, the fonts by role (and font names that cannot inject LaTeX), the website unchanged, and the export **compiled with XeLaTeX** (and refused by pdfLaTeX with a clear message): checks the PDF's text and fonts; the compilation checks are skipped if XeLaTeX or `gb4e` is not installed | scripted, needs `xelatex`, `pdftotext`, `pdffonts` for the compilation checks |
| `xmlimport` | the XML import wizard (logic of LExport): the engine's direct tests (`tests/test_xmlimport.py`), the author-only endpoints, tokens, hostile files (external entity, bomb, not XML), the preview that writes nothing, replace and add, the backup, the shipped file never overwritten, and the wizard in a browser from the file to the imported entries, the native-format shortcut and the *Powered by LExport* link; importing examples as a new text (one for each language, numbering that goes on, backups and glosses when replacing) and semantic relations (by identifier or by headword) from the API and the wizard | scripted |
| `relations` | semantic relations: the API (validation of what the editor sends, other relation types never touched, removal with the sense or the entry, the author-only switch that everybody's display follows) and the page (the reverse side drawn, plural labels, the editor's search over senses, add and remove, the switch) | scripted |
| `glossary` | the Glossary: the engine's direct tests (`tests/test_glossary.py`), the tab in every page, the entry *predicate* word for word with its Grammaticon link and logo, the API (public reading, author-only writing, ids, path tricks), entries written with the markup of the grammar (charts, figures, references, the shortcode itself), `{{glossary: id}}` in the grammar, LaTeX and the dictionary, and the page and its editor in a browser (the very toolbar of the grammar, the 📖 menu, add, edit, delete) | scripted |
| `backup` | the backups: the engine's direct tests (`tests/test_backup.py`), the author-only endpoints, the daily snapshot (first request, once a day, skipped when nothing changed, the hour in the name of a second one), the download (byte for byte, manifest, nothing of the backups themselves), a restore from the archive, the reminder (never / ok / due after a week / old after a month), the disposal of snapshots a month old (29 days no, 30 days yes; paths and other files refused), and the button and the panel in a browser on every page, with a narrow screen | scripted |
| `dictionary` | entries listed per headword language, the etymology of a form with its cognates and no other forms, senses per language, the Entries / Senses list, the grammar's chips (cognates for lexical material, all forms for grammatical material), the examples chosen for each sense with {{cite: …}} (display, search, author's window around the headword and its cognates, API rules, a one-language project, hostile input) | scripted, on a dictionary with languages ticked |
| `references` | the bibliography: APA 7 formatting through the server (templates of the UTS APA guide), who may edit, keys and year letters, `{{source: …}}` in the grammar and in the LaTeX export, BibTeX (read by a real parser) and EndNote, hostile input, the author's form in a browser, narrow screens, a project with no references | scripted, with `tests/test_references.py` (direct tests of `references.py`) |
| `migration` | that an installation whose data sits in the old places (live edits included) is moved into `project/` safely: backup first, the live version wins, every file checked, the old places removed only afterwards, done once, and a move that cannot finish deletes nothing | scripted, on copies of the site shaped like a live installation |
| `functional` | the features, used like a person would: editing entries, IPA suggestions, Settings, glossing and confirming texts, the alignment editor, citing in the grammar, exporting | scripted, with assertions |

## Running them

    pip install -r tests/requirements-test.txt
    playwright install chromium

    python tests/run_tests.py                       # everything
    python tests/run_tests.py --only functional     # one suite: visual | api | functional | generality | security | setup | migration | references | dictionary | concordance | textstats | refimport | refletters | phonotable | ipafont | captions | xref | latex | xmlimport | relations | glossary | backup | xmlimport | relations
    python tests/run_tests.py --update-baseline     # record the current behaviour as the new baseline
    python tests/run_tests.py --record-missing      # record only the baselines that do not exist yet (never overwrites)

A failing screenshot is saved with a diff image in `tests/output/diff/`. `tests/output/` is rebuilt at every run.

## The baseline

`tests/baseline/` is the recorded behaviour. Run `--update-baseline` **only** when a change is meant to alter how
something looks or what the server returns. Screenshots depend on the fonts of the machine that drew them, so a baseline
belongs to the machine that recorded it: on a new machine, record your own first (`--update-baseline`, on code you trust).

## Adding a check

Functional checks live in `suite_functional` in `run_tests.py`: use the `check(suite, name, condition)` helper.

The `references` group uses `bibtexparser` to check the BibTeX export if it is installed (`pip install bibtexparser`); without it that one check is skipped.
