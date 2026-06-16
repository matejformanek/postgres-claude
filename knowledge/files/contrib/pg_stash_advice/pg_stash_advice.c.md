# `contrib/pg_stash_advice/pg_stash_advice.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 773
- **Source:** `source/contrib/pg_stash_advice/pg_stash_advice.c`

Core module file for `pg_stash_advice`. Implements `_PG_init`,
the `pgsa_advisor` callback registered with `pg_plan_advice`,
all the shared-memory attach plumbing (`pgsa_attach` against
`GetNamedDSMSegment` + `dshash_create`/`dshash_attach`), the
six core stash-mutation primitives (`pgsa_create_stash`,
`pgsa_drop_stash`, `pgsa_set_advice_string`,
`pgsa_clear_advice_string`, `pgsa_reset_all_stashes`,
`pgsa_lookup_stash_id`), GUC plumbing, and the
`pgsa_start_worker` bgworker-registration helper. [verified-by-code]

## What this module is (overall architecture)

The pipeline:

1. **`pg_plan_advice`** is a separate contrib that takes a *query-jumble
   id* and accepts a query-specific "advice string" (semantics defined
   by `pg_plan_advice` itself; this module is opaque to the format).
2. **`pg_stash_advice`** persists those `(stash_id, queryId) ->
   advice_string` mappings in dynamic shared memory, addressable by a
   human-readable `stash_name`. It registers itself as an *advisor* via
   `pg_plan_advice_add_advisor()` so that when the planner runs, the
   stashed string for the current `queryId` is automatically applied.
3. A **persistence bgworker** (`stashpersist.c`) periodically saves the
   stash to `$PGDATA/pg_stash_advice.tsv` and reloads it on startup so
   advice survives a restart.

A user picks an active stash by setting the session GUC
`pg_stash_advice.stash_name`. Stashes are namespace-flat at the cluster
level (not per-database), so the GUC is `PGC_USERSET` and the
advisor early-exits when name is empty or queryId is 0
(`:162-163`). [verified-by-code]

## API / entry points

- `_PG_init` `:85-143` — defines three GUCs
  (`pg_stash_advice.persist`, `…persist_interval`, `…stash_name`),
  calls `EnableQueryId()` (the module is useless without query jumbling),
  registers the bgworker if `persist=true`, and calls
  `pg_plan_advice_add_advisor()` (looked up dynamically via
  `load_external_function`, allowing pg_stash_advice to coexist with a
  newer pg_plan_advice ABI). [verified-by-code]
