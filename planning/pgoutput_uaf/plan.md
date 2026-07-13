# Phase 2 plan — pgoutput_uaf (blind)

## §1 Problem statement

pgoutput's static `RelationSyncCache` HTAB outlives the decoding
context (`ctx->context` and its child `data->cachectx`) when a
SQL-driven decoding call errors mid-flight. `pgoutput_shutdown`
(the standard cleanup) is not called on the error path.  The next
decoding call sees `RelationSyncCache != NULL`, follows entries
into torn-down memory, UAFs.

## §2 Design

Register a `MemoryContextRegisterResetCallback` on
`data->cachectx` in `pgoutput_startup` that hash_destroys +
NULLs `RelationSyncCache` on any teardown.  The callback runs
on both error-path (context torn down by aborting transaction)
and success-path (context torn down after `pgoutput_shutdown`
has already NULLed the cache, so the callback sees NULL and
no-ops).

Approach E from brainstorm §6.  L7 details:
- **Storage:** embed `MemoryContextCallback sync_cache_cb` in
  `PGOutputData` (F34).
- **Function shape:** wrapper `pgoutput_relsync_reset_callback`
  because two operations (hash_destroy + NULL) can't cast a
  single well-known cleanup function (F35 justifies wrapper here).
- **Ownership:** single-owner via callback (F36); existing
  `pgoutput_shutdown` remains as the happy-path NULL-first
  disarm.

## §3 Files that change — at parent pin `71540dcdcb2`

| File                                            | Change            | Size   | Summary                                                                 |
|-------------------------------------------------|-------------------|--------|-------------------------------------------------------------------------|
| `src/backend/replication/pgoutput/pgoutput.c`   | modify            | small  | Add `MemoryContextCallback` field to `PGOutputData` (line ~208); add wrapper function `pgoutput_relsync_reset_callback` near line 1760; register callback in `pgoutput_startup` right after `init_rel_sync_cache` at line 545. |
| `src/include/replication/pgoutput.h` (?)        | if PGOutputData is public | small | Only if `PGOutputData` struct is defined in a header — parent-pin inspection shows it's file-local (line ~130 of pgoutput.c), so header change is NOT needed. |

**Estimated diff size:** ~15-25 lines inserted, 0-3 removed.
Well within the shape of `+24 / −5` in the target commit's stat.

## §4 Catalog + on-disk impact

None. No `pg_*.dat`, no header struct exposed to callers.

## §5 WAL impact

None. Pure pgoutput decoding-side; no WAL record touches.

## §6 Locking + concurrency

None. `RelationSyncCache` is a backend-static global; the callback
fires during context teardown while the backend is single-threaded.

## §7 Memory + resource management — F30 grep-verified ownership

**Ownership claim under test:**
> `RelationSyncCache` is a backend-static HTAB that lives in
> `CacheMemoryContext`. Its ENTRIES point to state (row filters,
> column lists) in each `RelationSyncEntry.entry_cxt` — descendants
> of `data->cachectx`. When `data->cachectx` is torn down, the
> entries' targets become UAF-hazards. The static HTAB must be
> NULLed at that moment.

**F30 grep verification:**

```
grep -RnE 'RelationSyncCache\s*=' \
    /Users/matej/Work/postgres/postgresql-dev-feature-pgoutput-uaf/src/backend/replication/pgoutput/pgoutput.c
```

Result — 4 assignments:

| Site                                            | Assignment                          | Reason                                          |
|-------------------------------------------------|-------------------------------------|-------------------------------------------------|
| pgoutput.c:220                                  | `= NULL` (initializer)              | Static file-scope                               |
| pgoutput.c:1766 (`pgoutput_shutdown`)           | `= NULL` after hash_destroy         | Happy-path cleanup                              |
| pgoutput.c:1965 (`init_rel_sync_cache`)         | `= hash_create(...)`                | Lazy init on first decode session               |
| pgoutput.c:NEW (this plan)                      | `= NULL` in callback                | Error-path cleanup (fix)                        |

