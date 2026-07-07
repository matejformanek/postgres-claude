---
source_url: https://www.postgresql.org/docs/current/textsearch-indexes.html
fetched_at: 2026-07-06T00:00:00Z
anchor_sha: a8c2547eaac7
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18, §12.9)
primary: false
---

# Docs distilled — §12.9: GIN and GiST Index Types for FTS

FTS works without an index; GIN and GiST are the two accelerators for the
`@@` match operator on `tsvector`. The load-bearing internals fact: **GiST
is lossy** (fixed-size signature with hash collisions → the executor must
recheck the heap), while **GIN is exact** except when the query needs weight
labels the index doesn't store.

## GIN — inverted, exact, the default choice

- Inverted index: one entry per lexeme with a compressed posting list of
  locations; fast for lookups, especially multi-word `@@` queries.
  `[from-docs]`
- Slower to build/update than GiST; build speed scales with
  `maintenance_work_mem`; larger on disk. `[from-docs]`
- Stores lexemes only, **not weight labels** → a *weight-sensitive* query
  (`@@` against a weighted `tsquery`) forces a **heap recheck**. `[from-docs]`
- Opclass `gin_tsvector_ops` (implicit); `tsvector` only. `[from-docs]`

## GiST — signature tree, lossy, needs recheck always

- Each row is reduced to a **fixed-length signature** — a bloom-filter-style
  bit vector where each lexeme is hashed to one bit and the bits are OR-ed
  together. Hash collisions → **false matches**, so GiST is *lossy* and
  PostgreSQL **always rechecks the heap tuple** to drop false positives.
  `[from-docs]`
- Default signature length **124 bytes**, max 2024; longer = fewer false
  matches but bigger/slower index:
  `CREATE INDEX … USING gist (col tsvector_ops (siglen = N))`. `[from-docs]`
- Verified in code: `SIGLEN_DEFAULT = 31 * 4 = 124` bytes; the per-index
  value comes from opclass option `siglen` (falling back to the default).
  `[verified-by-code]`
  source/src/backend/utils/adt/tsgistidx.c:35 (`#define SIGLEN_DEFAULT
  (31 * 4)`), :37-39 (`GET_SIGLEN()` reads the opclass option or
  `SIGLEN_DEFAULT`), :36 (`SIGLEN_MAX = GISTMaxIndexKeySize`).
- GiST build is insensitive to `maintenance_work_mem`, supports `INCLUDE`,
  and indexes **both `tsvector` and `tsquery`** (`gist_tsvector_ops`); the
  random-heap-access cost of false-match rechecking limits its scale.
  `[from-docs]`

## Practical rule

- **Default to GIN** for lookup performance; pick GiST only when index size
  matters and false-match recheck overhead is acceptable. Reduce unique-word
  count (good dictionaries/stemming) to shrink either index. `[from-docs]`

## Links into corpus

- The `@@` operand producers (parser + dictionaries):
  [docs-distilled/textsearch-parsers.md](./textsearch-parsers.md),
  [docs-distilled/textsearch-dictionaries.md](./textsearch-dictionaries.md)
- General GIN / GiST AM internals:
  [docs-distilled/gin.md](./gin.md), [docs-distilled/gist.md](./gist.md)
- GiST tsvector signature code: source/src/backend/utils/adt/tsgistidx.c;
  GIN tsvector support in source/src/backend/utils/adt/tsginidx.c.
- Relevant skills: `access-method-apis` (GIN/GiST opclass registration),
  `executor-and-planner` (the lossy-index recheck path).
