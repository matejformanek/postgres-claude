---
scenario: add-new-buffer-strategy
when_to_use: New ring-buffer class for a recurring workload that pollutes shared_buffers and doesn't fit BULKREAD/BULKWRITE/VACUUM.
companion_skills: ["memory-contexts"]
related_scenarios: ["add-new-table-am"]
canonical_commit: 28e626bde00
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new BufferAccessStrategy ring

## Scope — what's in / out

**In scope:**
- Adding a new `BAS_*` enumerator to `BufferAccessStrategyType` plus the matching
  ring-size policy in `GetAccessStrategy()` and the matching `IOContextForStrategy()`
  arm in `src/backend/storage/buffer/freelist.c`.
- Adding the paired `IOCONTEXT_*` enumerator to `IOContext` in
  `src/include/pgstat.h` plus its name string in `pgstat_get_io_context_name()`
  so the new context appears in `pg_stat_io`.
- Updating the `pgstat_tracks_io_object` / `pgstat_tracks_io_op` predicates
  so backend-type × context × op combinations are correctly filtered.
- Optional but expected: a tunable ring-size GUC if the workload is
  user-visible (pattern: `vacuum_buffer_usage_limit` for `BAS_VACUUM`).
- Decision-point note: only do this if you have evidence that none of
  `BAS_BULKREAD` / `BAS_BULKWRITE` / `BAS_VACUUM` fits. Most "I want a ring"
  cases get covered by `GetAccessStrategyWithSize(BAS_BULKREAD, n)` from the
  caller.

**Out of scope:**
- Adjusting an *existing* ring's size — that's a one-line change in
  `GetAccessStrategy()` or a call-site swap to `GetAccessStrategyWithSize()`
  and doesn't need a scenario.
- Changing `StrategyRejectBuffer()` policy for `BAS_BULKREAD` (i.e. WAL-flush
  avoidance) — single-file change in `freelist.c`.
- Adding `IOOBJECT_*` or `IOOP_*` categories — same shape but different
  axis; not covered here.
- Local-buffer strategy (temp relations bypass `BufferAccessStrategy`
  entirely; see `localbuf.c`).

## Pre-flight

- **Companion skills:** load `memory-contexts` — the strategy object is
  `palloc0`'d in the caller's CurrentMemoryContext and lives only as
  long as that context. Lifetime mismatches (strategy outlives its
  parent context, or vice versa) are the most common runtime bug in
  this change-class.
- **Canonical commit:** `28e626bde00` — *pgstat: Infrastructure for
  more detailed IO statistics* (TODO: find a historical canonical
  commit that adds a BAS class itself; this one adds the paired
  IOContext infrastructure that every new BAS class must extend).
  Read it before starting — it's the textbook example of wiring a new
  `IOContext` value end-to-end through pgstat tracking predicates and
  the `pg_stat_io` view.
