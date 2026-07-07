---
name: collation-provider
description: PostgreSQL's collation-provider abstraction — the 3-way split between `builtin` (PG-owned), `icu` (ICU library), and `libc` (OS-provided). Covers `src/backend/utils/adt/pg_locale.c` (the dispatcher) + `pg_locale_builtin.c` / `pg_locale_icu.c` / `pg_locale_libc.c` (per-provider implementations) plus the encoding conversion layer (`src/backend/utils/mb/`). Loads when the user asks about `CREATE COLLATION`, provider semantics, `LC_COLLATE` / `LC_CTYPE`, ICU integration + version tracking, the `builtin` provider added PG 17, `collversion` upgrade detection, why an ORDER BY differs between PGs on the same OS, `pg_c_utf8` builtin, or multibyte encoding conversion. Skip when the ask is about client encoding (server-client convert is included but psql `\encoding` is client-side), full-text search dictionaries (different subsystem `tsearch`), or `CREATE TEXT SEARCH CONFIGURATION`.
when_to_load: Understand or extend the collation provider dispatch; investigate collation-version mismatches; add a new builtin collation; touch encoding-conversion code; debug locale-dependent sort/comparison behavior.
companion_skills:
  - catalog-conventions
  - error-handling
  - executor-and-planner
---

# collation-provider — builtin, ICU, libc — the 3-way split

Every text comparison in PG (equality, LIKE, ORDER BY, index key comparison) goes through a **collation**. Collations are catalog objects (`pg_collation`) that tell the backend WHICH library to use for comparison, WHICH locale within that library, and WHICH encoding the strings are in.

Since PG 17, collations come from **three providers**:

- `builtin` — PG-owned; deterministic Unicode + a few special cases. Added PG 17 to avoid OS/library upgrade breakage.
- `icu` — ICU library (International Components for Unicode). Rich, version-tracked, portable across OSes.
- `libc` — OS-provided (glibc / macOS / Windows). Fast + backwards-compatible + fragile (OS upgrades change collation order silently).

## The file map

| File | KB | Role |
|---|---:|---|
| `utils/adt/pg_locale.c` | 50 | The dispatcher. `pg_locale_deterministic`, `pg_strcoll`, `pg_strxfrm`, provider dispatch table. Handles the fast paths (deterministic C-locale). |
| `utils/adt/pg_locale_builtin.c` | 7 | PG-owned builtin provider — `C.UTF-8`, `unicode`, `PG_C_COLLATION_OID`. Small because the rules ARE the code. |
| `utils/adt/pg_locale_icu.c` | 36 | ICU integration — UCollator setup, version reading, `u_strcmp` etc. Conditional on `--with-icu`. |
| `utils/adt/pg_locale_libc.c` | 34 | libc integration — `newlocale` / `strcoll_l` / `strxfrm_l`. Historical + widely deployed. |
| `include/utils/pg_locale.h` | 8 | Public API surface + `pg_locale_t` opaque handle. |
| `utils/mb/mbutils.c` | 53 | Encoding conversion — client-encoding ↔ server-encoding, wchar helpers. NOT collation but tightly related. |
| `utils/mb/conv.c` | 13 | Conversion function dispatch. |
| `utils/mb/Unicode/` | — | Auto-generated codepoint mapping tables. |

## The provider dispatch

Every text-op call site does:

1. Look up the collation OID from the input columns / cast / GUC.
2. Fetch a `pg_locale_t` via `pg_newlocale_from_collation(colloid)` — this is CACHED per backend.
3. Call the provider-specific op:
   - `pg_strcoll_l(a, b, locale)` for compare.
   - `pg_strxfrm(dst, src, srclen, locale)` for sort-key generation.
   - Etc.

The `pg_locale_t` struct carries a `provider` tag; every dispatch routine switches on it.

## The `builtin` provider (PG 17+)

Motivation: OS/ICU upgrades change collation ordering silently, invalidating indexes. The builtin provider is PG-owned, versioned by PG major release, and (mostly) deterministic Unicode.

Two builtin locales:

- `C.UTF-8` (`PG_C_COLLATION_OID` — literally OID hardcoded) — codepoint comparison + UTF-8 aware ctype (upper/lower/digit).
- `unicode` — Unicode ROOT collation (DUCET) — the canonical Unicode ordering, no locale-specific tailoring.

**Deterministic by design** — two byte-equal strings compare equal, two byte-unequal strings never compare equal at the `builtin` provider. No expansion ligatures. This is why `builtin` is safe for hash-based dedup (indexes, DISTINCT).

Adding a new builtin collation would touch `pg_locale_builtin.c` + `pg_collation.dat` for the catalog entry + bump `CATALOG_VERSION_NO`.

## The ICU provider

Uses libicuuc + libicui18n. Each ICU collation has:

