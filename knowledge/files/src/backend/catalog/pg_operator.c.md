# pg_operator.c

- **Source path:** `source/src/backend/catalog/pg_operator.c`
- **Lines:** ~920
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_operator relation." CREATE OPERATOR backend: defines the unary/binary operator, sets its commutator/negator links (possibly via shell-operator forward references), records dependencies on the implementing function and the argument types.

## Public surface

- `OperatorShellMake` — reserve OID+name when the operator is referenced before it's created (forward references in CREATE OPERATOR's COMMUTATOR/NEGATOR clauses).
- `OperatorCreate` — main entry. Writes the pg_operator row; updates the commutator/negator's row to point back at this one (the "shell + back-fill" dance).
- `makeOperatorDependencies` — dependency recording: NORMAL on left/right types, result type, the implementing function, namespace, owner.
- `OperatorUpd` — patch an existing row's commutator/negator fields.
- `get_other_operator` — lookup by (name, leftarg, rightarg, namespace).

## Confidence tag tally

`[inferred]=4`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
