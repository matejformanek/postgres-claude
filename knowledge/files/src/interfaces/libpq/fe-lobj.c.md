---
path: src/interfaces/libpq/fe-lobj.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 1064
depth: deep
---

# fe-lobj.c

- **Source path:** `source/src/interfaces/libpq/fe-lobj.c`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **LOC:** 1064
- **Companion files:** `libpq-fe.h` + `libpq/libpq-fs.h` (INV_READ/INV_WRITE flag macros), `libpq-int.h` (PGlobjfuncs struct, conn->lobjfuncs cache), `fe-exec.c` (`PQfn`, `PQexec`, `PQresultStatus`, `PQntuples`, `PQgetvalue` — heavy consumer), backend counterparts in `src/backend/libpq/be-fsstubs.c` and `src/backend/storage/large_object/inv_api.c`

## Purpose

Frontend wrappers for the PostgreSQL **large object** API — the legacy interface for storing >1 GiB blobs as inversion-indexed pg_largeobject rows. Every `lo_*` function here translates a client call into either a Function-Call (`'F'`) protocol message via `PQfn` against a server function OID, or in a few cases a normal SQL roundtrip. Server function OIDs are looked up once per connection by `lo_initialize` and cached in `conn->lobjfuncs`.

Note: large objects are **not** the same as TOAST. TOAST is automatic; large objects are an explicit, lo_open/lo_read/lo_close-style interface that pre-dates TOAST.

## Public API surface

| Function | Line | One-liner | Server OID resolved to |
|---|---|---|---|
| `lo_open` | 57 | Open existing LO, return fd. | `pg_catalog.lo_open(lobjid, mode)` |
| `lo_close` | 96 | Close LO fd. | `lo_close(fd)` |
| `lo_truncate` | 131 | 32-bit truncate. | `lo_truncate(fd, len)` |
| `lo_truncate64` | 195 | 64-bit truncate. | `lo_truncate64(fd, len)` |
| `lo_read` | 245 | Read up to `len` bytes. | `loread(fd, len)` (note: server fn names differ from lib names for `read`/`write`) |
| `lo_write` | 295 | Write `len` bytes. | `lowrite(fd, buf)` |
| `lo_lseek` | 344 | 32-bit seek. | `lo_lseek(fd, offset, whence)` |
| `lo_lseek64` | 385 | 64-bit seek. | `lo_lseek64(fd, offset, whence)` |
| `lo_creat` | 438 | Create LO, server picks OID. | `lo_creat(mode)` |
| `lo_create` | 474 | Create LO with caller-chosen OID. | `lo_create(oid)` |
| `lo_tell` | 515 | 32-bit position query. | `lo_tell(fd)` |
| `lo_tell64` | 548 | 64-bit position query. | `lo_tell64(fd)` |
| `lo_unlink` | 589 | Delete the LO. | `lo_unlink(lobjid)` |
| `lo_import` | 626 | Read local file, create LO with its contents. | `lo_creat` + `loread`/`lowrite` loop |
| `lo_import_with_oid` | 641 | Same, caller-specified OID. | `lo_create` + loop |
| `lo_export` | 748 | Read LO into a local file. | `lo_open` + read loop |

## Internal landmarks

### `PGlobjfuncs` cache

Each connection lazily resolves the server-side function OIDs once (first `lo_*` call) via a SQL query against `pg_catalog.pg_proc`:

```sql
select proname, oid from pg_catalog.pg_proc
where proname in ('lo_open','lo_close','lo_creat','lo_create',
                  'lo_unlink','lo_lseek','lo_lseek64','lo_tell',
                  'lo_tell64','lo_truncate','lo_truncate64',
                  'loread','lowrite')
and pronamespace = (select oid from pg_catalog.pg_namespace where nspname='pg_catalog')
```

[verified-by-code, fe-lobj.c:881-901] Result rows go into a `PGlobjfuncs` struct stashed at `conn->lobjfuncs`. The `lo_lseek64`, `lo_tell64`, `lo_truncate64`, `lo_create` entries may be absent on very old servers; the validation step (~lines 960-1020) requires at least the core 8 (open/close/creat/unlink/lseek/tell/truncate/loread/lowrite). 64-bit variants degrade gracefully.

### `lo_initialize` (843)

Pre-flight for every `lo_*`. Logic:

1. `pqClearConnErrorState`.
2. If `conn->lobjfuncs != NULL` → return 0 (cached).
3. Allocate `PGlobjfuncs`, `MemSet` to zero.
4. Run the catalog SELECT via `PQexec`.
5. Walk rows, store `foid` per name.
6. Validate required ones are present; reject (set error, free) if not.
7. Stash in `conn->lobjfuncs`.

[verified-by-code, fe-lobj.c:842-1021]

### Endian-safe 64-bit conversion

`lo_hton64` (1023) / `lo_ntoh64` (1048) — converts an `int64_t` to/from network byte order in a portable way: split into two `uint32`, swap via `pg_hton32`, reassemble. Used by `lo_lseek64`, `lo_tell64`, `lo_truncate64`. Needed because PG's `pg_hton64` macro may not exist on all platforms libpq targets. [verified-by-code, fe-lobj.c:1022-1063]

### `lo_import` / `lo_export` patterns

`lo_import_internal` (647) opens the local file with `open(O_RDONLY | PG_BINARY)`, calls `lo_creat` or `lo_create`, then loops `read(fd, buf, LO_BUFSIZE) → lo_write(conn, lobj, buf, n)` until EOF. `LO_BUFSIZE` is hardcoded at 8192. The error paths are careful: if `lo_write` fails, the transaction is now aborted server-side, so `lo_close` is skipped (it would just overwrite the useful error). [verified-by-code, fe-lobj.c:725-746]

