---
source_url: https://www.postgresql.org/docs/current/fdw-row-locking.html
chapter: "58.5 Row Locking in Foreign Data Wrappers"
fetched_at: 2026-06-16
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# FDW row locking — §58.5

How an FDW participates in `SELECT FOR UPDATE/SHARE` and in READ COMMITTED
re-fetch semantics over a *remote* store that has no native PG TID. This is
the conceptual frame behind the `GetForeignRowMarkType` / `RefetchForeignRow`
callbacks catalogued in [[knowledge/docs-distilled/fdw-callbacks.md]].

## Non-obvious claims

- **Two locking models, author's choice.** *Early locking*: lock the row when
  first read — simple, no extra round trips, but over-locks and risks remote
  deadlocks. *Late locking*: lock only when the row is confirmed needed —
  preserves concurrency but **requires the ability to uniquely re-identify a
  row later** (ideally a version-identifying row id like a PG TID).
  [from-docs §58.5]
- **The default is "core ignores locking for FDWs."** An FDW can implement
  *early* locking with **no explicit core support** at all. *Late* locking
  needs the API functions added in **PostgreSQL 9.5** (the §58.2.6 callback
  group). [from-docs §58.5]
- **READ COMMITTED re-fetch has two strategies.** Default: project an
  **entire-row copy** through joins (more memory, but no special FDW
  capability needed). Optimized: project only the **TID of non-target
  tables** and re-fetch on demand (needs cheap re-fetch + version-stable row
  ids). The choice is signalled via the rowmark type. [from-docs §58.5]
- **`GetForeignRowMarkType` returning anything other than `ROW_MARK_COPY`
  is the switch that makes the executor call `RefetchForeignRow`.**
  `ROW_MARK_COPY` (the default) = copy whole rows, no re-fetch.
  `ROW_MARK_REFERENCE` = override the copy, re-fetch unlocked rows later.
  The explicit-lock strengths — `ROW_MARK_EXCLUSIVE`,
  `ROW_MARK_NOKEYEXCLUSIVE`, `ROW_MARK_SHARE`, `ROW_MARK_KEYSHARE` — come
  from a `FOR UPDATE/SHARE` clause. [from-docs §58.5]
- **Detecting "am I a lock/modify target" splits plan-time vs exec-time:**
  - *Plan time:* compare the rel's `relid` to
    `root->parse->resultRelation` (UPDATE/DELETE target), and call
    `get_plan_rowmark()` then check `strength != LCS_NONE`.
  - *Exec time:* `ExecRelationIsTargetRelation()` for the modify target,
    `ExecFindRowMark()` for rowmark info (again checking the strength field).
  [from-docs §58.5]
- **`RefetchForeignRow` with `markType == ROW_MARK_REFERENCE` must NOT
  acquire a lock** — it re-reads the unlocked row. (Contrast the locking
  rowmark strengths, where it re-fetches *and* locks.) [from-docs §58.5]
- The authoritative comments live in three headers — `lockoptions.h`
  (`LockClauseStrength`/`LCS_*`), `plannodes.h` (`RowMarkType`,
  `PlanRowMark`), and `execnodes.h` (`ExecRowMark`) — read those for the
  exact enum/field semantics, not just the prose. [from-docs §58.5]

## Links into corpus

- The callbacks: [[knowledge/docs-distilled/fdw-callbacks.md]] (§58.2.6 late
  row locking group — `GetForeignRowMarkType`, `RefetchForeignRow`).
- Struct/enum sources to verify against:
  `source/src/include/nodes/lockoptions.h`,
  `source/src/include/nodes/plannodes.h`,
  `source/src/include/nodes/execnodes.h`.
- MVCC / row-lock backdrop: [[knowledge/docs-distilled/mvcc.md]].
- Parent: [[knowledge/docs-distilled/fdwhandler.md]].

## Caveats / verification

- All claims `[from-docs §58.5]`. The `ROW_MARK_*` enum and the
  `get_plan_rowmark` / `ExecFindRowMark` signatures are verifiable in the
  three named headers and `src/backend/executor/execMain.c` at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735`.
