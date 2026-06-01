# lockcmds.c

- **Source path:** `source/src/backend/commands/lockcmds.c`
- **Lines:** 299
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"LOCK command support code." [from-comment, lockcmds.c:3-4] The SQL `LOCK TABLE name IN mode MODE [NOWAIT]` statement.

## Public surface

- `LockTableCommand` — top-level entry.
- `LockTableRecurse` — recurse into inheritance/partition children, taking the requested lock on each. The recursion uses `find_inheritance_children` (not `find_all_inheritors`) at each level so we can release the parent's lock if a child fails.
- `LockTableAclCheck` — permission check. A LOCK requires either USAGE+SELECT-on-table for low modes, or full update privileges for AccessExclusive — encoded in this function.
- `RangeVarCallbackForLockTable` — name-resolution callback used so we hold the right lock through name lookup.
- `LockViewRecurse` — LOCK TABLE on a view locks all the base tables the view reads; this recursion uses `ancestor_views` to detect view cycles (which the rewriter already forbids but defence-in-depth).

## NOWAIT vs wait

`LOCK ... NOWAIT` calls `ConditionalLockRelationOid`; on conflict it errors immediately. Without NOWAIT it calls `LockRelationOid` which blocks until grant or deadlock.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`
