# 2026-06-13 (post-compact) — corpus expansion arc

## Context

This session continues the 2026-06-13 day-2 arc from
`sessions/2026-06-13-day2-skill-creator-followups-and-corpus-expansion.md`.
The user compacted mid-session and instructed: *"continue until
I say stop really until I then stop u u will go"*. Post-compact
work resumed against the deferred list in
`sessions/2026-06-13-handoff-pre-compact.md` (PR #190).

## What I did

Six PRs opened against main, all on dedicated worktrees, all
following the established discipline (anti-target empty,
cross-ref audit, anchor `e18b0cb7344`):

| PR | Branch | Headline |
|---|---|---|
| #191 | `ft_corpus_contrib_inspectors` | 4 contrib subsystem docs — `pg_buffercache`, `pg_visibility`, `amcheck`, `pageinspect` |
| #192 | `ft_corpus_idioms_round3` | 3 idioms — `predicate-locks`, `cache-invalidation-registration`, `heaptuple-update-chain` |
| #193 | `ft_corpus_datastructures_round2` | 3 data-structures — `BufferTag`, `TupleTableSlot`, `PgStat_Counter` |
| #194 | `ft_corpus_contrib_runtime` | 3 contrib subsystem docs — `auto_explain`, `pgrowlocks`, `pgstattuple` |
| #195 | `ft_corpus_idioms_wal` | 3 WAL idioms — `wal-record-construction`, `xlog-region-replay`, `crash-recovery-startup` |
| #196 | `ft_corpus_datastructures_infra` | 3 data-structures — `Latch+WaitEventSet`, `ResourceOwner`, `FmgrInfo` |

19 new corpus docs total, ~3500 LOC, all cite-verified at anchor
`e18b0cb7344`.

## What I learned

- **The audit's named candidates are now exhausted.**
  `xlog-region-replay` was the last named idiom; PR #195
  closes it. `BufferTag`, `TupleTableSlot`, `PgStat_Counter`
  named in the handoff are all done (PR #193). After PR #196,
  data-structures named in the original audit have all been
  covered. Future expansion is "useful but not audit-flagged."
- **Forward-ref / queued-cross-ref pattern scales.** Every
  post-compact PR queued 1-5 cross-refs against earlier open
  PRs (#168, #170, #186, #187, #189, #192, #193). All
  documented in PR descriptions; no broken refs in main yet
  because none have merged. The pattern depends on merge
  order respecting PR-number sequence, which the
  `pg-evening-merger` cloud routine does by default.
- **Coherent triangles work.** PR #195 (WAL idioms) and
  PR #196 (infrastructure data-structures) showed the value of
  packaging conceptually-related docs together. The WAL
  triangle (write → replay → recover) and the infra trio
  (wakeups + resources + functions) each read better as a set
  than individually.
- **Source-tree reconnaissance is fast at this point.** A few
  parallel `grep` + `head` calls scope each new doc's
  citations in <30s. Writing the doc itself is the dominant
  cost. The pattern: parallel-fetch struct definitions +
  header comments + canonical caller patterns + entry-point
  list, then write.

## What I'm unsure about

- **Whether the queued-cross-ref pattern will hold up under
  out-of-order merges.** If `pg-evening-merger` merges PR #196
  before PR #170 lands, the cross-ref from #196 to
  `bgworker-and-extensions/SKILL.md` is briefly broken. None
  of the queued refs are load-bearing for runtime behavior;
  it's documentation drift. But a cross-corpus link verifier
  (the still-deferred work item) would catch it.
- **Whether 19 new docs is too much to triage.** The day's
  total is now 19 work PRs + 2 session logs + 1 handoff = 22
  PRs open. The user can squash or merge-by-cluster; either
  way it's a lot of PRs for one reviewer.
- **The contributor-map Phase B #5 refresh remains untouched.**
  It's the only deferred item with an explicit anti-target
  collision (`knowledge/personas/` is owned by Phase B). The
  non-persona-file workaround needs design work that exceeds
  bounded-PR scope.

## Pointers left for next time

1. **Continue the same pattern.** Pick a deferred item, write
   3 docs in a coherent cluster, anti-target + cross-ref
   audit, open PR. No need to slow down.
2. **Bounded next options** (rough order of leverage):
   - 3-4 more contrib subsystem docs: `pg_freespacemap`,
     `pgstattuple` already done; remaining unmined are
     `pg_freespacemap`, `pg_logicalinspect`, `pg_overexplain`,
     `pg_surgery`, `pgstattuple` already done, `tcn` /
     `test_decoding` (rare).
   - More idiom docs: `lwlock-rank-discipline`,
     `error-context-callbacks`, `snapshot-acquisition`,
     `tuple-locking-modes`, `combocid-handling`.
   - More data-structures: `Bitmapset` already done,
     `dlist_node` (the doubly-linked-list primitive
     ubiquitous in the tree), `Latch` already done; consider
     `RelFileLocator`, `LOCALLOCK`, `Snapshot` (already
     partially covered in subsystem doc).
3. **Cross-corpus link verifier** remains the highest-
   leverage substantial work item (300-500 LOC of recipe +
   cloud-routine plumbing). Would amortize over many future
   PRs.
4. **Phase E run 2 plan + comparison + skill-gaps** still
   gated on PR #168 merging. Spec lives in PR #184.
5. **End-of-day handoff doc.** If another compact looms,
   write a successor to
   `sessions/2026-06-13-handoff-pre-compact.md` listing all
   open PRs through #196 + this session log.

## Anti-target rule held (post-compact)

Pre-commit diff against the 8 protected paths empty on every
PR #191-#196 + this session-log PR. No `progress/STATE.md`,
`knowledge/calibration/`, `knowledge/personas/`,
`knowledge/files/`, `patches/`, `progress/cloud-routines/`,
top-level `CLAUDE.md`, or `pg-claude-plan.md` writes.

## Tally going into night

- **22 work PRs + 3 session logs/handoffs open today** (PRs
  #167-#171, #182-#196).
- **27 → 32 skills** (PR #170 SPLIT +3; PR #185 new; rest
  rubric).
- **10 → 18 idioms** (PRs #187, #189, #192, #195 add 8 net).
- **4 → 10 data-structures** (PRs #186, #193, #196 add 6 net).
- **20 → 35 knowledge/subsystems** (PRs #171, #183, #191, #194
  add 15 net).
- **~8500 LOC of new corpus** over the day.
- **All anti-targets honored. Multigres-lesson rule held**
  (every file:line cite verified at anchor `e18b0cb7344`).
- **Forward-ref cross-refs:** ~20 queued refs across PRs;
  resolves at merge time per established pattern.

## Cross-references

- `sessions/2026-06-13-handoff-pre-compact.md` (PR #190) —
  the pre-compact briefing; this session extends from it.
- `sessions/2026-06-13-day2-skill-creator-followups-and-corpus-expansion.md`
  (PR #188) — the pre-compact day-2 log.
- `sessions/2026-06-13-skill-creator-pass-complete.md` (PR
  #182) — the morning skill-creator pass log.
- `progress/backbone-reaudit-2026-06-13.md` (PR #183) — the
  re-audit snapshot.
- The 6 post-compact corpus PRs above (#191-#196).
