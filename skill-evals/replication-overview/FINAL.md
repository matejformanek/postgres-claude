# replication-overview — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/replication-overview/SKILL.md`.

## Score progression

| Run | with_skill | baseline | delta (skill - baseline) |
|---|---|---|---|
| Iteration 1 | 26 / 27 = 0.963 | 11 / 27 = 0.407 | +0.556 |
| Iteration 2 | 27 / 27 = 1.000 | 13 / 27 = 0.481 | +0.519 |

The skill clears the assertion bar at 100% after iteration 2's edits. The
absolute lift over baseline stays in the +0.5 range across both runs;
baseline variance accounts for the small baseline shift (slotsync.c name
recall and a couple of mid-confidence items landed differently on this run).

## What changed between iter-1 and iter-2

Four edits from `iteration-1/proposed-edits.md` were applied to SKILL.md:

1. **Edit #1** — `logical_decoding_work_mem = 64MB` added to the Knob
   cheatsheet under a new "Logical decoding tuning" sub-block. Closes the
   only iter-1 with_skill miss.
2. **Edit #2** — wakeup-chain entry point added to §"When to send the
   user deeper": names `WalSndWaitForWal → PhysicalWakeupLogicalWalSnd →
   wal_confirm_rcv_cv`.
3. **Edit #3** — slotsync.c bullet expanded to enumerate the three
   sync-ready preconditions and the RS_TEMPORARY → RS_PERSISTENT flip,
   cited to `slotsync.c:11-40`.
5. **Edit #5** — `MAX_SEND_SIZE = XLOG_BLCKSZ * 16` (~128 KB) named
   inline with the Sender bullet, cited to `walsender.c:110-118`.

Edit #4 (`remote_apply` ordering subtlety) was skipped — optional, not
covered by any assertion, and the architecture doc already discusses it.

## Source-value verifications performed

Before applying, the following claims in `proposed-edits.md` were
verified against `source/`:

- `logical_decoding_work_mem`: real GUC at
  `source/src/backend/utils/misc/guc_parameters.dat:1928`, default 64MB
  (postgresql.conf.sample:151).
- `MAX_SEND_SIZE = XLOG_BLCKSZ * 16` at
  `source/src/backend/replication/walsender.c:118`. Header comment
  explicitly calls out 128 kB at 8 K block size.
- `RS_INVAL_*` constants at
  `source/src/include/replication/slot.h:60-68`. Already correct in
  SKILL.md.
- slotsync.c three-precondition predicate at
  `source/src/backend/replication/logical/slotsync.c:11-40`.

All values used in the edits match source exactly.

## Verdict

`replication-overview` is **ready**. The skill provides a strong absolute
lift over baseline (~+0.5) and now clears 100% of assertions in this
test set. The structural split (SKILL.md = orientation + cheatsheet,
`knowledge/architecture/replication.md` = conceptual depth) is correct
and was preserved.

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/skills/replication-overview/SKILL.md`
- `/Users/matej/Work/postgres/postgres-claude/skill-evals/replication-overview/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/skill-evals/replication-overview/iteration-2/`
