# Iteration 2 — edits applied

Applied edits from `iteration-1/proposed-edits.md` to
`.claude/skills/replication-overview/SKILL.md`.

## Verification of values against source/

- `logical_decoding_work_mem` — verified as a real GUC at
  `source/src/backend/utils/misc/guc_parameters.dat:1928,1932` and default
  shown in `postgresql.conf.sample:151` (`64MB`, min `64kB`).
- `MAX_SEND_SIZE` — verified at `source/src/backend/replication/walsender.c:118`
  as `#define MAX_SEND_SIZE (XLOG_BLCKSZ * 16)`. Comment at lines 110-117
  explicitly mentions "128kB (with default 8k blocks)".
- `RS_INVAL_*` constants — verified at `source/src/include/replication/slot.h:60-68`
  (`RS_INVAL_NONE`, `RS_INVAL_WAL_REMOVED=1<<0`, `RS_INVAL_HORIZON=1<<1`,
  `RS_INVAL_WAL_LEVEL=1<<2`, `RS_INVAL_IDLE_TIMEOUT=1<<3`). Already correct
  in SKILL.md, no edit needed.
- slotsync.c three-condition predicate — verified at
  `source/src/backend/replication/logical/slotsync.c:11-40` (header comment
  enumerates WAL-past-confirmed-flush, catalog xmin, consistent snapshot at
  restart_lsn before confirmed_flush_lsn, all flipping RS_TEMPORARY →
  RS_PERSISTENT).

## Edits applied

1. **Edit #1** — added `logical_decoding_work_mem = 64MB` line with comment
   to the Knob cheatsheet, in a new "Logical decoding tuning" sub-block
   between "Logical replication subscriber" and "Synchronous".
2. **Edit #2** — added the "Why is my logical slot stuck behind a physical
   standby?" bullet to §"When to send the user deeper", naming the wakeup
   chain `WalSndWaitForWal → PhysicalWakeupLogicalWalSnd → wal_confirm_rcv_cv`.
3. **Edit #3** — expanded the `logical/slotsync.c` bullet under §"Where to
   look in source" → "Logical replication (PUB/SUB)" to enumerate the three
   sync-ready preconditions and the RS_TEMPORARY → RS_PERSISTENT flip with
   `synced=true`. Cited `slotsync.c:11-40`.
5. **Edit #5** — named `MAX_SEND_SIZE = XLOG_BLCKSZ * 16` (~128 KB) inline
   with the Sender bullet under §"Where to look in source" → "Physical
   streaming", with cite to `walsender.c:110-118`.

## Edits NOT applied

- **Edit #4** (remote_apply ordering subtlety) — optional, not covered by
  any iter-1 assertion, and the architecture doc already discusses it.
  Skipped to keep SKILL.md tight.
