# `contrib/pg_stash_advice/stashfuncs.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** 347
- **Source:** `source/contrib/pg_stash_advice/stashfuncs.c`

The SQL interface layer for `pg_stash_advice`. Exposes six
`PG_FUNCTION_INFO_V1` entry points that wrap the C primitives in
`pg_stash_advice.c` with `pgsa_attach()` (lazy attach), `pgsa_check_lockout()`
(refuse writes during persistence load), and the necessary LWLock acquire
patterns. Plus a private simplehash (`pgsa_stash_count_table`) used by
`pg_get_advice_stashes` to count entries per stash without `O(stashes ×
entries)` lookup. [verified-by-code]

## API / entry points

- `pg_create_advice_stash(text)` `:50-63` — acquires lock EXCLUSIVE,
  calls `pgsa_create_stash`. [verified-by-code]
- `pg_drop_advice_stash(text)` `:68-81` — acquires lock EXCLUSIVE,
  calls `pgsa_drop_stash`. [verified-by-code]
- `pg_get_advice_stashes()` `:86-144` — SRF (`InitMaterializedSRF`).
  Builds a `pgsa_stash_count_table` simplehash by iterating
  `pgsa_entry_dshash`, then iterates `pgsa_stash_dshash` and emits
  `(name, count)` tuples. Returns empty set rather than erroring when
  `stashes_ready` is clear (`:102-103`). [verified-by-code]
- `pg_get_advice_stash_contents(text)` `:149-263` — SRF returning
  `(stash_name, query_id, advice_string)`. NULL arg = dump all stashes
  (allocates a stash-id-to-name local hash, since lookups in dshash
  while iterating would re-lock); non-NULL = restrict to one stash.
  Skips entries with `InvalidDsaPointer` advice_string (intermediate
  state). [verified-by-code]
- `pg_set_stashed_advice(text, int8, text)` `:273-321` — main write
  endpoint. NULL stash or queryId → returns NULL. Query ID 0 →
  errors (zero is the "no query id computed" sentinel). NULL advice
  string → calls `pgsa_clear_advice_string`. Non-NULL → calls
  `pgsa_set_advice_string`. **Lock acquired SHARED** for both
  set/clear (`:307`, `:315`). [verified-by-code]
- `pg_start_stash_advice_worker()` `:326-347` — reads
  `pgsa_state->bgworker_pid` under SHARED lock; if non-Invalid,
  errors "already running"; else calls `pgsa_start_worker`.
  [verified-by-code]

## Notable invariants / details

- **INV-1: All SQL-visible functions call `pgsa_attach()` lazily on
  first use.** Pattern is `if (unlikely(pgsa_entry_dshash == NULL))
  pgsa_attach();` — `pgsa_attach` is itself idempotent.
  [verified-by-code]
- **INV-2: Write-side functions check lockout BEFORE acquiring the
  lock.** Calling `pgsa_check_lockout` after `LWLockAcquire` would
  leak the lock on ereport(ERROR). [verified-by-code] `:58, 76, 302`
- **INV-3: `pg_set_stashed_advice` takes SHARED, not EXCLUSIVE.**
  Both `pgsa_set_advice_string` and `pgsa_clear_advice_string` only
  require SHARED (see comments in `pg_stash_advice.c:656-671` —
  the lock holds off interrupts and serializes against drops, but
  doesn't need to be exclusive between concurrent set/clear because
  dshash provides its own per-bucket exclusion). [from-comment]
- **INV-4: `pg_get_advice_stash_contents` accepts orphaned entries.**
  Comment `:236-244`: if a stash has been dropped between iterations
  but its entries remain (race), the function makes up a name like
  `<stash 17>` and emits them. [from-comment]
- **INV-5: The local `pgsa_stash_count_table` is `static inline`,**
  generated only within this TU. No multi-TU simplehash duplication
  issue. [verified-by-code] `:36-45`

## Potential issues

- `:101-103` `pg_get_advice_stashes` silently returns an empty set
  during persistence load (when `stashes_ready` is clear). A monitoring
  query could mistake "still loading" for "no stashes exist". The
  symmetric write paths *error* via `pgsa_check_lockout`. The
  asymmetry is intentional but undocumented in user docs.
  [from-comment] **[ISSUE-doc-drift: read returns empty, write errors,
  during persistence load — asymmetry not documented (nit)]**
- `:243-244` `psprintf("<stash %" PRIu64 ">", ...)` for orphaned
  entries leaks no memory (CurrentMemoryContext is the per-call SRF
  context) but the synthesized name could collide with a legitimate
  stash name on a non-ASCII identifier or be confused for a real
  stash. Since stash names are restricted to ASCII identifiers
  (`pg_stash_advice.c:357-372`), `<` and `>` are not valid → no
  collision is possible. Worth documenting. [verified-by-code]
  **[ISSUE-undocumented-invariant: orphan-name `<...>` syntax relies
  on identifier rule for non-collision (nit)]**
- `:279-280` Returning NULL when args are NULL is reasonable for
  `pg_set_stashed_advice(NULL, ...)`, but pg18 SQL-strict semantics
  might prefer `STRICT`/return-NULL declared in the SQL `.sql` file
  (`pg_stash_advice--1.0.sql`). Worth confirming the SQL declaration
  matches. [inferred] **[ISSUE-question: is the SQL function declared
  STRICT or do we rely on this manual check? (nit)]**
- `:106` `pgsa_stash_count_table_create(CurrentMemoryContext, 64,
  NULL)` is called inside an SRF callback — `CurrentMemoryContext`
  is per-call. For a stash with thousands of entries this rebuilds the
  count hash on every SRF call window. Fine in materialize mode (single
  call). [verified-by-code]
