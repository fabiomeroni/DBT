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
| `dictionary` | entries listed per headword language, the etymology of a form with its cognates and no other forms, senses per language, the Entries / Senses list, the grammar's chips (cognates for lexical material, all forms for grammatical material) (display, search, author's window around the headword and its cognates, API rules, a one-language project, hostile input) | scripted, on a dictionary with languages ticked |
| `references` | the bibliography: APA 7 formatting through the server (templates of the UTS APA guide), who may edit, keys and year letters, `{{source: …}}` in the grammar and in the LaTeX export, BibTeX (read by a real parser) and EndNote, hostile input, the author's form in a browser, narrow screens, a project with no references | scripted, with `tests/test_references.py` (direct tests of `references.py`) |
| `migration` | that an installation whose data sits in the old places (live edits included) is moved into `project/` safely: backup first, the live version wins, every file checked, the old places removed only afterwards, done once, and a move that cannot finish deletes nothing | scripted, on copies of the site shaped like a live installation |
| `functional` | the features, used like a person would: editing entries, IPA suggestions, Settings, glossing and confirming texts, the alignment editor, citing in the grammar, exporting | scripted, with assertions |

## Running them

    pip install -r tests/requirements-test.txt
    playwright install chromium

    python tests/run_tests.py                       # everything
    python tests/run_tests.py --only functional     # one suite: visual | api | functional | generality | security | setup | migration | references | dictionary
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
