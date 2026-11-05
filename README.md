# Digital Boasian Trilogy (DBT)
This repository contains the **code**, which knows no particular language, and, in `project/`, the first project built
with it (the five Gaua languages of Vanuatu), which is also the topic of my PhD dissertation *A Digital Boasian Trilogy for describing the languages of Gaua (Vanuatu)*.

## Run it

You need Python 3.10 or later.

    pip install -r requirements.txt
    python app.py

Then open your localhost, which should be at <http://localhost:5000>, in your browser of preference.

## The first time: set up your own project

If the folder `project/` has no `project.json`, the server starts in **setup mode**. In the console it prints a
one-time *setup code*; open the site, and the setup page asks for:

1. the name of your project;
2. your language(s)'s name, abbreviation, code, colour), **or** a small invented example to explore first (a few
   dictionary entries, a short text and a grammar section, so you can see how the three parts connect);
3. the author's password (you will need this for editing stuff directly in the DBT! See below);
4. the setup code from the console (so that nobody else can set the site up before you do from your device).

The server then restarts by itself, and your project is running. Nothing needs to be edited by hand.
(If you start the server with a WSGI server such as gunicorn, restart it yourself once the page says it is done.)

## The author's password

Visitors can read everything; only the **author**, once logged in, can edit. The password is **never written in the
code or in the repository**:

- it is stored as a *hash*, with the key that signs login cookies, in the folder `instance/`, which git ignores and
  the site never serves;
- you set it with `python app.py --set-password` at the setup page (it's normal if you don't see anything while you type, it's hidden!), 
  or later from the dictionary's *Settings* (Author password);
- alternatively, give it to the server through the `AUTHOR_PASSWORD` environment variable (a hash file, if there is
  one, takes precedence);
- repeated wrong guesses lock the address out for ten minutes.
  
If a password was ever published (in a file, a chat, a commit), consider it public forever and choose another.

Important: serve the site over HTTPS when it is on the internet.

## Use it for your own language

Everything specific to a language lives in `project/` (see [`project/README.md`](project/README.md)): the project's
settings (`project.json`: name, languages, wording of the top bar), the orthography table, the prose of the home page
and of the page about the place and its languages (`pages/`), **and the data itself**: `dictionary.xml`,
`fieldnotes.xml`, `grammar/`, `texts/`, `images/`.

The data is added through the site, as the author: a dictionary (`.xml`, or entries typed in the
editor), a corpus of texts (`.xml`, or texts typed in the editor), and a grammar (`.md`, or sections typed in the editor). The author edits it while the server runs,
so **back up `project/`** regularly (or commit it!).

The DBT is built so that, to build a DBT for another language, you change `project/`, not
the code. This is made so that everyone can enjoy the DBT's architecture, which is not 
language specific! 

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

`tests/run_tests.py` checks that the site looks and behaves as it should (screenshots, server responses, every feature
used like any user would), that the code knows no language (other projects run on it: one language, eight languages,
another set of names), that no secret is in the files, and that the first-run setup works. See
[`tests/README.md`](tests/README.md) for more.

## Credits

Proposed by [Fabio Meroni]([project/README.md](https://www.lattice.cnrs.fr/membres/fabio-meroni/)) - Lattice & HéLiCéO (CNRS, ENS-PSL, USN). 

A way to cite the DBT code will come in the future, also with a DOI (Zenodo?), once the first release is out. 
