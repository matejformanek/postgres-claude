---
path: src/backend/utils/adt/name.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 355
depth: deep
---

# name.c

- **Source path:** `source/src/backend/utils/adt/name.c`
- **Lines:** 355
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/c.h` (`NameData` struct, `NameStr`, `Name` typedef), `src/include/pg_config_manual.h` (`NAMEDATALEN`), `src/include/utils/builtins.h` (declares `namein`/`namestrcpy`/`namestrcmp`), `src/include/catalog/pg_proc.dat` (namein/nameout/nameeq/btnamecmp/current_user/current_schema/nameconcatoid entries), `src/include/catalog/pg_type.dat` (`name` type, NAMEOID), `src/include/catalog/pg_collation.h` (`C_COLLATION_OID`)

## Purpose

Implements the built-in `name` type — a fixed-physical-length (`NAMEDATALEN`, default 64) NUL-terminated string used for catalog identifiers [from-comment `name.c:3-9`]. Provides I/O (`namein`/`nameout`/`namerecv`/`namesend`), the six btree comparison operators plus `btnamecmp`/`btnamesortsupport`, two C-string helper routines (`namestrcpy`/`namestrcmp`), and the SQL functions `CURRENT_USER`/`SESSION_USER`/`CURRENT_SCHEMA`/`CURRENT_SCHEMAS`/`nameconcatoid` [verified-by-code `name.c:47-355`].

## Public symbols

| Symbol | file:line | Role |
| --- | --- | --- |
| `namein` | `name.c:47` | Input; truncates oversize via `pg_mbcliplen`, zero-pads to NAMEDATALEN |
| `nameout` | `name.c:70` | Output; `pstrdup` of the NUL-terminated bytes |
| `namerecv` | `name.c:81` | Binary recv; errors if >= NAMEDATALEN, zero-pads |
| `namesend` | `name.c:105` | Binary send; sends `strlen` bytes (not full NAMEDATALEN) |
| `nameeq` | `name.c:147` | Equality (collation-aware) |
| `namene` | `name.c:156` | Inequality |
| `namelt` | `name.c:165` | Less-than |
| `namele` | `name.c:174` | Less-or-equal |
| `namegt` | `name.c:183` | Greater-than |
| `namege` | `name.c:192` | Greater-or-equal |
| `btnamecmp` | `name.c:201` | btree 3-way comparison support function |
| `btnamesortsupport` | `name.c:210` | SortSupport via generic `varstr_sortsupport` |
| `namestrcpy` | `name.c:232` | C helper: copy str into a Name, zero-pad + force NUL |
| `namestrcmp` | `name.c:246` | C helper: compare Name to C string (C collation, NULL-safe) |
| `current_user` | `name.c:262` | SQL CURRENT_USER |
| `session_user` | `name.c:268` | SQL SESSION_USER |
| `current_schema` | `name.c:278` | SQL CURRENT_SCHEMA (first non-deleted search_path entry) |
| `current_schemas` | `name.c:293` | SQL CURRENT_SCHEMAS(bool) → name[] |
| `nameconcatoid` | `name.c:332` | Append `_oid` suffix, truncating the name part to fit NAMEDATALEN |

## Internal landmarks

- `namecmp` (static, `name.c:134`): the shared comparator behind all six operators + `btnamecmp`. Fast path for `C_COLLATION_OID` uses `strncmp(..., NAMEDATALEN)` (`name.c:138-139`); otherwise delegates to `varstr_cmp` with the real `strlen`s and the collation (`name.c:142-144`).
- `namein` truncation (`name.c:56-58`): oversize input clipped to a multibyte-safe boundary via `pg_mbcliplen(s, len, NAMEDATALEN - 1)`, leaving room for the terminator.
- `namerecv` length guard (`name.c:90-95`): unlike `namein`, binary input that is `>= NAMEDATALEN` is a hard `ereport(ERROR, ...)` "identifier too long", not silently truncated.
- `nameconcatoid` suffix build (`name.c:342-352`): formats `_%u` into a 20-byte stack buffer, then clips only the *name* part (never the oid suffix) so the suffix is preserved [from-comment `name.c:322-331`].
- `current_schema`/`current_schemas` use `fetch_search_path` + `get_namespace_name`, skipping recently-deleted namespaces (`name.c:284-289`, `name.c:309-313`).

## Invariants & gotchas

- **A `name` value is always physically NAMEDATALEN bytes, zero-padded, NUL-terminated.** `namein`/`namerecv`/`nameconcatoid` all `palloc0(NAMEDATALEN)` precisely so the tail is zeroed (`name.c:60-62`, `name.c:96-97`, `name.c:349-352`). Callers and on-disk layout depend on this fixed physical width [from-comment `name.c:6-9`, `name.c:60`].
- **Never hard-code 64; always use `NAMEDATALEN`.** Explicit instruction in the file header [from-comment `name.c:8-9`].
- **Comparisons ignore bytes past the terminator.** Use of `strncmp` with the NAMEDATALEN limit is "mostly historical"; `strcmp` would suffice because every valid name has a `'\0'` and trailing bytes are irrelevant [from-comment `name.c:129-132`].
- **`namestrcpy` uses `strncpy` then forces the last byte to NUL** (`name.c:236-237`): `strncpy` zero-pads when the source is shorter than NAMEDATALEN, and the explicit `NameStr(*name)[NAMEDATALEN-1] = '\0'` guarantees termination even when the source is exactly NAMEDATALEN or longer. Both behaviors are required to keep the always-NUL-terminated invariant [verified-by-code `name.c:235-237`].
- **`namestrcmp` assumes C collation** and is NULL-safe with NULL sorting first (`name.c:241-256`); the comment warns it should only be used for equality unless you accept C-collation ordering [from-comment `name.c:242-245`].
- **`btnamesortsupport` switches into `ssup->ssup_cxt` before calling `varstr_sortsupport`** (`name.c:217-222`) so any allocations made by the generic sort-support setup live in the correct (longer-lived) memory context.
- **`namein` truncates silently; `namerecv` errors.** This asymmetry is intentional: text input gets the historical truncate-to-fit behavior, while the binary protocol rejects over-length identifiers (`name.c:56-58` vs `name.c:90-95`).
- **`current_user`/`session_user`/`current_schema(s)` build the result by `DirectFunctionCall1(namein, ...)`** (`name.c:265`, `name.c:271`, `name.c:290`, `name.c:311`) — so a user/namespace name longer than NAMEDATALEN-1 would be truncated by `namein`, not errored.

## Cross-references

- [[knowledge/idioms/fmgr-and-spi]] — `Datum foo(PG_FUNCTION_ARGS)`, `DirectFunctionCall1` used to invoke `namein` internally.
- [[knowledge/idioms/memory-contexts]] — the `MemoryContextSwitchTo(ssup->ssup_cxt)` discipline in `btnamesortsupport`.
- [[knowledge/idioms/error-handling]] — `ereport(ERROR, ...)` in `namerecv`.
- Sibling adt scalar-type files: [[knowledge/files/src/backend/utils/adt/bool.c]], [[knowledge/files/src/backend/utils/adt/char.c]].
- Collation-aware comparison core: `varstr_cmp`/`varstr_sortsupport` in `src/backend/utils/adt/varlena.c`.
- Multibyte clip helper: `pg_mbcliplen` in `src/backend/utils/mb/mbutils.c`.

## Potential issues

- **[ISSUE-undocumented-invariant: nameconcatoid suffix buffer assumes oid text fits in 20 bytes]**
  `name.c:338-342` — `char suffix[20]` then `snprintf(suffix, sizeof(suffix), "_%u", oid)`. A 32-bit OID is at most 10 digits, so `_` + 10 digits + NUL = 12 bytes, comfortably within 20; the bound is safe but undocumented. If Oid ever widened (it will not in current PG), this fixed buffer would be a silent constraint. Severity: nit (correct today, `snprintf` is bounded anyway).

## Confidence tag tally

- [verified-by-code]: 3
- [from-comment]: 6
- [inferred]: 0
- [unverified]: 0
