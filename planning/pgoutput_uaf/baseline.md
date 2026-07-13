# Baseline — pgoutput RelationSyncCache UAF (5th calibration)

**Target commit:** `b46efe90482` (Vignesh C + Masahiko Sawada, "Fix
access-to-already-freed-memory issue in pgoutput.", 2025-10-09,
back-patched through PG15).

**Parent pin (worktree):** `71540dcdcb2` in
`/Users/matej/Work/postgres/postgresql-dev-feature-pgoutput-uaf/`.

**Bug shape (per public commit summary):** "If a logical decoding
invoked via SQL functions like `pg_logical_slot_get_binary_changes`
fails with an error, subsequent logical decoding executions could
access already-freed memory of the entry's cache, resulting in a
crash."

**Fix shape (per public commit summary):** register a
`MemoryContextRegisterResetCallback` on some pgoutput-owned context to
clean up `RelationSyncCache` on error.

Everything below is derived from reading only the parent-pin source at
`src/backend/replication/pgoutput/pgoutput.c` and the surrounding
logical-decoding infrastructure — NOT the target patch, NOT the
pgsql-hackers thread, NOT the four prior calibration outputs.

## Step 0.1 — Subsystem entry points

`src/backend/replication/pgoutput/pgoutput.c` (2463 lines at parent
pin) is the built-in output plugin used by all logical-replication
subscribers. Its `_PG_output_plugin_init` registers the standard
`OutputPluginCallbacks` (begin/change/commit/truncate/message/…) plus
optional streaming and two-phase callbacks. Two per-decoding-session
data structures are the load-bearing state:

- `PGOutputData` — per-session plugin state, allocated in
  `ctx->output_plugin_private`. Owns three child contexts of
  `ctx->context`:
  - `data->context` — `ALLOCSET_DEFAULT_SIZES`, scratch for per-change
    encoding (reset at end of each change: line 1625, 1693).
  - `data->cachectx` — `ALLOCSET_DEFAULT_SIZES`, parent of every
    `entry_cxt` created by `pgoutput_ensure_entry_cxt` for row filter
    expression trees, column lists, and the `EState` used to evaluate
    them.
  - `data->pubctx` — `ALLOCSET_SMALL_SIZES`, holds the
    `data->publications` list rebuilt on each publication-invalidation.
  All three are documented (line 1756-1758) as "we don't need to clean
  ... they are child contexts of the ctx->context so they will be
  cleaned up by logical decoding machinery."
- `RelationSyncCache` — a static-file `HTAB *` (line 220) keyed on
  `Oid` → `RelationSyncEntry`. Created in `init_rel_sync_cache` (line
  1957) with `HASHCTL.hcxt = cachectx` where `cachectx` is passed in
  as `CacheMemoryContext` (see `pgoutput_startup` line 545). Destroyed
  only by `pgoutput_shutdown` (line 1761-1767).

## Step 0.2 — The load-bearing invariant that goes stale on error

`RelationSyncEntry` (lines 126-188) carries a `MemoryContext
entry_cxt` field. That context is created by `pgoutput_ensure_entry_cxt`
(line 869-885) as a child of `data->cachectx`, and holds row filter
`ExprState`s, `EState`, tuple slots' bookkeeping, column bitmaps, and
attribute maps.

The lifetime asymmetry that the bug exploits:

- **`RelationSyncCache` (the HTAB itself)** lives in
  `CacheMemoryContext`, which is a long-lived process-lifetime context.
  It is NOT destroyed by transaction abort or by decoding-session
  teardown.
- **`entry->entry_cxt` (per-entry private data)** lives under
  `data->cachectx`, which is a child of `ctx->context`, which IS
  destroyed by `FreeDecodingContext` (`logical.c:685
  MemoryContextDelete(ctx->context)`).

On the happy path both are torn down together: the SQL function's
`PG_TRY` runs `FreeDecodingContext(ctx)` which invokes the shutdown
callback (line 679-680), and `pgoutput_shutdown` calls
`hash_destroy(RelationSyncCache); RelationSyncCache = NULL;`
(line 1763-1766). Then the caller resets its memory context.