- A locale identifier (`en-US`, `de-DE-u-co-phonebk`).
- A rule string (optional customization on top of the locale).
- A version identifier (from ICU's `ucol_getVersion`).

The version identifier is stored in `pg_collation.collversion` at CREATE time. On collation use, PG compares the stored version to the CURRENT ICU version — if they differ, `pg_collation_actual_version()` reports the mismatch and functions like `ALTER COLLATION ... REFRESH VERSION` are expected to run after ICU is upgraded, followed by REINDEX of affected indexes.

## The libc provider

Uses OS `newlocale` / `strcoll_l` etc. Fast but:

- **glibc-version dependent** — glibc 2.28 (2018) changed collation ordering. Indexes built on older glibc silently mis-sort on newer.
- **No version fingerprint** — libc doesn't expose a version identifier PG can store. Some catalog entries carry the version PG guesses from `uname` but it's unreliable.
- **Locale must exist on the system** — a collation for `de_DE.UTF-8` fails if the OS doesn't have that locale generated.

**Recommendation in the docs**: use `builtin` for deterministic C.UTF-8, `icu` for language-aware collation with version tracking. libc is legacy but ubiquitous.

## Encoding conversion (the mb/ side)

Separate from collation but interlocks:

- **Server encoding** — fixed at initdb (`ENCODING = 'UTF8'` etc.), same for the whole cluster.
- **Client encoding** — per-session, via `SET client_encoding`.
- Every text going over the wire gets converted: server → client on send, client → server on receive.

Conversion procs live in `src/backend/utils/mb/conversion_procs/` — one directory per encoding pair (e.g. `utf8_and_win1252`).

Multibyte string handling helpers (character length, character-boundary detection) are in `mbutils.c`. Every text function that operates on characters (not bytes) uses these — e.g. `substring`, `length`, `left`, `right`.

## Common patch shapes

### Add a new builtin collation

- Add row to `pg_collation.dat` with `collprovider => 'b'`.
- Add matching case in `pg_locale_builtin.c`'s dispatch.
- Update `pg_locale_deterministic` if the new collation is non-deterministic.
- Bump `CATALOG_VERSION_NO`.
- Test in `src/test/regress/sql/collate.linux.utf8.sql` + `.icu.utf8.sql`.

### Extend ICU integration

- Touch `pg_locale_icu.c`.
- Consider version tracking — every new field affects the `collversion` string.
- Test with multiple ICU versions locally (buildfarm has several).

### Debug "index scan skips rows after glibc upgrade"

- `pg_collation.collversion` should show the mismatch (if PG stored one).
- `SELECT pg_collation_actual_version('en_US'::regcollation);` — current OS version.
- Fix: `ALTER COLLATION ... REFRESH VERSION` + `REINDEX INDEX ...` for every affected index.
- Prevention: migrate to `icu` provider for cross-OS-upgrade stability.

### Add a new encoding conversion

- New directory in `utils/mb/conversion_procs/<encA>_and_<encB>/`.
- Meson-buildable module producing `<encA>_to_<encB>` and `<encB>_to_<encA>` functions.
- Grant SQL-callable via `pg_conversion` catalog row.
- Test with `SELECT convert('...'::bytea, 'encA', 'encB');`.

## Pitfalls

- **`collversion` mismatch is silent by default** — a `SELECT` may return wrong results if the OS collation library upgraded and the index is stale. PG emits WARNINGs on `pg_collation_actual_version` mismatch but doesn't refuse the query.
- **`ORDER BY` in tests is provider-dependent** — a regress test using a language-aware locale may pass on the author's box (glibc 2.31) and fail on the CI (glibc 2.35) with entirely different ordering. Prefer `C.UTF-8` (builtin) for regress tests unless testing collation semantics specifically.
- **`LIKE 'x%'` optimization requires locale-independent prefix comparison** — deterministic collations (C, builtin) enable a fast-path where the planner can use B-tree index range scans on `col LIKE 'prefix%'`. Non-deterministic ICU collations disable this.
- **Non-deterministic collations don't work with hash indexes** — hash equality requires byte-identity, which non-deterministic collations don't provide.
- **`char_length` / `octet_length`** — different values for multibyte. `char_length('café')` = 4, `octet_length('café')` = 5 in UTF-8. Common bug.
- **Client-encoding conversion happens per wire message** — an app that sends 1M small INSERT statements with client_encoding ≠ server_encoding pays per-conversion cost.
- **`pg_locale_deterministic` returns FALSE for ICU with custom tailorings** — some ICU rules add expansions/contractions that make equal-bytes non-equal-collation. Check with `SELECT collationdeterministic FROM pg_collation`.
- **Backend caches `pg_locale_t` per collation** — hot-reload of ICU (e.g. ldconfig then keeping backends alive) has undefined behavior. Restart the backends.

## Related corpus

- **File docs**: `knowledge/files/src/backend/utils/adt/pg_locale.c.md` + the 3 provider files + `mbutils.c.md`.
- **Subsystems**: `utils-cache` (relcache/typcache cache collation info), `parser-and-rewrite` (parse-time collation inference via `parse_collate.c`).
- **Related planning**: `planning/sp7-tablefunc-quoting/` — the tablefunc contrib bug touched identifier quoting which interacts with encoding.
- **Docs distilled**: `knowledge/docs-distilled/§24` (locale + collation + multibyte) + `§23.2` (specific collations chapter).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/utils/adt/pg_locale.c
python3 scripts/corpus-chain.py --file src/backend/utils/mb/mbutils.c
```

Neighborhood: 4-6 files under `utils/adt/` for collation + ~15 under `utils/mb/` for encoding.

## Boundary

**Use this skill** for `pg_locale*.c` + `mb/` encoding + collation catalog + provider dispatch.

**Don't use** for:
- **`tsearch`** — full-text search dictionaries (`utils/adt/tsvector*.c` + `tsearch/*.c`). Separate subsystem.
- **`CREATE TEXT SEARCH CONFIGURATION`** — text-search DDL, not collation.
- **`nls.mk` / gettext** — server-message localization. Different concern; touches `src/backend/utils/misc/*` and per-locale `.po` files.
- **Client-side encoding** — `psql \encoding` etc. is in `src/bin/psql/`.
- **Custom text ordering via callbacks** — that's implementing a function using existing collations; use `fmgr-and-spi` for the fn side.
