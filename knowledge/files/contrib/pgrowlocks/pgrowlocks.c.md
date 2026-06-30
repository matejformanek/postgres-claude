# `pgrowlocks/pgrowlocks.c` — per-row lock introspection

**Verified against source pin `4b0bf0788b0`** (path: `source/contrib/pgrowlocks/pgrowlocks.c`)

## Role

Single SQL function `pgrowlocks(text)` that scans a heap relation under
the active snapshot and returns one row per tuple currently locked
(`HTSU == TM_BeingModified`), including the locking xids/multixacts,
lock modes, and PIDs.

## Public API

- `pgrowlocks(text) -> SETOF (tid, xmax, ismulti, xids, modes, pids)` — `source/contrib/pgrowlocks/pgrowlocks.c:68`

SQL gating: `REVOKE ALL FROM PUBLIC` is in `pgrowlocks--1.2.sql`
[verified-by-code grep above].

## Invariants

- Rejects partitioned tables ("partitioned tables do not contain rows"),
  non-relations, and non-heap AMs [verified-by-code]
  (`source/contrib/pgrowlocks/pgrowlocks.c:88-102`).
- Privilege gate: `ACL_SELECT` on the table OR `has_privs_of_role(...,
  ROLE_PG_STAT_SCAN_TABLES)` [verified-by-code]
  (`source/contrib/pgrowlocks/pgrowlocks.c:108-115`).
- Scan uses `GetActiveSnapshot()`, so visible tuples follow normal MVCC,
  but `HeapTupleSatisfiesUpdate` is checked under
  `BUFFER_LOCK_SHARE` [verified-by-code]
  (`source/contrib/pgrowlocks/pgrowlocks.c:118-136`).
- Buffer lock is released before building the tuplestore row to keep
  the lock window short [verified-by-code lines 265, 273].
- `GetMultiXactIdMembers` is called with `allow_old = HEAP_LOCKED_UPGRADED(infomask)`
  so locked-but-upgraded multixacts still resolve [verified-by-code
  line 160].

## Notable internals

- Mode strings produced via fixed `snprintf` into 32-byte buffers
  (`NCHARS=32`): `For Update`, `For No Key Update`, `For Share`, `For
  Key Share`, `transient upgrade status`.
- For multi-member multixacts, the function builds three `{a,b,c}`-style
  brace strings (xids/modes/pids) using `strcat` into per-array
  buffers sized `NCHARS * nmembers`. Each member contributes at most
  one numeric token plus a mode word (longest is "For No Key Update" =
  18 chars including null) — well within `NCHARS=32` per slot.
- The `nmembers == -1` case (multixact has gone away — transient upgrade
  status) emits the literal strings `{0}`, `{transient upgrade
  status}`, `{0}`
  (`source/contrib/pgrowlocks/pgrowlocks.c:162-167`).

## Trust-boundary / Phase D surface

1. **The function exposes `xmax`, lock modes, member PIDs.** This is
   data about ongoing transactions visible to a SELECT-privileged role,
   beyond what `pg_locks` shows (which is row-level locks not in
   `pg_locks` — they live in tuple infomask). Probably intended
   behavior, but it's a side channel into other backends' work.
   [ISSUE-defense-in-depth: pgrowlocks exposes per-tuple lock holder PIDs
   and modes to anyone with SELECT on the table — beyond pg_locks
   coverage of heavyweight locks. Useful, but worth knowing for
   monitoring-vs-attacker thread modeling (nit)]
   (`source/contrib/pgrowlocks/pgrowlocks.c:127-263`).
2. **No `CHECK_FOR_INTERRUPTS()` in the per-tuple loop.** Each iteration
   does `LockBuffer/UnlockBuffer` plus optionally a `GetMultiXactIdMembers`
   call, which can be expensive. A relation with millions of locked
   tuples will block cancellation between blocks.
   [ISSUE-correctness: per-tuple loop in pgrowlocks (lines 125-275) has
   no CHECK_FOR_INTERRUPTS; only the per-block heap_getnext-level
   interrupt window applies. Large relations make Ctrl-C slow (maybe)]
   (`source/contrib/pgrowlocks/pgrowlocks.c:125-275`).
3. **`values[Atnum_xids] = "{0}"`** at line 164 assigns a string literal
   to a buffer slot that downstream pfree might attempt? No — the
   `BuildTupleFromCStrings` path doesn't free the input strings, so a
   non-`palloc`'d literal is safe. But it's mixed-ownership in the
   `values[]` array (some palloc'd, some literal). [ISSUE-nit: mixed
   palloc'd / string-literal values in the values[] array; works
   because BuildTupleFromCStrings doesn't free its inputs (nit)]
   (`source/contrib/pgrowlocks/pgrowlocks.c:164-166`).
4. **`pg_stat_scan_tables` membership grants pgrowlocks even without
   ACL_SELECT** (line 111). `pg_stat_scan_tables` is intended for
   monitoring — its purview includes pgstattuple's heap-page-scanning
   functions. Extending that to a per-row lock dump is a reasonable
   interpretation but worth flagging. [ISSUE-defense-in-depth:
   pg_stat_scan_tables membership grants pgrowlocks read access
   beyond what ACL_SELECT would gate — consistent with pgstattuple
   policy (nit)] (`source/contrib/pgrowlocks/pgrowlocks.c:108-115`).
5. **The buffer-pin is held across the row build for the multixact
   case** (lines 132-265 — buffer locked at 132, unlocked at 265). The
   multixact path can call `GetMultiXactIdMembers` which can take
   MultiXact{Offset,Member}SLRULock under the buffer lock. Documented
   as safe by core, but it's the kind of ordering worth checking against
   `knowledge/idioms/locking.md`.
   [ISSUE-concurrency: buffer share-lock held across
   GetMultiXactIdMembers call; intended but creates a lock-ordering
   constraint between buffer lock and SLRU locks (maybe)]
   (`source/contrib/pgrowlocks/pgrowlocks.c:132-265`).

## Cross-refs

- `knowledge/subsystems/access-heap.md` — MultiXact infomask layout
- `knowledge/idioms/locking.md` — buffer lock + SLRU lock ordering
- `knowledge/files/contrib/pgstattuple/` — A12 pgstattuple, same pg_stat_scan_tables pattern
- `knowledge/files/contrib/pg_visibility/pg_visibility.c.md` — also reads heap pages bypassing MVCC

<!-- issues:auto:begin -->
- [Issue register — `pgrowlocks`](../../../issues/pgrowlocks.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-defense-in-depth: exposes per-tuple lock holder PIDs and modes; goes beyond pg_locks (nit)] — `source/contrib/pgrowlocks/pgrowlocks.c:127-263`
2. [ISSUE-correctness: no CHECK_FOR_INTERRUPTS in per-tuple loop; cancel responsiveness suffers on big relations (maybe)] — `source/contrib/pgrowlocks/pgrowlocks.c:125-275`
3. [ISSUE-nit: mixed palloc'd / string-literal pointers in values[] array (nit)] — `source/contrib/pgrowlocks/pgrowlocks.c:164-166`
4. [ISSUE-defense-in-depth: pg_stat_scan_tables grants beyond ACL_SELECT (nit)] — `source/contrib/pgrowlocks/pgrowlocks.c:108-115`
5. [ISSUE-concurrency: buffer share-lock held across GetMultiXactIdMembers; introduces buffer→SLRU lock-ordering constraint (maybe)] — `source/contrib/pgrowlocks/pgrowlocks.c:132-265`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgrowlocks.md](../../../subsystems/contrib-pgrowlocks.md)
