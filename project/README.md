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
| `captions` | optional: the words of the captions, `table` (default `Table`), `figure` (default `Figure`), `separator` (default ` – `, with its spaces), the plurals `tables` and `figures` (the singular and an s if you do not give them: write `Tableaux` yourself) and `and` (the word between the last two items of a list, default `and`): for a grammar in another language, e.g. `{"table": "Tableau", "tables": "Tableaux", "and": "et", "separator": " : "}` |
| `latex` → `fonts` | optional: the fonts of the LaTeX export by role, `{"body": "…", "headings": "…", "captions": "…", "ipa": "…"}` (plain font names; see *The LaTeX export*) |
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

## Importing an XML dictionary (the wizard)

The **⬆ Upload XML** button of the dictionary (author only) opens a wizard that takes **any XML dictionary**, not only files in the DBT's own format
(LEXICA XML): LIFT (FLEx, WeSay, Lexique Pro), TEI, or a schema of your own. You say once which XML node is what, and the DBT converts the file. The logic is
that of **LExport** (https://lexport-anonymous.streamlit.app/), the tool that converts lexical XML dictionaries into other formats; the wizard says *Powered by LExport*.

1. **File.** Choose the file. XML namespaces (TEI) are removed so that you see plain tag names. A file that is already in the DBT's format says so and can be used
   as it is.
2. **Entries.** Which node wraps each entry. The likeliest one is chosen for you; the first entries are shown as XML. For LIFT and TEI files the whole mapping is
   started for you: check each step.
3. **Headwords.** The node that holds the headword, and what is read from it (its text, an attribute, or the text of a child, as `./text` in LIFT). The **language**
   is a language of the project (all the headwords), or comes from an attribute (`lang`), whose values you map to the project's languages (those you leave
   blank are ignored). Optional: the IPA (LIFT's `nme-fonipa` is the IPA of `nme`); the forms without IPA are derived from your orthography table as usual.
4. **Grammar.** The part of speech (a node, or an attribute such as LIFT's `grammatical-info`, `value`) and a table saying how each value is written in the DBT
   (`Noun` → `n.`); optionally the semantic domain.
5. **Senses.** The sense node (or none: the entry is its own sense), optionally subsenses (they become senses of their own), the definition, the short gloss and
   the notes. Each of these can be **filtered by an attribute**: *only where `lang` is `en`* (the DBT shows English definitions). Samples of what is read are shown
   under each field.
6. **Examples.** If the file has example sentences, you choose to **ignore** them (the default) or to **use** them. If you use them, they become a **text
   of the Texts page**, *Examples from pre-existent dictionary* (on the model of *Examples from papers*), and each sense cites its own examples, so they appear
   under the sense in the dictionary. You say which node is an example, where its sentence is, and where its translation is (filtered by language: only where
   `lang` is `en`); the language of a sentence is the headwords' language, or read from an attribute and mapped (a table lists the values found on the sentences,
   which can be languages no headword has). A text has one language, so with several languages there is one text for each, with the language in its title
   (*Examples from pre-existent dictionary (Nume)*). You can then gloss the sentences like any other text.
7. **Relations.** If the file says that a sense is a **synonym** or an **antonym** of another, you choose to import the relations (the default when the file has
   them) or to ignore them. You say which node is a relation, where its type is (LIFT: the attribute `type` of the node itself) with a table saying what each type
   is in the DBT (*Synonyms* → Synonym, *Antonyms* → Antonym; the others are not imported), where its target is (LIFT: the attribute `ref`), and how the target is
   found: by an **identifier** (the attribute of the entries, such as LIFT's `guid`, and of the senses, such as `id`) or by its **headword**. Targets are resolved after all the entries
   are converted, so a relation can point to an entry that comes later; one that points to nothing is skipped and reported. A relation under a sense belongs
   to it; one under the entry belongs to its first sense.
8. **Etymology.** Optional: the node, the form, the language (a child, or an attribute of the node itself, as LIFT's `source`) and a gloss.
9. **Review.** How many entries will be imported (and with how many senses), which are skipped and why (for instance no headword in a language of the project),
   a **coverage report** (how many entries lack the part of speech, the IPA …, with examples), and the first entries as the DBT will hold them. Choose to
   **replace** the dictionary (the current one is backed up first, in `uploads/backups`) or to **add** to it (identifiers already in use are not reused).
   Nothing is written until you press *Import*.

An imported dictionary is saved as the uploaded dictionary: the file shipped with the project (`project/dictionary.xml`) is never overwritten.

**Replacing and adding.** *Add* goes on in the text of examples that is already there (the new sentences are numbered after the old ones, so the glosses you made
stay valid). *Replace* starts the text again: the old text and the glosses made on it are first backed up (in `uploads/backups`) and the glosses removed, since they
belonged to the old sentences.

**Safety.** Only the author can use the wizard. The file is read without expanding entities or fetching anything (an external entity cannot read a file of the
server), is limited to 60 MB, and is kept for one hour under a random name until the import is made or abandoned. A path typed into the wizard can only look
*inside* the entries.

## Captions: tables and figures, numbered through the grammar

A **phonological chart** is a table and has its **caption above** it, an **image** is a figure and has its **caption below** it. The author writes
only the text; the number is automatic and goes on through the **whole grammar**: the sections in the order of their file names, the tables and
the figures in the order of the text, each kind counted by itself (*Table 1 – …*, *Table 2 – …*, *Figure 1 – …*). When a section gains or loses a
table or a figure, the numbers of the sections after it change, and the page shows them again at once.

- **A chart** has no title. Its **Caption** box (in the *Phonological table* tab) is the text after “Table 3 –”; the preview shows the number the
  chart will have. Left empty, the chart has its number alone. (A chart written before captions existed keeps its old title, as its caption.)
- **A figure** is an image alone on a line: `![the caption](images/map.png)`. The caption is what is between the brackets. The **📷 Image** button of the
  editor uploads the picture and writes the line for you, with the caption ready to be typed over. An image in the middle of a line of text is only an
  image: no caption, no number. (Ordinary Markdown tables are not numbered.)
- **Referring to them: `{{ref: label}}`.** Give a table or a figure a **label**, a short name made of letters, digits, `-` and `_`: a chart has a
  *Label* box in the *Phonological table* tab, a figure takes it after the image, `![the caption](images/map.png){#map}` (an image uploaded from the
  editor gets one made from its file name). Then `{{ref: map}}` in the grammar **or in the dictionary** (a definition or a note) becomes a link that
  reads *Figure 3* or *Table 2*, always with the number the item has now, and goes to it (from the dictionary it opens the Grammar page at that
  table or figure). Several at once: `{{ref: a, b}}` gives "Table 1 and Figure 2". The **🔗 Reference** button of the grammar editor lists everything
  that can be referred to and inserts the shortcode. An unknown label is shown as a visible error; a shortcode inside a code block or in `inline code`
  is shown as written. A label belongs to one item (tables and figures share their names): the chart editor refuses a label that is taken, and the
  first item to use a label keeps it. In the LaTeX export the shortcode becomes the project's word and LaTeX's own number (`\tablename~\ref{…}`,
  with `\label`s in the tables and the figures), so the PDF follows the same numbers.
- **The words** ("Table", "Figure", the separator) are in `project.json` (`captions`, above); the defaults are English.
- **LaTeX:** the charts are `table` environments with the caption above and the images are `figure` environments with the caption below, so LaTeX numbers
  them in the same order; the words and the separator are given to LaTeX (the `caption` package). The images are taken from an `images` folder next to
  the `.tex` file (copy the project's `images` folder there).

## The Glossary

The **Glossary** tab (after *References* in the navigation) holds the **concepts** that the grammar and the dictionary refer to: *predicate*, *omnipredicative*, … An entry has a
**term**, a **definition** and, if you wish, a link to a reference site (for instance the Grammaticon).

- **An entry is a text file** in `project/glossary/`, written with **the markup of the grammar**: the same Markdown, the same editor (toolbar, 📷 images, 🔗 references, the
  *Phonological table* tab) and **every shortcode of the grammar** (`{{source: …}}`, `{{cite: …}}`, `{{example: …}}`, `{{entry: …}}`, `{{ref: …}}`, tables, figures). The file name (without
  `.md`) is the entry's **id** and its first heading is its **term**: `predicate.md` begins `## Predicate`. For example the entry *predicate*:

  ```
  ## Predicate

  The predicate makes a statement … can act as a predicate.

  [see in the Grammaticon](https://grammaticon.clld.org/concepts/25) ![Grammaticon](grammaticon_logo.png){.glossary-logo}
  ```

  (`{.glossary-logo}` makes the logo a line high, after the link; a picture of your own can go in `project/images` or next to the pages, as for the grammar.)
- **Adding, editing, deleting** (author only): *＋ Add entry* asks for the term and makes the id from it (`Case marking` → `case_marking`); *✏ Edit* opens the editor; *🗑 Delete*.
  Under each entry the author sees the shortcode to copy. Entries are listed alphabetically (accents and case ignored) and the sidebar lists the terms.
- **Referring to an entry: `{{glossary: id}}`** in the grammar, in the dictionary (a definition or a note), or in another entry. It becomes a link that reads as the **term**, with the
  beginning of the definition as a tooltip, to `glossary.html#id` (the entry is shown). `{{glossary: id | the words shown}}` shows your own words. An unknown id is shown as a visible
  error; inside a code block or `inline code` the shortcode is left as written. The **📖 Glossary** button of the editors lists the entries and inserts the shortcode.
- **In the LaTeX export** the shortcode is plain text (the term, or the words shown): the Glossary is a page of the site.
- **Settings** (`project.json`): `nav.glossary` is the label at the right of the navigation bar (default *Glossary*); `files.glossaryDir` is the folder (default `project/glossary`).
- **Numbers.** Tables and figures inside an entry are numbered within the glossary (*Table 1* in each entry's own series), not after those of the grammar; `{{ref: label}}` in an
  entry refers to the grammar's tables and figures and goes to the Grammar page.
- **For developers.** The editor is shared by the Grammar and Glossary pages (`editor.js`, and `grammar.css` for the look of the texts), so that both always accept the same markup.

## Semantic relations (synonyms and antonyms)

A sense can be related to another sense as its **synonym** or its **antonym**. Relations belong to **senses**, not to entries: the word *know* has a sense that is a
synonym of one word and another sense that is an antonym of another.

- **In the entry editor** each sense has a *Semantic relations* block: choose the type, type a form or a meaning, and pick the sense you mean in the results (each result is a
  sense: its headword, its number if the entry has several, its gloss). The ✕ removes a relation. A sense is never offered as its own relation.
- **On the page** the relations appear under the sense (*Synonym: …  ·  Antonyms: …*, each a link to the entry). A relation is entered **once**; since both types are symmetric,
  the page shows it on **both** senses. The reverse side is only drawn, never stored.
- **The author's choice:** *Settings → Display → Show the semantic relations* hides them from everybody (the data stays).
- **In the XML:** `<Sens> … <RelationSémantique><Type>synonym</Type><Cible cible="idⓢ2">headword</Cible></RelationSémantique> … </Sens>`, where `cible` is the identifier of the **target
  sense**. Only the two types are shown and edited; a relation of any other type that an older dictionary has is left exactly as it is.
- **When a sense or an entry is removed,** the relations that point to it are removed with it.
- **Import:** the wizard's *Relations* step (below) brings them from LIFT, TEI or any schema.

## The LaTeX export (and the Word and PDF exports to come)

**Tables by language.** On the website a phonological chart is one table with all the languages (the colours tell them apart). In the exports each
language has its own table, in black, in the order of the project's languages, with the rows and columns that are empty for that language left out.
The tables of a chart share its number and are lettered: *Table 1a*, *1b*, *1c*… (a chart with the sounds of a single language is not split and is
*Table 1*). The numbers of the website and of the exports always agree.

- **`{language}` in a caption.** Write it where the name of the language belongs: *Consonant phonemes of {language}*. The website shows the names of the
  languages that have sounds in the chart (*Consonant phonemes of Nume, Dorig, Koro, Olrat and Lakon*); each table of the exports has its own name
  (*Table 1a – Consonant phonemes of Nume*). A caption without `{language}` gets the name in parentheses in the exports (*Table 1a – Consonants (Nume)*).
- **References.** `{{ref: cons}}` is *Table 1* on the website and *Tables 1a–e* in the exports (*1a–b* for two languages); `{{ref: cons#drg}}`, with the
  code of a language, is *Table 1b* in the exports (on the website, where there is one chart, it is *Table 1*).
- **XeLaTeX.** The `.tex` file must be compiled with **XeLaTeX** or LuaLaTeX (twice, for the references): the IPA and the fonts need it. It begins with
  `% !TEX program = xelatex`, which most editors understand (Overleaf: *Menu → Compiler → XeLaTeX*; command line: `xelatex grammar.tex`). With
  pdfLaTeX it stops with a message saying so. The packages it uses (`fontspec`, `gb4e`, `booktabs`, `caption`, `adjustbox`, `newunicodechar`, `titlesec`,
  `hyperref`, `xcolor`, `iftex`) come with TeX Live and MiKTeX (on Debian and Ubuntu, `gb4e` is in `texlive-humanities`). Copy the project's `images`
  folder next to the `.tex` file. If a journal insists on pdfLaTeX, the IPA would have to be converted for it (`tipa`): that is not done.
- **Fonts by role.** In `project.json`, `"latex": {"fonts": {"body": "…", "headings": "…", "captions": "…", "ipa": "…"}}` (plain font names; anything
  else is ignored). Default: Latin Modern for the text, no change for the headings and captions, and for the IPA **Charis SIL**, then Gentium Plus, Doulos SIL
  and DejaVu Serif, whichever is installed on the machine that compiles (if none is, the compilation warns that the IPA letters will be missing). Each IPA
  letter of the document is set in the IPA font wherever it appears, as on the website, the combining marks and the ordinary letters excepted. A font
  that is not installed falls back to Latin Modern, so that the document always compiles.

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
