# Issues — `contrib/pg_stash_advice`

New-in-PG18+ contrib module that parks `pg_plan_advice` advice strings
in dynamic shared memory keyed by `(stash_id, queryId)` and reapplies
them automatically as queries plan. 4 source files / ~2 138 LOC.

**Parent docs:** `knowledge/files/contrib/pg_stash_advice/*` (4 docs:
`pg_stash_advice.c.md`, `pg_stash_advice.h.md`, `stashfuncs.c.md`,
`stashpersist.c.md`).

**Source:** ~16 entries surfaced 2026-06-11 by A21-B.

## Architecture in one paragraph

`pg_plan_advice` (separate contrib) accepts advice strings keyed by
the query-jumble ID. `pg_stash_advice` stores those (`stash_id`,
`queryId`) -> `advice_string` mappings in a DSA-backed `dshash_table`,
addressable by a human-readable ASCII `stash_name`. A bgworker
serializes the whole thing to `$PGDATA/pg_stash_advice.tsv` every
`pg_stash_advice.persist_interval` seconds (default 30), and reloads
on startup. The current stash is selected via the per-session GUC
`pg_stash_advice.stash_name`. `_PG_init` calls `EnableQueryId()` and
registers `pgsa_advisor` with `pg_plan_advice_add_advisor` via
`load_external_function`.

## Headlines

1. **DSA pointer / shmem-OOM dance is fragile by design.** `pgsa_set_advice_string`
   must hold `pgsa_state->lock` (any mode) for the entire
   `dsa_allocate -> dshash_find_or_insert -> write` sequence because
   the lock holds off interrupts, preventing leak of the freshly-
   allocated DSA blob if a longjmp fires between allocate and
   insert. Comment is explicit; no `Assert` makes it mechanical.
2. **Lifetime contract with `pg_plan_advice` is comment-only.** The
   pstrdup'd advice string into `CurrentMemoryContext` is "good
   enough" because `pg_plan_advice` only needs it long enough to
   parse. If that consumer caches the pointer, it's a use-after-free.
3. **Persistence file is bare-basename `pg_stash_advice.tsv` in cwd
   (= data directory).** Comment at `stashpersist.c:297-299` hints
   at "possibly multiple save files in future"; the bare-basename
   pattern blocks expansion. Also: an oversized dump file DoSes the
   bgworker via `MCXT_ALLOC_HUGE` slurp.

## Entries — `pg_stash_advice.h`

- [ISSUE-style: hardcoded `PGSA_DUMP_FILE` basename, no GUC to redirect (nit)] — `:25`
- [ISSUE-style: shared-state struct mixes atomics + LWLock + tranches without padding (nit)] — `:57-70`

## Entries — `pg_stash_advice.c`

- [ISSUE-undocumented-invariant: DSA-pointer leak prevention is comment-only at call site, no Assert (nit)] — `:656-671`
- [ISSUE-leak: `DSHASH_INSERT_NO_OOM` NULL return must free `new_dp` — fragile idiom (nit)] — `:684-702`
- [ISSUE-style: `pgsa_check_stash_name` and `pgsa_check_stash_name_guc` must stay in sync manually (maybe)] — `:337-338, 377-378`
- [ISSUE-undocumented-invariant: pstrdup'd advice string lifetime contract with pg_plan_advice is comment-only (maybe)] — `:188-189, 200-201`
- [ISSUE-doc-drift: `_PG_init` silently calls `EnableQueryId()` overriding user's compute_query_id GUC (nit)] — `:90-91`
- [ISSUE-question: should `pgsa_attach` happen at backend start vs lazily during plan? (nit)] — `:166-167`
- [ISSUE-correctness: `pg_atomic_unlocked_test_flag(stashes_ready)` lacks acquire fence; depends on subsequent lock (nit)] — `:170-171`

## Entries — `stashfuncs.c`

- [ISSUE-doc-drift: read returns empty set during persistence load; write errors — asymmetry not documented (nit)] — `:101-103`
- [ISSUE-undocumented-invariant: `<stash 17>` synthesized name relies on identifier ASCII rule for non-collision (nit)] — `:243-244`
- [ISSUE-question: is `pg_set_stashed_advice` declared STRICT or do we rely on `PG_ARGISNULL` checks? (nit)] — `:279-280`

## Entries — `stashpersist.c`

- [ISSUE-security: oversized dump file DoSes the bgworker via slurp + MCXT_ALLOC_HUGE (maybe)] — `:311`
- [ISSUE-undocumented-invariant: `queryId == 0` sentinel cross-cuts parse + write paths (nit)] — `:441-444`
- [ISSUE-correctness: silent drop of orphan entries (`stash_id` missing from `nhash`) during write (maybe)] — `:745-746`
- [ISSUE-doc-drift: `persist_interval = 0` means "save only on clean shutdown" — undocumented (nit)] — `:163-169`
- [ISSUE-style: hardcoded basename blocks future multi-file expansion hinted at `:297-299` (nit)] — `:264-272, 297-299`