- **Common pitfalls (one-line each):**
  - Forgot to add the paired `IOCONTEXT_*` value — the comment at
    `bufmgr.h:31-33` mandates it [from-comment](source/src/include/storage/bufmgr.h:31-33).
  - Forgot to extend `IOContextForStrategy()` switch — backend crashes
    with `elog(ERROR, "unrecognized BufferAccessStrategyType")` on the
    first I/O recorded against the new strategy [verified-by-code](source/src/backend/storage/buffer/freelist.c:736).
  - `pgstat_tracks_io_object()` / `pgstat_tracks_io_op()` left
    untouched — every (backend_type, object, context, op) combination
    silently disappears from `pg_stat_io` because the predicates default
    to filtering unknown contexts.
  - Re-used `BAS_BULKREAD`-specific `StrategyRejectBuffer()` path —
    only `BAS_BULKREAD` rejects dirty buffers; all other strategies
    write-and-WAL-flush. The guard at `freelist.c:755` is `btype !=
    BAS_BULKREAD` and silently returns false for anything else
    [verified-by-code](source/src/backend/storage/buffer/freelist.c:754-756).
  - `GetAccessStrategyPinLimit()` default arm (everything except
    `BAS_BULKREAD`) returns `nbuffers / 2`. If your strategy benefits
    from pinning more, add an explicit case [verified-by-code](source/src/backend/storage/buffer/freelist.c:579-598).

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/storage/bufmgr.h` | Add the new `BAS_*` value to the `BufferAccessStrategyType` enum. The header comment at lines 31-33 explicitly mandates "If adding a new BufferAccessStrategyType, also add a new IOContext" [from-comment](source/src/include/storage/bufmgr.h:31-33). | — | memory-contexts |
| 2 | `src/include/pgstat.h` | Add the paired `IOCONTEXT_*` enumerator to the `IOContext` enum at lines 288-295. Bump `IOCONTEXT_NUM_TYPES` accordingly (currently `IOCONTEXT_VACUUM + 1` at line 297) [verified-by-code](source/src/include/pgstat.h:288-297). | — | memory-contexts |
| 3 | `src/backend/storage/buffer/freelist.c` | Add a `case BAS_<NEW>:` arm to `GetAccessStrategy()` (line 436) that sets `ring_size_kb`. Pick a size with the same reasoning as the README §"Buffer Ring Replacement Strategy" [verified-by-code](source/src/backend/storage/buffer/freelist.c:436-498). | [freelist.c.md](../files/src/backend/storage/buffer/freelist.c.md) | memory-contexts |
| 4 | `src/backend/storage/buffer/freelist.c` | Add the `case BAS_<NEW>:` arm to `IOContextForStrategy()` (line 717) returning the new `IOCONTEXT_*` value. The final `elog(ERROR, ...)` at line 736 is the safety net that crashes on a missed case [verified-by-code](source/src/backend/storage/buffer/freelist.c:711-737). | [freelist.c.md](../files/src/backend/storage/buffer/freelist.c.md) | memory-contexts |
| 5 | `src/backend/storage/buffer/freelist.c` (optional) | If the new strategy benefits from pinning more than `nbuffers/2` (the default-arm value), add an explicit `case BAS_<NEW>:` to `GetAccessStrategyPinLimit()` at line 579 [verified-by-code](source/src/backend/storage/buffer/freelist.c:573-599). | [freelist.c.md](../files/src/backend/storage/buffer/freelist.c.md) | memory-contexts |
| 6 | `src/backend/utils/activity/pgstat_io.c` | Add the new `IOCONTEXT_*` case to `pgstat_get_io_context_name()` (line 240) returning the lowercase string that will appear in `pg_stat_io.context` [verified-by-code](source/src/backend/utils/activity/pgstat_io.c:239-258). | — | — |
| 7 | `src/backend/utils/activity/pgstat_io.c` | Update `pgstat_tracks_io_object()` if the new context excludes certain `IOObject` values (e.g. WAL, temp relations) — pattern at lines 406-467 [verified-by-code](source/src/backend/utils/activity/pgstat_io.c:406-468). | — | — |
| 8 | `src/backend/utils/activity/pgstat_io.c` | Update `pgstat_tracks_io_op()` — in particular, the `strategy_io_context` predicate at line 528 currently lists `BULKREAD|BULKWRITE|VACUUM`; add your new context so `IOOP_REUSE` and the `IOOP_FSYNC` suppression apply [verified-by-code](source/src/backend/utils/activity/pgstat_io.c:478-558). | — | — |
| 9 | `src/backend/utils/activity/pgstat_io.c` | If the new context excludes certain backend types (cf. checkpointer/bgwriter exclusion at lines 454-458), add the matching guard. Skipping this leaves spurious rows in `pg_stat_io` [verified-by-code](source/src/backend/utils/activity/pgstat_io.c:449-465). | — | — |
| 10 | `src/backend/storage/buffer/README` | Update the "Buffer Ring Replacement Strategy" section (lines 206-247) describing the new ring class, its size rationale, and any dirty-buffer policy [from-README](source/src/backend/storage/buffer/README:206-247). | — | — |
| 11 | `doc/src/sgml/monitoring.sgml` | Add the new context name to the `pg_stat_io.context` enumeration (list at lines 2987-3000) and update any per-context narrative (lines 3160-3185 enumerate contexts that observe `IOOP_REUSE` etc.) [verified-by-code](source/doc/src/sgml/monitoring.sgml:2987-3185). | — | — |
| 12 | `doc/src/sgml/glossary.sgml` | The "Buffer Access Strategy" glossary entry at lines 314-330 is generic — usually no edit needed, but re-read it to confirm your addition doesn't invalidate the description [verified-by-code](source/doc/src/sgml/glossary.sgml:314-330). | — | — |
| 13 | `src/backend/commands/<area>.c` (callers) | At least one caller must invoke `GetAccessStrategy(BAS_<NEW>)` — otherwise the new class is dead code. Pattern: existing call sites for `BAS_BULKREAD` are in `heapam.c:409` (seqscan), `dbcommands.c:286` (CREATE DATABASE), `bufmgr.c:5399` (copy block) [verified-by-code](source/src/backend/access/heap/heapam.c:409). | — | — |
| 14 | `src/backend/utils/misc/guc_tables.c` (optional) | If the new strategy needs a user-tunable ring size, add a GUC (pattern: `vacuum_buffer_usage_limit` defined via `check_vacuum_buffer_usage_limit` at `src/backend/commands/vacuum.c:140` [verified-by-code](source/src/backend/commands/vacuum.c:140-160)). Most new strategies shouldn't expose this; the built-in heuristic at the head of `GetAccessStrategy()` is usually enough. | — | gucs-config |
| 15 | `src/backend/utils/misc/postgresql.conf.sample` (optional) | Sample-conf row for the GUC if added in #14. | — | gucs-config |
| 16 | `src/test/regress/sql/stats.sql` + `expected/stats.out` | The `stats` regression test enumerates `pg_stat_io` rows. Adding a new context will append rows; update the expected output. Pattern: lines 14-35 of `stats.out` list every (backend_type, object, context) tuple [verified-by-code](source/src/test/regress/expected/stats.out:14). | — | testing |
| 17 | `src/test/regress/expected/rules.out` | The `pg_stat_io` view definition is dumped here at line 1949. A new context value doesn't change the view text, but if you also touched `system_views.sql` it will diff [verified-by-code](source/src/test/regress/expected/rules.out:1949). | — | testing |

(NEW files are unlikely for this change-class — every site is an
existing-file edit. If your strategy is genuinely novel enough to want
its own `.c` file, you're probably building a custom buffer-pool
manager and this scenario doesn't cover that.)

## Phases — suggested split for `pg-feature-plan`

1. **Phase 1 — Enum + ring policy.** Files: [1, 2, 3, 4, 5]. Add
   `BAS_<NEW>` + matching `IOCONTEXT_<NEW>` and wire both switches in
   `freelist.c`. Phase-end check: `meson compile -C dev/build-debug`
   builds clean (the `elog(ERROR, "unrecognized ...")` arms catch
   missed cases at compile time only via `-Wswitch-enum`; rebuild
   with `meson configure -Dwerror=true` if paranoid).
2. **Phase 2 — pgstat plumbing.** Files: [6, 7, 8, 9]. Wire the name
   string and the two tracking predicates. Phase-end check:
   `dev/install-debug/bin/initdb` + `SELECT context FROM pg_stat_io`
   shows the new context value (or correctly hides it for filtered
   backend types).
3. **Phase 3 — Caller + docs.** Files: [10, 11, 12, 13, optional
   14-15]. Invoke `GetAccessStrategy(BAS_<NEW>)` from at least one
   site and update README + SGML. Phase-end check:
   `meson compile -C dev/build-debug docs` clean; smoke-test the new
   caller and observe `pg_stat_io` rows incrementing.
4. **Phase 4 — Tests + expected.** Files: [16, 17]. Re-run regression;
   regenerate `stats.out` to include the new context rows. Phase-end
   check: `meson test -C dev/build-debug --suite regress --test
   stats` is green.


## Likely reviewers
<!-- persona-reviewers:auto -->

*Personas whose Domain-ownership paths overlap this scenario's §Files. Reflect who might catch this on hackers-list.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

| Persona | Overlapping path(s) |
|---|---|
| [`heikki-linnakangas`](../personas/heikki-linnakangas.md) | `src/include`, `src/backend/utils` (+3) |
| [`michael-paquier`](../personas/michael-paquier.md) | `src/backend/utils`, `src/backend/access` (+1) |
| [`nathan-bossart`](../personas/nathan-bossart.md) | `src/include`, `src/backend/utils` (+1) |
| [`tom-lane`](../personas/tom-lane.md) | `src/backend/utils`, `src/test/regress` (+1) |
| [`peter-eisentraut`](../personas/peter-eisentraut.md) | `src/include`, `src/backend/commands` |
| [`david-rowley`](../personas/david-rowley.md) | `src/test/regress` |

<!-- /persona-reviewers:auto -->

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`heap-tuple-freeze`](../idioms/heap-tuple-freeze.md) | shares files: `src/backend/access/heap/heapam.c` |
| [`heaptuple-update-chain`](../idioms/heaptuple-update-chain.md) | shares files: `src/backend/access/heap/heapam.c` |
| [`memory-contexts`](../idioms/memory-contexts.md) | direct reference |
| [`tuple-locking-modes`](../idioms/tuple-locking-modes.md) | shares files: `src/backend/access/heap/heapam.c` |
| [`wal-record-construction`](../idioms/wal-record-construction.md) | shares files: `src/backend/access/heap/heapam.c` |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **Forgot the paired IOContext.** The comment at `bufmgr.h:31-33`
  is the only place this contract is stated; it's easy to miss. The
  bug surfaces as: code compiles, runs, but
  `IOContextForStrategy()` hits `elog(ERROR)` on the first I/O
  recorded against the new strategy [verified-by-code](source/src/backend/storage/buffer/freelist.c:736).
- **`pgstat_tracks_*` predicates not updated.** Symptom: new strategy
  works, `pg_stat_io` either silently drops rows (no match in
  `pgstat_tracks_io_object`) or includes spurious rows for backend
  types that shouldn't track the new context. Test by running the
  workload and `SELECT * FROM pg_stat_io WHERE context = '<new>'`.
- **`IOOP_REUSE` and `IOOP_FSYNC` discipline.** The
  `strategy_io_context` predicate at `pgstat_io.c:528` decides which
  contexts count `IOOP_REUSE` (only ring-strategy contexts do) and
  which suppress `IOOP_FSYNC` (ring strategies report fsync under
  `IOCONTEXT_NORMAL` instead; see `register_dirty_segment()` comment
  at line 549-553) [verified-by-code](source/src/backend/utils/activity/pgstat_io.c:525-555).
- **Ring-size cap.** `GetAccessStrategyWithSize()` silently caps the
  ring to `NBuffers / 8` [verified-by-code](source/src/backend/storage/buffer/freelist.c:525-526). On a tiny
  `shared_buffers` your headline number is a lie. Document the cap if
  it matters; otherwise rely on existing test coverage.
- **`StrategyRejectBuffer()` is BULKREAD-only.** Every non-`BAS_BULKREAD`
  strategy will dirty its ring and WAL-flush on reuse. If your
  workload is read-mostly but occasionally hint-bit-dirties, you want
  to either piggyback on `BAS_BULKREAD` or extend the reject path —
  the latter is a wider change than this scenario covers
  [verified-by-code](source/src/backend/storage/buffer/freelist.c:754-756).
- **Pin-limit default.** `GetAccessStrategyPinLimit()` returns
  `nbuffers / 2` for everything except `BAS_BULKREAD`. If your caller
  uses read-stream lookahead this caps prefetch distance harshly
  [verified-by-code](source/src/backend/storage/buffer/freelist.c:579-598).
- **Synchronization traps** (sibling files that must change together):
  - `bufmgr.h` `BufferAccessStrategyType` ↔ `pgstat.h` `IOContext`
    (mandated by header comment).
  - `freelist.c` `GetAccessStrategy()` ↔ `IOContextForStrategy()`
    (both switches must cover the new enumerator; missed case becomes
    runtime `elog(ERROR)`).
  - `pgstat_io.c` `pgstat_get_io_context_name()` ↔
    `pgstat_tracks_io_object()` ↔ `pgstat_tracks_io_op()` (a context
    without a name string crashes the view; a context without
    tracking predicates produces wrong rows).
  - `monitoring.sgml` ↔ `stats.out` (docs enumerate context strings;
    regress dumps actual rows; both must agree).

## Verification (exact test invocations)

```bash
# Build (catches missing switch cases via -Wswitch warnings)
meson compile -C dev/build-debug

