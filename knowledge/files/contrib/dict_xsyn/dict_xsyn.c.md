# contrib/dict_xsyn/dict_xsyn.c

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role

Implements `dict_xsyn` — an extended synonym text-search dictionary
template. Each rules-file line is "word syn1 syn2 …"; on lexize,
the word and/or its synonyms can be matched and/or kept. Backed by a
flat `Syn` array sorted by `strcmp`, looked up with `bsearch`.
[verified-by-code] `source/contrib/dict_xsyn/dict_xsyn.c:77-143`
(read_dictionary), `:201-264` (dxsyn_lexize).

## Public API (SQL-callable)

- `dxsyn_init(internal) → internal` — dictionary template init (`:146-199`).
- `dxsyn_lexize(internal, internal, int4, internal) → internal` —
  lexize hook (`:202-264`).

Options accepted (`:165-192`): `matchorig`, `keeporig`, `matchsynonyms`,
`keepsynonyms` (all bools), `rules` (filename). Unknown name →
`ERRCODE_INVALID_PARAMETER_VALUE`. [verified-by-code]

## Invariants

- Rules file resolved via `get_tsearch_config_filename(filename,
  "rules")` (`:80`) — basename limited to `[a-z0-9_]+` by the same
  ts_utils.c logic that protects unaccent. [verified-by-code]
- Empty lines are skipped (`:98-99`).
- Lines beginning with `#` are skipped because `find_word` (`:50-69`)
  returns NULL for `#`. [verified-by-code]
- Words are lower-cased with `str_tolower(line, …, DEFAULT_COLLATION_OID)`
  (`:101`), so synonym match is collation-independent ASCII-fold.
  [verified-by-code]
- Array growth: `d->syn` doubles from 16 (`:110`) using
  `repalloc_array`. No upper bound. `cur` is `int`, so overflow at
  INT_MAX entries — well beyond MaxAllocSize / sizeof(Syn). [verified-by-code]
- Final sort by `strcmp(key)` (`:139-140`) so `bsearch` in
  `dxsyn_lexize` (`:224`) is O(log N). [verified-by-code]

## Notable internals

- `Syn.value` stores the **entire original lowercased line** —
  `d->syn[cur].value = pstrdup(value)` (`:121`). If the file has K
  lines of average L bytes, total memory is O(K * L) regardless of
  number of synonyms per line. [verified-by-code]
- Per-word duplication: every key on a line gets its own copy of the
  same `value` string (`:121`). 10 synonyms on a line → 10 copies of
  the whole line. [verified-by-code]
- `dxsyn_lexize`: search by lowercased input (`:218`), find matching
  entry, parse `found->value` left-to-right, emit each synonym as a
  `TSLexeme` (`:241-259`). Uses `repalloc` per synonym (`:243`) — N
  reallocs for N synonyms. Result array NULL-terminated (`:260`).
  [verified-by-code]

## Trust-boundary / Phase-D surface

- **Path traversal blocked** — same `get_tsearch_config_filename`
  filter as unaccent. Cannot reference files outside
  `$sharepath/tsearch_data/`. [verified-by-code]
- **Memory growth unbounded** — admin-supplied rules file of N MB
  expands to ~N MB * (avg synonyms per line) inside the per-dict
  cache context. Long-lived because `lookup_ts_dictionary_cache`
  caches. [ISSUE-DoS-low]
- **`str_tolower` runs on every line under DEFAULT_COLLATION_OID**
  — collation behavior may include locale-specific case folding
  (Turkish dotless i, etc.). The matched key uses the same folding,
  so semantics are consistent, but rule files written against one
  collation may misbehave on a server with a different default.
  [ISSUE-correctness-low]
- **`bsearch` over `Syn` requires `key` field** but no NULL guard if
  rules file is empty — `d->len == 0` shortcuts in `dxsyn_lexize`
  (`:211`) before `bsearch`. [verified-by-code, defensive]
- **No mblen awareness in `find_word`** — uses `isspace((unsigned
  char) *in)` (`:56,63`) and `pg_mblen_cstr` to advance, so multibyte
  sequences are not broken in the middle. [verified-by-code]

## Cross-refs

- `source/contrib/unaccent/unaccent.c` — sibling dictionary, shares
  filesystem trust model.
- `source/src/backend/tsearch/dict_synonym.c` — core synonym dict
  (basic, single key per line).
- `source/src/backend/tsearch/ts_utils.c:33-61` — path validation.

<!-- issues:auto:begin -->
- [Issue register — `dict_xsyn`](../../../issues/dict_xsyn.md)
<!-- issues:auto:end -->

## Issues

- `[ISSUE-DoS-low: dict_xsyn loads entire rules file into memory with
  per-key full-line copy; ~K*L*S total bytes for K lines, L line
  length, S synonyms/line] (low)` —
  `source/contrib/dict_xsyn/dict_xsyn.c:118-122`
- `[ISSUE-correctness-low: str_tolower uses DEFAULT_COLLATION_OID,
  not the dictionary's collation; behavior changes silently if
  server default collation differs from when the rules file was
  written] (low)` — `source/contrib/dict_xsyn/dict_xsyn.c:101,218`
- `[ISSUE-robustness-low: no upper bound on d->len; admin-supplied
  100M-line rules file fills heap before any error is raised] (low)`
  — `source/contrib/dict_xsyn/dict_xsyn.c:108-115`
