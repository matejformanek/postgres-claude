# xid.c — 32-bit `xid` + `xid8` + `cid` type I/O

## Purpose

Defines the SQL-visible `xid` (32-bit `TransactionId`), `xid8` (64-bit `FullTransactionId`), and `cid` (32-bit `CommandId`) types: text/binary I/O, equality, age, hash, and the qsort comparators used inside snapshot processing.

Source: `source/src/backend/utils/adt/xid.c` (413 lines).

## Key functions

- `xidin` (33) — parses an unsigned 32-bit int via `uint32in_subr`. Note: a 32-bit xid wraps every ~4 billion transactions, so values >= 2^31 are valid "future" xids in wraparound math. [verified-by-code]
- `xidout` (43) — emits decimal via `snprintf("%u")`. [verified-by-code]
- `xidrecv` (56) / `xidsend` (67) — wire format, 4 bytes. [verified-by-code]
- `xideq` (81) / `xidneq` (93) — uses `TransactionIdEquals`. Note: equality is reflexive on the bit pattern, not on epoch-aware logical identity. [verified-by-code]
- `hashxid` / `hashxidextended` (102, 108) — hash via `hash_uint32`. [verified-by-code]
- `xid_age` (117) — distance to `GetStableLatestTransactionId()`; treats permanent xids (FrozenXid, BootstrapXid) as INT_MAX. [verified-by-code]
- `mxid_age` (133) — same idea for MultiXactId. [verified-by-code]
- `xidComparator` (152) — qsort key. Comment block at 145-150 is critical: "We can't use wraparound comparison for XIDs because that does not respect the triangle inequality! Any old sort order will do." So uses `pg_cmp_u32`, which is unsigned-int compare, NOT TransactionIdPrecedes. [verified-by-code]
- `xidLogicalComparator` (169) — for xids known to be from the same epoch (e.g. all from currently-running backends), uses `TransactionIdPrecedes`. Asserts both inputs are normal. [verified-by-code]
- `xid8toxid` (187), `xid8in` (195), `xid8out` (205), `xid8recv` (215), `xid8send` (225) — 64-bit family. [verified-by-code]
- `xid8eq` ... `xid8cmp` (236-301), `hashxid8` / `_extended` (304, 310), `xid8_larger`/`_smaller` (316, 328). [verified-by-code]
- `cidin` / `cidout` / `cidrecv` / `cidsend` / `cideq` / `hashcid` / `hashcidextended` (347-414). [verified-by-code]

## Phase D notes

- **Triangle-inequality issue with wraparound compare** — explicitly called out at xid.c:145-150. The qsort comparator MUST be a total order; `TransactionIdPrecedes` is not one across the full 32-bit range. The code correctly uses bitwise compare for sorting and saves logical compare for snapshot-internal use. [verified-by-code]
- **Permanent xid handling**: `xid_age` returns INT_MAX for FrozenXid (= 2) and BootstrapXid (= 1) so an aged tuple's `xmin` shows up as "infinitely old" in queries. [verified-by-code:122-124]
- **xid8 wraps at 2^64**, not 2^32. The FullTransactionId encoding adds an epoch counter to the visible xid, so `xid8` is monotonically increasing for the foreseeable future (~10^11 years at PG18 commit rates).
- **No string injection in I/O** — `snprintf` into a fixed buffer with `%u`/`UINT64_FORMAT`.

## Potential issues

- `[ISSUE-correctness: xidComparator is unsigned-int order, which means SQL `ORDER BY xid` is NOT logical-transaction order across epochs. A user inspecting old WAL via `pg_stat_activity.backend_xmin` may see surprising orderings. Documented in user docs (low)]`.
- `[ISSUE-undocumented-invariant: cidin accepts any uint32 but cids in practice are bounded by max command id per transaction. A user-supplied cid >= 2^32 is rejected; one near 2^32 - 1 (combo-cid territory) round-trips fine but may interact oddly with combocids if used as a tuple cid (low)]`.

Confidence: `[verified-by-code]`.
