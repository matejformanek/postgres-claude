# pg_constraint.c

- **Source path:** `source/src/backend/catalog/pg_constraint.c`
- **Lines:** ~1 800
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `catalog/pg_constraint.h` (with the Form_pg_constraint struct), `commands/tablecmds.c` (DDL drivers), `catalog/heap.c` (StoreRelCheck/StoreRelNotNull insert via CreateConstraintEntry).

## Purpose

Low-level catalog access for pg_constraint — the catalog that stores CHECK, NOT NULL, UNIQUE, PRIMARY KEY, FOREIGN KEY, and EXCLUDE constraints in a single row format. Provides `CreateConstraintEntry` (the universal inserter), name-management helpers, accessors for FK metadata, and the operator/element lookup helpers for FK PERIOD support.

## Public surface

- `CreateConstraintEntry` (51) — **the universal pg_constraint inserter.** Takes 30+ parameters: name, namespace, conrelid, contypid (for domain constraints), conindid (for U/PK/EXCL), confrelid (FK referenced), confkey/conkey (column attnums), CHECK expr tree, etc. Returns the new constraint OID. Records dependencies: NORMAL on referenced columns/types, AUTO on the heap (for table constraints) or domain (for domain constraints), INTERNAL on the index for U/PK. [verified-by-code, pg_constraint.c:51-411]
- `ConstraintNameIsUsed` (412), `ConstraintNameExists` (457), `ChooseConstraintName` (513) — name conflict / auto-naming. ChooseConstraintName produces names like `t1_a_key`, `t1_check`, with numeric suffixes when needed.
- `findNotNullConstraintAttnum` (592), `findNotNullConstraint` (642), `findDomainNotNullConstraint` (658), `extractNotNullColumn` (702), `AdjustNotNullInheritance` (742), `RelationGetNotNullConstraints` (834) — the NOT-NULL-as-pg_constraint-row machinery (PG 17+: NOT NULL has its own pg_constraint rows with `contype='n'`).
- `RemoveConstraintById` (912) — drop one constraint; cascades to the underlying index if INTERNAL.
- `RenameConstraintById` (1005) — for ALTER ... RENAME CONSTRAINT.
- `AlterConstraintNamespaces` (1057) — move constraints to a new schema when their table moves.
- `ConstraintSetParentConstraint` (1126) — link a child partition's constraint to its parent partitioned-table's constraint (partitioned PK/U inheritance).
- `get_relation_constraint_oid` (1200), `get_relation_constraint_attnos` (1257), `get_relation_idx_constraint_oid` (1346), `get_domain_constraint_oid` (1393), `get_primary_key_attnos` (1452) — lookups.
- `DeconstructFkConstraintRow` (1538) — unpack conkey/confkey/conpfeqop/conppeqop/conffeqop arrays into C arrays — used everywhere FK metadata is needed.
- `FindFKPeriodOpers` (1668) — find the range-overlap operator for temporal (PERIOD) foreign keys.
- `check_functional_grouping` (1742) — supports the relaxed GROUP BY rule: "if you grouped by the PK, you can SELECT any other column".

## Confidence tag tally

`[verified-by-code]=4 [inferred]=1`
