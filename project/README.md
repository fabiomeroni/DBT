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
- **Examples belong to senses.** The author chooses the examples shown under a sense with the same markup as in the grammar, one
  per line, in the sense's *Examples* box of the editor (stored in the sense's `<Exemples>`): `{{cite: fieldnotes#0#d01.Road:02}}`,
  `{{cite: papers#id}}`, `{{cite: recording.xml#sentence}}`. The editor lists the examples already attested for the entry, with a
  button to add each one. A sense with a chosen list shows exactly those examples, and no other sense shows them. A sense with
  none shows the attested examples whose word was glossed like it (an entry with a single sense shows all of its examples).
  Nothing is gathered at the entry level: the author is told, on the entry, when an attested example is shown under no sense.
- **Chips in the grammar.** `{{entry: id}}` shows, for **grammatical** material (an entry whose semantic domain is one of
  `grammaticalDomains`, default *Grammar*), all its forms, one slot per language. For **lexical** material (every other domain) it
  shows only the cognates (the union of the languages of its etymons) or, if none are named, the form in the project's headword
  language. The LaTeX export lists the same forms. To make a word's chip show its cognates, set its cognates in the dictionary.
- **An example** begins with its source, as the sentence is cited (for example *Fieldnotes · D01 ~ Trigeta i mit long rot · d01.Road:02*),
  which is also the link to the sentence in its text.
- **Proposed entries** (words that confirmed texts suggest adding to the dictionary) are the author's worklist: they are shown, and
  served by the API, to the logged-in author only.
- **Two ways to list.** The *List* switch in the sidebar shows the dictionary as **Entries** (each headword with its etymology,
  cognates and senses) or as **Senses** (each meaning, with the headwords of the language that have it, each showing what the entry says about that sense: IPA, part of speech, domain, definition, etymology and cognates, notes and the attested examples). The choice is kept in
  the address (`?mode=senses`) and remembered in the browser.
- **In the editor** (author mode) the window opens on the headword: its form and IPA, then **Cognates**: tick a language and write
  its form; then the senses (each with a tick per language) and, optionally, the proto-form. Forms that are not cognates are not
  asked for: a form already stored in the entry stays in the data, is listed in a note, and shows under its own language (the
  author sees a line "Not cognates, so not shown here" **under each sense**, with a link to set the cognates: it lists the forms
  of the languages *that sense applies to*, since the words that merely mean the same belong to a sense, not to the entry as a whole).
  For a project with one language there is nothing to tick.

## Fonts: the IPA is in Charis SIL

All the IPA of the site is shown in **Charis SIL** (SIL Global, SIL Open Font License; the license is in `fonts/OFL.txt`). The font files are in
the `fonts/` folder and are served by the site itself: visitors need nothing installed, and nothing is asked of Google for it (the other fonts
of the site still come from Google Fonts, as before). Charis SIL has all the IPA, including the tie bars (k͡pʷ, ŋ͡mʷ, ɛ͡a), the superscripts (ᵐb, ⁿd, kʷ)
and the length mark.

- **Where it is used by design:** the IPA beside a headword, the IPA field of the entry editor, the orthography ↔ IPA settings (and their "try it"
  boxes), the list of forms of the IPA → orthography converter, the proto-forms of the etymologies, the phonological charts and the cells where
  their sounds are typed.
- **Everywhere else, automatically:** wherever an IPA letter appears in the site's text, even in a paragraph of the grammar, a concordance line
  or a note, it is drawn in Charis SIL, with no markup: the IPA letters (ɣ ʧ ɪ ʊ ɛ ɔ ʔ ʃ ...), the modifier letters (ʷ ʰ ː), ᵐ ⁿ, and æ ð ø œ ŋ β θ χ.
  Ordinary letters and the combining marks (the macron of ō and n̄) are deliberately **not** in this list, so that the orthography is never split
  between two fonts. (A sound written only with ordinary letters, such as /pata/, stays in the text font: use the IPA parts of the site, or the
  `ipa` class in HTML, for those.)
