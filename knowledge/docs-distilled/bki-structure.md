---
source_url: https://www.postgresql.org/docs/current/bki-structure.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §69.2: BKI File Structure

The ordering constraints inside `postgres.bki` — the bootstrap script `initdb`
replays to build a brand-new catalog from nothing. Companion to the
`catalog-conventions` skill, which covers the `.dat`/`.h` side that *generates*
this file.

## What the file is [from-docs]

- `postgres.bki` is the **bootstrap script** for the system catalogs: a sequence
  of low-level `create` / `open` / `insert` / `declare index` / `build indices`
  commands the **bootstrap backend** replays during `initdb` to materialize the
  catalogs in an empty cluster. [from-docs]
  [verified-by-code, source/src/backend/bootstrap/bootparse.y — the BKI grammar;
  bootstrap.c drives the replay]

## The mandatory ordering [from-docs]

The script is not free-form; it must obey a strict sequence:

1. **`create bootstrap`** the handful of *critical* tables — `pg_class`,
   `pg_attribute`, `pg_proc`, `pg_type` — and insert at least their own catalog
   rows. `create bootstrap` **implicitly opens** the table for inserts.
2. Close each, repeat for the other critical tables.
3. **`create`** (without `bootstrap`) the remaining tables, then **`open`** each,
   insert rows, `close`.
4. **`declare index`** and **`declare toast`** for indexes and TOAST tables.
5. **`build indices`** at the very end to populate all declared indexes. [from-docs]

### Why the order is forced [from-docs]

- `open` cannot be used until `pg_class`, `pg_attribute`, `pg_proc`, and `pg_type`
  exist *with proper entries* — because opening any table requires reading its own
  metadata back out of those four catalogs. The bootstrap chicken-and-egg is
  exactly why those four are special-cased with `create bootstrap`. [from-docs]
- `declare index` / `declare toast` need the catalogs created and filled first;
  `build indices` needs every base table populated. [from-docs]
- The docs candidly warn: *"There are doubtless other, undocumented ordering
  dependencies."* [from-docs]

## How it connects to catalog edits [inferred, from-docs]

- `postgres.bki` is **generated**, not hand-edited: `genbki.pl` consumes the
  `src/include/catalog/*.h` definitions and `*.dat` data files to emit it. A new
  builtin (a `pg_proc.dat` row, a new catalog column) flows through `genbki.pl`
  into this BKI script — which is why a catalog change also requires a
  **catversion bump** so a mismatched `postgres.bki` is rejected. [inferred;
  the .dat→genbki.pl→postgres.bki pipeline is the catalog-conventions workflow]

## Links into corpus

- [[knowledge/idioms/catalog-conventions.md]] — the `.dat`/`.h` → `genbki.pl`
  generation side and the catversion-bump rule.
- [[knowledge/docs-distilled/bki.md]] — the parent BKI chapter (command reference).
- [[knowledge/docs-distilled/source.md]] — coding conventions for catalog headers.

## Gaps / follow-ups

- The `genbki.pl` / `.dat` generation pipeline and single-user bootstrap-mode
  invocation are **not** on this page (the WebFetch confirmed it covers only the
  ordering rules); they live in the catalog-conventions idiom + `genbki.pl`
  itself. No per-file corpus doc for `bootparse.y`/`bootstrap.c` yet.
