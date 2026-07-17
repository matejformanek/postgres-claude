---
source_url: https://www.postgresql.org/docs/current/textsearch-features.html
fetched_at: 2026-07-17T20:56:00Z
anchor_sha: 5174d157a038
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "12.4 Additional Features"
maps_to_skill: [type-cache, gin, plpgsql-internals]
---

# Docs distilled — textsearch-features (tsvector/tsquery operators, ts_rewrite, ts_stat)

The algebra over `tsvector` and `tsquery` values: concatenation and weighting of
vectors, boolean/phrase composition of queries, query rewriting (`ts_rewrite`),
the auto-update trigger pair, and corpus statistics (`ts_stat`). These are the
operators an application composes to build weighted documents and expand
synonyms without reindexing.

## Non-obvious claims

- **`tsvector || tsvector` re-bases positions** [from-docs]: every position in
  the right operand is offset by the largest position in the left operand, so
  the concatenation is (nearly) equivalent to `to_tsvector` on the joined text —
  but lets each section use a **different configuration** and its own
  `setweight` before joining. This is the idiomatic way to build a
  title=A / body=D weighted document.
- **`setweight(vec, 'A'|'B'|'C'|'D')` labels positions, and is a no-op on a
  stripped vector** [from-docs] — because there are no positions left to label.
  `D` is default/unshown. Weight labels are what `ts_rank`/`ts_rank_cd`
  multiply against `{0.1,0.2,0.4,1.0}` (see
  `[[docs-distilled/textsearch-controls.md]]`).
- **`strip(vec)` drops ALL positions and weights** [from-docs], yielding a much
  smaller vector. Two consequences: relevance ranking degrades, and **`<->`
  (FOLLOWED BY) can never match a stripped vector** (no positions ⇒ no distance).
  `length(vec)` = count of distinct lexemes.
- **tsquery composition operators**: `q1 && q2` (AND), `q1 || q2` (OR),
  `!! q` (NOT), `q1 <-> q2` (FOLLOWED BY, distance 1). [from-docs]
- **`tsquery_phrase(q1, q2 [, distance])`** builds `q1 <N> q2` for an exact
  lexeme gap `N`. [from-docs] The `<N>` distance is bounded by the same
  `MAXENTRYPOS` ceiling the parser enforces — `l > MAXENTRYPOS` raises "distance
  in phrase operator should not be greater than %d" [[tsquery.c:207]], with
  `MAXENTRYPOS = (1<<14)` = 16384 [[ts_type.h:85]]. [verified-by-code @ 5174d157a038]
- **`numnode(q)` vs `querytree(q)`** [from-docs]: `numnode` counts nodes
  (lexemes+operators) — `0` means the query was all stop words. `querytree`
  returns the **GIN-searchable** portion; it returns literal `T` when the query
  is unindexable (e.g. a bare negation `!defined`), which is the signal an
  application uses to decide whether an index scan is even possible.
- **`ts_rewrite(query, target, substitute)`** substitutes a sub-query in place —
  the run-time synonym/thesaurus mechanism that, unlike a thesaurus dictionary,
  needs **no reindex** to change. [from-docs] Table-driven form
  `ts_rewrite(query, 'SELECT target, substitute FROM aliases ...')` applies a
  rule set row-by-row; use the `@>` (tsquery-contains) operator in the WHERE to
  prune candidate rules, and `ORDER BY` to make multi-rule application
  deterministic.
- **Two built-in trigger functions** [from-docs]:
  `tsvector_update_trigger(tsv_col, 'schema.cfg', text_col, ...)` uses a constant
  config name (must be schema-qualified, e.g. `'pg_catalog.english'`);
  `tsvector_update_trigger_column(tsv_col, cfg_col, text_col, ...)` reads the
  config per-row from a `regconfig` column. Both treat all source columns
  identically — for differential weighting you must write a custom
  BEFORE INSERT/UPDATE trigger doing `setweight(...) || setweight(...)`.
- **Prefer a stored generated column over the trigger** [from-docs]: the docs
  now flag `tsvector_update_trigger` as superseded by
  `GENERATED ALWAYS AS (to_tsvector(...)) STORED`.
- **`ts_stat(sqlquery [, weights]) → (word text, ndoc int, nentry int)`**
  [from-docs] aggregates lexeme frequencies across a corpus: `word` = lexeme,
  `ndoc` = number of documents containing it, `nentry` = total occurrences. The
  optional `weights` string (e.g. `'ab'`) restricts the tally to those weight
  labels. Primary use: finding stop-word candidates and validating a config.

## Links into corpus

- `[[docs-distilled/textsearch-controls.md]]` — ranking consumes exactly the
  weights/positions these operators produce; `strip()` here → `ts_rank_cd`=0 there.
- `[[docs-distilled/textsearch-dictionaries.md]]` — `ts_rewrite` is the
  reindex-free alternative to the thesaurus dictionary described there.
- `[[docs-distilled/textsearch-limitations.md]]` — the `MAXENTRYPOS`/position
  and node ceilings that bound `<->`, `tsquery_phrase`, and query size.
- `plpgsql-internals` skill — the custom weighting trigger is the canonical
  small BEFORE-trigger `plpgsql` function in the FTS docs.

## Code-vs-docs / verification notes

- The `<N>` / `tsquery_phrase` distance ceiling (`MAXENTRYPOS = 16384`) is
  **code-verified** at `5174d157a038` (`tsquery.c:207` + `ts_type.h:85`). The
  operator semantics, `ts_rewrite`, trigger behavior, and `ts_stat` columns are
  `[from-docs]`.
