# Iteration 1 — Summary

**Skill**: `replication-overview`
**Date**: 2026-06-02
**Method**: single-context, no subagents

## Prompts evaluated

1. Trace a COMMIT through physical streaming replication with `synchronous_commit=remote_apply`.
2. Logical decoding pipeline: WAL -> output plugin.
3. Failover slot mechanism (v17+): mirroring, sync-ready preconditions, `synchronized_standby_slots`.

## Scores

| Cohort | Passed / Total | Pass rate |
|---|---|---|
| with_skill | 26 / 27 | 0.963 |
| baseline   | 11 / 27 | 0.407 |

Skill delta: +0.556 (15 additional assertions out of 27).

## What the skill clearly helped with

- File:line cites (walsender.c:1801-1886, slotsync.c:11-35, syncrep.c:60-65) — baseline had none.
- Function/identifier names: WalSndWaitForWal, PhysicalWakeupLogicalWalSnd, wal_confirm_rcv_cv, SyncRepQueue, ReorderBufferProcessXid.
- Constants: MAX_SEND_SIZE = 16*XLOG_BLCKSZ = 128 KB, the four RS_INVAL_* causes, three RS_* persistency states.
- Non-obvious details: walreceiver is dynamically loaded (not linked against libpq), shutdown-order subtlety, spill picks LARGEST txn, reorder buffer's Slab+Generation context split.
- The three sync-ready preconditions for failover slots — baseline missed all three.

## Where baseline kept up

- High-level pipeline shape (decode -> reorderbuffer -> plugin).
- Existence of failover/sync_replication_slots/synchronized_standby_slots GUCs.
- remote_apply visibility semantics.
- test_decoding and pgoutput as canonical plugins.

## One miss against the skill

Skill does NOT name `logical_decoding_work_mem` (per-reorderbuffer memory ceiling). Baseline produced it from general PG admin familiarity.

## Recommended edits (see proposed-edits.md)

1. HIGH: name `logical_decoding_work_mem` in the knob cheatsheet.
2. MED: add "logical slot stuck behind physical standby" entry point.
3. MED: surface the three sync-ready preconditions in SKILL.md (currently only in architecture doc).
4. LOW: clarify remote_apply visibility ordering.
5. LOW: name MAX_SEND_SIZE inline.

## Decision

Skill is strong. Edit #1 is the only meaningful gap. Recommend applying #1 and #2 before iteration 2.
