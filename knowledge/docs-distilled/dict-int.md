---
source_url: https://www.postgresql.org/docs/current/dict-int.html
fetched_at: 2026-07-15T20:50:00Z
anchor_sha: 8f71f64deee6
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.11 dict_int — example full-text-search dictionary for integers"
maps_to_skill: [extension-development, fmgr-and-spi]
---

# Docs distilled — dict_int (integer-controlling text-search dictionary template)

The canonical *tiny* example of a text-search dictionary **template**: it
implements just an `init` and a `lexize` method over the `Ts_dict` interface,
and exists to stop many-distinct-large-integers from bloating a GIN/GiST
full-text index. Because the whole module is ~110 lines it is the cleanest
reference for "how do I write a custom `ts_lexize` dictionary" — the template
that `unaccent` (filtering) and the thesaurus/synonym dictionaries generalize.

## Non-obvious claims

- **Three tuning parameters, defaults `maxlen=6, rejectlong=false,
  absval=false`.** Set in `dintdict_init` at
  `source/contrib/dict_int/dict_int.c:42-44`. [verified-by-code]
- **`maxlen` = max digits kept, not max value.** A token longer than `maxlen`
  digits is *truncated to the first `maxlen` digits* by default —
  `dict_int.c:98` (`if (len > d->maxlen)`) → `dict_int.c:109`
  (`txt[d->maxlen] = '\0'`). `ts_lexize('intdict','12345678')` → `{123456}`.
  [verified-by-code]
- **`rejectlong=true` flips truncation into rejection.** An over-length integer
  becomes a **stop word** — the lexize returns an empty lexeme so it is neither
  indexed nor searchable (`dict_int.c:100`, the `rejectlong` branch inside the
  `len > maxlen` block). This is the "don't index huge numbers at all" mode,
  vs. the default "index a truncated prefix". [verified-by-code]
- **`absval=true` strips a leading sign before applying `maxlen`.**
  `dict_int.c:90` — `if (d->absval && (in[0]=='+' || in[0]=='-'))` advances past
  the sign, so `-1234567` is measured/kept as `1234567`. Without it the sign
  counts toward the digit budget. [verified-by-code]
- **`maxlen` must be ≥ 1** — validated at init with an
  `errmsg("maxlen value has to be >= 1")` (`dict_int.c:54-57`). [verified-by-code]
- **The point is index-size control, not correctness.** The docs frame it as
  "preventing excessive growth in the number of unique words, which greatly
  affects the performance of searching": a numeric-heavy corpus otherwise
  produces one distinct lexeme per distinct integer. [from-docs]
- **It ships as a *template* + a default dictionary instance.** `CREATE
  EXTENSION dict_int` installs template `intdict_template` and dictionary
  `intdict`; you tune via `ALTER TEXT SEARCH DICTIONARY intdict (MAXLEN = 4,
  REJECTLONG = true)` and wire it with `ALTER TEXT SEARCH CONFIGURATION … ALTER
  MAPPING FOR int, uint WITH intdict`. [from-docs]
- **Trusted extension** — installable by a non-superuser holding `CREATE` on the
  database. [from-docs]

## Links into corpus

- `[[docs-distilled/unaccent.md]]` — the *filtering*-dictionary sibling. dict_int
  is a terminal dictionary (emits or stops a lexeme); unaccent is a filtering
  dictionary (rewrites and always passes through). Together they are the two
  smallest complete `TSLexeme`-returning examples.
- `[[docs-distilled/textsearch-dictionaries.md]]` — the interface these
  implement (`init`/`lexize`, the stop-word convention, dictionary chaining).
- `extension-development` / `fmgr-and-spi` skills — dict_int is the minimal
  template for a C dictionary: a `Datum … PG_FUNCTION_ARGS` init that parses
  `DefElem` options and a lexize returning `TSLexeme *`.