**Cleanup path:**
- **Happy path** (decoding completes without error):
  `pgoutput_shutdown` runs → `hash_destroy(RelationSyncCache); RelationSyncCache = NULL;`.
  Later `data->cachectx` reset triggers callback which sees NULL,
  no-ops.
- **Error path** (decoding errors mid-flight):
  `pgoutput_shutdown` does NOT run.  Aborting transaction resets
  `ctx->context` which triggers `data->cachectx` teardown which
  fires callback which `hash_destroy(RelationSyncCache); RelationSyncCache = NULL;`.

**Verified: no double-free.**  Two release paths, exactly one
fires per invocation.

**L7 sub-block (callback-based approach detail — mandatory per
plan skill §7):**

1. **Callback storage location.** *F34: embed in state struct.*
   Add `MemoryContextCallback sync_cache_cb` as a field of
   `PGOutputData`. Rationale: `PGOutputData` is already palloc'd
   in `pgoutput_startup` (via `palloc0(sizeof(PGOutputData))` at
   parent-pin line ~440); embedded field lives in the same
   allocation. Zero extra palloc. No separate ownership question.

2. **Callback function shape.** *F35: direct cast when possible;
   wrapper only when bookkeeping needed.* Here the cleanup is
   `hash_destroy(RelationSyncCache); RelationSyncCache = NULL;` —
   TWO operations against a file-static global. Direct-cast
   idiom cannot express this. Write a wrapper:
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
   `arg` is unused; the target is a static global. F35's
   preference for direct cast doesn't apply because there's no
   single stdlib/libpq routine that does both hash_destroy + NULL.

3. **Ownership semantics.** *F36: single-owner via callback.*
   The callback is armed permanently for the lifetime of
   `data->cachectx`. On happy path `pgoutput_shutdown` (line
   1766) NULLs the cache FIRST; the callback fires later and
   sees NULL (no-op). On error path only the callback fires.
   The check `if (RelationSyncCache != NULL)` inside the callback
   is the disarm; no explicit `cb.arg = NULL` bookkeeping is
   needed because the target (the global) is what encodes armed
   state.

## §8 Phased implementation

Single phase — the fix is small enough.

### Phase 1 — Register RelationSyncCache reset callback on data->cachectx

**Files:** `src/backend/replication/pgoutput/pgoutput.c`.

**Edits:**

1. Add `MemoryContextCallback sync_cache_cb;` field to
   `PGOutputData` struct definition (parent-pin line ~130,
   near the `MemoryContext cachectx;` field).

2. Add wrapper function `pgoutput_relsync_reset_callback` near
   `pgoutput_shutdown` (parent-pin line ~1760):
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

3. In `pgoutput_startup` (parent-pin line ~440 approx),
   immediately after `init_rel_sync_cache(CacheMemoryContext);`
   (line 545), register the callback on `data->cachectx`:
   ```c
   data->sync_cache_cb.func = pgoutput_relsync_reset_callback;
   data->sync_cache_cb.arg = NULL;    /* target is a file-static global */
   MemoryContextRegisterResetCallback(data->cachectx,
                                      &data->sync_cache_cb);
   ```

**Phase-end check** (R13 scope — replication/decoding
subsystem):

```
meson test --no-rebuild --suite regress --suite isolation
```

Plus the manual proxy from baseline.md — invocation-1 errors,
invocation-2 succeeds cleanly on post-fix vs crashes on parent.