On the error path (`logicalfuncs.c:319-324 PG_CATCH`), only
`InvalidateSystemCaches()` and `PG_RE_THROW()` run —
`FreeDecodingContext` is NOT called. Instead, the ambient error
recovery in the SQL function's caller resets the message-level memory
context, which is the parent of `ctx->context`, so:

1. `ctx->context` and all its children (`data->cachectx`, every
   `entry_cxt`) are destroyed.
2. `RelationSyncCache` in `CacheMemoryContext` is NOT destroyed and
   `RelationSyncCache != NULL` remains true.
3. Every `RelationSyncEntry` in the surviving HTAB still holds
   `entry_cxt`, `exprstate[]`, `estate`, `new_slot`, `old_slot`,
   `attrmap`, `columns` pointers into now-freed memory.

Next invocation of `pg_logical_slot_get_binary_changes`:

- `pgoutput_startup` runs, creates fresh `data->cachectx` etc.
- Reaches `init_rel_sync_cache(CacheMemoryContext)` (line 545), which
  short-circuits at line 1958-1959: "Nothing to do if hash table
  already exists" — so the old, corrupt HTAB is inherited wholesale.
  Note also line 1969-1970: `Assert(RelationSyncCache != NULL);` fires
  only if the hash-create returned NULL, not if the old HTAB was reused.
- First relation seen in the new session hits `get_rel_sync_entry`
  (line 2029), does `hash_search(HASH_ENTER, &found)`. If the relid
  matches a survivor entry, `found = true`, and the initializer block
  at line 2044-2058 is SKIPPED.
- Falls through to the "validate" block. But `entry->replicate_valid`
  is UNCHANGED from the prior session (still `true` in most cases, or
  `false` from an inval callback), so the code either uses stale
  pointers directly or reruns the rebuild path.
- The rebuild path itself accesses stale state: line 2153
  `MemoryContextDelete(entry->entry_cxt)` on a dangling pointer, or
  line 2143 `free_attrmap(entry->attrmap)` on freed memory, or line
  2115 `ExecDropSingleTupleTableSlot(entry->old_slot)` on a freed slot.

Any of those is the UAF. Under `--enable-cassert` the most likely
symptom is a MemoryContext method-table dispatch on garbage → SIGSEGV
in `AssertNotInCriticalSection` or in the context-header check. Under
release build the symptom is a heap-corruption crash somewhere in
`hash_destroy` or the next `MemoryContextDelete`.

## Step 0.3 — Cross-check via callback registration comment

