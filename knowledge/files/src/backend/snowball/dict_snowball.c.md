---
path: src/backend/snowball/dict_snowball.c
anchor_sha: e18b0cb7344
file_count: 1
depth: deep
---

# `src/backend/snowball/dict_snowball.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~362
- **Source:** `source/src/backend/snowball/dict_snowball.c`

PG-authored bridge between the tsearch dictionary API
(`pg_ts_template` / `pg_ts_dict`) and the language-specific
`stem(SN_env *)` functions imported from Snowball under `libstemmer/`.
Two SQL-visible entry points — `dsnowball_init` (dictionary
construction) and `dsnowball_lexize` (per-token stemming) — plus a
static `stemmer_modules[]` table that maps `(language, encoding)`
tuples to the imported `_create_env` / `_close_env` / `_stem`
callbacks. Everything outside this file in the `snowball/` tree is
imported verbatim from upstream and is not to be hand-edited.
[verified-by-code]

## API / entry points

- `Datum dsnowball_init(PG_FUNCTION_ARGS)` — `PG_FUNCTION_INFO_V1`.
  Called by tsearch's `lookup_ts_dictionary_cache` when a dictionary
  is first used. Receives `List *dictoptions`; recognises
  `Language` (mandatory) and `StopWords` (optional). Returns a
  pointer-Datum to a freshly palloc'd `DictSnowball`. Errors with
  `ERRCODE_INVALID_PARAMETER_VALUE` on duplicate or unknown options,
  and propagates whatever error `locate_stem_module` raises for an
  unsupported language [verified-by-code: lines 234-282].
- `Datum dsnowball_lexize(PG_FUNCTION_ARGS)` — `PG_FUNCTION_INFO_V1`.
  Called by tsearch each time a token needs stemming. Receives
  `(DictSnowball *, char *in, int32 len)`. Returns a pointer-Datum
  to a 2-element `TSLexeme` array (palloc'd with `palloc0_array`):
  index `[0]` carries the stemmed lexeme (or stays NULL to signal
  "stopword/drop"); index `[1]` is the zero-terminator the tsearch
  API expects [verified-by-code: lines 284-362].

Both functions are surfaced to SQL via the bootstrap `pg_ts_template`
row written by `snowball_create.pl` (i.e. they are *not* the result
of a `CREATE FUNCTION` — they are wired in at initdb time, like every
other built-in tsearch template). The module also declares
`PG_MODULE_MAGIC_EXT(.name = "dict_snowball", .version = PG_VERSION)`
[verified-by-code: lines 85-92].

## Internal types

### `stemmer_module` — the dispatch-table row

```c
typedef struct stemmer_module
{
    const char     *name;                       /* e.g. "english"     */
    pg_enc          enc;                        /* PG_LATIN1/UTF8/... */
    struct SN_env *(*create)(void);
    void           (*close)(struct SN_env *);
    int           (*stem)(struct SN_env *);
} stemmer_module;
```

Built via the `STEMMER_MODULE(name, enc, senc)` macro at line 105,
which expands `name##_##senc##_create_env` etc. — that is, the
language name and Snowball's own encoding spelling (`ISO_8859_1`,
`ISO_8859_2`, `KOI8_R`, `UTF_8`) are token-pasted to form the
imported symbol names. Adding a new language is a single
`STEMMER_MODULE(...)` row plus an `#include
"snowball/libstemmer/stem_<senc>_<name>.h"` at the top
[verified-by-code: lines 104-106].

The table (lines 108-174) holds **52 entries** for distinct
`(name, enc)` tuples — 17 Latin-1, 2 Latin-2, 1 KOI8-R, 32 UTF-8 —
plus a trailing **`PG_SQL_ASCII` english** sentinel row used as the
"any-encoding" fallback (see invariants below) and a `{NULL, ...}`
list terminator. The `english`-as-`PG_SQL_ASCII` row is intentional:
it lets a `SQL_ASCII` database use the English stemmer even though
no exact encoding match would otherwise be possible
[verified-by-code: lines 167-173].

### `DictSnowball` — the per-dictionary instance

```c
typedef struct DictSnowball
{
    struct SN_env  *z;            /* Snowball stemmer workspace      */
    StopList        stoplist;     /* loaded by readstoplist()        */
    bool            needrecode;   /* re-encode to/from UTF-8?        */
    int           (*stem)(struct SN_env *z);
    MemoryContext   dictCtx;      /* long-lived context for SN_env   */
} DictSnowball;
```

One per `pg_ts_dict` row, kept in the tsearch dictionary cache for
the lifetime of the backend (or until a relevant catalog
invalidation). The `dictCtx` field records `CurrentMemoryContext` at
construction so `dsnowball_lexize` can switch into it before calling
Snowball's `stem()` — which internally `realloc`s its workspace
buffer between calls and would otherwise leak into a short-lived
per-tuple context [from-comment: lines 184-189; verified-by-code:
lines 279, 333-336].

