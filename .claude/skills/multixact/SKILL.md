---
name: multixact
description: PostgreSQL's MultiXact machinery — `src/backend/access/transam/multixact.c` — the multi-transaction ID system that lets a single heap tuple record multiple concurrent lockers (for `SELECT ... FOR SHARE` and `SELECT ... FOR UPDATE` blends) plus the multixact-freeze / wraparound path. Loads when the user asks about MultiXactId semantics, `xmax` interpretation with the `HEAP_XMAX_IS_MULTI` bit, why a tuple can appear to be locked by multiple transactions, tuple-locking modes (`FOR SHARE` / `FOR NO KEY UPDATE` / `FOR KEY SHARE`), the multixact SLRU (`pg_multixact/`), MultiXact member offsets, or the `autovacuum_multixact_freeze_max_age` wraparound path. Skip when the ask is about clog (regular transaction commit status — sibling but different code) or 2PC prepared transactions.
when_to_load: Investigate MultiXact-related bugs (wraparound, SLRU exhaustion); understand tuple-locking semantics; touch heap_lock_tuple / heap_lock_updated_tuple; audit tuple visibility with HEAP_XMAX_IS_MULTI set.
companion_skills:
  - locking
  - vacuum-autovacuum
  - access-method-apis
---

# multixact — multi-transaction IDs for tuple locking

Every heap tuple has an `xmax` field. In the simple case, `xmax` is the XID of a transaction that either deleted or exclusively locked the tuple. But PG supports **multiple concurrent lockers** on the same tuple (row-level shared locks + key-share locks + non-blocking-with-updates), which requires representing "this tuple is currently locked by transactions A, B, and C" in a fixed-size field.

The solution: when a tuple has multiple lockers, `xmax` holds a **MultiXactId** and the `HEAP_XMAX_IS_MULTI` infomask bit is set. The MultiXact ID is a handle into a separate lookup table (`pg_multixact/`) that maps to the set of member XIDs + their per-member lock strength.

## The file map

| File | Lines | Role |
|---|---:|---|
| `access/transam/multixact.c` | 95K | **The single file for all things MultiXact.** SLRU management, ID allocation, member lookup, freezing, wraparound. |
| `access/transam/subtrans.c` | 13K | Not multixact but often confused — subtransaction xid → parent xid mapping. Same SLRU pattern, different purpose. |
| `access/transam/clog.c` | 37K | Also not multixact but often confused — regular transaction commit status. Same SLRU pattern, different purpose. |

MultiXact lives on-disk in **two SLRU segments**:

- `pg_multixact/offsets/` — one entry per MultiXactId, giving the offset into `members/` for that multixact's member list.
- `pg_multixact/members/` — variable-length arrays; each entry is `(xid, TransactionId) + status (5 bits for lock strength)`.

## The 4 tuple-locking modes

Row-level locks come in 4 strengths (from `heap_lock_tuple` in `access/heap/heapam.c`):

| Mode | SQL | Blocks other |
|---|---|---|
| **`FOR KEY SHARE`** | `SELECT ... FOR KEY SHARE` | Only KEY UPDATE and stronger |
| **`FOR SHARE`** | `SELECT ... FOR SHARE` | UPDATE + KEY UPDATE + DELETE + stronger |
| **`FOR NO KEY UPDATE`** | `SELECT ... FOR NO KEY UPDATE` | Any UPDATE / DELETE / stronger |
| **`FOR UPDATE`** | `SELECT ... FOR UPDATE` | Everything |

Foreign-key checks use `FOR KEY SHARE` — the weakest lock that still blocks the parent-row's KEY UPDATE. This is why PG can have a table with FK to another table under contention without every INSERT into the child fighting for row-level exclusive locks.

## When xmax becomes a MultiXact

- Base case: `heap_lock_tuple` on a currently-unlocked tuple sets `xmax = current_xid`, `HEAP_XMAX_LOCK_ONLY = true`, appropriate KEYSHR/SHR bits.
- On a tuple ALREADY locked: promotes to MultiXact. Creates a new multixact containing `{old xmax, new_xid}` with their respective strengths. Sets `xmax = new_multixactid`, `HEAP_XMAX_IS_MULTI = true`.
- On a MultiXact already: allocates a new multixact adding the new locker to the existing members.
- Waking up: when a locker's transaction commits/aborts, subsequent readers computing "who really still holds this?" walk the multixact members and skip finished ones.

## Reading a locked tuple

`GetMultiXactIdMembers(mxid, &members)` — returns the list of `(xid, status)` tuples. Filter out ones whose xid is `TransactionIdDidCommit` (past) or `TransactionIdDidAbort` (past) to see actual current lockers.

The infomask bits tell you at a glance without dereferencing the multixact:

- `HEAP_XMAX_IS_MULTI` — xmax is a MultiXactId, not an XID.
- `HEAP_XMAX_LOCK_ONLY` — this is a lock, not a delete.
- `HEAP_XMAX_KEYSHR_LOCK` / `HEAP_XMAX_SHR_LOCK` / `HEAP_XMAX_EXCL_LOCK` — strength (or dominant strength if multi).
- `HEAP_XMAX_COMMITTED` / `HEAP_XMAX_INVALID` — hint bits.

## Freeze + wraparound

MultiXactIds wrap around, just like XIDs. Two horizons matter:

- `oldestMultiXactId` — must-be-preserved. Below this, all multixacts are frozen or the file is gone.
- `nextMultiXactId` — allocation cursor.

