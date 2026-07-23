---
source_url: https://www.postgresql.org/docs/current/lo-interfaces.html
chapter: "35.3 Large Objects: Client Interfaces (lo-interfaces)"
fetched_at: 2026-07-22
anchor_sha: d774576f6f0
---

# Large object client interfaces — lo-interfaces

The libpq client-side `lo_*` function family (`src/interfaces/libpq/fe-lobj.c`)
that models a `pg_largeobject` LO as a Unix file descriptor: open → read/write/
seek → close. Every one of these is a thin wrapper that ships a **fast-path
function call** to the backend; the actual storage engine is `inv_api.c` (see
`[[knowledge/docs-distilled/lo-implementation.md]]`). This is the *client* half
of Chapter 35; the *server* SQL functions are §35.4
(`[[knowledge/docs-distilled/lo-funcs.md]]`).

## Non-obvious claims

- **These are NOT ordinary SQL — they are libpq fast-path calls.** Every
  client `lo_*` function routes through `PQfn(conn, conn->lobjfuncs->fn_lo_*,
  …)` [verified-by-code fe-lobj.c:75 (lo_open), :109 (lo_close), :172
  (lo_truncate)], and the fast-path is bootstrapped once per connection by
  `lo_initialize()` [verified-by-code fe-lobj.c:44 decl, :64 first call],
  which queries `pg_proc` to cache the function OIDs into `conn->lobjfuncs`.
  The docs describe the behavior but never name the fast-path mechanism —
  code confirms it. This is why LO transfer avoids the parse/plan/execute path
  entirely.
- **LO descriptors are transaction-scoped, non-negotiably.** "All large object
  manipulation using these functions **must** take place within an SQL
  transaction block, since large object file descriptors are only valid for the
  duration of a transaction." Any descriptor still open at transaction end is
  closed automatically. [from-docs] A single-statement autocommit `lo_read`
  therefore opens+reads+closes inside that one implicit transaction.
- **The two mode bits are `INV_WRITE = 0x00020000` and `INV_READ = 0x00040000`**
  [verified-by-code src/include/libpq/libpq-fs.h:21-22]. They are OR-able bit
  flags, *not* small enum values — a footgun if you assume `INV_READ == 1`.
- **`INV_WRITE` alone and `INV_READ|INV_WRITE` are treated identically by the
  server** — you may read from a write-opened descriptor either way. [from-docs]
- **But the mode changes read *snapshot* semantics.** A descriptor opened
  `INV_READ` reads the object as of the transaction snapshot (REPEATABLE-READ-
  like); one opened with `INV_WRITE` sees all committed data plus the current
  transaction's own writes (READ-COMMITTED-like). [from-docs] This is a subtle
  correctness point for concurrent readers/writers.
- **`INV_WRITE` (incl. `lo_open` for write) is rejected in a read-only
  transaction.** [from-docs]
- **The 64-bit variants exist purely to break the 2 GB signed-int ceiling.**
  `lo_lseek`/`lo_tell`/`lo_truncate` fail once the offset/position/length would
  exceed `INT_MAX`; callers must use `lo_lseek64` / `lo_tell64` /
  `lo_truncate64` (all server 9.3+) for objects past 2 GB. [from-docs]
  Confirmed present as distinct client entry points [verified-by-code
  fe-lobj.c:385 lo_lseek64, :548 lo_tell64, :195 lo_truncate64].
- **`lo_read`/`lo_write` `len` is declared `size_t` but capped at `INT_MAX`.**
  "this function will reject length values larger than `INT_MAX`. In practice,
  it's best to transfer data in chunks of at most a few megabytes anyway."
  [from-docs] So the descriptor may address >2 GB, but any single read/write
  call is still a ≤2 GB, best-kept-few-MB, transfer.
- **`lo_import`/`lo_export` here operate on the CLIENT's filesystem** with the
  client process's permissions — the opposite of the server-side SQL
  `lo_import`/`lo_export` (§35.4), which touch the *server's* filesystem and are
  superuser-gated. Same name, different machine. [from-docs]