Line 531-542 registers `publication_invalidation_cb` and
`rel_sync_cache_relation_cb` with `CacheRegisterSyscacheCallback` /
`CacheRegisterRelSyncCallback`, gated by a `static bool
publication_callback_registered` (line 519). The callbacks are
registered process-wide and CANNOT be unregistered — the comment at
line 2361-2368 ("We can get here if the plugin was used in SQL
interface as the RelationSyncCache is destroyed when the decoding
finishes, but there is no way to unregister the relcache
invalidation callback") EXPLICITLY acknowledges that
`RelationSyncCache` and its owning callback subsystem outlive a single
decoding session's teardown. That's a strong hint that the
process-lifetime `CacheMemoryContext` residency of the HTAB is by
design — the fix cannot move the HTAB itself into a shorter-lived
context without also refactoring callback dispatch.

## Step 0.4 (F31) — SQL-invocation path shape check

`pg_logical_slot_get_binary_changes(fcinfo)` →
`pg_logical_slot_get_changes_guts(fcinfo, confirm=true, binary=true)`
in `src/backend/replication/logical/logicalfuncs.c`. The function
wraps decoding in `PG_TRY`/`PG_CATCH`:

- `PG_TRY` body: `CreateDecodingContext` → main decode loop calling
  `LogicalDecodingProcessRecord` → `FreeDecodingContext` on completion.
- `PG_CATCH`: `InvalidateSystemCaches()`, then `PG_RE_THROW()`.
  **No `FreeDecodingContext` call on the error path.** This is the
  precise ingredient the commit summary calls out.

Reproducer strategy (Step 0.5 below): trigger an ERROR during
`LogicalDecodingProcessRecord` on the first invocation, then invoke
the SQL function a second time and observe a crash or corrupt HTAB
lookup. Cleanest triggers are:

- Row-filter parse failure: create a publication whose row filter
  references a column dropped between publication creation and
  decoding. `pgoutput_row_filter_init` → `pg_parse_query` /
  `pg_analyze_and_rewrite` on the qualified text will ereport on the
  missing column while `entry_cxt` is already allocated.
- Bad type conversion in row filter: filter expression `(x + 'not a
  number')::integer` where the coercion fails during ExecEvalExpr.
- Publication drop mid-decode via a concurrent session — but this
  raises other subtleties around invalidation delivery so it's not the
  cleanest choice.

Simplest verbatim reproducer, one session, no concurrency:

```sql
-- Session setup
CREATE TABLE t (a int, b int);
CREATE PUBLICATION p1 FOR TABLE t
    WHERE (b / 0 = 0);  -- row filter that will divide-by-zero
                        -- at execution time, not at publish time.
SELECT pg_create_logical_replication_slot('slot1', 'pgoutput');

-- Generate WAL under the slot's snapshot horizon
INSERT INTO t VALUES (1, 5);

-- Invocation 1: fails
SELECT pg_logical_slot_get_binary_changes(
    'slot1', NULL, NULL,
    'proto_version', '4',
    'publication_names', 'p1');
-- Expected: ERROR: division by zero (inside pgoutput_row_filter)
--          At this point the RelationSyncEntry for 't' has been
--          initialized (entry_cxt allocated) but the session ERRORed
--          out.  data->cachectx (child of ctx->context) is destroyed
--          by ambient MessageContext reset; RelationSyncCache
--          in CacheMemoryContext survives with a dangling
--          entry->entry_cxt.

-- Invocation 2: crashes or reads freed memory
SELECT pg_logical_slot_get_binary_changes(
    'slot1', NULL, NULL,
    'proto_version', '4',
    'publication_names', 'p1');
-- Expected under cassert: SIGSEGV in MemoryContextDelete
-- (from get_rel_sync_entry line 2153) or heap sanitizer trap.
```

**Note on macOS crash reproducibility.** The four prior calibrations
(F26/F27 in the earlier sessions) documented that direct SIGSEGV
reproduction on macOS is unreliable for UAF-shape bugs — the freed
region often stays mapped and readable long enough to escape a crash
while still returning garbage. The proxy signals we can reliably
observe at parent pin without a full working reproducer are:

- **cassert context header check** — the freed `MemoryContext` still
  has stale magic bytes but its method-table pointer is invalidated by
  the `AllocSetDelete` free of its containing block. Adding a
  `Assert(MemoryContextIsValid(entry->entry_cxt))` right before line
  2153 would fire on invocation 2.
- **`log_error_verbosity = verbose` + `client_min_messages = LOG` +
  `MEMORY_CONTEXT_CHECKING`** — the double-free path through
  `hash_destroy` on invocation-2 shutdown may print a chunk-header
  mismatch warning if the region has already been re-used.
- **Elog before the suspect line** — instrument
  `get_rel_sync_entry` with an `elog(LOG, "reentering entry %u
  entry_cxt=%p replicate_valid=%d", entry->relid, entry->entry_cxt,
  entry->replicate_valid);` and compare `entry_cxt` addresses across
  invocations. If invocation 2 sees a `entry_cxt` != NULL that matches
  invocation 1's freed address, the bug is confirmed even without a
  crash.

For the calibration scaffolding this is sufficient. Full-strength
crash reproduction is out of scope for this trilogy — the goal is L7
validation, not bug hunting.

## Step 0.5 (F37) — Target-suite health at parent pin

Per the `fix-memory-leak` scenario §Step 0.5 (F37), we must confirm
which test suite the R13 phase-end gate should target BEFORE assuming
the default `--suite regress`. The pgoutput code exercises:

- `src/test/regress/sql/publication.sql` — DDL-level pubs/subs, no
  actual logical-decoding runtime; regress suite covers it.
- `src/test/subscription/t/*.pl` — the actual apply-worker + walsender
  + pgoutput integration; TAP suite (needs `-Dtap_tests=enabled`,
  which needs IPC::Run installed).
- `contrib/test_decoding/sql/*.sql` — logical-decoding output plugin
  smoke tests, but they exercise `test_decoding` not `pgoutput`.

**Meson configure status at parent pin:**

```
cd /Users/matej/Work/postgres/postgresql-dev-feature-pgoutput-uaf
rm -rf build-debug
PKG_CONFIG_PATH=/opt/homebrew/opt/openssl@3/lib/pkgconfig \
  meson setup build-debug \
  --prefix=$PWD/install-debug \
  -Dcassert=true -Ddebug=true -Dc_args="-O0 -g"
```

Configure succeeded. TAP tests could NOT be enabled because IPC::Run
is not installed on this box; the configure failed initially with
"Additional Perl modules are required to run TAP tests." and had to
be redone without `-Dtap_tests=enabled`. **This means the R13
phase-end gate for this feature cannot rely on the subscription TAP
suite locally — plan §7 must call out `--suite regress` +
`--suite pg_stat_statements` for the catalog-adjacent testing and
`--suite isolation` for the multi-session shape**, plus an explicit
CI hook comment noting subscription TAP as the upstream backstop.

Following F37 discipline: this Step 0.5 result gates the R13 scope
choice in the phase-end check ladder. The plan explicitly does not
promise the subscription TAP suite runs in the pre-commit hook; that
is a CI-only signal on this workstation.

## Signal magnitude

The bug is a UAF (crash / SIGSEGV / SIGABRT under cassert), NOT an RSS
leak. Its magnitude is binary: either the second invocation crashes
or it does not. The prior four calibrations' baseline RSS
measurements (`ps -o rss` before/after) do not apply. The relevant
success signal for the phased implementation is:

1. **Instrumentation-visible:** `elog(LOG, ...)` in
   `get_rel_sync_entry` and `pgoutput_ensure_entry_cxt` shows that
   invocation 2's `entry` has fresh `entry_cxt = NULL` (not the stale
   pointer from invocation 1).