## Control flow

### `dsnowball_init` (lines 234-282)

1. `palloc0_object(DictSnowball)` zero-allocates the struct.
2. Walk `dictoptions` (a `List *` of `DefElem`):
   - `"stopwords"` → call `readstoplist(filename, &d->stoplist,
     str_tolower)`. Duplicate raises `ERRCODE_INVALID_PARAMETER_VALUE`
     "multiple StopWords parameters".
   - `"language"` → call `locate_stem_module(d, lang)`. Duplicate
     raises the matching "multiple Language parameters" error.
   - Anything else → raise "unrecognized Snowball parameter".
3. If no `Language` was supplied, raise "missing Language parameter".
4. Capture `d->dictCtx = CurrentMemoryContext` and return the
   pointer.

### `locate_stem_module` (lines 193-232)

Two-pass search of `stemmer_modules[]`:

1. **Exact-encoding pass.** Match where `m->enc == GetDatabaseEncoding()`
   *or* `m->enc == PG_SQL_ASCII` (treated as a wildcard), with
   case-insensitive `pg_strcasecmp` on `m->name`. On hit:
   `d->stem = m->stem; d->z = m->create(); d->needrecode = false`.
2. **UTF-8 fallback pass.** If no exact match, look for any
   `m->enc == PG_UTF8` with the right language. On hit: same
   assignment as above but `d->needrecode = true` — meaning
   `dsnowball_lexize` will round-trip the token through
   `pg_server_to_any` / `pg_any_to_server` to make UTF-8 the wire
   format for the stemmer.
3. No match → `ereport(ERROR, ERRCODE_UNDEFINED_OBJECT, "no Snowball
   stemmer available for language \"%s\" and encoding \"%s\"")`.

### `dsnowball_lexize` (lines 284-362)

1. `txt = str_tolower(in, len, DEFAULT_COLLATION_OID)` — note this
   uses `DEFAULT_COLLATION_OID`, *not* the per-dictionary collation
   (tsearch dictionaries do not have one); lowercase folding is
   collation-independent for the stemmer's purposes
   [verified-by-code: line 290].
2. Allocate `res = palloc0_array(TSLexeme, 2)` (the tsearch
   "lexeme array terminated by NULL `lexeme`" convention).
3. **Long-input fast path (`len > 1000`).** Skip the stemmer
   entirely, set `res->lexeme = txt`, return. Rationale per comment
   lines 293-302: protects against junk strings (base64-like data)
   and against known stemmer pathologies — the Turkish stemmer has
   "an indefinite recursion, so it can crash on long-enough strings"
   [from-comment].
4. **Empty / stopword path.** If `*txt == '\0'` or
   `searchstoplist(&d->stoplist, txt)` returns true, `pfree(txt)`
   and leave `res->lexeme == NULL` — tsearch interprets that as
   "stopword, drop this token".
5. **Stemming path.**
   a. If `d->needrecode`, transcode `txt` to UTF-8 via
      `pg_server_to_any(txt, strlen(txt), PG_UTF8)`. Free the
      original buffer iff the transcoder returned a new pointer.
   b. `MemoryContextSwitchTo(d->dictCtx)` (see "Lifetime" below).
   c. `SN_set_current(d->z, strlen(txt), (symbol *) txt)` hands the
      buffer to Snowball's `SN_env`, then `d->stem(d->z)` invokes
      the language-specific stemmer.
   d. Restore the prior memory context.
   e. If the stemmer produced output (`d->z->p && d->z->l`),
      `repalloc(txt, d->z->l + 1)`, `memcpy(d->z->p)` into it, and
      NUL-terminate. The reuse of `txt` is deliberate: the buffer
      is now owned by the lexize caller's context, not the dict
      context.
   f. If `d->needrecode`, reverse-transcode back to server encoding
      with `pg_any_to_server`, same conditional `pfree` pattern.
   g. `res->lexeme = txt`.
6. `PG_RETURN_POINTER(res)`.

## Lifetime / memory model

There are two memory contexts in play, and confusing them is the
trap this file is designed to avoid:

- **Per-lexize context** — whatever tsearch's caller has set.
  Short-lived: typically per-tuple or per-token. The returned
  `TSLexeme *res` and `res->lexeme` are allocated here so they get
  reclaimed naturally [verified-by-code: lines 291, 358].
- **Per-dict context (`d->dictCtx`)** — captured at `init` time, so
  it is whatever long-lived context tsearch was using when it built
  the cache entry. The `SN_env *z` and the workspace buffer
  Snowball maintains internally between calls both live here. The
  switch happens around the `SN_set_current` / `d->stem` /
  workspace-grow window only — *not* around the encoding round-trip
  or the result copy [verified-by-code: lines 332-336].

