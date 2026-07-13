# Phase 2 brainstorm — pgoutput_uaf (blind)

## §0 Usage surface

Grep summary of `RelationSyncCache` and `entry_cxt` touch sites in
parent-pin `src/backend/replication/pgoutput/pgoutput.c`:

**Static global:**
- Line 220: `static HTAB *RelationSyncCache = NULL;`

**Initialization:**
- Line 545: `init_rel_sync_cache(CacheMemoryContext);` — invoked
  from `pgoutput_startup`, only if not already initialized.
- Line 1965: `hash_create(...)` inside `init_rel_sync_cache`.

**Per-entry sub-context:**
- Line 187: `MemoryContext entry_cxt;` field of `RelationSyncEntry`.
- Line 879: `entry->entry_cxt = AllocSetContextCreate(data->cachectx, ...)`
  — child of `data->cachectx` which is child of `ctx->context`.
- Line 2154: `MemoryContextDelete(entry->entry_cxt);` — called
  from `rel_sync_cache_relation_cb`.

**Reads / walks:**
- Lines 1004, 1106, 2041, 2333, 2387, 2397, 2428: `hash_search`,
  `hash_seq_init`, ensure-entry-cxt.

**Clean shutdown:**
- Lines 1761-1768: `pgoutput_shutdown` — `hash_destroy` +
  `RelationSyncCache = NULL`.

**Load-bearing site (R15a):**
The load-bearing invariant is at line 220 + 1763-1766:
`RelationSyncCache` is a static global outliving `ctx->context`
lifetime, so its stale pointer survives error-path teardown of
`data->cachectx` and every `entry_cxt` inside it. Any consumer
that reads `RelationSyncCache` on a second invocation (lines
2038-2041 primarily — `get_rel_sync_entry`) UAFs.

## §0.5 Existing-mechanism survey

Grep `MemoryContextRegisterResetCallback` in `src/backend/`:

| Site                                       | Purpose                            |
|--------------------------------------------|------------------------------------|
| `postgres_fdw.c` (post-232d8caeaaa)        | Free PGresult on scan teardown     |
| `dsm.c` (multiple)                         | Detach DSM segments on ctx reset   |
| `funccache.c` (post-be86ca103a4)           | Free CachedFunction on error       |
| `tuplesort.c`                              | Close tape files on ctx reset      |
| `spi.c`                                    | Free SPI plans on abort            |
| `replication/logical/tablesync.c`          | Free relmap on subscription reset  |

The idiom is well-established. F34+F35+F36 (from `memory-contexts.md`)
apply.

## §1 Problem statement

Logical decoding via `pg_logical_slot_get_binary_changes` (or peer
SQL functions) that errors mid-decode tears down `ctx->context`
(and all descendants including `data->cachectx` and every entry's
`entry_cxt`). But `RelationSyncCache` — a static HTAB rooted in
`CacheMemoryContext` — survives. The stale entries hold pointers
into now-freed `entry_cxt` blocks. The next SQL-driven decoding
call reads `RelationSyncCache != NULL`, tries to use its entries,
UAFs.

## §2 Scope contract

**IN scope:**
- Ensure `RelationSyncCache` is NULLed on ANY teardown of
  `data->cachectx` or an ancestor (including error paths).
- Preserve existing successful-shutdown behavior (line 1761).

**OUT of scope:**
- v13/v14 back-port (upstream declined; per commit message).
- Changing pgoutput's decoding-callback contract.
- Refactoring `RelationSyncCache` to not be static.
- Fixing sister UAFs in other output plugins (`test_decoding`).

## §5 Candidate approaches

### Approach A — Explicit NULL in every error catcher

Wrap every error-raising site in pgoutput with a `PG_TRY` that
NULLs `RelationSyncCache` in the CATCH. Rejected — the error can
propagate from anywhere in the decode stack (LoadPublications,
row-filter evaluation, column-list build, tuplestore write, etc.);
we'd need ~15 PG_TRY sites plus every future error path forever.
High blast-radius maintenance debt.

### Approach B — Single PG_TRY at pgoutput's plugin entry

Wrap the outermost pgoutput callback with a PG_TRY that NULLs the
cache in CATCH. Rejected — the errors that trigger the UAF fire
BENEATH the plugin callbacks (from executor / row-filter / etc.),
and PG_TRY at the top-of-callback doesn't help once we've returned
to logical-decoding infrastructure.

### Approach C — Register a callback on `CacheMemoryContext`

Register a reset callback on `CacheMemoryContext` itself. Rejected —
`CacheMemoryContext` outlives decoding sessions and is shared by
many subsystems; registering there would fire on unrelated resets.

### Approach D — Move `RelationSyncCache` into `data->cachectx`

Create `RelationSyncCache` as an HTAB in `data->cachectx` instead
of `CacheMemoryContext`. When `data->cachectx` is deleted on
error, the HTAB dies too. Interesting but rejected: it changes
the cache lifetime semantics substantially (every fresh decoding
session rebuilds from scratch) and doesn't match the existing
"static HTAB" pattern the rest of pgoutput uses (which the invcalidation
callbacks depend on).

