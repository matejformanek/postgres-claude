# spgvacuum.c

- **Source path:** `source/src/backend/access/spgist/spgvacuum.c` (1019 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

VACUUM for SP-GiST: `spgbulkdelete` + `spgvacuumcleanup`. Single sequential index scan + pending-list re-check for concurrent moves. [from-comment, spgvacuum.c:1-13; from-README, README:321-373]

## Algorithm

1. Initialize `spgBulkDeleteState` (target TIDs, pending list, predecessor scratch).
2. Sequential scan blocks 0..nblocks-1 via `read_stream`.
3. Per leaf page (`vacuumLeafPage`):
   - Build predecessor[] from nextOffset links (reverse map).
   - Identify chain heads (no predecessor) vs body.
   - For each tuple in a chain: check against target TIDs; if dead:
     - If body tuple → replace with PLACEHOLDER, unlink from chain.
     - If head tuple with surviving members → move one survivor to head's offset, PLACEHOLDER the original.
     - If only dead tuples in chain → head becomes DEAD (downlink-preservation), body becomes PLACEHOLDERs.
   - Convert any expired REDIRECTs to PLACEHOLDERs.
   - Trim trailing PLACEHOLDERs.
   - Emit `XLOG_SPGIST_VACUUM_LEAF`.
4. Per inner page (`vacuumRedirectAndPlaceholder`):
   - Convert expired REDIRECTs (XID < safe-horizon) to PLACEHOLDERs.
   - Trim trailing PLACEHOLDERs.
   - Emit `XLOG_SPGIST_VACUUM_REDIRECT` (carries `snapshotConflictHorizon` = the *latest* REDIRECT XID being converted).
5. Drain the pending list (see below).

## Pending-list mechanism [HIGH-RISK]

A concurrent `MoveLeafs` or `PickSplit` can migrate a leaf chain from an already-scanned page to a not-yet-scanned page. To avoid missing the target TIDs:
- When `vacuumLeafPage` encounters a REDIRECT tuple whose XID indicates it was created **after** VACUUM started, add the target TID to a pending list.
- Between pages of the main scan, drain pending list: for each entry, visit the target. If it's an inner tuple, recurse on its node downlinks; if leaf, vacuum the page.
- Pending-list entries are **marked done** rather than removed, ensuring termination even with concurrent activity. [from-README, README:347-368; verified-by-code]

## Conflict horizon

The `snapshotConflictHorizon` in `XLOG_SPGIST_VACUUM_REDIRECT` is the **newest** XID being recycled (i.e. the latest-created REDIRECT being converted). At replay, the standby drains conflicts up to that XID before the recycle happens, so any in-progress Hot Standby query that might have followed an old REDIRECT is given a chance to complete first. [verified-by-code at spgxlog.c:871]

## Cross-references

- **Called by:** `commands/vacuum.c` via AM slots.
- **Calls into:** `read_stream.c`, `spgutils.c` (placeholder helpers), `xloginsert.c`.

Tags: [from-README, README:321-368]; [verified-by-code at function structure].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
