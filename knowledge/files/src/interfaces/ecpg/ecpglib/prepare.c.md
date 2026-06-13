---
path: src/interfaces/ecpg/ecpglib/prepare.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 662
depth: deep
---

# `prepare.c` — ecpglib runtime PREPARE/EXECUTE/DEALLOCATE and auto-prepare statement cache

## Purpose
Implements the ecpglib runtime support for `EXEC SQL PREPARE`, `DEALLOCATE PREPARE`,
and the auto-prepare statement cache used when the precompiler is run with
auto-prepare enabled. Two distinct data structures live here: (1) a *per-connection
linked list* of `struct prepared_statement` (anchored at `con->prep_stmts`),
tracking every named statement that has been `PQprepare`'d on a connection
`[verified-by-code prepare.c:107-113]`; and (2) a *global hash-bucketed statement
cache* (`stmtCacheEntries`, `stmtCacheNBuckets * stmtCacheEntPerBucket + 1` slots)
that maps an ECPG-format query text to a generated statement ID so identical queries
reuse a server-side prepared statement `[verified-by-code prepare.c:23-38, 536-597]`.
`ecpg_auto_prepare` ties them together: hash-lookup the query, reuse or evict a cache
slot, ensure the statement is prepared on the target connection, and bump an execution
counter used as the LRU-ish eviction key `[verified-by-code prepare.c:600-662]`.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `bool ecpg_register_prepared_stmt(struct statement *stmt)` | prepare.c:58 | Registers an already-built `struct statement` as a prepared-statement list entry (used by the PREPARE-FROM path); deallocates a same-named existing one first. |
| `bool ECPGprepare(int lineno, const char *connection_name, const bool questionmarks, const char *name, const char *variable)` | prepare.c:248 | Entry point for `EXEC SQL PREPARE name FROM :var`. `questionmarks` retained only for API stability `[from-comment prepare.c:247]`. |
| `struct prepared_statement *ecpg_find_prepared_statement(const char *name, struct connection *con, struct prepared_statement **prev_)` | prepare.c:270 | Linear search of `con->prep_stmts` by name; optionally returns the predecessor for unlink. |
| `bool ECPGdeallocate(int lineno, int c, const char *connection_name, const char *name)` | prepare.c:346 | `EXEC SQL DEALLOCATE PREPARE name`; INFORMIX mode silently succeeds if not found `[verified-by-code prepare.c:362-364]`. |
| `bool ecpg_deallocate_all_conn(int lineno, enum COMPAT_MODE c, struct connection *con)` | prepare.c:368 | Drains the whole `con->prep_stmts` list. |
| `bool ECPGdeallocate_all(int lineno, int compat, const char *connection_name)` | prepare.c:381 | Connection-name wrapper over `ecpg_deallocate_all_conn`. |
| `char *ecpg_prepared(const char *name, struct connection *con)` | prepare.c:392 | Returns the stored command text for a prepared name, or NULL. |
| `char *ECPGprepared_statement(const char *connection_name, const char *name, int lineno)` | prepare.c:402 | Public wrapper over `ecpg_prepared`. |
| `bool ecpg_auto_prepare(int lineno, const char *connection_name, const int compat, char **name, const char *query)` | prepare.c:600 | Auto-prepare driver; allocates `*name` (caller owns/frees) and bumps the cache exec counter. |

## Internal landmarks
- **Per-connection prepared list**: singly-linked `struct prepared_statement`, head at
  `con->prep_stmts`, prepended on insert `[verified-by-code prepare.c:107-112, 237-242]`.
  Each node owns a `struct statement *stmt` (carrying `command`) and a `char *name`.
- **`replace_variables` (prepare.c:116)**: rewrites host-variable placeholders (`:` /
  `?`) in the command text into positional `$n` params, skipping `'...'` string
  literals and `::` casts. Allocates a fresh buffer per substitution and swaps `*text`,
  freeing the old copy `[verified-by-code prepare.c:146-161]`.
- **`prepare_common` (prepare.c:171)**: the real PREPARE — builds the statement, runs
  `replace_variables`, calls `PQprepare`, and on success links into `con->prep_stmts`.
  Has a full unwind-free ladder on every failure point `[verified-by-code prepare.c:194-231]`.
- **`deallocate_one` (prepare.c:291)**: issues a server-side `DEALLOCATE "name"`,
  unlinks the node, and frees `stmt->command`, `stmt`, `name`, and the node
  `[verified-by-code prepare.c:333-341]`. Non-INFORMIX modes raise on a failed
  server dealloc `[verified-by-code prepare.c:326-330]`.