Freezing (in `heap_prepare_freeze_tuple`):

- If a tuple's xmax is a multixact and all members are committed/aborted (i.e. no live lockers), the xmax can be simplified: either replaced with the winning updater's XID (if any updated) or cleared entirely (all were lockers who released).
- If the multixact is old enough (`vacuum_multixact_freeze_min_age`), we DO simplify.
- If dangerously old (`autovacuum_multixact_freeze_max_age`), we MUST simplify — wraparound autovacuum fires unconditionally.

## The two SLRU sizes matter

- `pg_multixact/offsets/` — 4 bytes per multixact. On a 2-billion-multixact system, that's 8 GB.
- `pg_multixact/members/` — 5 bytes per (xid+status). If avg multixact has 3 members, that's 30 GB at 2 billion multixacts.

This is why "multixact exhaustion" bugs are severe: consuming multixacts faster than autovacuum can freeze them fills the SLRU. Symptoms: "database is not accepting commands to avoid wraparound data loss" errors.

## Common patch shapes

### Debug "database is not accepting commands to avoid multixact wraparound"

- `SELECT relname, mxid_age(relminmxid) FROM pg_class WHERE relminmxid <> 0 ORDER BY 2 DESC LIMIT 20;` — find tables with old multixact horizons.
- Run VACUUM FREEZE on the top offenders.
- If autovacuum isn't keeping up: increase `autovacuum_multixact_freeze_max_age` (temporary bandaid; increase autovacuum aggression instead).
- Long-term: identify the workload creating multixacts faster than expected (usually heavy foreign-key checks + concurrent updates on the referenced table).

### Change tuple-locking behavior

Very rare and dangerous. Would touch `access/heap/heapam.c` `heap_lock_tuple` + all callers reading `HEAP_XMAX_IS_MULTI`. Every existing PG version must interpret the tuple correctly, so backward-compat is critical.

### Add a new lock strength

Doesn't scale — infomask bits are precious. Historically this required a catalog version bump AND on-disk format bump. Not attempted since the initial 4-mode design.

## Pitfalls

- **`xmax` interpretation always requires the infomask** — never treat xmax as an XID without checking `HEAP_XMAX_IS_MULTI` first. Getting this wrong = silent visibility bugs.
- **MultiXact SLRU pressure is invisible via basic monitoring** — need to monitor `pg_stat_slru` (in pgstat-framework) for `multixact_offsets` and `multixact_members`.
- **`FOR KEY SHARE` blocks FEWER things than `FOR SHARE`** — the FK-check optimization. Applications sometimes use FOR SHARE thinking it's the "gentlest" lock; FOR KEY SHARE is gentler.
- **HOT chain interaction** — updates in a HOT chain share the same key. If a row is currently multixact-locked and someone does a NON-HOT update, the multixact is "inherited" by the new tuple version. Complexity here is hidden in `heap_update`.
- **`heap_prepare_freeze_tuple` may create a NEW multixact** — if a multixact has some live members and some dead, the freeze may replace it with a smaller multixact containing only the live members. This is why FREEZE can PRODUCE multixacts, not just consume them.
- **`autovacuum_multixact_freeze_max_age` is separate from XID freeze_max_age** — you can have XIDs freshly frozen while multixacts are old. Both need monitoring.
- **`SELECT ... FOR UPDATE OF t` vs `SELECT ... FOR UPDATE OF u` in same query** — different tables, potentially different lock strengths per-row per-table. `RowMarkClause` in `parsenodes.h` carries the per-table info.
- **Prepared transactions retain MultiXact memberships** — a 2PC prepared but not committed transaction is a live multixact member. Long-lived prepared txns delay freezing.

## Related corpus

- **Idioms** (subset relevant): `heap-tuple-freeze` (multixact simplification during freeze), `heaptuple-update-chain` (HOT interaction), `heap-tuple-visibility-mvcc` (xmax interpretation with infomask), `hint-bits-setbufferdirty` (HEAP_XMAX_COMMITTED / INVALID hint bits), `tuple-locking-modes`.
- **Subsystems**: `access-heap` (all heap_lock_tuple callers), `access-transam` (SLRU management, xact.c), `vacuum-autovacuum` (freeze coordination).
- **Data structures**: `heap-tuple-layout` (xmax field), `pgproc-fields` (per-backend state used by lock waits).
- **README**: `source/src/backend/access/heap/README.tuplock` — the definitive multixact + tuple-locking design doc. Shorter than this skill, worth reading before deep work.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/access/transam/multixact.c
python3 scripts/corpus-chain.py --idiom heap-tuple-freeze
python3 scripts/corpus-chain.py --idiom tuple-locking-modes
```

Third surfaces the tuple-locking semantics + strengths.

## Boundary

**Use this skill** for MultiXact + tuple-locking-modes + related freeze work.

**Don't use** for:
- **CLOG (`pg_xact/`)** — regular transaction commit status. Sibling SLRU, different code path (`access/transam/clog.c`).
- **Subtrans (`pg_subtrans/`)** — subtransaction parent mapping. Sibling SLRU, different code path (`access/transam/subtrans.c`).
- **`pg_serial`** — SSI serializable-isolation ordering. Different SLRU.
- **Advisory locks** — `pg_advisory_lock` — that's session/transaction-level, not tuple-level. Lives in `storage/lmgr/lock.c`.
- **Heavyweight relation locks** — that's the `LOCK TABLE` semantic, different `lmgr` code.