**Exit condition:**
- Regress + isolation green.
- Invocation-2 completes without crash on post-fix build.
- Parent-pin build reproduces UAF on invocation-2 (proxy — the
  demonstrable direction of the fix, even if hard to run
  reliably on macOS per baseline's F26+F27 caveat).

## §9 Test surface

- **Regress**: pgoutput has no dedicated regress file; the
  subscription TAP suite `src/test/subscription/` covers it
  end-to-end (requires `-Dtap_tests=enabled`, not this box's
  default). Phase-end R13 falls back to core regress + isolation.

- **Own-test-suite (R14)**: A dedicated TAP test could
  `pg_logical_slot_get_binary_changes` with a bad publication
  name (first call), then a good one (second call), and assert
  the second returns successfully. NOT part of this phase — flag
  for follow-up if we decide to upstream.

## §10 Documentation impact

None. `MemoryContextCallback` idiom is a well-established
internal pattern (see `knowledge/idioms/memory-contexts.md`
§Reset / delete callbacks). No user-facing docs.

## §11 Backport

Upstream back-patches to PG15 per commit message. Our worktree
targets master at `71540dcdcb2`; the fix is small enough to
apply cleanly to older branches modulo minor context drift.
Not our concern this run.

## §12 Cross-references

- Idiom: `knowledge/idioms/memory-contexts.md` §"Reset / delete
  callbacks" + §"Idioms for callback-based ownership"
  (F34+F35+F36).
- Scenario: `knowledge/scenarios/fix-memory-leak.md` §Step 0.4
  (F31 reproducer verification) + §Step 0.5 (F37 target-suite
  health).
- Skill: `.claude/skills/pg-feature-brainstorm/SKILL.md` §5
  Mandatory approach E + §Method step 6 "Adversarial-pass for
  control-flow shape (L6)".
- Skill: `.claude/skills/pg-feature-plan/SKILL.md` §7 Callback-based
  approach detail sub-block (L7).

## §13 Known risks + unknowns

1. **Callback fires but RelationSyncCache is already destroyed
   by pgoutput_shutdown.** Guard: the `if (RelationSyncCache != NULL)`
   check inside the callback handles this. Verified in §7.
2. **Callback armed on wrong context.** Chose `data->cachectx`
   over `ctx->context` because `data->cachectx` is
   pgoutput-specific — armed callback fires only when
   pgoutput-specific state is being torn down. Arming on
   `ctx->context` would also work but is broader.
3. **hash_destroy on stale entries.** `hash_destroy` walks the
   hash's context list. If `data->cachectx` teardown has already
   started before the callback fires, the entries' contexts may
   be inaccessible. Verify empirically in Phase 3 by observing
   the callback fires BEFORE `data->cachectx` frees its blocks
   (which is the documented `MemoryContextRegisterResetCallback`
   behavior).
4. **`pgoutput_shutdown` becomes redundant.** With the callback
   armed permanently, `pgoutput_shutdown`'s hash_destroy + NULL
   could be deleted (rely on callback for both paths). Deferred
   to a follow-up — current plan keeps `pgoutput_shutdown`
   unchanged to minimize back-patch surface.

## §14 Phase-4 comparison hook

Pre-declared axes for comparison against `b46efe90482` (do not
consult during Phase 3):

1. **Callback storage location.** We chose F34 embed in
   `PGOutputData`. Does Tom / Vignesh do the same?
2. **Callback function shape.** We chose a wrapper (F35 not
   applicable — two-op cleanup). Did upstream also write a
   wrapper?
3. **Callback armed on which context?** We chose `data->cachectx`.
   Did upstream choose `ctx->context` or `data->cachectx` or
   somewhere else?
4. **Ownership semantics.** We kept `pgoutput_shutdown` as
   happy-path disarm (F36 belt-and-suspenders). Did upstream
   delete `pgoutput_shutdown`'s cleanup or keep it?
5. **Diff size.** Ours estimated +15-25 lines, ~0-3 removed.
   Upstream is +24/-5. Should be close.
6. **Regress test additions.** We deferred. Did upstream ship
   a TAP test?

The L7 sub-block is the primary calibration criterion — did the
blind trilogy correctly name the same 3 detail choices as
Tom's upstream fix?
