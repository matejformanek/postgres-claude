---
path: src/include/snowball/
anchor_sha: e18b0cb7344
loc: aggregate
depth: read
---

# src/include/snowball/

Headers that pair with `src/backend/snowball/` — the in-tree Snowball stemmer
used by `tsearch2`'s `snowball` dictionary template. Two layers:

1. **`snowball_runtime.h`** — PostgreSQL's wrapper around Snowball's own
   `libstemmer/snowball_runtime.h`. It pulls in `postgres.h` first, undefs
   `MAXINT`/`MININT`, and re-binds `malloc/calloc/realloc/free` to
   `palloc/palloc0/repalloc/pfree`, so the upstream Snowball C compiles
   unmodified against PG memory contexts. Every backend `*.c` stemmer
   `#include "snowball_runtime.h"` and the build's `-I` lookups land here
   first.
2. **`libstemmer/*.h`** — the upstream Snowball tree, vendored under
   `libstemmer/`. Each `stem_<ENCODING>_<language>.h` is a tiny
   machine-generated declaration of the three SN_env-based entry points
   for one (language, encoding) pair, plus `api.h` (the public
   `SN_env`/`symbol` typedefs) and `libstemmer/snowball_runtime.h` (the
   actual runtime support API the stemmers call into).

## Purpose

For each language Snowball supports, the upstream project generates a
matched pair: `stem_<E>_<L>.c` (the algorithm) and `stem_<E>_<L>.h` (its
three-function declaration). `dict_snowball.c` keeps a static dispatch
table (see `source/src/backend/snowball/dict_snowball.c:60`) keyed on
language string + server encoding; at dictionary init time it picks the
matching `*_create_env` / `*_stem` / `*_close_env` triple. These headers
are what makes that dispatch table compile.

`snowball_runtime.h` (the PG wrapper, NOT the libstemmer/ one) is the
only file in this directory written by PG; everything else is vendored
verbatim from snowballstem.org and re-imported by
`src/tools/snowball/snowball-prepare.sh` whenever Snowball cuts a new
release.

## Files

| File | Encoding | Language |
| --- | --- | --- |
| `snowball_runtime.h` | (PG wrapper) | shared |
| `libstemmer/api.h` | (typedefs) | shared |
| `libstemmer/snowball_runtime.h` | (runtime API) | shared |
| `libstemmer/stem_ISO_8859_1_basque.h` | ISO 8859-1 | basque |
| `libstemmer/stem_ISO_8859_1_catalan.h` | ISO 8859-1 | catalan |
| `libstemmer/stem_ISO_8859_1_danish.h` | ISO 8859-1 | danish |
| `libstemmer/stem_ISO_8859_1_dutch.h` | ISO 8859-1 | dutch |
| `libstemmer/stem_ISO_8859_1_dutch_porter.h` | ISO 8859-1 | dutch_porter |
| `libstemmer/stem_ISO_8859_1_english.h` | ISO 8859-1 | english |
| `libstemmer/stem_ISO_8859_1_finnish.h` | ISO 8859-1 | finnish |
| `libstemmer/stem_ISO_8859_1_french.h` | ISO 8859-1 | french |
| `libstemmer/stem_ISO_8859_1_german.h` | ISO 8859-1 | german |
| `libstemmer/stem_ISO_8859_1_indonesian.h` | ISO 8859-1 | indonesian |
| `libstemmer/stem_ISO_8859_1_irish.h` | ISO 8859-1 | irish |
| `libstemmer/stem_ISO_8859_1_italian.h` | ISO 8859-1 | italian |
| `libstemmer/stem_ISO_8859_1_norwegian.h` | ISO 8859-1 | norwegian |
| `libstemmer/stem_ISO_8859_1_porter.h` | ISO 8859-1 | porter |
| `libstemmer/stem_ISO_8859_1_portuguese.h` | ISO 8859-1 | portuguese |
| `libstemmer/stem_ISO_8859_1_spanish.h` | ISO 8859-1 | spanish |
| `libstemmer/stem_ISO_8859_1_swedish.h` | ISO 8859-1 | swedish |
| `libstemmer/stem_ISO_8859_2_hungarian.h` | ISO 8859-2 | hungarian |
| `libstemmer/stem_ISO_8859_2_polish.h` | ISO 8859-2 | polish |
| `libstemmer/stem_KOI8_R_russian.h` | KOI8-R | russian |
| `libstemmer/stem_UTF_8_*.h` (33 files) | UTF-8 | arabic, armenian, basque, catalan, danish, dutch, dutch_porter, english, esperanto, estonian, finnish, french, german, greek, hindi, hungarian, indonesian, irish, italian, lithuanian, nepali, norwegian, polish, porter, portuguese, romanian, russian, serbian, spanish, swedish, tamil, turkish, yiddish |

Every `stem_*.h` file has the same 14-line shape:

```c
/* Generated from <lang>.sbl by Snowball 3.0.0 - https://snowballstem.org/ */
#ifdef __cplusplus
extern "C" {
#endif
extern struct SN_env * <lang>_<enc>_create_env(void);
extern void <lang>_<enc>_close_env(struct SN_env * z);
extern int <lang>_<enc>_stem(struct SN_env * z);
#ifdef __cplusplus
}
#endif
```

## Why per-file analysis is deferred

The `stem_*.h` files are mechanical artifacts: 14 lines each, identical
structure, names parameterized over `<lang, encoding>`. There is no
PG-specific behavior or invariant in them to document — they exist so
that `dict_snowball.c`'s dispatch table type-checks. Documenting each
one individually would be 55 near-identical pages with zero marginal
information. The single point of variability — which `(language,
encoding)` pairs PG ships — is captured in the table above and in
`source/src/backend/snowball/Makefile` (the canonical list of which
`.sbl` sources get compiled in).

`snowball_runtime.h` (the PG wrapper) and `libstemmer/snowball_runtime.h`
(the upstream runtime API) get their own docs because they're shared
across all stemmers and carry real behavior (palloc redirection, the
`SN_env` shape, slice/cursor primitives).

## Origin

All files except `snowball_runtime.h` are vendored verbatim from the
Snowball upstream project at <https://snowballstem.org/>. They are
re-imported via the helper script in `src/tools/snowball/` whenever a
new Snowball release lands. The current vintage is **Snowball 3.0.0**
(see the auto-generated comment at the top of any `stem_*.h`).

The PG-authored `snowball_runtime.h` is the **only** file in this tree
that's manually maintained — its job is to inject `postgres.h` and
re-bind allocation calls before the upstream `libstemmer/snowball_runtime.h`
is included.

## Cross-refs

- `knowledge/files/src/backend/snowball/README.md` — the matching
  `.c` side (algorithm bodies + dispatch table).
- `knowledge/files/src/backend/snowball/dict_snowball.c.md` — the
  consumer of these headers; builds `SN_env`, calls `*_stem`, manages
  per-dictionary state.
- `knowledge/files/src/backend/snowball/libstemmer/README.md` — the
  same vendored Snowball tree, on the `.c` side.
- Upstream Snowball: <https://snowballstem.org/>.
