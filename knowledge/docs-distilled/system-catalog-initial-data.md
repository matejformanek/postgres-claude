---
source_url: https://www.postgresql.org/docs/current/system-catalog-initial-data.html
fetched_at: 2026-06-14T19:49:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — System Catalog Initial Data (§68.2)

The `.dat` data-file format that seeds built-in catalog rows (pg_proc.dat,
pg_type.dat, …), plus the OID-assignment rules and the genbki.pl/Catalog.pm
toolchain. Docs companion to the `catalog-conventions` skill — the single most
useful page when adding a builtin function/type/operator.

## .dat is a Perl array of per-row hashes

- Each seeded catalog has a `pg_*.dat` = a **`[ { ... }, { ... } ]`** Perl
  literal: one **`{ col => 'value', ... }`** hash per row, comma after each. **All
  values are single-quoted strings**; **`_null_`** is the literal NULL; `#` lines
  are comments. Escaping: a literal backslash in data needs **four** backslashes
  (`\\\\` → bootstrap scanner sees `\\`). [from-docs]

## Metadata keys (not catalog columns)

- **`oid`** — the manually-assigned numeric OID. **`oid_symbol`** — the C macro
  emitted for it (e.g. `Template1DbOid`). **`array_type_oid`** — OID for the
  auto-generated array type. **`descr`** — a description string that genbki
  inserts into **`pg_description`** (or `pg_shdescription` for shared catalogs).
  `reformat_dat_file.pl` keeps these four first, in that order. [from-docs]

## OID ranges — know which band you're in

- **1–9999**: reserved for **manual** assignment (a new builtin picks here).
  **10000–11999**: auto-assigned by genbki to rows lacking an `oid` key.
  **≥12000** (`FirstUnpinnedObjectId`): not for hand assignment. **≥16384**:
  normal runtime user objects. Tools: **`unused_oids`** (find a free range),
  **`duplicate_oids`** (conflict check), **`renumber_oids.pl`** (renumber a
  committed patch's OIDs to avoid collisions). [from-docs]
  [cross: skill `catalog-conventions`]

## BKI_LOOKUP — reference other catalog objects by name, not OID

- A column declared `BKI_LOOKUP(rule)` lets the `.dat` write a **symbolic
  reference** that genbki resolves to a numeric OID: catalog objects by `name`
  (`pg_default`), functions by `proname` or `proname(argtypes)` for overloaded
  ones (`string_to_array(text,text)`), **types by exact `typname`** (`int4`, NOT
  `integer`), operators `oprname(left,right)` (`=(int4,int4)`), opclasses
  `am/object` (`btree/int4_ops`). **`BKI_LOOKUP_OPT`** additionally allows `0`
  (or `-` for `regproc` columns). [from-docs]
- genbki **records these BKI_LOOKUP foreign-key links for a regression test** —
  so a dangling reference fails the build, not runtime. [from-docs]

## Defaults are omitted; the toolchain round-trips them

- If a row's column equals its header `BKI_DEFAULT(x)`, **`reformat_dat_file.pl`
  omits it** to keep `.dat` compact; the default is re-supplied at expand time.
  Editing-default workflow: **`make expand-dat-files`** (write all defaults
  explicit) → change the `BKI_DEFAULT` annotation → **`make
  reformat-dat-files`** (re-elide). Add/remove a column = edit the `.h` then
  `make reformat-dat-files`. [from-docs]
- **Array types** auto-generate: a row with `array_type_oid` makes genbki emit
  the `pg_type` array entry (name = scalar name with `_` prepended), wiring
  `typarray`/`typelem`, copying `BKI_ARRAY_DEFAULT(...)` fields. [from-docs]

## The scripts

- **`genbki.pl`** (with **`Catalog.pm`**) resolves symbolic refs → OIDs,
  auto-assigns 10000–11999 OIDs, detects duplicate OIDs at compile time, emits
  `postgres.bki` + `pg_*_d.h`. **`reformat_dat_file.pl`** enforces the canonical
  `.dat` formatting (metadata-first, 80-col wrap, defaults elided). [from-docs]
  [cross: knowledge/docs-distilled/bki-structure.md]

## Links into corpus
- Skill: **`catalog-conventions`** — adding a pg_proc.dat / pg_operator.dat / pg_type.dat entry, OID + catversion discipline.
- [[knowledge/docs-distilled/system-catalog-declarations.md]] — the `.h` side that defines the columns + BKI_DEFAULT / BKI_LOOKUP these rows fill.
- [[knowledge/docs-distilled/bki.md]] / [[knowledge/docs-distilled/bki-structure.md]] — the emitted postgres.bki this becomes.

## Gaps / follow-ups
- The page documents the format thoroughly; the `make reformat-dat-files` round
  trip is the operational gotcha to remember (hand-formatted `.dat` edits get
  rewritten — match the canonical form or run the target).
