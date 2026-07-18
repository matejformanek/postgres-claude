# `src/include/storage/locktag.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 190

## Role

`LOCKTAG` — the 16-byte hashable key that identifies a lockable
object in shared memory. The lock manager hashtable is keyed on
the full struct. Designed to fit exactly 16 bytes with no
padding. [from-comment] `source/src/include/storage/locktag.h:56-62`

## Struct layout (exactly 16 bytes)

```
LOCKTAG {
    uint32  locktag_field1   // 4
    uint32  locktag_field2   // 4
    uint32  locktag_field3   // 4
    uint16  locktag_field4   // 2
    uint8   locktag_type     // 1  (LockTagType enum)
    uint8   locktag_lockmethodid  // 1  (1=DEFAULT, 2=USER)
}                            // 16 total, no padding
```

[verified-by-code] lines 64-72.

## The 12 LockTagTypes (line 35-50)

| Type | Field overload |
|---|---|
| `LOCKTAG_RELATION` | (dbOid, relOid, 0, 0) |
| `LOCKTAG_RELATION_EXTEND` | same layout, different sem |
| `LOCKTAG_DATABASE_FROZEN_IDS` | (dbOid, 0, 0, 0) — pg_database.datfrozenxid update lock |
| `LOCKTAG_PAGE` | (dboid, reloid, blocknum, 0) |
| `LOCKTAG_TUPLE` | (dboid, reloid, blocknum, offnum) |
| `LOCKTAG_TRANSACTION` | (xid, 0, 0, 0) — wait-for-xact |
| `LOCKTAG_VIRTUALTRANSACTION` | (procNum, localXid, 0, 0) |
| `LOCKTAG_SPECULATIVE_TOKEN` | (xid, token, 0, 0) — INSERT ON CONFLICT |
| `LOCKTAG_OBJECT` | (dboid, classoid, objoid, objsubid) — non-rel objects |
| `LOCKTAG_USERLOCK` | (legacy contrib/userlock; reserved) |
| `LOCKTAG_ADVISORY` | (id1, id2, id3, id4) — user-controlled, `USER_LOCKMETHOD` |
| `LOCKTAG_APPLY_TRANSACTION` | (dboid, suboid, xid, objid) — logical-replication apply |

`LOCKTAG_LAST_TYPE = LOCKTAG_APPLY_TRANSACTION` (line 52).
`LockTagTypeNames[]` is a parallel `const char *` array exported
for `DescribeLockTag` and `pg_locks`.

`SET_LOCKTAG_*` setter macros (lines 81-188) — every one
zero-fills unused fields to ensure `memcmp` equality.

## Invariants

- INV-1: **NO unused padding** — struct depends on all-tight
  layout for hashtable keying via `memcmp`. Widening any of
  `Oid`, `BlockNumber`, `TransactionId` past 32 bits would
  require restructuring. [from-comment] lines 57-59.
- INV-2: 256 LockTagTypes max (`uint8 locktag_type`). 256
  lockmethods max (`uint8 locktag_lockmethodid`). [from-comment]
  lines 19-22, 32-33.
- INV-3: `SUBID` (`locktag_field4` for OBJECT) is constrained to
  16 bits, narrower than pg_depend's representation.
  [from-comment] lines 155-160.
- INV-4: setter macros multi-evaluate `locktag`. [from-comment]
  line 77.

## Trust boundary (Phase D)

- **Advisory locks** (`LOCKTAG_ADVISORY`, `USER_LOCKMETHOD`) are
  the only locktag type with attacker-controlled fields. The
  SQL-visible `pg_advisory_lock(int8)` and 2-arg variants
  produce a deterministic LOCKTAG from caller input. There is
  no ACL on advisory lock keys — collision-DOS by colliding
  with another app's advisory keys is a known limitation
  (documented).
- **Information leak via `pg_locks`**: an unprivileged role can
  read LOCKTAGs of other sessions' locks (subject to view
  filters). The (dboid, reloid, blocknum) for TUPLE/PAGE locks
  leaks which rows/blocks another session is touching — an
  oracle for inferring schema and activity. Cluster: A11/A14
  monitoring-as-extraction.

## Cross-refs

- `knowledge/subsystems/storage-lmgr.md`
- `knowledge/files/src/include/storage/lock.h.md` (existing)
- `knowledge/files/src/include/storage/lmgr.h.md`
- `knowledge/files/src/include/storage/lockdefs.h.md`

## Issues

- ISSUE-DESIGN: 16-bit `objsubid` in `LOCKTAG_OBJECT` differs
  from pg_depend's storage; values > 65535 silently truncate.
  [from-comment] is correct but a static-assert against
  `MaxAttrNumber < 65536` would harden. (Low — current values
  fit.)
- ISSUE-PHASE-D: `pg_locks` LOCKTAG fields reveal activity to
  unprivileged users; same cluster as A11/A14. (Informational.)

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/locktag.md](../../../../data-structures/locktag.md)

- [subsystems/storage-lmgr.md](../../../../subsystems/storage-lmgr.md)