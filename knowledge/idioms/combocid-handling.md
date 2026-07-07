# ComboCID handling — cmin/cmax for self-modifying transactions

A tuple's `t_cid` field stores either the cmin (command-id of
the inserting command) OR the cmax (command-id of the
deleting/updating command). One slot, two roles. For tuples
that are both inserted AND modified in the SAME transaction,
neither cmin nor cmax fits alone — both are needed for
correct visibility. PostgreSQL solves this with **ComboCIDs**:
a backend-local table mapping a synthetic uint32 to a (cmin,
cmax) pair. The tuple stores the synthetic ID and a flag.

Anchors:
- `source/src/backend/utils/time/combocid.c` — implementation
  [verified-by-code]
- `source/src/include/access/htup_details.h:195` —
  `HEAP_COMBOCID` flag [verified-by-code]
- `source/src/include/utils/combocid.h` — public API
- `knowledge/data-structures/heap-tuple-layout.md` — tuple
  layout including `t_cid`

## The problem

`HeapTupleHeaderData.t_cid` is 32 bits. It records the
command-id within the transaction that inserted (cmin) OR
updated/deleted (cmax) the tuple. Visibility checks need:

- `cmin` to decide "is this tuple visible to the inserting
  command's continuation?" (yes if `cmin < CurrentCommandId`).
- `cmax` to decide "did the deleter overwrite us?" (yes if
  `cmax < CurrentCommandId`).

For tuples that the SAME transaction inserts THEN deletes (or
updates), both cmin and cmax matter — the tuple is visible
to itself for a window between insert and delete. With one
field, you can't store both.

## The ComboCID solution

`HEAP_COMBOCID` flag in `t_infomask`
[verified-by-code `htup_details.h:195`]:

```c
#define HEAP_COMBOCID  0x0020  /* t_cid is a combo CID */
```

When set, `t_cid` is NOT a real command-id — it's a synthetic
index into a backend-local **ComboCIDHashTable** that maps the
synthetic ID to a `(cmin, cmax)` pair.

When unset, `t_cid` is interpreted normally:
- If the tuple's xmin is the current xact AND xmax is invalid,
  `t_cid` is the cmin.
- Otherwise it's the cmax.

## The decoder inlines

[verified-by-code `combocid.c:104-133`]

```c
CommandId
HeapTupleHeaderGetCmin(const HeapTupleHeaderData *tup)
{
    if (tup->t_infomask & HEAP_COMBOCID)
        return GetRealCmin(tup->t_cid);    /* synthetic → real */
    return tup->t_cid;                     /* direct */
}

CommandId
HeapTupleHeaderGetCmax(const HeapTupleHeaderData *tup)
{
    if (tup->t_infomask & HEAP_COMBOCID)
        return GetRealCmax(tup->t_cid);
    return tup->t_cid;
}
```

The decoder branches on `HEAP_COMBOCID`. The combocid module
maintains the lookup table per backend.

## When ComboCIDs are allocated

A new ComboCID is allocated when:

1. A tuple is being updated/deleted by the SAME transaction
   that inserted it.
2. The cmin is already in `t_cid`.
3. A different cmax must now also be remembered.

The combocid module looks up "(cmin=X, cmax=Y)" in its hash
table; if present, reuses the synthetic ID; if not, allocates
a new one. The tuple's `t_cid` is overwritten with the
synthetic ID and `HEAP_COMBOCID` is set.

This means the **same (cmin, cmax) pair across multiple tuples
shares one ComboCID**. The hash table is keyed by the pair,
not by tuple.

## Backend-local, not transaction-local

The ComboCID table is **per backend**. Two backends running
concurrent transactions allocate ComboCIDs independently; the
synthetic IDs only mean anything within the issuing backend.

Consequence: **a tuple's t_cid is only interpretable while
the inserting backend is still alive** in the current
transaction. After commit/abort, the ComboCIDs are
discarded — tuples written in this transaction become
visible to others, who never see the `HEAP_COMBOCID` flag's
meaning differently (the flag is reset by
`AtEOXact_ComboCid`).

## AtEOXact_ComboCid — the cleanup

[verified-by-code `combocid.c:182`]

```c
void
AtEOXact_ComboCid(void)
```

Called at transaction commit/abort. Discards the entire
ComboCID hash table. The next transaction starts with a fresh
empty table; ComboCIDs allocated in transaction T1 are not
valid in T2.

## Why this works correctly

The genius of ComboCIDs: the flag matters ONLY for the
inserting transaction itself, because:

- **Other transactions** see a tuple's `xmin` or `xmax`
  belonging to some other XID; they consult the **clog** for
  commit/abort, NOT the cmin/cmax.
