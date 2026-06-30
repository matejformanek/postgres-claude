# tablecmds.c

- **Source path:** `source/src/backend/commands/tablecmds.c`
- **Lines:** 24131 (the largest single file in the backend after the parser)
- **Last verified commit:** pinned `02f699c14163`, re-verified + re-pinned 2026-06-30 by pg-quality-auditor AUDIT mode after anchor-bump `4abf411e2328..02f699c14163` (triggering commits: 0cd17fdd3c00 "Prevent inherited CHECK constraints from being weakened", Andrew Dunstan + cdae794af31b "Take into account default_tablespace during MERGE/SPLIT PARTITION(S)", Alexander Korotkov — entry points shifted +7). Previously `9a60f295bcb1`.
- **Companion files:** `tablecmds.h`, `catalog/heap.c` (low-level catalog munging), `catalog/index.c`, `catalog/partition.c`, `commands/typecmds.c` (composite-type recursion), `commands/trigger.c`, `commands/repack.c` (rewrite mechanics), `commands/event_trigger.c` (start/end hooks).

## Purpose

Implements `CREATE TABLE`, `DROP TABLE`, `TRUNCATE`, **and the entire ALTER TABLE machinery**, including inheritance/partition recursion, constraint addition and validation, type changes that require a full table rewrite, ATTACH/DETACH/MERGE/SPLIT PARTITION, FK enforcement transitions, and replica-identity bookkeeping. Top-of-file comment: "Commands for creating and altering table structures and settings." [from-comment, tablecmds.c:3-5]

## Top-level entry points (line cites)

- `DefineRelation` (817) — CREATE TABLE / CREATE FOREIGN TABLE; called also from `CREATE TABLE AS`, partition-creation, and `SELECT INTO`. Calls `heap_create_with_catalog`, then loops over per-relkind setup (toast, indexes, constraints).
- `RemoveRelations` (1596) — DROP TABLE/VIEW/etc.; uses `RangeVarCallbackForDropRelation` to do permission/relkind checks under the namespace lock.
- `ExecuteTruncate` (1923) / `ExecuteTruncateGuts` (2047) — TRUNCATE, including foreign-table dispatch via `ForeignTruncateInfo` and per-server batching.
- `renameatt` (4073), `RenameConstraint` (4220), `RenameRelation` (4270), `RenameRelationInternal` (4334) — name changes with inheritance recursion.
- `AlterTable` (4598) / `AlterTableInternal` (4627) — public entry points; AlterTableInternal is the internal-recursion form (skips parse-side checks).
- `AlterTableGetLockLevel` (4672) — **the lock-level computation that scans the cmd list and returns the maximum required LOCKMODE**. Many subcommands return `ShareUpdateExclusiveLock` to allow concurrent reads; rewrites and type-changes return `AccessExclusiveLock`. [verified-by-code, tablecmds.c:4672-4930]
- `ATController` (4939) — **The three-phase top-level driver.**
- `ATPrepCmd` (4974), `ATRewriteCatalogs` (5377), `ATExecCmd` (5451), `ATRewriteTables` (5929), `ATRewriteTable` (6218) — the phase implementations.

## The three-phase ALTER TABLE model [load-bearing]

`ATController` runs exactly three phases (comments at tablecmds.c:4932-4962): [verified-by-code]

