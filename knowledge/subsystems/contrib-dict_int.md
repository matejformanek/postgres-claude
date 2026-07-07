# contrib-dict_int (text-search dictionary for integers)

- **Source path:** `source/contrib/dict_int/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `dict_int.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

A minimal **text-search dictionary template** for the PG
full-text-search subsystem. Filters integer-typed tokens
during text indexing — discarding integers longer than N
digits, or truncating them to N digits. Used to prevent
huge ID numbers from polluting the lexeme list in
documents that mix prose and code.

This is the **reference implementation** for custom text-
search dictionaries: ~150 LOC total, demonstrates the
full dictionary callback protocol.

## 2. The two callbacks

```c
PG_FUNCTION_INFO_V1(dintdict_init);
PG_FUNCTION_INFO_V1(dintdict_lexize);
```

[verified-by-code `dict_int.c:31-32`]

The PG full-text-search subsystem (`tsvector` /
`ts_lexize` pipeline) loads dictionaries dynamically; each
dictionary provides exactly these two callbacks:

- **`dintdict_init(text[])`** — parse the dictionary's
  options. Returns an opaque state struct.
- **`dintdict_lexize(state, token, length, ...)`** —
  process a token. Returns either an array of replacement
  lexemes (often just one) or NULL (reject the token).

## 3. The init callback

```c
Datum
dintdict_init(PG_FUNCTION_ARGS)
{
    List *dictoptions = (List *) PG_GETARG_POINTER(0);
    DictInt *d = palloc0(sizeof(DictInt));

    /* Process options: maxlen, rejectlong */
    foreach(l, dictoptions) {
        DefElem *defel = (DefElem *) lfirst(l);
        if (strcmp(defel->defname, "maxlen") == 0)
            d->maxlen = atoi(defGetString(defel));
        else if (strcmp(defel->defname, "rejectlong") == 0)
            d->rejectlong = defGetBoolean(defel);
        else
            ereport(ERROR, ...);
    }

    PG_RETURN_POINTER(d);
}
```

(abstracted from dict_int.c)

Configuration is passed as `List *` of `DefElem`. The
init function walks the list, validates options, and
returns the dictionary state to keep around.

## 4. The lexize callback

```c
Datum
dintdict_lexize(PG_FUNCTION_ARGS)
{
    DictInt *d = (DictInt *) PG_GETARG_POINTER(0);
    char *token = (char *) PG_GETARG_POINTER(1);
    int len = PG_GETARG_INT32(2);
    TSLexeme *res;

    /* Only operate on integer tokens */
    if (!is_integer(token, len))
        PG_RETURN_POINTER(NULL);     /* Pass through; let other dict handle */

    if (len <= d->maxlen)
        return token_as_is(token, len);     /* Short enough */

    if (d->rejectlong)
        return reject_token();      /* Drop entirely */
    else
        return truncate_to_maxlen(token, d->maxlen);
}
```

Three behaviors:
- **Token not an integer** → return NULL → next dictionary
  in the chain handles it.
- **Integer within `maxlen`** → keep verbatim.
- **Integer longer than `maxlen`** → either reject or
  truncate based on `rejectlong`.

## 5. Configuration

```sql
CREATE TEXT SEARCH DICTIONARY my_dict_int (
    TEMPLATE = pg_catalog.dict_int_template,
    maxlen = 6,
    rejectlong = false  -- truncate instead of drop
);

CREATE TEXT SEARCH CONFIGURATION my_config
    (COPY = pg_catalog.english);

ALTER TEXT SEARCH CONFIGURATION my_config
    ALTER MAPPING FOR int WITH my_dict_int;
```

Now `to_tsvector('my_config', '1234567890')` produces a
truncated lexeme `123456` rather than the full digit string.

## 6. The dictionary template pattern

`dict_int_template` is a **template** — a record in the
`pg_ts_template` catalog that names the two callback
functions and the dictionary class. Multiple actual
dictionaries can be created from one template with
different options.

The template-vs-dictionary split is the same as
**function template** vs **function**: one template, many
instances with different configurations.

## 7. Other built-in dictionaries

PG ships with several other dictionary templates:

- `simple` — passes everything through (default).
- `synonym` — substitutes synonyms from a file.
- `thesaurus` — multi-word phrase replacement.
- `ispell` / `snowball` — stemming dictionaries for various
  languages.
- `dict_int` — this one.

`dict_xsyn` (extended synonyms; another contrib) is the
companion to `synonym`.

## 8. Custom-dictionary use cases

You'd write a custom dictionary when:
- You need domain-specific token filtering (e.g., "drop
  chemical-formula tokens like `H2SO4`").
- You need a custom synonym source (loaded from a DB
  table, not a file).
- You need a custom stemming algorithm.

`dict_int` is the smallest reference; copy + modify.

## 9. Production-use guidance

- **For real text-search, use snowball** (built-in stemmer
  for many languages).
- **`dict_int` is useful** when documents contain mixed
  prose + code with long numeric IDs.
- **Custom dictionaries can use SPI** — query catalog or
  other tables in init / lexize. But cache results;
  lexize fires per token.

## 10. Invariants

- **[INV-1]** `init` returns the state struct; `lexize`
  receives it on every call.
- **[INV-2]** `lexize` returning NULL passes the token to
  the next dictionary in the chain.
- **[INV-3]** Templates are catalog records; dictionaries
  are instances with options.
- **[INV-4]** Trusted extension; CREATE EXTENSION without
  superuser.

## 11. Useful greps

- The two callbacks:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/dict_int/dict_int.c`
- The template registration SQL:
  `cat source/contrib/dict_int/dict_int--1.0.sql`
- All dictionary templates in PG:
  `grep -n 'TSTemplate' source/src/include/catalog/pg_ts_template.dat | head`

## 12. Cross-references

- `knowledge/subsystems/parser-and-rewrite.md` —
  full-text-search parsing.
- `.claude/skills/fmgr-and-spi/SKILL.md` — dictionaries can
  use SPI for catalog lookups.
- `.claude/skills/extension-development/SKILL.md` —
  CREATE EXTENSION with text-search-template payload.
- `knowledge/subsystems/contrib-pg_trgm.md` — sibling text-
  search contrib; complementary capability.
- `source/contrib/dict_int/dict_int.c` — implementation
  (~150 LOC).
- `source/src/backend/tsearch/` — the TS subsystem.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/dict_int/dict_int.c`](../files/contrib/dict_int/dict_int.c.md) |

<!-- /files-owned:auto -->