`lo_export` (748) is the reverse: `lo_open` then `lo_read → write(local_fd, buf, n)` loop. Same skip-`lo_close`-on-error discipline.

### `lo_open` mode flags

`INV_READ` (0x40000) and `INV_WRITE` (0x20000) from `libpq/libpq-fs.h`. Can be ORed. `lo_creat(INV_READ | INV_WRITE)` is the canonical "make me a new LO and open it" pattern. [from-comment, fe-lobj.c]

## Invariants & gotchas

- **Every `lo_*` requires an active transaction.** Large-object fds are session-bound: `lo_open` returns an integer that's only valid within the same transaction. Crossing a `COMMIT` or `ROLLBACK` invalidates all open LO fds. The server enforces this (returns "invalid large-object descriptor"); libpq just relays. [from-comment in inv_api.c, not duplicated here] If a wrapping framework auto-commits between SQL statements, `lo_open` + `lo_read` patterns break.
- **`lo_initialize`'s catalog query runs in the user's privilege context.** It needs SELECT on `pg_proc` and `pg_namespace`. Failure is reported as "query to initialize large object functions did not return data". [verified-by-code, fe-lobj.c:907-913]
- **Permission checks happen server-side, not here.** Frontend trusts the OID input. A client passing arbitrary `lobjId` to `lo_open` will get a server-side permission error if the LO isn't readable by the role; the frontend has no way to pre-check. [inferred from `PQfn` dispatch pattern]
- **64-bit fns fall back to 32-bit if server is old.** `lo_lseek64` validates `conn->lobjfuncs->fn_lo_lseek64 != InvalidOid` and returns -1 if zero. Callers using 64-bit variants must check return values; the lib does NOT silently call the 32-bit variant. [verified-by-code, fe-lobj.c:384-435]
- **`lo_read`/`lo_write` returns are `int`, not `ssize_t`.** Capped at ~2 GiB per call. Use the loop pattern in `lo_import`/`lo_export` for huge LOs.
- **`lo_export` opens the file with mode `0666`** (umask applies). Could be surprising on multi-user machines.
- **`LO_BUFSIZE` is hardcoded at 8192.** Many round-trips for big LOs. No tunable. [verified-by-code, fe-lobj.c:42]
- **`lo_creat(mode)` vs `lo_create(oid)`** — easy to confuse. `lo_creat` lets the server pick the OID (most common). `lo_create` reserves a specific OID and is mostly for pg_dump's benefit. [verified-by-code, fe-lobj.c:437-512]
- **`lo_import` / `lo_export` errors that arrive after `lo_close` may overwrite `conn->errorMessage`.** The functions explicitly call `pqClearConnErrorState` before setting their own error to "deliberately overwrite any error from lo_close". A `lo_close` failure on an aborted xact is expected and uninteresting. [from-comment, fe-lobj.c:670-680, 794-805]

## Cross-refs

- `knowledge/files/src/interfaces/libpq/fe-exec.c.md` — `PQfn` / `PQnfn` (the dispatch mechanism), `PQexec` (used by `lo_initialize`), and the `PQresult*` accessors.
- Backend counterparts (when written): `knowledge/files/src/backend/libpq/be-fsstubs.c.md` (the server-side `lo_*` C functions registered in pg_proc) and `knowledge/files/src/backend/storage/large_object/inv_api.c.md` (the backing storage).
- `libpq/libpq-fs.h` — `INV_READ`/`INV_WRITE` macros.

## Potential issues

- **[ISSUE-question: large-object permission check is server-side only]** fe-lobj.c — frontend has no client-side ACL check before issuing `lo_open`/`lo_unlink`. This is by design (single source of truth is the server) but means a malicious client can attempt to probe OIDs. Server should respond uniformly to "no such LO" vs "permission denied" to avoid information leak. Verify backend response uniformity. **Severity: maybe.** Phase D consideration.
- **[ISSUE-leak: `lo_import` reads file with `0666` permissions]** fe-lobj.c:777 — the local file created by `lo_export` is mode 0666 (subject to umask). Sensitive LO contents could be world-readable on a server with permissive umask. **Severity: maybe.** Phase D should consider 0600.
- **[ISSUE-stale-todo: `LO_BUFSIZE = 8192` is hardcoded]** fe-lobj.c:42 — no tunable; many round-trips for big LOs. **Severity: nit.**
- **[ISSUE-undocumented-invariant: must be in transaction]** fe-lobj.c — the "must be in xact" rule is enforced server-side and breaks subtly with auto-commit ORMs. Not documented in this file's comments at all. Should at least surface in `knowledge/idioms/large-objects.md` (when written). **Severity: maybe (docs).**
- **[ISSUE-correctness: `lo_initialize` catalog query is not parameterized]** fe-lobj.c:881-901 — the query is constant text, but it's run via `PQexec` which means any server-side function name change requires updating this literal in lockstep. Stale entries would silently disappear from the cache. Phase D code-review: verify CI catches name drift. **Severity: nit.**
- **[ISSUE-doc-drift: server-side `read`/`write` are named `loread`/`lowrite`]** fe-lobj.c:912-915 — but the client-side wrappers are `lo_read`/`lo_write`. The mismatch is historical and is the easiest source of confusion when grepping. Document explicitly. **Severity: nit.**
- **[ISSUE-correctness: error path leaks fds on `lo_import` if `lo_create` succeeds but `lo_open` fails]** fe-lobj.c:684-721 — actually checked: `(void) close(fd)` is called before returning `InvalidOid`. Good. But the *created* LO is left behind in the database. **Severity: maybe (orphan LO on rare error path).**

## Tally

`[verified-by-code]=11 [from-comment]=4 [from-readme]=0 [inferred]=1 [unverified]=0`