2. **cassert-visible:** an added Assert on `MemoryContextIsValid` at
   the vulnerable dereferences does not fire on invocation 2.
3. **TAP-visible (post-fix, in CI):** a new subscription TAP test
   `src/test/subscription/t/NNN_pgoutput_error_recovery.pl` that
   drives invocation-1 error + invocation-2 success would surface any
   regression.

## Cross-references

- Skill: `.claude/skills/pg-feature-brainstorm/SKILL.md` (L5 storage
  representation adversarial pass, L6 approach-E mandatory
  enumeration).
- Skill: `.claude/skills/pg-feature-plan/SKILL.md` (F30 grep-pass, L7
  callback sub-block).
- Idiom: `knowledge/idioms/memory-contexts.md` (F34+F35+F36 callback
  idioms, section "Reset / delete callbacks").
- Scenario: `knowledge/scenarios/fix-memory-leak.md` §Step 0.5 (F37
  target-suite health check).

## Summary of Phase 0 findings

- Bug etiology is fully derivable from parent-pin source alone.
- The stale-HTAB-vs-freed-entry-context lifetime mismatch is the
  precise mechanism.
- The fix has to arm cleanup on the FIRST context that dies on error
  and outlives the HTAB entries' referenced state — either
  `data->cachectx` (dies with `ctx->context` on error) or `ctx->context`
  itself.
- Full crash reproduction is difficult on macOS; the trilogy proceeds
  with instrumentation-visible proxy signal.
- Target-suite for R13: `regress` + `isolation` +
  `pg_stat_statements`; subscription TAP is CI-only on this box.