- **Privilege checks moved to `lo_open` time in PG 11.** `lo_open` fails without
  `SELECT` on the LO, or without `UPDATE` when `INV_WRITE` is set; before PG 11
  the check fired at first read/write. Both are disabled by the
  `lo_compat_privileges` GUC [verified-by-code be-fsstubs.c:330 the server-side
  gate `if (!lo_compat_privileges && …)`].
- **`lo_creat(mode)` is the legacy creator; `lo_create(lobjId)` (server 8.1+)
  is preferred.** Since 8.1 the `mode` argument to `lo_creat` is ignored (access
  is decided at `lo_open`). `lo_create` additionally lets the caller *pick* the
  OID. [from-docs] Both present as distinct entry points [verified-by-code
  fe-lobj.c:438 lo_creat, :474 lo_create].
- **Cannot be used in libpq pipeline mode.** [from-docs] (Pipeline mode is
  §34.5 — see `[[knowledge/docs-distilled/libpq-pipeline-mode.md]]`.)
- **Failure convention: return an "otherwise-impossible" sentinel** (`InvalidOid`
  = 0 for creators/importers; `-1` for `lo_open`/`lo_close`/`lo_export`/
  `lo_unlink`), with the text in `PQerrorMessage(conn)`. [from-docs]

## Client function inventory

| Function | Server since | Role |
|---|---|---|
| `lo_create(conn, lobjId)` | 8.1 | Create, optionally with a chosen OID (0 → server picks) |
| `lo_creat(conn, mode)` | any | Legacy create; `mode` ignored on 8.1+ |
| `lo_import(conn, filename)` | any | Import a **client** file → new LO |
| `lo_import_with_oid(conn, filename, lobjId)` | 8.4 | Import with chosen OID (uses `lo_create` internally) |
| `lo_export(conn, lobjId, filename)` | any | Write LO → a **client** file |
| `lo_open(conn, lobjId, mode)` | any | Open, `mode` = `INV_READ`/`INV_WRITE` bits → fd |
| `lo_read` / `lo_write(conn, fd, buf, len)` | any | ≤`INT_MAX` byte transfer at the fd's position |
| `lo_lseek` / `lo_lseek64(conn, fd, off, whence)` | any / 9.3 | Reposition (64-bit past 2 GB) |
| `lo_tell` / `lo_tell64(conn, fd)` | any / 9.3 | Current position |
| `lo_truncate` / `lo_truncate64(conn, fd, len)` | 8.3 / 9.3 | Truncate/extend |
| `lo_close(conn, fd)` | any | Close (auto at xact end anyway) |
| `lo_unlink(conn, lobjId)` | any | Delete the LO |

## Links into corpus

- `[[knowledge/docs-distilled/lo-implementation.md]]` — §35.5, the `inv_api.c`
  chunked-row storage these descriptors read/write.
- `[[knowledge/docs-distilled/lo-funcs.md]]` — §35.4, the server-side SQL twins
  (`loread`/`lowrite`, server-filesystem `lo_import`/`lo_export`).
- `[[knowledge/docs-distilled/libpq-exec.md]]` — `PQfn` is the fast-path entry
  these wrappers call; the wire encoding is the Function-Call sub-protocol.
- `[[knowledge/docs-distilled/libpq-pipeline-mode.md]]` — the mode in which
  `lo_*` is explicitly unusable.
- Skill `wire-protocol` — the fast-path (Function-Call) message pair `lo_*`
  rides on; `fmgr-and-spi` — the `be_lo_*` server entry points these OIDs
  resolve to.

## Verification note

Client entry points + `PQfn`/`lo_initialize` bootstrap verified against
`src/interfaces/libpq/fe-lobj.c` @ `d774576f6f0`; `INV_READ`/`INV_WRITE` values
against `src/include/libpq/libpq-fs.h:21-22`; `lo_compat_privileges` gate
against `src/backend/libpq/be-fsstubs.c:330`. Snapshot-semantics + transaction-
scope + `INT_MAX` caps are [from-docs] (behavioral contract, not a single
line).
