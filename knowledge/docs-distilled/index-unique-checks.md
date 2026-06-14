---
source_url: https://www.postgresql.org/docs/current/index-unique-checks.html
fetched_at: 2026-06-12T20:47:00Z
anchor_sha: e18b0cb
chapter: "63.5 Index Uniqueness Checks"
---

# Index Uniqueness Checks (docs §63.5)

How a unique index enforces SQL uniqueness under MVCC, and the four-valued
`checkUnique` contract on `aminsert`. `[from-docs]` unless a `source/` cite is
given.

## Non-obvious claims

- **Only `amcanunique` AMs can enforce uniqueness, and today only B-tree sets
  it.** Columns in the `INCLUDE` clause are *not* part of the uniqueness key —
  they ride along as payload only. `[from-docs]`
- **The invariant is snapshot-level, not entry-level:** duplicate index entries
  *must* be allowed to physically coexist (successive MVCC versions of one
  logical row), but **no MVCC snapshot may ever see two rows with equal keys.**
  Enforcement therefore can't be "reject any duplicate key" — it has to consult
  tuple liveness. `[from-docs]`
- **The AM reaches into the heap to check commit status of the conflicting
  row.** The docs openly call this a non-modular wart, justified because folding
  the liveness check into insertion avoids a redundant index descent and closes
  a race window. `[from-docs]`
- **Three conflict cases at insert time:** (1) conflicting row deleted *by the
  current transaction* → allow the insert (this is exactly what an UPDATE that
  doesn't change the key needs); (2) conflicting row inserted by an
  *uncommitted* txn → wait for it to commit/abort, then re-test (rollback clears
  it; commit-without-delete = violation); (3) conflicting valid row deleted by an
  *uncommitted* txn → wait, then re-test. `[from-docs]`
- **Pre-violation liveness recheck of the *being-inserted* row.** Right before
  raising the error, the AM must recheck that the new row is itself still live;
  if it's already committed-dead, suppress the violation. This case arises under
  `CREATE UNIQUE INDEX CONCURRENTLY`, not during ordinary insertion. `[from-docs]`
- **"Live" is defined over the whole HOT chain:** a tuple counts as live if *any*
  tuple in the index entry's HOT chain is live. `[from-docs]`
- **`checkUnique` is the four-valued `aminsert` argument:**
  - `UNIQUE_CHECK_NO` — not a unique index; no checking.
  - `UNIQUE_CHECK_YES` — non-deferrable unique index; check immediately, full
    protocol above.
  - `UNIQUE_CHECK_PARTIAL` — deferrable constraint path. The AM **must allow the
    duplicate into the index** and signal a *possible* conflict by **returning
    `false` from `aminsert`** (true = definitely no conflict). False positives
    are allowed; the row is queued for a deferred recheck. Crucially, this path
    must *not* block waiting on other transactions.
  - `UNIQUE_CHECK_EXISTING` — the deferred recheck itself. The entry is already
    present, so the AM **must not insert a new one**; it checks whether *another*
    live entry with the same key exists and, if so and the target row is still
    live, raises the error. `[from-docs]`
- **Recommended `UNIQUE_CHECK_EXISTING` hardening:** the AM should verify the
  target row actually *has* an existing index entry and error if not. This
  guards against non-truly-immutable index expressions sending the recheck to
  the wrong part of the index — it confirms the recheck is scanning the same key
  values the original insert produced. `[from-docs]`

## Links into corpus

- [[knowledge/subsystems/access-nbtree.md]] — the sole `amcanunique`
  implementation; `_bt_check_unique` is the code behind this protocol.
- [[knowledge/files/src/backend/access/nbtree/nbtinsert.c.md]] — where the
  insert-time conflict cases and dirty-snapshot wait live.
- [[knowledge/subsystems/access-heap.md]] — HOT chains and the "any tuple in the
  HOT chain is live" liveness rule.
- [[knowledge/files/src/backend/access/index/indexam.c.md]] — `aminsert`
  dispatch + the `IndexUniqueCheck` enum.
- Skill: `access-method-apis` (aminsert/`amcanunique`), `catalog-conventions`
  (INCLUDE columns / pg_index).

## Citations

- All claims `[from-docs]`. The `IndexUniqueCheck` enum
  (`UNIQUE_CHECK_NO/YES/PARTIAL/EXISTING`) is declared in
  `source/src/include/access/genam.h`; the protocol is implemented in
  `source/src/backend/access/nbtree/nbtinsert.c` (`_bt_check_unique`). Verify
  line numbers at anchor e18b0cb before quoting.
