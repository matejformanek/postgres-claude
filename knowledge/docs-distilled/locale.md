---
source_url: https://www.postgresql.org/docs/current/locale.html
fetched_at: 2026-07-06T00:00:00Z
anchor_sha: a8c2547eaac7
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18; page body still numbers this §23.1, ToC calls it §24.1)
primary: false
---

# Docs distilled — §24.1: Locale Support

The six POSIX locale categories, which are frozen at cluster/database
creation vs runtime-settable, the three locale *providers* (builtin / libc
/ icu), and the operational hazards. The load-bearing internals fact: only
`LC_COLLATE` and `LC_CTYPE` are immutable per-database (they determine
index sort order) — the other four are plain GUCs.

## The six categories — what is frozen, what is a GUC

| Category | Governs | Fixed at DB creation? |
|---|---|---|
| `LC_COLLATE` | string sort order (`<`, `ORDER BY`, btree) | **yes** — determines index order |
| `LC_CTYPE` | char classification (`upper`/`lower`/`initcap`, regex classes) | **yes** |
| `LC_MESSAGES` | server message language | no — session GUC |
| `LC_MONETARY` | currency formatting | no — session GUC |
| `LC_NUMERIC` | number formatting | no — session GUC |
| `LC_TIME` | date/time formatting | no — session GUC |

- `LC_COLLATE`/`LC_CTYPE` cannot change for an existing database because
  doing so would silently corrupt the sort order of every text index built
  under the old setting. `SHOW lc_collate` is read-only per-database; the
  four format categories are settable via `SET lc_messages = …` etc.
  `[from-docs]`
- The escape hatch for per-column/per-expression order is the *collation*
  system (§24.2 `COLLATE`), which decouples sort order from the fixed
  database `LC_COLLATE`. `[from-docs]`
- Server inherits from the environment at startup: `LC_ALL` > category-
  specific `LC_*` > `LANG` > default `C`. `[from-docs]`

## Locale providers (builtin / libc / icu)

- **builtin** — PG-internal, no OS/ICU dependency. Supports only `C`,
  `C.UTF-8`, and `PG_UNICODE_FAST`. `C.UTF-8` = code-point collation +
  simple case mapping + "POSIX Compatible" regex; `PG_UNICODE_FAST` =
  code-point collation + *full* Unicode case mapping + "Standard" regex.
  Both UTF-8 only. `[from-docs]`
- **libc** (historic default) — `setlocale()` on the OS C library;
  `LC_COLLATE` and `LC_CTYPE` are *coupled* (one OS locale drives both).
  Same name may sort differently across platforms/OS updates. `[from-docs]`
- **icu** — external ICU library, BCP-47 language tags (`ja-JP`,
  `en-US-u-kn-true`); `LC_COLLATE`/`LC_CTYPE` can be set *independently*;
  platform-independent but ICU-version dependent. `[from-docs]`
- Providers mix across scopes: libc cluster + icu database + either at the
  collation level. Chosen with `initdb --locale-provider=icu
  --icu-locale=…` (or per-DB / per-collation). `[from-docs]`
- Provider dispatch lives in `pg_newlocale_from_collation()`, which branches
  on `collform->collprovider` (`COLLPROVIDER_BUILTIN` / `_ICU` / `_LIBC`).
  `[verified-by-code]` source/src/backend/utils/adt/pg_locale.c:1189 (entry),
  :1062-1066 + :1257 (the three-way provider branch).

## The "Problems" section — silent failures the hacker must know

- **Non-`C` locale disables plain-index use for `LIKE`.** A btree on `text`
  under a non-C collation can't accelerate `LIKE 'foo%'`. Fixes: build the
  index with `COLLATE "C"`, or use the `text_pattern_ops` opclass (strict
  byte-order comparison, ignores locale), or use the `builtin` `C.UTF-8`.
  `[from-docs]`
- **OS locale-data drift** (libc): the OS can update locale definitions
  under you, silently changing sort/ctype behavior; indexes built before the
  change may now be out of order — the same corruption-risk collation
  *versioning* (§24.2) exists to detect. `[from-docs]`
- **Message language is the server's, not the client's** — parsing error
  *text* breaks under a different `lc_messages`; use SQLSTATE codes instead.
  `[from-docs]`
- Invalid ICU locale → WARNING unless `icu_validation_level = ERROR`.
  `[from-docs]`

## Links into corpus

- Collation objects, deterministic vs nondeterministic, versioning:
  [docs-distilled/collation.md](./collation.md)
- Encoding side of localization (must be compatible with `LC_CTYPE`):
  [docs-distilled/multibyte.md](./multibyte.md)
- The `text_pattern_ops` escape opclass: [docs-distilled/btree.md](./btree.md)
- Config GUCs `lc_messages`/`lc_monetary`/`lc_numeric`/`lc_time`:
  [docs-distilled/runtime-config-client.md](./runtime-config-client.md)
- Relevant skills: `catalog-conventions` (pg_collation / pg_database
  `datlocprovider`), `coding-style` (message-language rule).