- **The inserting transaction itself** needs cmin/cmax to
  decide its own intra-transaction visibility ("did I delete
  this in command 3 before reading it in command 5?").
- After the inserting transaction commits, no one consults
  cmin/cmax — visibility resolves entirely through xmin/xmax
  + clog.

So storing the ComboCID table backend-locally is safe; no
one else needs to interpret the synthetic ID.

## Common visibility scenarios

| Scenario | t_cid stores | HEAP_COMBOCID |
|---|---|---|
| Tuple inserted, never modified | cmin | unset |
| Tuple inserted, deleted in same xact, both in t_cid | synthetic ID → (cmin, cmax) | SET |
| Tuple inserted by xact A, deleted by xact B | cmax (cmin lost) | unset |
| Tuple INSERTed and never read by inserter | cmin (no cmax allocated) | unset |

The "inserted by A, deleted by B" case loses cmin — but A's
cmin is irrelevant to B's visibility check (B sees xmin =
committed by clog) and to A's (A already committed). So the
loss is OK.

## The HeapTupleHeaderSetCmin / SetCmax inlines

[verified-by-code `htup_details.h:417-429`]

```c
HeapTupleHeaderSetCmin(tup, cid):
    tup->t_cid = cid;
    tup->t_infomask &= ~HEAP_COMBOCID;

HeapTupleHeaderSetCmax(tup, cid, isCombo):
    tup->t_cid = cid;
    if (isCombo)
        tup->t_infomask |=  HEAP_COMBOCID;
    else
        tup->t_infomask &= ~HEAP_COMBOCID;
```

The setter for cmax takes an `isCombo` flag because the caller
must have already gone through `GetComboCommandId` to allocate
the synthetic ID; SetCmax just stamps the result.

## Common review-time concerns

- **Don't read `t_cid` directly.** Always go through
  `HeapTupleHeaderGetCmin` / `Cmax` — they handle the
  ComboCID indirection.
- **Don't compare two tuples' `t_cid` for equality** to
  decide "same insert" — one may be a ComboCID, the other not.
- **ComboCID table lives in backend memory** — long-running
  transactions with many self-modifications can grow the
  table. Not commonly a problem.
- **Code that walks tuples cross-process** (logical replication
  decoding, FDW push-down) doesn't have access to the original
  backend's ComboCID table — these paths use snapshot-based
  visibility, not cmin/cmax.

## Invariants

- **[INV-1]** `HEAP_COMBOCID` set ⇒ `t_cid` is a synthetic
  ID; clear ⇒ `t_cid` is the raw cmin or cmax.
- **[INV-2]** ComboCID table is per-backend; synthetic IDs
  meaningful only within the issuing backend's current xact.
- **[INV-3]** `AtEOXact_ComboCid` discards the table at
  commit/abort.
- **[INV-4]** Always use `HeapTupleHeaderGetCmin/Cmax`
  inlines, not direct `t_cid` access.
- **[INV-5]** ComboCIDs only matter for intra-transaction
  visibility; inter-transaction visibility uses xmin/xmax
  + clog.

## Useful greps

- ComboCID consumers:
  `grep -RIn 'GetComboCommandId\|HEAP_COMBOCID\|HeapTupleHeaderGetCmin\|HeapTupleHeaderGetCmax' source/src/backend | head -20`
- The allocation site:
  `grep -n 'GetComboCommandId' source/src/backend/utils/time/combocid.c`
- The cleanup hook:
  `grep -n 'AtEOXact_ComboCid' source/src/backend`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/time/combocid.c`](../files/src/backend/utils/time/combocid.c.md) | — | implementation |
| [`src/include/access/htup_details.h`](../files/src/include/access/htup_details.h.md) | 195 | HEAP_COMBOCID flag |
| [`src/include/access/htup_details.h`](../files/src/include/access/htup_details.h.md) | — | HEAP_COMBOCID flag + decoder inlines |
| [`src/include/utils/combocid.h`](../files/src/include/utils/combocid.h.md) | — | public API |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/data-structures/heap-tuple-layout.md` — tuple
  layout; `t_cid` is one of the header fields.
- `knowledge/idioms/heaptuple-update-chain.md` — chain walk
  consumers of cmin/cmax visibility.
- `knowledge/idioms/snapshot-acquisition.md` — snapshot
  semantics; ComboCIDs are orthogonal (intra-xact only).
- `knowledge/subsystems/access-heap.md` — heap layout +
  visibility decisions.
- `source/src/backend/utils/time/combocid.c` —
  implementation.
- `source/src/include/utils/combocid.h` — public API.
- `source/src/include/access/htup_details.h` —
  `HEAP_COMBOCID` flag + decoder inlines.