# Reinitdb is NOT required (no catalog change) but re-running ensures
# a clean baseline for stats.out comparisons.
rm -rf dev/data-debug && dev/install-debug/bin/initdb -D dev/data-debug
dev/install-debug/bin/pg_ctl -D dev/data-debug -l logfile start

# Regression scope this scenario expects to exercise
meson test -C dev/build-debug --suite regress --test stats
meson test -C dev/build-debug --suite regress --test rules
meson test -C dev/build-debug --suite regress --test sanity_check

# Full check-world to be safe (BAS_* is touched by many heap / vacuum
# / copy tests indirectly)
meson test -C dev/build-debug

# Docs build (catches monitoring.sgml typos)
meson compile -C dev/build-debug docs

# Smoke-test the new context appears in pg_stat_io
dev/install-debug/bin/psql -c "SELECT DISTINCT context FROM pg_stat_io ORDER BY 1;"
# Run a workload that uses the new strategy and confirm rows increment:
dev/install-debug/bin/psql -c "SELECT backend_type, object, context, reads, writes, reuses FROM pg_stat_io WHERE context = '<new>';"
```

If the change adds a brand-new test, prefer to extend
`src/test/regress/sql/stats.sql` rather than create a new schedule
entry — the existing test already enumerates every
(backend_type, object, context) tuple and is the natural home for new
context coverage [verified-by-code](source/src/test/regress/expected/stats.out:14-35).

## Cross-refs

- Companion skills: `.claude/skills/memory-contexts/SKILL.md` (strategy
  object is palloc'd in caller's CurrentMemoryContext;
  `FreeAccessStrategy()` is just a typed `pfree`),
  `.claude/skills/gucs-config/SKILL.md` (only if you add a tunable
  ring-size GUC).
- Related scenarios:
  - `scenarios/add-new-table-am.md` — a new table AM often needs a
    new strategy class, or at minimum a thoughtful choice among
    existing ones in its `scan_begin` / `relation_copy_for_cluster`
    hooks.
  - `scenarios/add-new-pg-stat-view.md` — if you also want a *new
    view* exposing the new context separately rather than folding it
    into `pg_stat_io`.
- Idioms: `knowledge/idioms/memory-contexts.md` (palloc/pfree
  discipline for strategy objects),
  `knowledge/idioms/catalog-conventions.md` (no catalog change here,
  but the SGML/glossary edits follow the same docs-update discipline).
- Subsystems: `knowledge/subsystems/storage-buffer.md` (the architecture
  doc for `src/backend/storage/buffer/`),
  `knowledge/files/src/backend/storage/buffer/freelist.c.md`,
  `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`.
- Issues: `knowledge/issues/storage-buffer.md` — read for prior traps
  with ring-buffer reuse, WAL-flush behavior, and pin-limit
  interactions.
- Reference patch (canonical_commit): `git -C source show 28e626bde00`
  for the pgstat-IO infrastructure that every new BAS class must
  extend. Also useful: `git -C source show 1cbbee03385` (BUFFER_USAGE_LIMIT
  option — pattern for a tunable per-strategy ring size) and
  `git -C source show 3bd8439ed62` (added `GetAccessStrategyPinLimit`,
  a recent example of extending the strategy API).
