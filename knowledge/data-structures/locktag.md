# LOCKTAG — the lockable-object identifier

`LOCKTAG` is the **lookup key** for the heavyweight lock-manager
hash table. Sixteen bytes, zero-padding, fits four ID fields +
type + lockmethod. Every kind of lockable thing in PG — a
relation, a tuple, a transaction, a virtual transaction, an
advisory user lock — encodes itself into a LOCKTAG, and the
lock manager hashes on the whole struct to find or create the
corresponding LOCK entry.

Anchors:
- `source/src/include/storage/locktag.h:65-72` —
  LOCKTAG struct [verified-by-code]
- `source/src/include/storage/locktag.h:35-49` —
  LockTagType enum [verified-by-code]
- `source/src/include/storage/locktag.h:81-90` —
  SET_LOCKTAG_RELATION macro [verified-by-code]
- `knowledge/data-structures/lock-struct.md` — companion;
  the hash entry keyed by LOCKTAG
- `knowledge/data-structures/proclock.md` — companion;
  LOCKTAG indirectly via PROCLOCK
- `knowledge/data-structures/locallock.md` — companion
  (already on main; LOCALLOCKTAG wraps LOCKTAG)
- `.claude/skills/locking/SKILL.md` — companion

## The struct

[verified-by-code `locktag.h:65-72`]

```c
typedef struct LOCKTAG
{
    uint32  locktag_field1;       /* a 32-bit ID field */
    uint32  locktag_field2;
    uint32  locktag_field3;
    uint16  locktag_field4;       /* a 16-bit ID field */
    uint8   locktag_type;          /* enum LockTagType */
    uint8   locktag_lockmethodid;  /* lockmethod indicator */
} LOCKTAG;
```

**Exactly 16 bytes**, no padding. The comment explicitly states
this is the malice-aforethought fit. If Oid, BlockNumber, or
TransactionId grew beyond 32 bits, the struct would need
redesign.

## The 12 LockTagTypes

[verified-by-code `locktag.h:35-49`]

```c
typedef enum LockTagType
{
    LOCKTAG_RELATION,            /* whole relation */
    LOCKTAG_RELATION_EXTEND,     /* right to extend a relation */
    LOCKTAG_DATABASE_FROZEN_IDS, /* pg_database.datfrozenxid */
    LOCKTAG_PAGE,                /* one page of a relation */
    LOCKTAG_TUPLE,               /* one physical tuple */
    LOCKTAG_TRANSACTION,         /* wait for xact done */
    LOCKTAG_VIRTUALTRANSACTION,  /* wait for vxact done */
    LOCKTAG_SPECULATIVE_TOKEN,   /* speculative insertion */
    LOCKTAG_OBJECT,              /* non-relation DB object */
    LOCKTAG_USERLOCK,            /* deprecated */
    LOCKTAG_ADVISORY,            /* advisory user locks */
    LOCKTAG_APPLY_TRANSACTION,   /* logical-rep apply */
} LockTagType;
```

12 distinct kinds of lockable thing. Each macro
`SET_LOCKTAG_*` knows how to encode the appropriate IDs into
field1-4.

## Field assignments by type

| Type | field1 | field2 | field3 | field4 |
|---|---|---|---|---|
| RELATION | dboid | reloid | 0 | 0 |
| RELATION_EXTEND | dboid | reloid | 0 | 0 |
| DATABASE_FROZEN_IDS | dboid | 0 | 0 | 0 |
| PAGE | dboid | reloid | blocknum | 0 |
| TUPLE | dboid | reloid | blocknum | offnum |
| TRANSACTION | xid | 0 | 0 | 0 |
| VIRTUALTRANSACTION | procnumber | localxid | 0 | 0 |
| SPECULATIVE_TOKEN | xid | token | 0 | 0 |
| OBJECT | dboid | classid | objid | objsubid |
| ADVISORY | dboid | id1 | id2 | objsubid |
| APPLY_TRANSACTION | dboid | subid | xid | 0 |

(from `SET_LOCKTAG_*` macros in `locktag.h`)

The encoding is deliberate: shared-relation locks have `dboid =
0`, so cross-database locks coexist in the hash without
collision.

## Why 16 bytes matters

[from-comment `locktag.h:58-62`]

> The LOCKTAG struct is defined with malice aforethought to fit
> into 16 bytes with no padding. Note that this would need
> adjustment if we were to widen Oid, BlockNumber, or
> TransactionId to more than 32 bits.

16 bytes:
- Fits in a single SSE register.
- `memcmp(tag1, tag2, sizeof(LOCKTAG))` is one cmpxchg-style
  op.