- **A newer Charis SIL:** replace the four `.woff2` files in `fonts/` by those of the new release (`fonts/README.txt`). The LaTeX export is not
  concerned (its font is chosen in LaTeX).

## Phonological charts (grammar)

In the editor of a grammar section there are two tabs: **Text** and **Phonological table**. The second makes a chart of the **consonants** or of
the **vowels** (each is a chart of its own; a section can have both) without any markup:

- **Columns and rows.** A new chart starts from the suggested order: for the consonants the columns Bilabial, Labiodental, Dental, Alveolar,
  Postalveolar, Retroflex, Palatal, Velar, Uvular, Pharyngeal, Glottal and the rows Plosive, Nasal, Trill, Tap or flap, Fricative, Lateral
  fricative, Approximant, Lateral approximant; for the vowels the columns Front, Central, Back and the rows Close, Near-close, Close-mid,
  Mid, Open-mid, Near-open, Open. Rename, move (↑ ↓), remove (✕) or add rows and columns of your own, with any names (the names are free text: nothing
  is suggested but the standard lists above); *Suggested columns and rows* puts the lists back. The suggested lists are in `phonotable.py` (`DEFAULT_AXES`).
- **Inventories.** The author types the sounds of each language of the project in the cells (separated by spaces: `p b`); a project with
  one language has one grid. A sound is one to sixteen characters (`t͡ʃ`, `kʷ`, `ᵐb` ...).
- **The chart.** One chart for all the languages: a sound that **all the languages that have an inventory share is black**; a sound
  **specific to one language is in that language's colour** (`color` in `project.json`); a sound of **several, but not all, shows their
  colours together** in the one character (it is split into as many coloured parts as there are languages). Under the chart the **legend is a set of check boxes, one for each language**: untick a language to leave its sounds
  out and see only the inventory of the languages of interest. The colours are then worked out again for the languages that remain ticked: black
  for what all of them share (so with a single language ticked its whole inventory is black), the language's colour for what is specific to
  one, their colours together for what is shared by some. The rows and columns stay, so charts stay comparable. (This works in the page, in
  the preview of the editor and for visitors; the LaTeX export prints the full chart.)
  The preview in the tab is made by the server with the same code as the page. In the LaTeX export a sound of several languages is
  printed once for each, in its colour (the graphicx package is loaded).
- **In the text.** *Insert into the text* writes the chart into the section where the cursor is, as a block (`&#96;&#96;&#96;phonotable` ... `&#96;&#96;&#96;`)
  that the tab reads and rewrites: *Update in the text* changes it, *Remove this chart from the text* takes it out. Press *Save & render* to
  keep it. Nothing in the block needs to be typed by hand.

## Searching the texts (the concordance)

The **Search the texts** tab of the Texts page searches every sentence of the corpus (the fieldnotes, the recordings and the examples
from papers, in every language, also those the project does not list) for a string, and shows each occurrence in its context
(key word in context), with the translation and a link to the sentence in its text.

- **The query is a plain string** (a dot is a dot), a word, a morpheme or a phrase. It can be searched **in** the words of the texts, in
  the glosses or in the translations, and matched **anywhere**, as **a whole word** or as **a whole morpheme** (between spaces, `-` or `=`).
  *Ignore case* is on by default; *ignore diacritics* is off, because in the orthography `n` and `n̄` are different letters. A letter and
  its combining-mark spelling count as the same.
- The hits can be narrowed to a language and to some sources, shown with 1 to 25 words of context, sorted by the word before or after,
  and downloaded as a CSV file. The address holds the whole search, so a link can be shared.
- For a word that is glossed, the hit also gives its gloss and, when its form is in the dictionary, the entry and the part of speech.
  The server keeps the corpus as a list of sentences whose words carry such annotations (`concordance.py`): a search on the part of
  speech or on a gloss is the next step, and a tagger or NLTK / spaCy can feed the same list.