- `pgsa_advisor` `:149-210` — the `pg_plan_advice_advisor_hook`
  implementation. Looks up the advice string for the current session
  stash + query ID, pstrdups it into `CurrentMemoryContext` (the
  caller's; expected to be short-lived plan-time context), releases
  the dshash lock, and returns it. [verified-by-code]
- `pgsa_attach` `:220-319` — idempotent attach. Allocates a long-
  lived module `MemoryContext` in `TopMemoryContext`. Uses
  `GetNamedDSMSegment` for the fixed-size state, then conditionally
  creates-or-attaches the DSA area and two dshash tables. Each
  conditional block is "try-fail-retry safe": a failure midway leaves
  the persistent handle slots untouched (`DSA_HANDLE_INVALID`),
  permitting a re-call. [from-comment + verified-by-code]
- `pgsa_check_lockout` `:324-332` — raises ERROR if `stashes_ready` flag
  is clear (i.e. the persistence worker hasn't finished restoring yet).
  Called by every write-side SQL function in `stashfuncs.c`.
  [verified-by-code]
- `pgsa_check_stash_name` `:339-373` — rejects empty, >NAMEDATALEN-1,
  non-ASCII, or non-identifier names. Identifier rule:
  `[a-zA-Z_][a-zA-Z0-9_]*`. Note: must stay in sync with the GUC
  check hook below — comment says so. [from-comment]
- `pgsa_check_stash_name_guc` `:379-417` — the
  `DefineCustomStringVariable` check hook. Same rules as above EXCEPT
  it allows the empty string (means "feature disabled"). [from-comment]
- `pgsa_create_stash` `:422-441` — caller must hold lock EXCLUSIVE.
  `dshash_find_or_insert` for the name → fresh id, bumps
  `next_stash_id`, bumps `change_count`. [verified-by-code]
- `pgsa_clear_advice_string` `:446-484` — caller must hold lock
  (any mode). Looks up, `dshash_delete_entry`, then `dsa_free` the
  payload AFTER releasing the entry lock — order matters because
  `dsa_free` could conceivably error. [from-comment]
- `pgsa_drop_stash` `:489-528` — caller must hold lock EXCLUSIVE.
  Deletes stash directory entry, then iterates ALL entry-hash entries
  and deletes any with matching `stash_id`. Bumps `change_count`.
  [verified-by-code]
- `pgsa_reset_all_stashes` `:536-562` — caller must hold lock
  EXCLUSIVE. Truncates both hashes and resets `next_stash_id = 1`.
  Used by `stashpersist.c:259-261` before restoring from disk.
  [from-comment]
- `pgsa_init_shared_state` `:567-598` — the `GetNamedDSMSegment`
  init callback. Initializes the LWLock, allocates three tranche IDs
  via `LWLockNewTrancheId`, sets handles to invalid, and sets
  `stashes_ready` IMMEDIATELY if persistence is disabled. [verified-by-code]
- `pgsa_is_identifier` `:604-620` — manual ASCII identifier check; not
  using `isalpha`/`isdigit` to avoid locale dependence. [inferred]
- `pgsa_lookup_stash_id` `:627-641` — read-side lookup; no lock
  required since dshash_find is internally locked. Returns 0 for
  "not found". [verified-by-code]
- `pgsa_set_advice_string` `:646-720` — caller must hold lock (any
  mode). The long comment at `:656-671` explains both reasons:
  (a) lock holds off interrupts so an OOM between dsa_allocate and
  hash-insert can't leak; (b) prevents race against `pgsa_drop_stash`.
  Uses `DSHASH_INSERT_NO_OOM` so out-of-shmem returns NULL rather than
  longjmps; on NULL, frees the newly-allocated DSA blob before
  ereport. [from-comment + verified-by-code]
- `pgsa_start_worker` `:725-773` — chooses between
  `RegisterBackgroundWorker` (postmaster startup) and
  `RegisterDynamicBackgroundWorker` (runtime). For dynamic case it
  waits with `WaitForBackgroundWorkerStartup` and ereport-fails if not
  started. [verified-by-code]

## Notable invariants / details

- **INV-1: `next_stash_id` starts at 1, never 0.** Zero is the
  sentinel returned by `pgsa_lookup_stash_id` for "not found"
  (`:636`) so it must never be a valid stash id.
  Set at init (`:577`) and after reset (`:561`). [verified-by-code]
- **INV-2: Stash names are ASCII identifiers.** Justification from
  comment `:357-358`: "advice stashes are visible across all
  databases and the encodings of those databases might differ".
  Important for security and cross-DB consistency.
  [from-comment]
- **INV-3: After `dsa_allocate` for an advice string, the caller
  must NOT longjmp before storing the dsa_pointer somewhere
  rooted.** Enforced by holding `pgsa_state->lock` (which holds off
  interrupts) for the entire allocate-then-insert sequence.
  [from-comment] `:656-671`. **ISSUE-undocumented-invariant: comment
  is explicit at the call site but no `Assert` makes it mechanical (nit)**
- **INV-4: `dshash_find_or_insert_extended(... DSHASH_INSERT_NO_OOM)`
  returns NULL on shmem-full instead of erroring.** The freshly-
  allocated `new_dp` MUST be `dsa_free`'d before throwing the
  out-of-memory error or it leaks (handled `:697`). **ISSUE-leak:
  not actually a leak in this file — but the idiom is fragile (nit)**
- **INV-5: change_count is bumped on every mutation.** The bgworker
  uses it as a "did anything change since last save?" tripwire
  (`stashpersist.c:191-198`).  [verified-by-code]
- **INV-6: `pgsa_check_stash_name_guc` does NOT call
  `pgsa_check_stash_name`** because they have different empty-string
  semantics. The two MUST be kept in sync manually. Comments at
  `:337-338` and `:377-378` flag this. [from-comment]
  **ISSUE-style: paired check functions easy to drift (maybe)**
- **INV-7: The advisor returns NULL when `stashes_ready` is clear**
  (`:170-171`). So while persistence is loading, queries plan
  WITHOUT advice — they don't error. Only modifications (`pgsa_check_lockout`)
  error. [verified-by-code]

## Potential issues

- `:201-202` `pstrdup` of the advice string into
  `CurrentMemoryContext` allocates in whatever short-lived context
  the planner is using. Comment says "good enough" because
  pg_plan_advice only needs it long enough to parse. If a future
  pg_plan_advice change holds the pointer longer (caches it across
  invocations), this becomes a use-after-free. [from-comment]
  **[ISSUE-undocumented-invariant: lifetime contract between pg_stash_advice
  and pg_plan_advice is comment-only (maybe)]**
- `:88-91` `EnableQueryId()` is called unconditionally in `_PG_init`,
  meaning loading this module forces `compute_query_id != off`.
  Comment notes only that "we would like query IDs" but a user who
  set `compute_query_id = off` for performance reasons might be
  surprised by the silent override. [verified-by-code]
  **[ISSUE-doc-drift: GUC override is implicit; not flagged in
  docs (nit)]**
- `:147-210` `pgsa_advisor` calls `pgsa_attach` lazily on first call
  via `if (unlikely(pgsa_entry_dshash == NULL))`. That's correct
  except that `pgsa_attach` can do EXCLUSIVE LWLock acquires, so
  planning a query may block on the lock — uncommon, but means
  pg_stash_advice can add latency to PLANNING (not just execution).
  Probably fine. [inferred] **[ISSUE-question: should attach happen
  at backend start instead of lazily? (nit)]**
- `:170-171` Use of `pg_atomic_unlocked_test_flag` for `stashes_ready`
  is a read-without-barrier. Comment elsewhere (`stashpersist.c`)
  argues it's safe because the flag is set once and never cleared. But
  there's no acquire fence — on weakly-ordered architectures, a
  reader could see `stashes_ready = set` but stale entries in the
  hash. The lock acquired immediately after by `dshash_find` provides
  a fence, so in practice OK. [inferred] **[ISSUE-correctness:
  acquire-fence reasoning is implicit (nit)]**
- `:766-771` Background-worker startup failure (`status !=
  BGWH_STARTED`) is ereport(ERROR) without trying to clean up the
  half-registered worker handle. `WaitForBackgroundWorkerStartup`
  semantics may leave the worker scheduled-but-not-running on
  postmaster-side; in single-user mode, you'd error out as comment
  notes. [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_stash_advice`](../../../issues/pg_stash_advice.md)
<!-- issues:auto:end -->
