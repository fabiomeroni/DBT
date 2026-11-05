# Digital Boasian Trilogy (DBT)

A **grammar**, a **dictionary** and a **corpus of texts** for a language, or a group of languages, kept as one
interconnected resource: every grammatical claim points to the text that illustrates it, every word of a text links
to its dictionary entry, and every dictionary entry shows the sentences where it occurs.

The name comes from Franz Boas, who held that a complete documentation of a language has these three parts.
This repository contains the **code**, which knows no particular language, and, in `project/`, the first project built
with it (the five Gaua languages of Vanuatu).

## Run it

You need Python 3.10 or later.

    pip install -r requirements.txt
    python app.py

Then open <http://localhost:5000>.

## The first time: set up your own project

If the folder `project/` has no `project.json`, the server starts in **setup mode**. In the console it prints a
one-time *setup code*; open the site, and the setup page asks for:

1. the name of your project;
2. your languages (name, abbreviation, code, colour), **or** a small invented example to explore first (a few
   dictionary entries, a short text and a grammar section, so you can see how the three parts connect);
3. the author's password;
4. the setup code from the console (so that nobody else can set the site up before you do).

The server then restarts by itself, and your project is running. Nothing needs to be edited by hand.
(If you start the server with a WSGI server such as gunicorn, restart it yourself once the page says it is done.)

## The author's password

Visitors can read everything; only the **author**, once logged in, can edit. The password is **never written in the
code or in the repository**:

- it is stored as a *hash*, with the key that signs login cookies, in the folder `instance/`, which git ignores and
  the site never serves;
- you set it with `python app.py --set-password` (you type it, hidden), at the setup page, or later from the
  dictionary's *Settings* (Author password);
- alternatively, give it to the server through the `AUTHOR_PASSWORD` environment variable (a hash file, if there is
  one, takes precedence);
- repeated wrong guesses lock the address out for ten minutes.

If a password was ever published (in a file, a chat, a commit), consider it public for ever and choose another.
Serve the site over HTTPS when it is on the internet.

## Use it for your own language

Everything specific to a language lives in `project/` (see [`project/README.md`](project/README.md)): the project's
settings (`project.json`: name, languages, wording of the top bar), the orthography table, the prose of the home page
and of the page about the place and its languages (`pages/`), **and the data itself**: `dictionary.xml`,
`fieldnotes.xml`, `grammar/`, `texts/`, `images/`.

The data is added through the site, as the author: a dictionary (XML in the LEXICA format, or entries typed in the
editor), transcribed texts (XML in the Pangloss format), fieldwork questionnaires, and the grammar written in
Markdown with shortcodes (`{{cite: …}}`, `{{entry: …}}`, `{{example: …}}`). The author edits it while the server runs,
so **back up `project/`** regularly (or commit it).

Nothing else in the repository mentions a language: to build a DBT for another language you change `project/`, not
the code.

## What is where

    app.py            the server (Flask)
    security.py       the password, the signing key, login throttling
    *.html, style.css, auth.js   the pages
    setup.html        the first-run setup page
    starter/          the small example offered by the setup
    project/          everything specific to one project: its settings AND its data (the Gaua project, here)
    instance/         secrets (created on first run; ignored by git)
    uploads/          what the author uploads, and backups (ignored by git)
    requirements.txt  the Python packages
    tests/            the regression tests: `python tests/run_tests.py`

## Tests

`tests/run_tests.py` checks that the site looks and behaves as it did (screenshots, server responses, every feature
used like a person would), that the code knows no language (other projects run on it: one language, eight languages,
another set of names), that no secret is in the files, and that the first-run setup works. See
[`tests/README.md`](tests/README.md).

## Credits

Proposed by Fabio Meroni (CNRS, Lattice) as a proof of concept. The Gaua project: documentation by Alexandre François and Fabio Meroni.