- **N-grams.** The *N-grams* tab of the same page lists the runs of 2 to 6 tokens (inside one sentence) that **contain the word, or the
  words, typed**, most frequent first, with their count, the number of sentences and the count by language; the word is highlighted in each,
  and *lines →* opens every occurrence of that n-gram in the concordance (as whole words in sequence, so the counts agree). Tokens are
  words (case and the punctuation at their edges ignored; `va-wē` is one word) or morphemes (the aligned tokens, `va-` `wē`); the n-grams can
  be of the words, of the glosses or of the translations, restricted to a language or to some sources, with a minimum frequency, and
  downloaded as CSV.
- **Lexical diversity.** Each text has, in the upper right corner of its card and of its page, its **tokens**, **types**, **type-token ratio**
  (TTR = types / tokens) and **Root TTR** (Guiraud's index = types / √tokens, which depends less on the length of the text). The Texts
  page gives them for the fieldnotes as a whole and for the recordings as a whole in the corner of each tab; **for the fieldnotes and for a
  fieldnotes text there is a row per language** (the questionnaire is in several languages), and the recordings are also given by language.
  The published examples are a text of their own. A token is a word as above, and types are counted ignoring case; both are computed from the
  texts as they are (`/api/texts/stats`, also by morpheme with `?unit=morpheme`). Compare Root TTR rather than TTR between texts of
  different lengths.
- The corpus is read again whenever a text, a gloss file or the questionnaire changes: nothing to rebuild.

## `references.json` (the bibliography)

The author adds, changes and deletes references on the **References** page (a form per work). They are stored here, as
what was typed (type, authors, year, title, journal or book, pages, DOI ...); the APA 7 text is made when it is shown, so it
can never go out of step. The grammar cites a reference by author and year, as one writes it in a text:
`{{source: Smith 2020}}` gives (Smith, 2020), `{{source: Smith 2020, p. 12}}` adds the page, `{{source: Smith 2020, narrative}}`
gives Smith (2020), and `{{source: Smith 2020; Jones 2019}}` cites two works. Two authors are written `Smith & Jones 2016`, three or
more `Smith et al. 2016`, and a first-author initial separates two authors of the same surname (`A. Smith 2020`). Works by the same
authors in the same year are told apart by letters (2020a, 2020b ...), and **the author chooses which is which**: when a reference is
saved (added, changed or imported) that would share its authors and year with another, the save waits and a window asks for the letters.
It suggests that **a** goes to the reference the grammar cites first (the sections in their order, the citations in theirs), then the others
that it cites, then those not cited yet, the older ones first and the new one last; if none of them is cited yet, give **a** to the one you
will cite first. Nothing is saved until the letters are chosen (Cancel saves nothing), and the citations in the grammar written by author and
year (`{{source: Smith 2020}}`) are changed to the letter of their reference (`Smith 2020a`); citations by key stay as they are. Without the
letter a citation of such a work is refused as ambiguous, in a message that names the choices. Each reference also has a **key** (`smith2020`) that can be used in place of the
author and year: it is the safe choice if a name is spelled in several ways. Changing a key on the page updates the citations
in the grammar.

**Importing a list.** The author can add many references at once with **⬆ Import** on the References page: choose one or more files in
**BibTeX** (`.bib`), **EndNote** (`.enw`, the tagged format that EndNote and many other programs export, and the one this site writes)
or **RIS** (`.ris`), or paste the references. The format is recognised from what is in the file. Nothing is added at once: a **preview**
shows each reference in APA 7 with its status: *new*, *key changed* (the key in the file was already used by another reference, so a free
one was given), *already there* (the same authors, year and title: it is not added again, so importing the same file twice is harmless)
or *not read* (with the reason, for instance that it has no title). Then **Import** adds the new ones. LaTeX accents (`{\c c}`, `{\"o}`),
protective braces and `@string` macros in BibTeX are resolved; a file saved in Windows-1252 is read correctly; a URL that does not
start with http(s) is left out with a warning. A year letter (2026b) is not part of these formats: the page adds the letters itself.

**One reference as a file.** Next to each reference everyone can download it alone as **BibTeX** or **EndNote** (`/api/references/<key>/export/bibtex`
and `.../endnote`), to drop into their own reference manager. The whole list is still on the buttons at the top of the page.

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
