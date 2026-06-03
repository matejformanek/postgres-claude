---
path: src/backend/utils/adt/xid.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 413
depth: deep
---

# xid.c

- **Source path:** `source/src/backend/utils/adt/xid.c`
- **Lines:** 413
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/access/transam.h` (TransactionId, FullTransactionId, TransactionIdPrecedes/Equals/IsNormal, FrozenTransactionId/BootstrapTransactionId/FirstNormalTransactionId, XidFromFullTransactionId/FullTransactionIdFromU64), `src/include/utils/xid8.h` (xid8 SQL-type get/return macros), `src/include/access/multixact.h` (ReadNextMultiXactId, MultiXactIdIsValid), `src/include/access/xact.h`, `src/include/catalog/pg_proc.dat` (SQL function bindings)

## Purpose
SQL type I/O, comparison, hashing, and aggregate-support functions for the transaction-identifier datatypes: `xid` (32-bit `TransactionId`), `xid8` (64-bit `FullTransactionId`), and `cid` (32-bit `CommandId`) [from-comment `xid.c:3-4`]. The key subtlety is that `xid` equality is exact but `xid` *ordering* is wraparound-aware (epoch-relative) and therefore not a total order, while `xid8` ordering is a plain 64-bit total order [verified-by-code `xid.c:80-99`, `xid.c:144-158`, `xid.c:253-301`]. `xid_age`/`mxid_age` compute distance from the latest stable (multi)xid using raw subtraction [verified-by-code `xid.c:116-142`].

## Public symbols
| Symbol | file:line | Role |
|---|---|---|
| `xidin` | `xid.c:32` | cstring → xid; parses via `uint32in_subr` |
| `xidout` | `xid.c:42` | xid → cstring (`%u`, 16-byte buf) |
| `xidrecv` | `xid.c:55` | binary recv (4-byte int) |
| `xidsend` | `xid.c:66` | binary send (int32) |
| `xideq` | `xid.c:80` | xid equality via `TransactionIdEquals` |
| `xidneq` | `xid.c:92` | xid inequality |
| `hashxid` | `xid.c:101` | hash via `hash_uint32` |
| `hashxidextended` | `xid.c:107` | extended (seeded) hash |
| `xid_age` | `xid.c:116` | age of xid vs `GetStableLatestTransactionId()` |
| `mxid_age` | `xid.c:132` | age of multixact vs `ReadNextMultiXactId()` |
| `xidComparator` | `xid.c:151` | qsort cmp, plain u32 order (NOT wraparound) |
| `xidLogicalComparator` | `xid.c:168` | qsort cmp, wraparound order; asserts normal xids |
| `xid8toxid` | `xid.c:186` | xid8 → xid (drops epoch) |
| `xid8in` | `xid.c:194` | cstring → xid8 via `uint64in_subr` |
| `xid8out` | `xid.c:204` | xid8 → cstring (21-byte buf) |
| `xid8recv` / `xid8send` | `xid.c:214` / `xid.c:224` | binary I/O (int64) |
| `xid8eq` / `xid8ne` | `xid.c:235` / `xid.c:244` | xid8 (in)equality |
| `xid8lt`/`xid8gt`/`xid8le`/`xid8ge` | `xid.c:253`/`262`/`271`/`280` | xid8 ordering via FullTransactionId Precedes/Follows[OrEquals] |
| `xid8cmp` | `xid.c:289` | btree 3-way compare for xid8 |
| `hashxid8` / `hashxid8extended` | `xid.c:303` / `xid.c:309` | delegate to `hashint8`/`hashint8extended` |
| `xid8_larger` / `xid8_smaller` | `xid.c:315` / `xid.c:327` | min/max aggregate support |
| `cidin`/`cidout`/`cidrecv`/`cidsend` | `xid.c:346`/`359`/`372`/`383` | CommandId I/O |
| `cideq` | `xid.c:394` | CommandId equality (plain `==`) |
| `hashcid` / `hashcidextended` | `xid.c:403` / `xid.c:409` | CommandId hashing |

## Internal landmarks
- `PG_GETARG_COMMANDID` / `PG_RETURN_COMMANDID` macros defined locally [verified-by-code `xid.c:28-29`].
- Wraparound vs non-wraparound comparison split: `xidComparator` deliberately uses `pg_cmp_u32` because wraparound comparison "does not respect the triangle inequality" and would break qsort [from-comment `xid.c:144-158`]. `xidLogicalComparator` uses `TransactionIdPrecedes` but asserts both inputs are normal (same-epoch) so the triangle inequality holds [from-comment + verified-by-code `xid.c:160-184`].
- `xid_age` special-cases non-normal xids (bootstrap/frozen/invalid) as `INT_MAX` ("infinitely old") and otherwise returns raw `now - xid` cast to int32 [verified-by-code `xid.c:122-126`].
- `mxid_age` mirrors this with `MultiXactIdIsValid` → `INT_MAX` for invalid [verified-by-code `xid.c:138-141`].
- `xid8cmp` is a plain total-order 3-way compare (Follows / Equals / else -1) — no wraparound concerns because xid8 carries the epoch [verified-by-code `xid.c:289-301`].

## Invariants & gotchas
- **xid ordering is epoch-relative and not a total order.** Any code sorting raw `xid` values must use `xidComparator` (plain u32) unless all values are guaranteed same-epoch normal xids, in which case `xidLogicalComparator` gives wraparound-correct order [verified-by-code `xid.c:144-184`].
- **`xideq`/`xidneq` use exact equality** (`TransactionIdEquals`), not wraparound — equality is well-defined regardless of epoch [verified-by-code `xid.c:80-99`].
- **Non-normal xids are special.** FrozenTransactionId/BootstrapTransactionId/InvalidTransactionId fail `TransactionIdIsNormal` and are treated as infinitely old by `xid_age` [verified-by-code `xid.c:123-124`].
- **Buffer sizes are exact.** `xidout` uses a 16-byte buffer (max u32 is 10 digits + NUL), `xid8out` 21 bytes (max u64 is 20 digits + NUL) [verified-by-code `xid.c:46-48`, `xid.c:208-210`].
- **`xid8toxid` silently drops the epoch** — converting a full xid to 32-bit xid is lossy and only the low 32 bits survive [verified-by-code `xid.c:186-192`].
- **xid8 hashing piggybacks on int8 hashing** — `hashxid8`/`hashxid8extended` pass `fcinfo` straight to `hashint8`/`hashint8extended`, so xid8 and int8 hash identically [verified-by-code `xid.c:303-313`].

## Cross-references
- [[knowledge/subsystems/access-transam.md]] — TransactionId allocation, wraparound, FullTransactionId epoch semantics.
- [[knowledge/idioms/fmgr.md]] — the `Datum foo(PG_FUNCTION_ARGS)` V1 calling convention used throughout.
- Sibling adt files: [[knowledge/files/src/backend/utils/adt/oid.c.md]], [[knowledge/files/src/backend/utils/adt/int8.c.md]], [[knowledge/files/src/backend/utils/adt/tid.c.md]], [[knowledge/files/src/backend/utils/adt/numutils.c.md]] (`uint32in_subr`/`uint64in_subr`/`pg_ulltoa_n`).

## Potential issues
None surfaced. The wraparound/triangle-inequality split is documented intentional design, not a bug.

## Confidence tag tally
- [verified-by-code]: 16
- [from-comment]: 5
- [inferred]: 0
- [unverified]: 0