### Approach E (L6 mandatory — target function has ≥3 error exit paths, fix needs a common teardown step)

Register a `MemoryContextRegisterResetCallback` on
`data->cachectx` that NULLs the `RelationSyncCache` global. Since
`data->cachectx` is a child of `ctx->context`, teardown of
`ctx->context` on error triggers teardown of `data->cachectx`,
which fires the callback, which NULLs the stale HTAB pointer.
Next SQL-driven decoding call sees NULL, `init_rel_sync_cache`
rebuilds fresh.

The existing `pgoutput_shutdown` (line 1761-1768) already does
`hash_destroy` + NULL on the SUCCESSFUL shutdown path; the callback
handles ONLY the ERROR path. On success, `pgoutput_shutdown` runs
first, NULLs the cache, then `data->cachectx` teardown fires the
callback which sees NULL and no-ops.

**L7 sub-block (MANDATORY per plan §7 template)** — for approach
E, the three implementation details:

1. **Callback storage location.** *F34: embed in state struct.*
   Add `MemoryContextCallback sync_cache_cb` as a field of
   `PGOutputData`. `PGOutputData` is already palloc'd in
   `pgoutput_startup` via
   `palloc0(sizeof(PGOutputData))` (parent-pin line ~440); the
   embedded callback field lives in the same block. Zero separate
   allocations. Alternative (separate palloc via
   `MemoryContextAlloc(data->cachectx, ...)`) is rejected — no
   reason to pay for a second palloc when the state struct has
   room.

2. **Callback function shape.** *F35: direct cast when possible;
   wrapper when bookkeeping needed.* The cleanup here is
   `RelationSyncCache = NULL` — a store to a static global — plus
   `hash_destroy(RelationSyncCache)` (the HTAB itself lives in
   `CacheMemoryContext` which survives; without hash_destroy we'd
   leak the HTAB shell across the error). This is TWO operations,
   so we NEED a wrapper. Wrapper signature:
   ```c
   static void
   pgoutput_relsync_reset_callback(void *arg)
   {
       if (RelationSyncCache != NULL)
       {
           hash_destroy(RelationSyncCache);
           RelationSyncCache = NULL;
       }
   }
   ```
   The `arg` is unused — the target of cleanup is the file-static
   global. F35's "direct cast" preference doesn't apply here
   because there's no single-shot cleanup function for both
   operations; the wrapper is genuinely necessary.

3. **Ownership semantics.** *F36: single-owner via callback.*
   Once armed, the callback owns the cache's lifecycle for the
   duration of `data->cachectx`. `pgoutput_shutdown` (line 1761)
   currently does the same cleanup; on the happy path it fires
   FIRST, NULLs the cache, then `data->cachectx` teardown triggers
   the callback which sees NULL and no-ops. This is single-owner
   with a "belt-and-suspenders" arrangement — the callback is
   armed always; the shutdown path is disarmed by the NULL check
   inside the callback. No detach needed.

## §6 Recommended approach

**Approach E.** Register a `MemoryContextCallback` on
`data->cachectx` that hash_destroys + NULLs `RelationSyncCache`.
Embed the callback struct in `PGOutputData` (F34). Wrapper
function is required (F35 wrapper is justified — two operations
needed). Single-owner via callback with `pgoutput_shutdown`'s
existing NULL-first cleanup providing happy-path disarm (F36).

What would make another approach win:
- If `pgoutput_shutdown` had been called reliably on error too,
  approach A (explicit NULL in a shared cleanup helper) could work
  — but it's not, that's the whole bug.
- If we wanted to eliminate `pgoutput_shutdown`'s hash_destroy
  entirely, approach E with callback-only ownership would be
  cleanest — deferred to a follow-up.

## §7 Load-bearing test

The invocation-1-errors-then-invocation-2-succeeds SQL sequence
from baseline.md §Reproducer draft. Under macOS + cassert +
`MALLOC_PERTURB_=209`, invocation-2 crashes with UAF signal on
parent-pin; succeeds cleanly on post-fix.

## §8 Open questions

1. Is `data->cachectx` the RIGHT context to arm on, or should the
   callback go on `ctx->context` itself? `data->cachectx` is a
   child of `ctx->context`, so both get torn down on error. If we
   arm on `data->cachectx`, callback fires BEFORE `data->cachectx`
   memory is reclaimed; if on `ctx->context`, callback fires
   AFTER `data->cachectx` is already gone (child contexts die
   first). Either works because the cleanup target is a
   file-static global, not the context contents. Prefer
   `data->cachectx` — closer to the resource whose lifetime we
   care about.

2. Does the fix need to preserve back-patch simplicity for PG15+?
   The change is 1 struct field + 1 callback function + 1
   registration line + no touches to hot paths. Minimal
   back-patch risk.

3. Is there a `test_decoding` sister leak? The commit message
   implies yes (mentions similar issues) but scopes out. Not our
   concern this run.
