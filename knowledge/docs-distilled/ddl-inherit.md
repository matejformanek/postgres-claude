---
source_url: https://www.postgresql.org/docs/current/ddl-inherit.html
fetched_at: 2026-07-11T19:54:35Z
anchor_sha: 54cd6fc83176d7c03abf95554aef26b0b24acc7d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "5.11 Inheritance"
---

# Docs distilled — Table Inheritance (ddl-inherit)

The older parent/child table mechanism. A query on a parent implicitly appends
its descendants; the planner expands it via the same `inherit.c` machinery that
declarative partitioning reuses. The load-bearing internals fact: **inheritance
does NOT propagate unique/PK/FK constraints or indexes to children** — the gap
that declarative partitioning was built to close.

## Non-obvious claims

- **Querying a parent is expanded into an append over parent + all
  descendants.** "a query can reference either all rows of a table or all rows
  of a table plus all of its descendant tables. The latter behavior is the
  default." The optimizer does this in `expand_inherited_rtentry`, the same
  entry point partitioning's `expand_partitioned_rtentry` sits beside.
  [from-docs] + [verified-by-code]
  `src/backend/optimizer/util/inherit.c:88` (`expand_inherited_rtentry`), `:320`
  (`expand_partitioned_rtentry`).
- **`ONLY` suppresses descendant expansion; trailing `*` forces it** (the `*` is
  redundant now that inclusion is default, kept for back-compat).
  `SELECT … FROM ONLY cities` scans only the named table. [from-docs]
- **`tableoid` is the only per-row signal of origin** in an inherited query —
  join `tableoid::regclass` to see whether a row came from the parent or a
  specific child. [from-docs]
- **The serious limitation: indexes and unique/FK constraints apply to single
  tables only.** "indexes (including unique constraints) and foreign key
  constraints only apply to single tables, not to their inheritance children."
  A `UNIQUE`/`PRIMARY KEY` on the parent does *not* stop a child from holding a
  duplicate; an FK on the parent does not cover children; and an FK *referencing*
  the parent accepts only the parent's own rows — "There is no good workaround
  for this case." This is the exact gap declarative partitioning closes.
  [from-docs]
- **CHECK and NOT NULL *are* inherited automatically** (unless `NO INHERIT`);
  other constraint types are not. When a column is inherited from multiple
  sources the definitions are *merged*, and the merged column is NOT NULL if any
  contributing definition is NOT NULL. [from-docs]
- **INSERT/COPY never route to children.** "Inheritance does not automatically
  propagate data from `INSERT` or `COPY` commands to other tables in the
  inheritance hierarchy." An INSERT hits exactly the named table — the
  fundamental behavioral split from partitioning's tuple routing. [from-docs]
- **Permission checks are done on the parent only for inherited access.**
  Granting `UPDATE` on `cities` implies permission to update `capitals` rows
  *when reached through* `cities`; direct access to the child still needs its
  own grants. Parent row-security policies apply to child rows in inherited
  queries; child policies apply only when the child is named directly.
  [from-docs]
- **`ALTER TABLE` propagates column-definition and CHECK-constraint changes down
  the hierarchy**; dropping a column other tables depend on needs `CASCADE`.
  [from-docs]
- **Declarative partitioning is the recommended successor.** "Some functionality
  not implemented for inheritance hierarchies is implemented for declarative
  partitioning." Partitioning is layered on the inheritance expansion machinery
  but adds tuple routing, spanning indexes/constraints, and bound-based pruning.
  [from-docs] + [inferred] from the shared `inherit.c` expansion path.

## Links into corpus

- [[knowledge/files/src/backend/optimizer/util/inherit.c.md]] — the shared
  append-expansion path (`expand_inherited_rtentry` /
  `expand_partitioned_rtentry`).
- [[knowledge/subsystems/optimizer.md]] — inheritance/appendrel expansion +
  constraint exclusion.
- [[knowledge/docs-distilled/ddl-partitioning.md]] — the successor mechanism
  that fixes the constraint/index gap.
- [[knowledge/docs-distilled/ddl-system-columns.md]] — `tableoid`, the per-row
  origin discriminator.
- [[knowledge/docs-distilled/explicit-joins.md]] —
  `from_collapse_limit`/`join_collapse_limit` interplay when appendrels are
  flattened into a join problem.
