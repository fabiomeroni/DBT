# The project folder

Everything that is specific to **one language, or one group of languages**, lives here and in the data files it
points to. The code (`app.py`, the pages, the stylesheet) knows no language: to build a DBT for another language,
you change this folder and your data, not the code.

## `project.json`

| field | what it is |
|---|---|
| `id` | a short identifier of the project |
| `name` | the name in the top bar (e.g. `DBT Gaua`) |
| `titleSuffix` | what follows the page name in the browser tab (`Comparative Dictionary — <titleSuffix>`) |
| `homeTitle` | the browser title of the home page |
| `nav` | the small label at the right of the top bar, for `home`, `about`, `dictionary`, `grammar`, `texts`. `{n}` is the number of languages; `{languages}` is that number with the word, in the singular or plural (`1 Language`, `5 Languages`) |
| `languages` | the project's languages, **in the order they are shown** (see below) |
| `headwordLanguage` | the language whose forms the dictionary opens on, and that names new entries |
| `recordings` | `author` and `year` shown for recordings whose XML does not say |
| `latex` | `title`, `subtitle` and `author` of the LaTeX export (LaTeX source: write `\&` for &) |
| `footer` | the line at the bottom of the home and about pages (inline HTML). Leave empty for no footer |
| `redirects` | old page names that now live elsewhere, e.g. `{"gaua.html": "about.html"}` |
| `files` | (optional) where the data lives, if it is not in the standard places below: `dictionary`, `fieldnotes`, `grammarDir`, `recordingsDir`, `imagesDir`, `pagesDir`, `orthography`, `seedPhonetic` |
| `legacyFiles` | (optional) the places where an older version of the project kept some of its data, as `{"dictionary": "dbt_dictionary.xml", "recordingsDir": "transcribed_narratives"}`. The first time the server starts and finds one of them, it moves that data into the project folder (see "Where the data is") |
| `grammaticalDomains` | (optional) the semantic domains that mark **grammatical** entries (markers, pronouns, TAMP forms …), e.g. `["Grammar"]`: the default. In the grammar, the chip of such an entry shows all its forms; see "The dictionary" below |

Each language has:

| field | what it is |
|---|---|
| `code` | a short code (lower case letters, digits, `-` `_`). It is what the dictionary XML writes in `langue="…"` |
| `name` | the name shown on the site |
| `abbr` | the abbreviation used in the interlinear lines |
| `color` | the default colour, `#rrggbb`. The author can change it in the dictionary's Settings |
| `aliases` | the other codes by which texts name the language (e.g. ISO 639-3 or Pangloss: `tgs`, `wwo`) |

`project.json` is read when the site starts: restart after editing it.

## How many languages?

