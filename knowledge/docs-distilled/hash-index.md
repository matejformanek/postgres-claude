---
source_url: https://www.postgresql.org/docs/current/hash-index.html
fetched_at: 2026-06-08T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter: Hash Indexes

The "equality-only, store-just-the-hash" AM. The non-obvious parts are the
four page types, the cached-metapage bucket-mapping trick, foreground bucket
splitting, and the fact that every hash scan is *lossy*.

## On-disk structure — four page types

- **Four page kinds** in a hash index: the **meta page** (page zero, statically
  allocated control info), **primary bucket pages**, **overflow pages**, and
  **bitmap pages** that track which overflow pages have been freed and are
  available for re-use. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/hash/hashpage.c.md]]
  + [[knowledge/files/src/backend/access/hash/hashovfl.c.md]]]
- **Metapage is cached per-backend in the relcache** so ordinary lookups don't
  lock/pin page zero on every operation. The cached copy gives the correct
  bucket mapping *as long as the target bucket hasn't split since the last
  refresh*; on a stale mapping the code refreshes and retries. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/hash/hashutil.c.md]]]
- The metapage carries the **bucket count, `highmask`, and `lowmask`** — the
  three fields needed to map a 32-bit hash code to a bucket number. [from-docs]
- **Within a single index page, entries are kept sorted by hash code** so a
  binary search is possible. There is **no** ordering assumption *across*
  different pages of the same bucket. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/hash/hashsearch.c.md]]]

## Query semantics & limitations

- **Single-column only, no uniqueness checking.** Hash indexes cannot be
  multi-column and cannot enforce UNIQUE. [from-docs]
- **`=` operator only** — strategy number 1 is the sole hash strategy; range
  predicates can never use a hash index. [from-docs]
- **Each index tuple stores only the 4-byte hash value, not the column value.**
  This makes the index much smaller than a btree for long keys (UUID, URL,
  long text) — but it also makes **every hash scan lossy** (the heap tuple must
  be rechecked). Hash indexes can still participate in **bitmap index scans and
  backward scans**. [from-docs]

## Bucket splitting & growth — the operational catch

- **Buckets split incrementally as rows grow:** when a new bucket is added,
  *exactly one* existing bucket is split. The hash→bucket mapping is chosen
  specifically to allow this incremental expansion. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/hash/hashpage.c.md]]]
- **Splitting happens in the foreground**, on the inserting backend's path, so
  it can lengthen user INSERTs. Hash indexes are therefore **not ideal for
  tables with rapidly increasing row counts**. [from-docs]
- A full bucket page **chains overflow pages** locally for that bucket. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/hash/hashovfl.c.md]]]
- **No shrinking:** there is no way to reduce the bucket count; the only way to
  compact a hash index is `REINDEX`. [from-docs]

## Crash safety, VACUUM, deletion

- **Fully crash-safe since PostgreSQL 10** — bucket splits are WAL-logged and
  the split algorithm is restartable if interrupted (pre-10 hash indexes were
  *not* WAL-logged and were unsafe on standbys / after crash). [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/access/hash/hash_xlog.c.md]]]
- **Simple (deferred) index-tuple deletion**, like btree: removes tuples whose
  item-id `LP_DEAD` bit is already set. [from-docs]
- **VACUUM squeezes** index tuples onto as few overflow pages as possible to
  shorten the overflow chain; emptied overflow pages are recycled (via the
  bitmap pages) for reuse by other buckets. [from-docs]

## Ideal workload

- Best for **equality scans on large tables**, SELECT/UPDATE-heavy, with
  **unique or nearly-unique data** (low rows-per-bucket). High-churn,
  fast-growing tables suffer from the foreground-split cost. [from-docs]

## Links into corpus
- [[knowledge/files/src/backend/access/hash/README.md]] — canonical structure description.
- [[knowledge/files/src/backend/access/hash/hashpage.c.md]] — metapage, bucket split, page allocation.
- [[knowledge/files/src/backend/access/hash/hashovfl.c.md]] — overflow-page chaining + bitmap free-tracking.
- [[knowledge/files/src/backend/access/hash/hash_xlog.c.md]] — the PG10 crash-safety WAL records.
- [[knowledge/files/src/backend/access/hash/hashfunc.c.md]] — the hash support functions.
- [[knowledge/docs-distilled/indexes-types.md]] — hash among the six core AMs.
- Skill: `access-method-apis` — implementing a hash opclass in C.

## Gaps / follow-ups
- The exact `hashm_*` metapage struct field names (`hashm_maxbucket`,
  `hashm_highmask`, `hashm_lowmask`, `hashm_spares`, `hashm_mapp`) live in
  `hash.h`; the docs page only names them functionally. Cross-check against the
  per-file hash docs when quoting field-level detail.