- **Statement cache hash (`HashStmt`, prepare.c:416)**: sums + rotates the first 50
  chars of the ECPG query, mod `stmtCacheNBuckets`, returns the first slot of the
  bucket (offset by 1 so slot 0 is the reserved "not found" sentinel)
  `[verified-by-code prepare.c:426-444]`.
- **`SearchStmtCache` / `AddStmtToCache` / `ecpg_freeStmtCacheEntry`** (prepare.c:452,
  536, 488): linear probe within a bucket of `stmtCacheEntPerBucket` (8) slots;
  eviction picks the least-executed entry in the bucket `[verified-by-code prepare.c:565-580]`.
- **Name generation**: `nextStmtID` (static, starts at 1) produces `ecpg%d` IDs in the
  auto-prepare insert path `[verified-by-code prepare.c:37, 639]`.

## Invariants & gotchas
- **Slot 0 is reserved.** `stmtCacheArraySize` is `NBuckets*EntPerBucket + 1`, and
  `HashStmt` adds 1 so a return of 0 means "not found." Do not let an entry land in
  slot 0 `[verified-by-code prepare.c:26, 443-444, 477-480]`.
- **`entry->connection` is stored by pointer, not copied.** `AddStmtToCache` does
  `entry->connection = connection` (prepare.c:592), keeping the caller's
  `const char *` connection-name pointer. `ecpg_freeStmtCacheEntry` later passes it to
  `ecpg_get_connection` (prepare.c:505). If the connection name's backing storage is
  freed/reused, this dangles `[inferred]`. In practice the callers pass a long-lived
  connection-name string, but this is an aliasing assumption, not a copy.
- **Cache eviction must go through `ecpg_freeStmtCacheEntry` before reuse**, which also
  tears down the server-side prepared statement via `deallocate_one`. `AddStmtToCache`
  calls it before overwriting the slot `[verified-by-code prepare.c:582-584]`.
- **Connection-gone is handled on eviction.** If `ecpg_get_connection(entry->connection)`
  returns NULL, the prepared-list cleanup is skipped but the cache slot is still cleared
  and reused `[verified-by-code prepare.c:505-520]`.
- **`ecpg_auto_prepare` `execs++` requires a valid `entNo`.** Every success path sets
  `entNo` to a found, reused, or freshly-added slot before line 659; a returned slot of
  0 only occurs on the not-found branch which then assigns from `AddStmtToCache`
  `[verified-by-code prepare.c:606-659]`.
- **Statement-name ownership.** In `ecpg_auto_prepare`, `*name` is `ecpg_strdup`'d and
  the caller owns it; every error path after the strdup frees it before returning
  `[verified-by-code prepare.c:618-655]`.
- **No thread locking in this file.** The global `stmtCacheEntries` and `nextStmtID` are
  process-global statics with no mutex here; ecpglib's threading model relies on
  per-thread connections, but the *auto-prepare cache and `nextStmtID` are shared*
  `[inferred — no lock visible in prepare.c]`. Concurrent auto-prepare across threads
  could race on the cache array and the ID counter.

## Cross-refs
- [[execute.c]], [[connect.c]], [[descriptor.c]]

## Potential issues
- **[ISSUE-leak: cache `ecpgQuery` never freed at shutdown]** `prepare.c:589` — the
  `stmtCacheEntries` array and the `ecpg_strdup`'d `ecpgQuery` strings are process-global
  and only freed on eviction; there is no teardown that frees the whole array, so the
  cache and its current entries persist for process life. Low severity (bounded by
  `stmtCacheArraySize`, freed/overwritten on reuse), but it is an unreclaimed global
  `[inferred]`.
- **[ISSUE-lifetime: cache stores connection-name pointer by reference]** `prepare.c:592`
  — `entry->connection` aliases the caller-supplied connection-name string rather than
  copying it; a later `ecpg_freeStmtCacheEntry` dereferences it via
  `ecpg_get_connection` (prepare.c:505). If a caller ever passes a transient buffer for
  the connection name, this is a use-after-free. Medium severity; depends on caller
  contract, which is not enforced here `[inferred]`.
- **[ISSUE-concurrency: global auto-prepare cache and `nextStmtID` unsynchronized]**
  `prepare.c:37, 552-594, 639` — `stmtCacheEntries` (lazy-allocated global) and
  `nextStmtID` are mutated without locking in `ecpg_auto_prepare`/`AddStmtToCache`.
  Multiple threads doing auto-prepare can race (duplicate IDs, torn slot writes,
  double-alloc of the array). Medium severity; only affects multithreaded ecpg programs
  using auto-prepare `[inferred — no lock present in this file]`.
