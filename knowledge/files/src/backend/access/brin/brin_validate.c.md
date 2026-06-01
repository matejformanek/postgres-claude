# brin_validate.c

- **Source path:** `source/src/backend/access/brin/brin_validate.c` (273 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

`amvalidate` slot for BRIN: cross-checks `pg_amop` and `pg_amproc` entries for an opclass against BRIN's required-proc rules, called from `ALTER OPERATOR FAMILY` and `pg_amcheck`. [from-comment, brin_validate.c:1-12]

## What it checks

- Required procnums 1-4 (`opcInfo`, `addValue`, `consistent`, `union`) exist and have valid signatures.
- Procnums above 10 are opclass-specific (per BRIN README). The validator does **not** enforce specific signatures for procs > 10; that's the opclass-private business.
- Each `pg_amop` entry's `(left, right, strategy)` is recorded for a final "must have at least one operator" check.

Returns true if valid; ereports WARNINGs but does not throw, matching the other AM validators. [verified-by-code: ereport(WARNING) calls throughout]

Tags: [from-comment, brin_validate.c:1-12]; behavior [verified-by-code].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