- Hash function (`hash_any` on 16 bytes) is fast and cache-
  friendly.
- The lock-mgr hash bucket fits more entries per cache line.

## SET_LOCKTAG_* macros — the constructors

[verified-by-code `locktag.h:81-90`]

```c
#define SET_LOCKTAG_RELATION(locktag, dboid, reloid) \
    ((locktag).locktag_field1 = (dboid), \
     (locktag).locktag_field2 = (reloid), \
     (locktag).locktag_field3 = 0, \
     (locktag).locktag_field4 = 0, \
     (locktag).locktag_type = LOCKTAG_RELATION, \
     (locktag).locktag_lockmethodid = DEFAULT_LOCKMETHOD)
```

The macro is the discipline: never set fields manually; use the
`SET_LOCKTAG_*` family. Each macro encodes the proper field
layout for that tag type AND zeroes unused fields (critical for
hashing — non-zero garbage in unused fields would create
distinct LOCKTAGs for "the same" lock).

## lockmethodid — sharing the hash

```c
uint8 locktag_lockmethodid;
```

Distinguishes between the default lock method (most locks) and
USER_LOCKMETHOD (advisory locks). One shared lock-mgr hash
table holds both; the lockmethodid field segregates them.

Currently only 2 methods (`DEFAULT_LOCKMETHOD = 1`,
`USER_LOCKMETHOD = 2`), but the type allows up to 256.

## Hash + comparison

```c
hash = hash_any((unsigned char *) &tag, sizeof(LOCKTAG));
match = memcmp(&tag1, &tag2, sizeof(LOCKTAG)) == 0;
```

The lock manager uses `dynahash` keyed on LOCKTAG. Hash and
equality are byte-wise. Because of the zero-padding-out
discipline, two LOCKTAGs for the same lockable thing always
have identical bytes.

## Common review-time concerns

- **Use SET_LOCKTAG_* macros** — never manual field
  assignment. Zeroing matters.
- **16-byte budget** — adding a new field requires re-design.
- **lockmethodid = DEFAULT** for normal PG locks;
  USER_LOCKMETHOD only for advisory.
- **APPLY_TRANSACTION is recent** (logical-rep); older code
  may not handle it.
- **Adding a new LockTagType** requires updates in
  `LockTagTypeNames[]`, the `SET_LOCKTAG_*` macro family, and
  often `lock.c` / `deadlock.c` handling.

## Invariants

- **[INV-1]** LOCKTAG fits in 16 bytes; no padding.
- **[INV-2]** Unused fields are zero (set by SET_LOCKTAG_*).
- **[INV-3]** locktag_lockmethodid segregates user vs default
  locks in shared hash.
- **[INV-4]** Hash + equality are byte-wise on the whole
  struct.
- **[INV-5]** 12 LockTagTypes; APPLY_TRANSACTION is the most
  recent.

## Useful greps

- All LOCKTAG users:
  `grep -RIn 'SET_LOCKTAG_' source/src/backend | head -20`
- LockTagTypeNames array:
  `grep -n 'LockTagTypeNames' source/src/backend/storage/lmgr/lock.c | head -3`
- The struct + enum:
  `sed -n '35,75p' source/src/include/storage/locktag.h`


## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/include/storage/locktag.h`](../files/src/include/storage/locktag.h.md) | 35 | LockTagType enum |
| [`src/include/storage/locktag.h`](../files/src/include/storage/locktag.h.md) | 65 | LOCKTAG struct |
| [`src/include/storage/locktag.h`](../files/src/include/storage/locktag.h.md) | 81 | SET_LOCKTAG_RELATION macro |
| [`src/include/storage/locktag.h`](../files/src/include/storage/locktag.h.md) | — | full file |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/data-structures/lock-struct.md` — the LOCK hash
  entry keyed by LOCKTAG.
- `knowledge/data-structures/proclock.md` — companion
  hash entry per (lock, proc) pair.
- `knowledge/data-structures/locallock.md` — backend-local
  LOCALLOCK wraps LOCKTAG.
- `knowledge/idioms/fastpath-locks.md` — fastpath bypasses
  the lock-mgr hash for some LOCKTAG_RELATION cases.
- `knowledge/idioms/predicate-locks.md` — SSI uses its own
  lock space, not LOCKTAG.
- `knowledge/idioms/relation-extension-lock.md` —
  LOCKTAG_RELATION_EXTEND specifically.
- `knowledge/subsystems/storage-lmgr.md` — lock manager.
- `.claude/skills/locking/SKILL.md` — companion.
- `source/src/include/storage/locktag.h` — full file.
