# operatorcmds.c

- **Source path:** `source/src/backend/commands/operatorcmds.c`
- **Lines:** 734
- **Last verified commit:** `ef6a95c7c64`

## Purpose

CREATE / DROP / ALTER OPERATOR — registers operators as pg_operator rows pointing to their implementing function (pg_proc). [from-comment, operatorcmds.c:3-5]

## Public surface

- `DefineOperator` — validate options (`FUNCTION` is mandatory, `LEFTARG`/`RIGHTARG` define unary vs binary, `COMMUTATOR`/`NEGATOR`/`RESTRICT`/`JOIN`/`HASHES`/`MERGES` are optional), then call `OperatorCreate` (in catalog/pg_operator.c). Owner is current user.
- `RemoveOperatorById`, `AlterOperator`, `AlterOperatorOwner_internal` — standard mutators.

## Quirk: commutator/negator self-references

If you say `COMMUTATOR = ===` for the operator you're currently defining (commutator-of-self), CreateOperator must first record a "shell" pg_operator entry, then complete the definition, then fix up the commutator link. Documented in operatorcmds.c around `DefineOperator`.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`
