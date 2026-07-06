---
source_url: https://www.postgresql.org/docs/current/collation.html
fetched_at: 2026-07-06T00:00:00Z
anchor_sha: a8c2547eaac7
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18; body numbers §23.2, ToC §24.2)
primary: false
---

# Docs distilled — §24.2: Collation Support

Collation as a first-class catalog object (`pg_collation`), the
derivation/resolution rules (explicit vs implicit, the "indeterminate"
error), the three providers, and — the load-bearing concept for a hacker —
**deterministic vs nondeterministic** collations and the restrictions they
carry.

## Collation object + provider tag

- Every value of a collatable type (`text`/`varchar`/`char`/user types)
  carries a collation; a collation maps an SQL name to locale data in
  `pg_collation`. Inspect via `\dOS+`. `[from-docs]`
- `pg_collation.collprovider` is a single char: `'b'` builtin, `'c'` libc,
  `'i'` icu. `[verified-by-code]`
  source/src/include/catalog/pg_collation.h:41 (`collprovider`).
- **libc** collations are encoding-*dependent* (same name may have a per-
  encoding variant); **icu** collations are encoding-*independent* (one per
  name per DB), named BCP-47 with an `-x-icu` suffix (`de-AT-x-icu`,
  `und-x-icu` = root). `[from-docs]`
- Standard predefined collations on all platforms: `C` / `POSIX` (byte
  values), `ucs_basic` (code-point, UTF-8), `unicode` (UCA, needs ICU),
  `pg_c_utf8` / `pg_unicode_fast` (builtin). `default` = the DB's creation-
  time locale. `[from-docs]`

## Derivation rules (how a collation is picked for an expression)

- **Explicit wins**: any `COLLATE` in the expression is explicit; all
  explicit collations present must be equal or → error. `[from-docs]`
- **Implicit**: a column's collation is implicit; a non-default implicit
  collation dominates `default`; **two conflicting non-default implicit
  collations → indeterminate**, and any operation needing the collation
  raises at runtime:
  ```
  ERROR:  could not determine which collation to use for string comparison
  HINT:  Use the COLLATE clause to set the collation explicitly.
  ```
  `[from-docs]`
- `||` doesn't care about collation but `ORDER BY a||b` does → must add
  `COLLATE`. Note `a COLLATE "C" < b COLLATE "POSIX"` still errors even
  though C and POSIX behave identically — it's object identity, not
  behavior, that must match. `[from-docs]`

## Deterministic vs nondeterministic — the load-bearing distinction

- **Deterministic** (the default, and mandatory for all predefined
  collations): string equality requires *identical byte sequences*; the
  collator only breaks ties in ordering. `pg_collation.collisdeterministic`
  defaults to true. `[verified-by-code]`
  source/src/include/catalog/pg_collation.h:42 (`collisdeterministic
  BKI_DEFAULT(t)`).
- **Nondeterministic**: strings can compare *equal* despite different bytes
  (case-insensitive / accent-insensitive / Unicode-normalization-insensitive).
  Must be requested: `CREATE COLLATION … (provider=icu, locale='und-u-ks-level2',
  deterministic=false)`. `[from-docs]`
- Restrictions carried by nondeterministic collations:
  - **Pattern matching is restricted** — `LIKE`, `SIMILAR TO`, regex on a
    nondeterministic-collated column are limited/unsupported. `[from-docs]`
  - **btree deduplication is disabled** for indexes on them. `[from-docs]`
  - **Slower** comparisons than deterministic. `[from-docs]`
  - (This is the mechanism behind the "nondeterministic LIKE" discussions on
    -hackers — the restriction is inherent to byte-inequality-but-equal
    semantics.)

## ICU custom collations (strength & settings)

- Sensitivity via the `ks` key: `level1` base only, `level2` +accents,
  `level3` (default) +case, `level4` +punctuation, `identic` +everything.
  Other BCP-47 keys: `kn` numeric ordering (`'id-45' < 'id-123'`), `kf`
  case-first, `ka=shifted` ignore punctuation, `kc` case as level 2.5.
  `[from-docs]`
- Tailoring rules: `CREATE COLLATION … (provider=icu, locale='und',
  rules='&V << w <<< W')`. `[from-docs]`

## Collation versioning (index-corruption tripwire)

- `pg_collation.collversion` records the provider's version at collation
  creation (libc changes on OS locale update, ICU on library upgrade).
  `[verified-by-code]` source/src/include/catalog/pg_collation.h:49
  (`collversion BKI_DEFAULT(_null_)`).
- A mismatch emits "collation version mismatch" — affected indexes may be
  corrupt; fix by rebuilding + `ALTER COLLATION … REFRESH VERSION`.
  `pg_import_system_collations()` re-imports OS/libc collations. `[from-docs]`

## Links into corpus

- Fixed database `LC_COLLATE`/providers this decouples from:
  [docs-distilled/locale.md](./locale.md)
- Deterministic-only escape opclass for pattern matching:
  [docs-distilled/btree.md](./btree.md)
- Provider dispatch in code: source/src/backend/utils/adt/pg_locale.c:1189.
- Relevant skills: `catalog-conventions` (pg_collation), `coding-style`.
