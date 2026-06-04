---
source_url: https://www.postgresql.org/docs/current/gin.html
fetched_at: 2026-06-03T19:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 70: GIN Indexes

The GIN (Generalized Inverted Index) chapter — the opclass-author view plus the
fast-update mechanism that dominates GIN's write performance.

## Structure

- **GIN = inverted index over component values.** It stores **(key, posting
  list)** pairs: each distinct key appears *once*, with a posting list of the
  row TIDs that contain it. That is the whole reason one GIN index answers
  "array/jsonb/tsvector contains element X" fast — keys are de-duplicated.
  [from-docs]
- **Two-level internals:** a B-tree over keys (the *entry tree*); each leaf holds
  either an inline *posting list* (few rows) or a pointer to a *posting tree*
  (many rows). [from-docs]
  [verified-by-code, source/src/backend/access/gin/ — `ginentrypage.c` (entry
  tree) + `gindatapage.c` (posting trees) + `ginpostinglist.c` (varbyte-coded
  posting lists), via knowledge/files/src/backend/access/gin/*.md]

## Operator-class support functions

An opclass **must** provide (the contract for indexing a new composite type):

- **`extractValue(itemValue, *nkeys, **nullFlags)`** — break an indexed datum
  into its array of keys. May return no keys.
- **`extractQuery(query, *nkeys, strategy, **pmatch, **extra_data, **nullFlags,
  *searchMode)`** — break the *query* into keys; sets `searchMode` to one of
  `GIN_SEARCH_MODE_DEFAULT` / `GIN_SEARCH_MODE_INCLUDE_EMPTY` /
  `GIN_SEARCH_MODE_ALL` (ALL is slowest — scans every non-null item).
- **`consistent(check[], …, *recheck, …)`** — boolean: does this item match,
  given which keys are present; sets `*recheck` if the heap tuple must be
  re-tested.
- **`triConsistent(check[], …)`** — ternary variant returning over
  `GIN_TRUE`/`GIN_FALSE`/`GIN_MAYBE`; preferred when implementable (lets GIN
  avoid heap rechecks). [from-docs]
- **`compare(a, b)`** — key ordering (or inherited from a btree opclass); nulls
  are never passed.
- Optional: **`comparePartial`** (partial-match scans; return <0 continue / 0
  match / >0 stop), **`options`** (opclass parameters via
  `PG_HAS_OPCLASS_OPTIONS()` / `PG_GET_OPCLASS_OPTIONS()`). [from-docs]
  [verified-by-code, via knowledge/files/src/backend/access/gin/ginlogic.c.md
  (tri-state consistent) + ginscan.c.md (extractQuery driving the scan)]

## Fast update — the write-performance lever

- **`fastupdate` (storage param, ON by default)** routes new entries into a
  **pending list** instead of the main entry tree, turning many small random
  index writes into cheap sequential appends. [from-docs]
- **The pending list is drained** on autovacuum/autoanalyze, on an explicit
  `gin_clean_pending_list()`, or when it exceeds **`gin_pending_list_limit`**
  (GUC, per-index overridable). [from-docs]
  [verified-by-code, via knowledge/files/src/backend/access/gin/ginfast.c.md —
  the pending-list implementation]
- **The cost:** every search must *also* scan the pending list, so a large
  pending list slows reads. The tuning trade is write-amortization vs read
  latency. [from-docs]
- **`gin_fuzzy_search_limit`** (default 0 = no limit) caps result set size,
  returning a random subset above the limit — a relief valve for huge FTS result
  sets; 5000–20000 is the doc's suggested FTS range. [from-docs]

## Built-in operator classes

| Opclass | Operators |
|---|---|
| `array_ops` | `&&`, `@>`, `<@`, `=` |
| `jsonb_ops` (default) | `@>`, `@?`, `@@`, `?`, `?|`, `?&` |
| `jsonb_path_ops` | `@>`, `@?`, `@@` (fewer ops, smaller/faster) |
| `tsvector_ops` | `@@` |

[from-docs]

## Gotchas / limitations

- **Indexable operators must be strict:** null items/queries skip key
  extraction. Null *keys within* a non-null composite are supported (since 9.1);
  placeholder entries are created for null items / items with no keys. [from-docs]
- **Bulk-load tip:** for a big initial load, drop the index and recreate it
  afterward (especially with `fastupdate=off`); `maintenance_work_mem` governs
  build speed. [from-docs]

## Links into corpus

- [[knowledge/files/src/backend/access/gin/ginfast.c.md]] — pending list /
  `fastupdate` / `gin_pending_list_limit` cleanup path.
- [[knowledge/files/src/backend/access/gin/ginget.c.md]] — scan-side
  `consistent`/`triConsistent` evaluation and recheck.
- [[knowledge/files/src/backend/access/gin/ginpostinglist.c.md]] — varbyte
  posting-list encoding (why GIN is compact).
- [[knowledge/files/src/backend/access/gin/README.md]] — the canonical
  entry-tree/posting-tree description.
- [[knowledge/docs-distilled/indexes-types.md]] — where GIN sits among the six AMs.
- [[knowledge/architecture/access-methods.md]] — `IndexAmRoutine` dispatch.
- Skill: `access-method-apis` — implementing a GIN opclass / AM in C.

## Gaps / follow-ups

- The chapter's "Implementation" sub-section detail on concurrency
  (page-deletion, posting-tree splits) is summarized only; the gin/README +
  per-file docs carry it. The `tsvector`/`jsonb` opclass-specific behavior lives
  in the datatype chapters, not here.
</content>
