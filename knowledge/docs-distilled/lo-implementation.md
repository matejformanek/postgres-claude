---
source_url: https://www.postgresql.org/docs/current/lo-implementation.html
chapter: "35.5 Large Objects: Implementation (lo-implementation)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# Large object implementation — lo-implementation

How the libpq/server-side large-object facility stores data: chunked rows in
`pg_largeobject`, B-tree-indexed by chunk number, sparse-file semantics, with
per-object ownership in `pg_largeobject_metadata`. The C side is `inv_api.c`.

## Non-obvious claims

- **A large object is stored as *chunked rows*, not one big value.** Each
  chunk is a row; this is the opposite design from TOAST (which is per-column,
  transparent). Large objects are addressed by `loid` and manipulated through
  the `lo_*` API. [from-docs lo-implementation]
- **Random access is fast because chunks are B-tree-indexed by chunk number.**
  A seek/read/write locates the right chunk via that index rather than scanning.
  [from-docs]
- **Storage is sparse (Unix-sparse-file semantics).** Seeking to offset
  1,000,000 and writing does **not** allocate a megabyte — only the chunks
  covering actually-written ranges exist. Reads of unallocated gaps *before*
  the last existing chunk return zeroes. [from-docs]
- **Per-object ownership + permissions since PG 9.0.** Large objects have an
  owner and a `GRANT`/`REVOKE`-managed permission set: `SELECT` to read,
  `UPDATE` to write or truncate. Only the owner or a superuser may delete,
  comment on, or reassign ownership. [from-docs]
- **`lo_compat_privileges` GUC restores pre-9.0 behavior** — when on, the
  permission checks above are relaxed for backward compatibility. [from-docs]
- **[from prior corpus, not on this page]** The on-disk catalogs are
  `pg_largeobject` (the chunk rows: `loid`, `pageno`, `data`) and
  `pg_largeobject_metadata` (owner + ACL). The chunk size is `LOBLKSIZE`
  (`BLCKSZ/4`, typically 2 KB). This page describes the *behavior*; the
  numbers live in the headers — verify before quoting.

## Links into corpus

- The server-side API implementing chunked read/write/seek/truncate:
  [[knowledge/files/src/backend/storage/large_object/inv_api.c.md]].
- The catalog access layer:
  [[knowledge/files/src/backend/catalog/pg_largeobject.c.md]].
- The contrasting per-column overflow mechanism:
  [[knowledge/docs-distilled/storage-toast.md]] (TOAST) — large objects are the
  *explicit* alternative to TOAST's transparency.

## Caveats / verification

- Page-sourced claims `[from-docs lo-implementation]`. The catalog/`LOBLKSIZE`
  bullet is tagged as off-page corpus knowledge — confirm `LOBLKSIZE` in
  `source/src/include/storage/large_object.h` and the chunk row shape in
  `inv_api.c` at anchor `e5f94c4808fe88c170840ac3a24cdfa423b404fc`.
