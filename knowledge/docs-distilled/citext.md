---
source_url: https://www.postgresql.org/docs/current/citext.html
fetched_at: 2026-07-14T20:55:00Z
anchor_sha: 1863452a4bfe
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.10 citext — a case-insensitive character string type"
maps_to_skill: [type-cache, collation-provider]
---

# Docs distilled — citext (case-insensitive text via lower()-then-compare)

A case-insensitive `text` variant. Interesting less as an index example than as
a **type whose comparison semantics are collation/`LC_CTYPE`-dependent** — and
as the module the docs now steer users *away from* in favor of nondeterministic
collations. Good cautionary reading for the `collation-provider` skill.

## Non-obvious claims

- **Case-insensitivity is implemented by folding each operand with `lower()`
  then comparing normally** — "essentially, it internally calls `lower` when
  comparing values." There is no special collation magic in the type itself.
  [from-docs]
- **Case-folding is frozen at DB-creation time via `LC_CTYPE`.** Even when a
  column carries an explicit non-default `COLLATE`, the *initial* fold to lower
  case always uses the database's `LC_CTYPE` (as though `COLLATE "default"`);
  the `COLLATE` only affects the post-fold comparison. So `citext` behavior can
  differ across databases with different `LC_CTYPE`. [from-docs]
- **`lower()`-folding is Unicode-incorrect for some cases** — one uppercase
  letter can have two lowercase equivalents; Unicode distinguishes *case
  mapping* from *case folding* and `citext` only does the former. **The docs
  now recommend nondeterministic collations instead** (which also cover
  accent-insensitivity and more Unicode edge cases correctly). [from-docs]
- **Deduplication cost**: only `text` supports B-tree **deduplication**; a
  `citext` B-tree index cannot deduplicate, so it is larger and slower than the
  equivalent `text` index. Every comparison copies + lower-cases the data.
  [from-docs]
- **But it beats the `lower()`-functional-index route on ergonomics**: a
  `citext` column can be a natural case-insensitive `PRIMARY KEY`/`UNIQUE` with
  no functional index, and it is "slightly more efficient than using `lower` to
  get case-insensitive matching." Plain `text` won't use an index for
  case-insensitive search unless you build `CREATE INDEX … (lower(col))`.
  [from-docs]
- **Overloaded operators/functions fold case**: `~`,`~*`,`!~`,`!~*` and
  `~~`,`~~*` (LIKE) and `!~~`,`!~~*`, plus `regexp_match(es)`,
  `regexp_replace`, `regexp_split_to_array/table`, `replace`, `split_part`,
  `strpos`, `translate`. Force case-sensitivity with the regexp `"c"` flag, or
  cast to `text` for the non-regexp ones. [from-docs]
- **Schema/`search_path` dependency**: the `citext` operators must be reachable
  via `search_path` (usually `public`) for a query to resolve to the
  case-insensitive versions. [from-docs]

## Links into corpus

- `collation-provider` skill — citext is the "before" picture; the "after" is
  `[[docs-distilled/collation.md]]` §nondeterministic collations
  (`collisdeterministic = false`), which the docs now prefer. The
  `LC_CTYPE`-frozen-at-createdb caveat ties to `[[docs-distilled/locale.md]]`.
- `[[docs-distilled/multibyte.md]]` — why `lower()` folding is encoding- and
  locale-sensitive.
- `type-cache` — a domain/base type whose operator functions do non-trivial
  work per comparison (copy + fold), a useful counter-example to cheap
  pass-by-value types.
