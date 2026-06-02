# Proposed SKILL.md improvements (NOT applied)

## 1. Add explicit "the next free ID" hint in §2.2

The skill currently says "add a PG_LWLOCK(id, name) entry in src/include/storage/lwlocklist.h". A first-time reader doesn't know that IDs are append-only and that retired numbers stay reserved. Suggest expanding to:

> add a `PG_LWLOCK(id, name)` entry **at the end** of `src/include/storage/lwlocklist.h` (the file's header comment lines 22-32 says "add at the end to avoid renumbering" — DTrace and external scripts key on the IDs). Reserve a new ID one past the current last entry; never reuse a retired number.

## 2. Add a sub-bullet to §2.3 explicitly calling out the heavyweight-lock no-op trap

Current text in §2.3 says "locks within a lock group don't conflict (except RELATION_EXTEND)". This is correct but easy to miss because it's the last bullet in the section. Suggest promoting to its own paragraph:

> **Trap**: an advisory or any other heavyweight lock used to serialize between a parallel leader and its workers will silently no-op. The conflict check in `lock.c:1610-1618` subtracts out same-group holders. Only `LOCKTAG_RELATION_EXTEND` still conflicts within a group (`lock.c:1600-1608`). Use an LWLock instead.

## 3. Add a smell-test entry for "expensive call under ProcArrayLock / similarly-hot LWLock"

§5 currently has "I'm holding an LWLock and calling something that does I/O — fine for correctness, bad for throughput." This understates the case for *contended* LWLocks. Suggest adding:

> "I'm calling `SearchSysCache*` / `RelationOpen` / `index_open` / anything that may take a heavyweight lock or BufMapping partition lock, while holding ProcArrayLock / WALInsert / a buffer content lock" → this is a **lock-ordering bug**, not just a throughput concern. The inner call can take locks that other paths take *before* the outer lock — silent LWLock deadlock. Hoist the call out of the critical section.

## 4. Add a one-line pointer to the three named-lock patterns

In §2.2 right after "Decide the lock's home", the three options (PG_LWLOCK, PG_LWLOCKTRANCHE, RequestNamedLWLockTranche) are listed parenthetically. Suggest a tiny decision table:

| You are | Pattern |
|---|---|
| Core code, single lock | `PG_LWLOCK` in `lwlocklist.h` + update `wait_event_names.txt` |
| Core code, partitioned array | `PG_LWLOCKTRANCHE` + `wait_event_names.txt` |
| Extension preloaded at startup | `RequestNamedLWLockTranche()` from `_PG_init` |
| Lock storage inside a DSM | `LWLockNewTrancheId()` + `LWLockInitialize()` + each attacher calls `LWLockRegisterTranche()` |

This last row (DSM-resident) is currently missing from the skill entirely and is the right answer for the iter-2 eval-1 parallel-aggregate case.

## Priority

- (4) DSM-resident-LWLock pattern is a real gap; recommend adding.
- (2) heavyweight-lock no-op trap deserves promotion — it's the kind of "confidently wrong" failure mode the project plan flags as the headline risk.
- (1) and (3) are nice-to-have polish.
