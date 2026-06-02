# Proposed edits — iteration 1 (NOT applied)

## Summary of gaps found in grading

The skill (+ knowledge/architecture/replication.md) covered nearly every assertion. Baseline lost mostly on specifics: process/function names, file:line cites, exact constants, and the three-condition sync-ready predicate. One miss against the skill itself: it does NOT mention `logical_decoding_work_mem` by name (the GUC governing the per-reorderbuffer memory limit). Baseline knew this one because it's commonly cited in PG admin docs.

## Concrete edits to consider

### 1. Add `logical_decoding_work_mem` to the knob cheatsheet (SKILL.md §Knob cheatsheet)

Under the "Primary (any flavor)" or a new "Logical decoding tuning" section:

```
logical_decoding_work_mem = 64MB   # per-reorderbuffer memory ceiling
                                   # before largest txn spills to disk
```

Rationale: this is the single most-asked operational knob in logical-decoding
incident response and the skill never names it. Currently knowledge/architecture/replication.md
mentions "per-reorderbuffer memory limit" without naming the GUC either.

### 2. Add a "wakeup chain" pointer to SKILL.md §When to send the user deeper

Add bullet:

> - "Why is my logical slot stuck behind a physical standby?" →
>   `synchronized_standby_slots` gate + the walsender wakeup chain
>   (`WalSndWaitForWal` → `PhysicalWakeupLogicalWalSnd` →
>   `wal_confirm_rcv_cv`). See `knowledge/architecture/replication.md` §2.

Rationale: this is non-obvious cross-walsender wakeup that the architecture doc
captures but SKILL.md doesn't surface as an entry point.

### 3. Make the three sync-ready preconditions discoverable from SKILL.md

Currently `knowledge/architecture/replication.md:200-209` has them, but SKILL.md
just says "failover slots" with no breadcrumb to the three preconditions.
Consider a short bullet under §Where to look → Replication slots:

> - Slot-sync three-condition sync-ready predicate (WAL past
>   `confirmed_flush_lsn`, catalog xmin sufficient, consistent snapshot at
>   `restart_lsn`): `logical/slotsync.c:11-35`. Full discussion in
>   `knowledge/architecture/replication.md` §2 "Failover / sync slots".

### 4. Optional: note remote_apply ordering subtlety

In SKILL.md or replication.md §5, the table of `synchronous_commit` levels could
note that `remote_apply` is the only level that makes a row visible on the
standby BEFORE the primary returns to the client — relevant for read-your-writes
on a hot standby. Currently implicit.

### 5. Optional: name MAX_SEND_SIZE in SKILL.md

The constant `MAX_SEND_SIZE = 16 * XLOG_BLCKSZ = 128 KB` (walsender.c:109-118)
shows up in tuning discussions. Skill currently only points at the file; one
line naming the constant would save a grep.

## Non-edits

- The skill correctly avoids inlining what belongs in the architecture doc. The
  current structure (skill = orientation + cheatsheet, knowledge/architecture =
  conceptual depth) is the right split.
- No spurious or out-of-date claims found. Frontmatter description triggers
  correctly on the prompts used.
- Files-examined table is accurate.

## Score delta if all edits applied

Iteration 1 with_skill: 26/27 (0.963), baseline: 11/27 (0.407).
Expected after edit #1 (logical_decoding_work_mem): with_skill 27/27.
Edits 2-5 are defensive — they'd help on prompts not in this iteration's set.