The comment block at lines 184-189 is the explicit statement of
why: *"snowball saves alloced memory between calls, so we should
run it in our private memory context. Note, init function is
executed in long lived context, so we just remember
`CurrentMemoryContext`."* [from-comment].

## Invariants

- **`d->stem` is set exactly once, by `locate_stem_module`.**
  `dsnowball_init` checks `if (d->stem)` to detect a duplicate
  `Language` option, and `if (!d->stem)` to detect a missing one
  [verified-by-code: lines 259, 274].
- **`d->needrecode` is `false` only when the stemmer's compiled
  encoding equals the database encoding (or the stemmer was the
  `PG_SQL_ASCII` wildcard).** Otherwise it's `true` and the
  per-token UTF-8 round-trip is mandatory. There is no per-token
  caching of the recoded buffer — every call pays the transcode cost
  twice (in and out) [verified-by-code: lines 207-209, 222-224].
- **`stemmer_modules[]` is null-terminated** (`{NULL, 0, NULL, NULL,
  NULL}` at line 173). Both passes of `locate_stem_module` rely on
  the terminator to exit.
- **The encoding sentinel `PG_SQL_ASCII` is treated as "any
  encoding" by the first-pass match** (line 204). Only English
  carries this sentinel today (line 171); other languages do not get
  a `PG_SQL_ASCII` row.
- **The `SN_env *z` is owned by `DictSnowball` for the cached
  dictionary's lifetime.** There is no path that calls
  `m->close(d->z)` — the `close` callback in `stemmer_module` is
  collected (line 100) but never invoked here. The expectation is
  that the per-dict context is reset/dropped as a whole when the
  cache entry is invalidated, which frees the workspace as a
  by-product.
- **Return convention:** `TSLexeme`-array with `res[0].lexeme == NULL`
  means "drop the token (stopword or empty)". `res[0].lexeme != NULL`
  with `res[1].lexeme == NULL` (the zero-terminator from `palloc0_array`)
  means "single replacement lexeme".

## Error paths

| Site | Errcode | Trigger |
|---|---|---|
| `dsnowball_init` line 251 | `INVALID_PARAMETER_VALUE` | `StopWords` specified twice. |
| `dsnowball_init` line 260 | `INVALID_PARAMETER_VALUE` | `Language` specified twice. |
| `dsnowball_init` line 267 | `INVALID_PARAMETER_VALUE` | Unknown dictionary parameter. |
| `dsnowball_init` line 275 | `INVALID_PARAMETER_VALUE` | `Language` not supplied. |
| `locate_stem_module` line 228 | `UNDEFINED_OBJECT` | No stemmer matches `(lang, GetDatabaseEncoding())` even via the UTF-8 fallback. |

All paths use `ereport(ERROR, ...)`. There is no soft-error
(`escontext`) handling here: tsearch dict construction is not a
soft-error site.

## Performance notes

- The two-pass scan in `locate_stem_module` is O(N) over the 53-row
  `stemmer_modules[]` table per `init`. This runs once per cached
  dictionary; not a hot path.
- `dsnowball_lexize` is a hot path. The dominant cost is usually
  the stemmer itself, but two structural overheads are worth noting:
  - Every call does `str_tolower(in, len, DEFAULT_COLLATION_OID)` —
    locale-aware lowercase. For multi-megabyte text streams this
    can dwarf the stemmer in `SQL_ASCII` databases where the stemmer
    is a no-recode trivial lookup.
  - When `d->needrecode`, two transcodes per token. Cost is roughly
    proportional to token length but is paid even when the stemmer
    leaves the token unchanged.
- The `len > 1000` cutoff bypasses both the stemmer and the
  stoplist scan. Stoplists are normally small enough that this
  doesn't matter, but it does mean *very long* "words" can sneak
  past the stopword filter.

## Related files

- `source/src/backend/snowball/libstemmer/api.c` — provides
  `SN_set_current`, the `SN_env *` allocator, and the workspace
  buffer's `realloc` strategy.
- `source/src/include/snowball/libstemmer/snowball_runtime.h` —
  the `SN_env`, `symbol` typedefs and stemmer-internal macros.
- `source/src/backend/tsearch/ts_locale.c` — `str_tolower` lives
  here.
- `source/src/include/tsearch/ts_public.h` — `TSLexeme`, `StopList`,
  `readstoplist`, `searchstoplist` declarations.
- `source/src/backend/snowball/snowball_create.pl` — emits the
  bootstrap `pg_ts_dict` / `pg_ts_template` rows that point at
  `dsnowball_init` / `dsnowball_lexize`.

## Cross-refs

- [README.md](README.md) — the snowball directory overview that
  covers the 111 autogenerated companion files.
- [`knowledge/subsystems/include-tsearch.md`](../../../../subsystems/include-tsearch.md)
  — the tsearch dictionary API this file implements.
- [`knowledge/files/src/backend/tsearch/dict.c.md`](../tsearch/dict.c.md)
  — the user-defined-template peer that uses the same shape.