1. **Phase 1 — Prep / build work queue.** `ATPrepCmd` walks each `AlterTableCmd`, does permission and parse-time-only checks, and creates/extends an `AlteredTableInfo` (the per-relation "wqueue entry"). Inheritance / partition recursion happens here via `ATSimpleRecursion` / `ATTypedTableRecursion`. The wqueue accumulates child relations and the cmd list per relation. Relation is then closed *but the lock is held* to commit.
2. **Phase 2 — Catalog rewrites.** `ATRewriteCatalogs` opens each queued relation, then runs `ATExecCmd` for every command for that relation. **Multiple passes** over the wqueue happen here (driven by `AlterTablePass cur_pass`): drops first, then adds, then constraint validation queueing, so e.g. a DROP COLUMN can free a name an ADD COLUMN later reuses, and an ADD CONSTRAINT happens after the column it references has been added. [verified-by-code, tablecmds.c:5377-5445]
3. **Phase 3 — Table scan / rewrite + after-statements.** `ATRewriteTables` decides per-relation whether (a) the table must be **rewritten** (`newrelpersistence` change, type-change that's not binary-compatible, AT_SetAccessMethod, etc. — `tab->rewrite != 0`), or (b) only **validated** by a scan (new CHECK/NOT NULL/FK constraints), or (c) nothing on-disk needed. If rewrite: a new transient relation is made via `make_new_heap` (in repack.c), tuples are copied with column transformations applied (`NewColumnValue` exprstates), constraints checked inline, and `finish_heap_swap` swaps relfilenodes. If validate-only: `ATRewriteTable` does a heap scan executing only the queued `NewConstraint` expressions.

The `AlteredTableInfo` struct (tablecmds.c:172) carries the per-relation state across the three phases: `rewrite` bitmask, `newvals` (List of `NewColumnValue`), `constraints` (List of `NewConstraint`), `changedConstraintOids`/`Defs` and `changedIndexOids`/`Defs` (for rebuild after ALTER TYPE), `chgPersistence`, `clusterOnIndex`, `replicaIdentityIndex`. [verified-by-code, tablecmds.c:172-214]

## Rewrite-vs-validate decision

Set in the per-subcommand `ATPrep*` and `ATExec*` functions. The most common rewrite triggers:

- `AT_AlterColumnType` (non-binary-compatible) — adds a `NewColumnValue` and sets `tab->rewrite |= AT_REWRITE_COLUMN_REWRITE`.
- `AT_AddColumn` with a volatile DEFAULT or stored generated expression.
- `AT_SetTableSpace`, `AT_SetAccessMethod`, `AT_SetLogged/AT_SetUnLogged` — set `tab->rewrite |= AT_REWRITE_ALTER_PERSISTENCE` and force a heap copy.
- Adding a stored generated column.

Validate-only triggers (no rewrite, just a scan checking new predicates per tuple): `AT_AddConstraint` for CHECK/NOT NULL/FK (queued via `QueueCheckConstraintValidation` / `QueueNNConstraintValidation` / `QueueFKConstraintValidation`, prototypes at lines 478-483), `AT_ValidateConstraint` for previously-NOT-VALID constraints. The actual per-row check happens in `ATRewriteTable` (line 6218). [verified-by-code]

**ADD COLUMN with a constant DEFAULT** is special: since PG 11 it does NOT rewrite — `pg_attribute.atthasmissing`/`attmissingval` stores the default and the executor synthesises it for old rows. See `StoreAttrMissingVal` in `catalog/heap.c`. [from-comment, tablecmds.c around ATExecAddColumn]

## Lock-level computation [HIGH-RISK SECTION]

`AlterTableGetLockLevel` is the single source of truth for what lock ALTER TABLE takes. Lock is the **max** over all subcommands. Highlights from tablecmds.c:4672-4930: [verified-by-code]

- Default is `AccessExclusiveLock`.
- `AT_SetStatistics`, `AT_ClusterOn`, `AT_DropCluster`, `AT_SetOptions`, `AT_ResetOptions`, `AT_ValidateConstraint`, `AT_AttachPartition`, `AT_DetachPartitionFinalize`, `AT_AddIndex` (CIC variant) → `ShareUpdateExclusiveLock`.
- `AT_AddConstraint CONSTR_FOREIGN` → `ShareRowExclusiveLock` (so we can add triggers to both tables but still permit reads).
- `AT_DetachPartition` non-concurrent → `AccessExclusiveLock`; **concurrent variant** → `ShareUpdateExclusiveLock`. The concurrent path uses a two-step state machine with `AT_DetachPartitionFinalize` as the second step.
- `AT_AddInherit`/`AT_DropInherit` → `AccessExclusiveLock` (tuple-descriptor change semantics).

This computation must be conservative — if it underestimates, deadlocks or torn-state visibility result. Every subcommand has a case here. [verified-by-code]

## Inheritance / partition recursion model

- `ATSimpleRecursion` (6913) is the canonical helper: walks `find_all_inheritors(relid, lockmode, NULL)`, then for each child calls `ATPrepCmd` with `recurse=false, recursing=true`. Children get their own `AlteredTableInfo` in the wqueue.
- Partitioned tables have stricter rules: `ATCheckPartitionsNotInUse` (6958) for changes that would break partition-routing during concurrent inserts; ADD COLUMN must propagate to all partitions atomically.
- `ATTypedTableRecursion` (6988) handles typed tables (`OF type`) so that an ALTER TYPE on the composite type propagates to all tables of that type.
- `MergeAttributes` (2611), `MergeChildAttribute` (3310), `MergeInheritedAttribute` (3480), `MergeCheckConstraint` (3231), `MergeAttributesIntoExisting` (17971), `MergeConstraintsIntoExisting` (18109) — these glue CREATE TABLE inheritance together: column types/collations from multiple parents must be compatible; CHECK constraints with the same name must merge consistently.

## Foreign-key state machine

FKs are stored as `pg_constraint` rows with a paired trigger pair (one on each side). FK lifecycle subcommands:

- `ATAddForeignKeyConstraint` (def 606; call site 9928) — creates the constraint, calls `CreateFKTriggers`, queues a `QueueFKConstraintValidation` (which runs in Phase 3 unless `NOT VALID`).
- `ATExecAlterFKConstrEnforceability` (prototype 429; def 12512) — transition between ENFORCED and NOT ENFORCED; if becoming ENFORCED, requeues validation.
- `ATExecAlterConstrDeferrability` (prototype 442; def 13029), `ATExecAlterConstrInheritability` (prototype 446; def 13086) — deferrability and inheritability changes on existing constraints; recurse to all children.
- `validateForeignKeyConstraint` (prototype 500; def 14168) — the actual scan: a query "SELECT 1 FROM fkrel ft LEFT JOIN pkrel pt ON ... WHERE pt.pk IS NULL" using SPI, or a direct check loop for simple cases.

## Composite-type and typed-table interaction

`find_composite_type_dependencies` (7033) recurses down: if you change a composite type, every table that has a column of that type (or a typed table OF that type) must be checked/rewritten. This is what makes `ALTER TYPE ... ADD ATTRIBUTE` an `AccessExclusiveLock` global operation in practice.

## Tests

- `src/test/regress/sql/alter_table.sql` (~5000 lines of regression coverage — every subcommand)
- `src/test/regress/sql/inherit.sql`, `partition_aggregate.sql`, `partition_join.sql`, `partition_prune.sql`
- `src/test/regress/sql/foreign_key.sql`
- `src/test/isolation/specs/alter-table-*` for concurrent-DDL behaviour
- `src/test/regress/sql/identity.sql`, `generated_stored.sql`, `generated_virtual.sql`

## Open questions / unverified

- **Concurrent DETACH PARTITION** two-phase commit boundary: the exact catalog state visible to in-flight queries between the two transactions of a concurrent detach is documented inline but not deep-read. [unverified]
- The interplay between `AT_SetAccessMethod` and the in-place table rewrite (does the new AM's `relation_set_new_filelocator` callback run inside the same critical section as the heap swap?) — not traced. [unverified]
- The exact pass ordering enumeration (`AlterTablePass`) versus subcommand types is dense; a complete mapping was not built. [unverified]

## Confidence tag tally

`[verified-by-code]=10 [from-comment]=2 [unverified]=3`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
