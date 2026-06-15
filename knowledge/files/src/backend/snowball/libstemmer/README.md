---
path: src/backend/snowball/libstemmer/
anchor_sha: e18b0cb7344
loc: aggregate
depth: read
---

# src/backend/snowball/libstemmer/

Aggregate doc for the auto-generated Snowball stemmer C sources imported into
PostgreSQL's tree. Covers 53 per-(encoding, language) stemmer translation units
plus the two small hand-shipped runtime files `api.c` and `utilities.c`.

## Purpose

This directory holds the C implementations of every Snowball stemmer shipped
with PostgreSQL's full-text-search dictionary `snowball`. Each translation unit
is a finite-state suffix-stripping automaton for one **(character encoding,
natural language)** pair:

- Encoding axis: `ISO_8859_1` (Western European Latin-1), `ISO_8859_2` (Central
  European Latin-2), `KOI8_R` (legacy Russian), `UTF_8` (everything else,
  including all non-Latin scripts).
- Language axis: ~30 natural languages (English, French, German, Russian,
  Arabic, Greek, Tamil, Hindi, Yiddish, Armenian, ...). A handful of languages
  ship multiple variants — e.g. `english` (Porter 2 / "english stemmer") vs.
  `porter` (the original 1980 Porter algorithm), and `dutch` vs. `dutch_porter`.

For each (encoding, language) pair, the corresponding `stem_<ENCODING>_<lang>.c`
file exports exactly three entry points:

```
struct SN_env *stem_<ENCODING>_<lang>_create_env(void);
void           stem_<ENCODING>_<lang>_close_env(struct SN_env *z);
int            stem_<ENCODING>_<lang>_stem(struct SN_env *z);
```

These are consumed by `dict_snowball.c` via a generated dispatch table keyed by
`(language, encoding)` — see the existing
`knowledge/files/src/backend/snowball/dict_snowball.c.md` for how PG resolves a
`CREATE TEXT SEARCH DICTIONARY ... TEMPLATE = snowball, Language = 'english'`
clause to one of these `_stem` functions.

## Origin

Upstream is Martin Porter & Richard Boulton's Snowball project
(`https://snowballstem.org/`, source repo at `snowball-tartarus/snowball`). The
algorithms are written in the **Snowball language** (`.sbl` source files) and
compiled to C by the in-tree `snowball` compiler shipped by upstream. PostgreSQL
imports the generated C — not the `.sbl` sources — under this directory.

The two non-generated runtime files are also imported verbatim from upstream:

- `api.c` — implements `SN_env` lifecycle: `SN_create_env`, `SN_close_env`,
  `SN_set_current`. Used by every `stem_*_create_env` / `_close_env`.
- `utilities.c` — implements the shared runtime that the generated automata
  call into: `SN_set_current`, `slice_*`, `find_among`, `eq_s` and friends,
  plus the small string-buffer growth machinery.

## Why we don't write per-file analysis

Every `stem_<ENCODING>_<lang>.c` is **machine-generated** from a `.sbl` source
by the Snowball compiler. They all follow the same syntactic shape:

1. A header comment marking the file as generated.
2. Static `unsigned char` tables (`s_0_0`, `s_0_1`, ...) holding the suffix
   strings the automaton matches against, one set per `among` block in the
   `.sbl` source.
3. Static `struct among` arrays binding each suffix to its replacement /
   action / continuation state.
4. A series of `static int r_<rule>(struct SN_env *z)` functions, one per
   rule label in the `.sbl` source, each calling into `utilities.c` /
   `api.c` helpers (`find_among`, `slice_from_s`, `slice_del`, ...).
5. The exported `stem_<ENCODING>_<lang>_stem` driver that sequences the
   rules.
6. The exported `_create_env` / `_close_env` wrappers around `SN_create_env`
   / `SN_close_env` from `api.c`.

There is no PG-side invariant introduced by any individual stemmer file —
every PG-visible contract lives in `dict_snowball.c`, `api.c`, and
`utilities.c`. The per-stemmer suffix tables matter **semantically** (they
encode which suffixes get stripped for, say, Turkish), but reviewing the
generated C tells you nothing the `.sbl` source wouldn't tell you more clearly.
For that reason we keep each per-file stub to the minimum (encoding, language,
the three entry-point names, pointer back to this README) and do not attempt
a function-by-function walkthrough.

If you actually need to debug a stemmer's behavior:

- Find the `.sbl` source in the upstream Snowball repo for that language.
- Read `dict_snowball.c.md` for how PG calls into the stemmer.
- Read `utilities.c` (this directory) for what `find_among` / `slice_from_s`
  / `slice_del` actually do.

## File naming

```
stem_<ENCODING>_<language>.c     # this directory
stem_<ENCODING>_<language>.h     # src/include/snowball/libstemmer/
```

Encodings: `ISO_8859_1`, `ISO_8859_2`, `KOI8_R`, `UTF_8`.
Languages observed in the file list:

- Latin-1 set: `basque`, `catalan`, `danish`, `dutch`, `dutch_porter`,
  `english`, `finnish`, `french`, `german`, `indonesian`, `irish`, `italian`,
  `norwegian`, `porter`, `portuguese`, `spanish`, `swedish`.
- Latin-2 set: `hungarian`, `polish`.
- KOI8-R set: `russian`.
- UTF-8 set: superset of the above plus `arabic`, `armenian`, `esperanto`,
  `estonian`, `greek`, `hindi`, `lithuanian`, `nepali`, `polish`, `romanian`,
  `russian`, `serbian`, `tamil`, `turkish`, `yiddish`.

Languages whose characters fit inside a single 8-bit codepage get **two**
files: one for the 8-bit encoding (faster, smaller tables) and one for UTF-8
(works regardless of database encoding). Languages outside Latin-1/Latin-2/
KOI8-R only ship the UTF-8 file.

## How regenerated

Regeneration is **manual** and rare — typically only when upstream Snowball
cuts a release with new stemmers or bug fixes. The in-tree helper scripts at
`src/tools/snowball-build/` automate the import: they invoke the Snowball
compiler against upstream `.sbl` sources and drop the generated C here and
matching `.h` files into `src/include/snowball/libstemmer/`. The existing
`src/backend/snowball/README` (the dictionary doc, mirrored at
`knowledge/files/src/backend/snowball/README.md`) is the operational guide for
this process.

PG carries local edits on top of the generated output only where strictly
required for warning-clean builds; whenever possible the import is verbatim.

## Header sibling

Every `.c` here has a matching header at
`src/include/snowball/libstemmer/stem_<ENCODING>_<language>.h` declaring the
three entry points (`_create_env`, `_close_env`, `_stem`). `dict_snowball.c`
includes these headers through a single generated jump table.

## Cross-refs

- `knowledge/files/src/backend/snowball/dict_snowball.c.md` — the SQL-callable
  dictionary handler that wraps these stemmers. Start here if you want to
  understand how PG picks a stemmer at `lookup` / `init` time.
- `knowledge/files/src/backend/snowball/README.md` — the existing PG-side
  operational README for the snowball dictionary, including the regeneration
  workflow.
- Upstream Snowball: `https://snowballstem.org/`.
