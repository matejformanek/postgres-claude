---
source_url: https://www.postgresql.org/docs/current/bki.html
also_referenced:
  - https://www.postgresql.org/docs/current/system-catalog-declarations.html
  - https://www.postgresql.org/docs/current/system-catalog-initial-data.html
fetched_at: 2026-06-06T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 68: System Catalog Declarations and Initial Contents

The chapter every catalog-touching patch needs: how `.h` declarations + `.dat`
initial data become `postgres.bki` and the `*_d.h` headers, and — the part with
the real footguns — the **OID assignment rules**. This is the primary source for
the `catalog-conventions` skill; the thresholds below are verified at the anchor.

## Declarations → BKI build pipeline (68.1)

- Catalog **structure** is declared in specially-formatted C headers under
  `src/include/catalog/` (e.g. `pg_class.h` for `pg_class`), using the `CATALOG()`
  macro and `BKI_*` annotations. [from-docs] [via knowledge/idioms/catalog-conventions.md]
- Catalog **initial data** lives in editable `.dat` files in the same directory
  (e.g. `pg_proc.dat`). [from-docs]
- At build time, the Perl script **`genbki.pl`** (with `Catalog.pm`) turns headers
  + `.dat` files into **`postgres.bki`** *and* a derived **`pg_class_d.h`**-style
  header per catalog containing auto-generated macros. `postgres.bki` is
  release-specific but **platform-independent**, installed under `share/`. [from-docs]
- A backend in **bootstrap mode reads `postgres.bki` during initdb** to create the
  catalogs and load initial data — bootstrapping the system to where it can run SQL.
  `pg_class.h` "must contain an entry for itself, as well as one for each other
  system catalog and index." [from-docs]
- "almost any nontrivial feature addition in the backend will require modifying the
  catalog header files and/or initial data files." [from-docs — exact]

## .dat file conventions (68.2)

- Rows are **Perl array-of-hashref literals**: `{ oid => '1', oid_symbol =>
  'Template1DbOid', datname => 'template1', ... }`. **All values single-quoted**
  (escape `'` with `\`); null is `_null_`; comments on their own `#` lines. [from-docs]
- **All defined columns must be provided** *except* where the `.h` gives a
  **`BKI_DEFAULT(value)`** — then the field may be omitted from the `.dat` entry and
  inherits the default. `reformat_dat_file.pl` strips redundant default-valued
  fields. [from-docs]
- **`BKI_LOOKUP(catalog)`** lets a column hold a **symbolic OID reference** instead
  of a number (on `Oid`/`regproc`/`oidvector`/`Oid[]` columns); `BKI_LOOKUP_OPT`
  also allows `0`/`-`. Type names must match `typname` **exactly** (`int4`, not
  `integer`); functions as `proname` or `proname(argtype,...)`; operators as
  `oprname(left,right)`; opclasses as `am/name`; no schema-qualification (all
  bootstrap objects are in `pg_catalog`). **`genbki.pl` resolves all symbolic
  references at build time** and emits plain numeric OIDs into the BKI. [from-docs]
- **`array_type_oid => nnnn`** in a scalar type's `pg_type` entry auto-generates the
  array type (name = scalar name with `_` prepended; `typelem`/`typarray`
  cross-filled). [from-docs]

## OID assignment — the rules that bite (68.2)

- **OIDs 1–9999 are reserved for manual assignment.** Rows referenced by C code or
  by cross-references need a preassigned `oid => nnnn`; `oid_symbol => Name` mints a
  C macro for it. [from-docs]
  [verified-by-code, source/src/include/access/transam.h:195 —
  `#define FirstGenbkiObjectId 10000`]
- **10000–11999 is genbki's auto-assign range.** "If `genbki.pl` needs to assign an
  OID to a catalog entry that does not have a manually-assigned OID, it will use a
  value in the range 10000—11999. The server's OID counter is set to 10000 at the
  start of a bootstrap run." [from-docs — exact]
- **Pinning at `FirstUnpinnedObjectId = 12000`.** "Objects with OIDs below
  `FirstUnpinnedObjectId` (12000) are considered 'pinned', preventing them from being
  deleted." initdb forces the counter to 12000 before creating unpinned objects;
  normal-operation OIDs are **16384+**. [from-docs]
  [verified-by-code, source/src/include/access/transam.h:196-197 —
  `FirstUnpinnedObjectId 12000`, `FirstNormalObjectId 16384`]
- **The patch-author rule:** "best practice is to use a group of more-or-less
  consecutive OIDs starting with some random choice in the range 8000—9999. This
  minimizes the risk of OID collisions with other patches being developed
  concurrently." After commit, OIDs are renumbered below 8000 (keeping 8000–9999
  free for in-flight patches) — so **OIDs assigned by a patch are NOT stable until
  released**; released manual OIDs are never changed. [from-docs — exact]
- **Helper scripts:** `unused_oids` (prints free OID ranges), `duplicate_oids`
  (detects collisions), `renumber_oids.pl` (renumber out of 8000–9999 post-commit /
  recover from a collision). [from-docs]

## Links into corpus

- [[knowledge/idioms/catalog-conventions.md]] — the corpus idiom this chapter is the
  upstream source for (CATALOG macro, .dat editing, catversion bump checklist).
- catalog-conventions skill — the operational checklist (add a pg_proc.dat builtin,
  bump catversion, regenerate postgres.bki) that operationalizes these rules.
- [[knowledge/subsystems/utils-cache.md]] — the syscache/relcache that serves these
  catalogs at runtime once bootstrapped.

## Gaps / follow-ups

- §68.3–68.6 (bki-format, bki-commands, bki-structure, bki-example) describe the BKI
  command language (`create`/`open`/`insert`/`declare toast`/`build indices`) the
  bootstrap backend executes; only the declaration/data + OID rules are mined here
  (the part patches actually touch). catversion bumping is covered by the
  `catalog-conventions` skill rather than this chapter.
