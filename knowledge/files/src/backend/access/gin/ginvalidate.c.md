# ginvalidate.c

- **Source path:** `source/src/backend/access/gin/ginvalidate.c` (328 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

`amvalidate` slot for GIN: cross-checks `pg_amop`/`pg_amproc` entries against GIN's required-proc rules. Called from `ALTER OPERATOR FAMILY` and `pg_amcheck`. [from-comment, ginvalidate.c:1-12]

## Required procs (cross-referenced)

| Procnum | Name | Purpose |
|---|---|---|
| 1 | `compare` | btree-style 3-way comparison on keys; **mandatory** |
| 2 | `extractValue` | break an indexable item into keys (one per inserted heap row) |
| 3 | `extractQuery` | break a scan-query into match-keys |
| 4 | `consistent` | boolean consistent (optional if 6 exists) |
| 5 | `comparePartial` | for partial-match range queries (optional) |
| 6 | `triConsistent` | ternary consistent (optional if 4 exists) |
| 7 | `options` | reloption parser (optional) |

The validator allows procs 4 OR 6 (must have at least one). Signature checks verify input types match `opcintype`/`opckeytype`.

## Behavior

Returns true if valid; ereports WARNINGs but does not throw. The validation logic walks the opfamily's procs and ops, sanity-checks each, and warns on missing strategies. [verified-by-code: ereport(WARNING) throughout]

Tags: [from-comment, ginvalidate.c:1-12].
