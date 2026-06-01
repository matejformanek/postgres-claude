# spgscan.c

- **Source path:** `source/src/backend/access/spgist/spgscan.c` (1090 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Scan engine for SP-GiST: setup (`spgbeginscan`/`spgrescan`/`spgendscan`), forward iteration (`spggettuple`), bitmap scan (`spggetbitmap`), KNN ordering via pairing heap. [from-comment, spgscan.c:1-13]

## Algorithm

Per README §"Search traversal algorithm":
1. Start at root (main tree if no nulls in query, also nulls tree if needed).
2. Maintain a stack/queue of `(page, parentLSN)` entries to visit.
3. At each inner tuple, call opclass `innerConsistent` to get list of node indexes to descend into. Push each child onto stack.
4. At each leaf tuple chain, call opclass `leafConsistent` per tuple; emit matching heap TIDs.
5. **Release lock on current page before locking next**. [from-README, README:252-256]

## Redirect handling

When the scan arrives at a leaf or inner page and finds a `SPGIST_REDIRECT` tuple at the expected offset, it follows the redirect link to wherever the chain was moved. [from-README, README:275-289]

The redirect's XID is checked against the scan's transaction snapshot: if the redirect was created after the scan started, the scan follows it; if before, the scan's parent-traversal already accounted for it (the downlink was updated). Actually — more conservatively, the scan always follows the redirect when it sees one, and the redirect's removal by VACUUM is gated by XID horizon. [verified-by-code in spgscan.c body; README:261-266]

## KNN

For order-by-op queries, an additional `distances[]` array per queue entry stores the opclass `leafConsistent`/`innerConsistent` reported distances. Queue is a pairing heap (`lib/pairingheap.h`) ordered by distance.

## SSI

`PredicateLockPage` on each leaf page visited.

Tags: [from-README, README:252-289]; [verified-by-code at function structure].