Any number, from one up. With **one** language the language selectors disappear (the headword-language buttons,
the Texts filter, the grammar's language toggles) and the text views show no language label in front of the single
row. With several, every view has a row or button per language, in the order of `languages`.

New languages go at the **end** of the list: column keys that texts have stored are read with the new number of
languages (the added language simply has an empty slot). Do not reorder or remove languages of a project that
already has glossed texts.

## `orthography.json`

The default correspondences between the orthography and the IPA (it feeds the IPA suggestions and the reading of
IPA). The author edits them in the dictionary's Settings; what they save there overrides this file. Without this
file the table is empty. `previousDefaults` lists tables an earlier release shipped: a Settings file saved
unchanged from one of them is ignored, so the current default applies.

## `seed-phonetic-forms.json`

Optional: the IPA the author gave for dictionary entries that were written before entries had a phonetic form,
as `{entry id: {language code: IPA}}`. They are used (as confirmed) only while the entry still has that form.

## `pages/home.json` and `pages/about.json`

The prose of the **home page** and of the **about page** (the page about the place and its languages). The layout is
code; the content is yours. Paragraphs are written in inline HTML (`<strong>`, `<em>`, links). A page whose file is
missing is simply left out: without `home.json` the home page has no map section, without `about.json` there is no
about page (the language strip on the home page then points to the dictionary).

In any paragraph, `{languages.count}` becomes the number of languages in words (`five`) and `{languages.list}` the
list of their names (`<strong>Nume, Dorig</strong>, and <strong>Lakon</strong>`).

**`home.json`**

| field | what it is |
|---|---|
| `byline` | the line under the title |
| `intro` | a list of paragraphs about the languages, after the standard text about the Boasian trilogy |
| `cards` | `grammar`, `texts`, `dictionary`: the sentence in each of the three cards (a generic one is used if missing) |
| `map` | the section with a map: `title`, `text` (paragraphs), `credit`, `image`, `imageAlt`, `moreLabel` (the link to the about page). Leave it out for no map |

**`about.json`**

| field | what it is |
|---|---|
| `tabTitle`, `title`, `subtitle` | the browser tab, the heading and the line under it |
| `sidebarImage`, `sidebarImageAlt` | the picture in the sidebar |
| `infobox` | `caption` and `rows` (a list of `[label, value]`), shown in the section flagged `infobox` |
| `sections` | a list of `{id, title, tocLabel, text: [paragraphs], infobox?, languageSections?}`. The section flagged `languageSections` is followed by one block per language of the project |
| `languages` | for each language **code**: `badge` (e.g. `~700 speakers`), `meta` (a list of short notes) and `text` (paragraphs). A language with nothing here still gets its block, with its links |

Image files are named as they sit in the site folder for now (`gaua_map.png`).

## The dictionary: entries, cognates, etymologies and senses

One entry (`<EntréeLexicale>`) is a **headword with its cognates**. The dictionary shows it in the **headword language** that is
chosen: only the entries that have a form in that language are listed, with that form as the headword.

- **Cognates, not parallels.** An entry shows, from the other languages, only the forms that are cognate with the headword: the
  languages of its etymology (`<Étymologie><Étymon langues="aa cc">`). Words that merely mean the same are not parallels of the
  entry (they are parallels for one sense only): they are found in the examples, and each stays an entry of its own language.
  An etymon may name its cognates without knowing the proto-form (it then has only `langues`). An etymon with no `langues`
  attribute (older data) applies to every language. An entry that names no cognates shows none.
- **Etymology belongs to forms.** The etymon that applies to the headword's language is shown, followed by its **cognates**.
  An entry may have several etymons for different groups of languages; a language belongs to one of them only.
- **Senses belong to languages.** `<Sens langues="aa cc">` is shown only for those languages; without the attribute a sense
  applies to all of them. Senses are numbered 1, 2 … among those shown.
- **Chips in the grammar.** `{{entry: id}}` shows, for **grammatical** material (an entry whose semantic domain is one of
  `grammaticalDomains`, default *Grammar*), all its forms, one slot per language. For **lexical** material (every other domain) it
  shows only the cognates (the union of the languages of its etymons) or, if none are named, the form in the project's headword
  language. The LaTeX export lists the same forms. To make a word's chip show its cognates, set its cognates in the dictionary.
- **Two ways to list.** The *List* switch in the sidebar shows the dictionary as **Entries** (each headword with its etymology,
  cognates and senses) or as **Senses** (each meaning, with the headwords of the language that have it). The choice is kept in
  the address (`?mode=senses`) and remembered in the browser.
- **In the editor** (author mode) the window opens on the headword: its form and IPA, then **Cognates**: tick a language and write
  its form; then the senses (each with a tick per language) and, optionally, the proto-form. Forms that are not cognates are not
  asked for: a form already stored in the entry stays in the data, is listed in a note, and shows under its own language (the
  author sees a line "Not cognates, so not shown here" on the entry, with a link to set the cognates). For a project with one
  language there is nothing to tick.

## `references.json` (the bibliography)

The author adds, changes and deletes references on the **References** page (a form per work). They are stored here, as
what was typed (type, authors, year, title, journal or book, pages, DOI ...); the APA 7 text is made when it is shown, so it
can never go out of step. The grammar cites a reference by author and year, as one writes it in a text:
`{{source: Smith 2020}}` gives (Smith, 2020), `{{source: Smith 2020, p. 12}}` adds the page, `{{source: Smith 2020, narrative}}`
gives Smith (2020), and `{{source: Smith 2020; Jones 2019}}` cites two works. Two authors are written `Smith & Jones 2016`, three or
more `Smith et al. 2016`, and a first-author initial separates two authors of the same surname (`A. Smith 2020`). Works by the same
authors in the same year have the letters a, b ... (or the author types 2020b); without the letter the citation is refused as
ambiguous, in a message that names the choices. Each reference also has a **key** (`smith2020`) that can be used in place of the
author and year: it is the safe choice if a name is spelled in several ways. Changing a key on the page updates the citations
in the grammar.

The top-bar label of the page is `nav.references` in `project.json` (default: References).

## Where the data is

Everything the project is made of sits in this folder:

    project/
      project.json            the project
      orthography.json        the orthography <-> IPA table
      seed-phonetic-forms.json
      dictionary.xml          the dictionary (LEXICA XML)
      fieldnotes.xml          the fieldwork questionnaire (optional)
      references.json         the bibliography (edited on the References page)
      grammar/                the grammar, one Markdown file per section
      texts/                  the transcribed texts (Pangloss XML) and "examples from papers";
                              it also receives what the authoring creates: glosses/, confirmed_glosses.json,
                              proposed_entries.json
      images/                 pictures used by the pages and the grammar
      pages/                  home.json, about.json

The author edits dictionary, grammar and glosses through the site, so these files change on the server while it runs:
**back up the `project/` folder** (or commit it) regularly.

### Moving an older installation into this layout

If the project's data used to sit in the site's root, list the old names in `legacyFiles`. The first start then
(1) copies the old locations to `uploads/backups/legacy-layout-<date>/`, (2) copies them into the project folder, the
live version winning over a shipped copy, (3) checks every file, and only then (4) removes the old locations. If anything
fails, the server stops with a message and nothing is deleted. It happens once (`uploads/layout-migrated.json`).
