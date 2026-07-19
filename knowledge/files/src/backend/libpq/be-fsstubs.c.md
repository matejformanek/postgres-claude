---
path: src/backend/libpq/be-fsstubs.c
anchor_sha: 4b0bf0788b0
loc: 873
depth: medium
---

# be-fsstubs.c

- **Source path:** `source/src/backend/libpq/be-fsstubs.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 873

## Purpose

Backend SQL functions for the LO ("large object") API: `lo_open`, `lo_read`,
`lo_write`, `lo_lseek`, `lo_creat`, `lo_unlink`, `lo_import`, `lo_export`,
`lo_truncate`, `lo_get`, `lo_get_fragment`, `lo_put`, `lo_from_bytea`. These
are thin SQL-callable wrappers around `inv_api.c` (which owns the
pg_largeobject catalog interaction); this file mostly manages the per-xact
"FD table" of `LargeObjectDesc *` cookies. The top-of-file note that this
"should be moved to a more appropriate place" has stood since at least
PG 8.0 — it lives in `libpq/` for purely historical reasons. [from-comment, be-fsstubs.c:13-35]

## Public API surface

| Line | SQL fn | Backing C |
|---|---|---|
| 87 | `lo_open(oid, mode)` | `be_lo_open` |
| 126 | `lo_close(fd)` | `be_lo_close` |
| 153 | (C-only) `lo_read(fd, buf, len)` | not fmgr-callable |
| 181 | (C-only) `lo_write(fd, buf, len)` | not fmgr-callable |
| 205/230 | `lo_lseek(fd, off32, whence)` / `lo_lseek64(fd, off64, whence)` | `be_lo_lseek[64]` |
| 248/261 | `lo_creat()` / `lo_create(oid)` | `be_lo_creat[e]` |
| 274/297 | `lo_tell(fd)` / `lo_tell64(fd)` | `be_lo_tell[64]` |
| 313 | `lo_unlink(oid)` | `be_lo_unlink` |
| 361/379 | `loread(fd, len)` / `lowrite(fd, bytea)` | `be_loread/lowrite` |
| 402/414 | `lo_import(path)` / `lo_import_with_oid(path, oid)` | wrappers around `lo_import_internal` |
| 485 | `lo_export(oid, path)` | `be_lo_export` |
| 578/590 | `lo_truncate(fd, int32)` / `lo_truncate64(fd, int64)` | `be_lo_truncate[64]` |
| 796/810 | `lo_get(oid)` / `lo_get_fragment(oid, off, len)` | `be_lo_get[_fragment]` |
| 831 | `lo_from_bytea(oid, bytea)` | `be_lo_from_bytea` |
| 854 | `lo_put(oid, off, bytea)` | `be_lo_put` |
| 606 | `AtEOXact_LargeObject(isCommit)` | xact-end hook |
| 652 | `AtEOSubXact_LargeObject(...)` | subxact-end hook |

## Internal landmarks

- **The FD table** (71-72):
  - `static LargeObjectDesc **cookies` — array of pointers, NULL = free slot.
  - `static int cookies_size` — current allocated length.
  - `static bool lo_cleanup_needed` — short-circuit for `AtEOXact_LargeObject`.
  - `static MemoryContext fscxt` — `AllocSetContextCreate(TopMemoryContext,
    "Filesystem", …)`. Holds the cookies array AND every `LargeObjectDesc`.
    Lifetime: from first LO op of an xact to xact end. [verified-by-code, be-fsstubs.c:686-690]
- `newLOfd` (679) — linear scan for free slot; first allocation = 64
  entries, then double via `repalloc0_array`. [verified-by-code, be-fsstubs.c:691-715]
- `closeLOfd` (720) — null the slot FIRST (so a faulting `inv_close`
  doesn't double-free), unregister snapshot, then `inv_close`. [verified-by-code, be-fsstubs.c:728-735]
- `lo_import_internal` (423) — server-file read; chunks of `BUFSIZE = 8192`.
  Uses `OpenTransientFile`. [verified-by-code, be-fsstubs.c:423-479]
- `lo_export` (485) — temporarily relaxes the backend's normal `077` umask
  to `022` so the exported file is group/world-readable. PG_TRY/PG_FINALLY
  restores the umask on error. [from-comment, be-fsstubs.c:507-510] [verified-by-code, be-fsstubs.c:512-522]
- `lo_get_fragment_internal` (745) — re-opens the LO each call (does NOT
  use the FD table; the SQL `lo_get` is "I want this LO, give it to me").
  Computes effective read length carefully against the LO's actual size
  and `MaxAllocSize - VARHDRSZ`. [verified-by-code, be-fsstubs.c:745-790]

## Invariants & gotchas

- **LO FDs are transaction-scoped.** Documented: "they're only good
  within a transaction." The top comment notes that since PG 8.0 the
  technical obstacles to cross-xact FDs are mostly gone, but backcompat
  freezes the semantics. [from-comment, be-fsstubs.c:23-34]
- **`fscxt` deletion at xact-end frees EVERYTHING.** `AtEOXact_LargeObject`
  calls `MemoryContextDelete(fscxt)` after closing FDs on commit (or
  unconditionally on abort) — so any palloc'd state hanging off a
  `LargeObjectDesc` is released as well. Don't keep external pointers
  into `fscxt` past xact boundary. [verified-by-code, be-fsstubs.c:634-637]
- **On abort we deliberately skip `closeLOfd`.** Comment: "on abort we can
  skip this step" because the memory context is being torn down anyway.
  We DO still `MemoryContextDelete(fscxt)`, but `inv_close` is never
  called, so any cached pg_largeobject state in `inv_api.c` relies on
  `close_lo_relation(isCommit)` for cleanup. [verified-by-code, be-fsstubs.c:621-640]
- **Subtransaction handling moves cookies, doesn't reopen.** On subxact
  commit, every `lobj->subid == mySubid` is rewritten to `parentSubid`.
  On subxact abort, the matching cookies are `closeLOfd`'d immediately.
  Caller of `lo_open` inside a subxact that aborts cannot reuse the FD.
  [verified-by-code, be-fsstubs.c:660-672]
- **Snapshot lifetime extension.** `lo_open` registers the LO's snapshot
  on `TopTransactionResourceOwner` rather than the current portal —
  otherwise closing a portal mid-xact would invalidate an FD. [from-comment, be-fsstubs.c:110-117]
- **`lo_compat_privileges` shortcut on `lo_unlink`.** Pre-9.0
  PostgreSQL allowed any user to drop any LO; setting this GUC restores
  that behaviour. The default (false) requires owner. This is the only
  residual auth-model relic in the LO API. [verified-by-code, be-fsstubs.c:330-334]
- **`be_lo_lseek` / `be_lo_tell` (32-bit) ereport on overflow.** The 64-bit
  variants don't. Callers using the legacy 32-bit RPC silently see
  numeric-out-of-range failures on LOs > 2 GB. [verified-by-code, be-fsstubs.c:220-225,287-292]
- **`lo_import` / `lo_export` are SUPERUSER-equivalent.** They access the
  server's filesystem; permission checks live in pg_proc ACL via
  `pg_read_server_files` / `pg_write_server_files` role membership (NOT
  enforced inside this file).

## Cross-refs

- Header: `source/src/include/libpq/be-fsstubs.h`
- Catalog/storage layer: `source/src/backend/storage/large_object/inv_api.c`
  (`inv_open`, `inv_create`, `inv_drop`, `inv_read`, `inv_write`,
  `inv_truncate`, `inv_seek`, `inv_tell`, `inv_close`)
- Pg catalog: `source/src/include/catalog/pg_largeobject.h`,
  `pg_largeobject_metadata.h`
- Client-side counterpart: `source/src/interfaces/libpq/fe-lobj.c`
- xact hook registry: called from `source/src/backend/access/transam/xact.c`
  (`CommitTransaction`, `AbortTransaction`, sub-variants)

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-correctness: int32 lo_lseek overflow detection]**
  `be-fsstubs.c:221-225` — `if (status != (int32) status)` is the
  truncation check. Compares int64 against signed-cast-to-int32. Works
  but reads as a "smells like UB" pattern; pgindent-shaped reviewers
  would flag. severity: nit
- **[ISSUE-leak: lo_import_internal does not pfree filename copy on error]**
  `be-fsstubs.c:439-445` — `text_to_cstring_buffer` writes into local
  `fnamebuf[MAXPGPATH]` (stack), so no actual heap leak. But if anyone
  refactors to palloc the buffer, the early ereport paths drop it.
  severity: nit
- **[ISSUE-leak: lo_export does not inv_close on file-write error]**
  `be-fsstubs.c:532-547` — once `inv_open` succeeds, an `ereport(ERROR)`
  on `write()` failure unwinds before `inv_close(lobj)` runs. The xact
  cleanup via `AtEOXact_LargeObject` does close FDs on commit, but
  `lo_export` doesn't use the FD table (passes
  `CurrentMemoryContext` to `inv_open`). The descriptor lives in
  whatever memory context was current, which is usually freed at
  xact-end via the per-portal context cleanup, but the open
  `pg_largeobject` relcache pin is held until `close_lo_relation` in
  `AtEOXact`. Likely benign in practice. severity: maybe
- **[ISSUE-question: lo_compat_privileges still ships in 2026]**
  `be-fsstubs.c:330-334` — `lo_compat_privileges` GUC is an
  acknowledged pre-9.0 backdoor for "drop any LO". It still defaults
  off but EXISTS. Worth a deprecation note in coverage; useful flag
  for security review. severity: maybe
- **[ISSUE-undocumented-invariant: be_lo_open accepts INV_READ |
  INV_WRITE on a read-only xact]** `be-fsstubs.c:98-99` — only
  `PreventCommandIfReadOnly` is called when `INV_WRITE` is set. A
  client opening with `INV_READ` and then attempting `lo_write` will
  fail at write time (good), but the API has no early signal. severity: nit
- **[ISSUE-stale-todo: top-of-file "should be moved to a more
  appropriate place"]** `be-fsstubs.c:14-15` — comment since at least
  PG 8.0. Not actionable, but flagging that the corpus knows about
  the misplacement. severity: nit

## Tally

`[verified-by-code]=18 [from-comment]=8 [inferred]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
