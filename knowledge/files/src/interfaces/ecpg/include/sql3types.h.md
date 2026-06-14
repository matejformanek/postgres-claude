---
path: src/interfaces/ecpg/include/sql3types.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 43
depth: read
---

# `sql3types.h` — SQL3 dynamic-SQL type codes

## Purpose
Two anonymous enums giving the SQL3-standard numeric type codes used in dynamic
SQL descriptors: the data-type codes (`SQL3_CHARACTER=1`, `SQL3_NUMERIC`, …,
`SQL3_BOOLEAN`) from SQL3 §13.1 table 2, and the datetime-subtype codes
(`SQL3_DDT_DATE=1` …) from table 3. [verified-by-code] These are what
`ECPGget_desc(... ECPGd_di_code ...)` returns for a result column.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `SQL3_CHARACTER … SQL3_abstract` | sql3types.h:8 | data-type codes; note the gap (no value 11) and `SQL3_CHARACTER_VARYING = 12` [verified-by-code] |
| `SQL3_DDT_DATE … SQL3_DDT_ILLEGAL` | sql3types.h:31 | datetime subtype codes [verified-by-code] |

## Internal landmarks
- The data-type enum has a deliberate hole: it runs 1–10 then jumps to
  `SQL3_CHARACTER_VARYING = 12` (sql3types.h:19-20), matching the standard's
  numbering (11 is unused / reserved). [verified-by-code]
- `SQL3_abstract` and the comment "the rest is xLOB stuff" (sql3types.h:25-26)
  mark where the standard's LOB codes would continue — not implemented. [from-comment]

## Invariants & gotchas
- These are standard-defined constants surfaced to applications via descriptors;
  treat as ABI. [inferred]
- The hole at 11 means a `for (i = SQL3_CHARACTER; i <= SQL3_BOOLEAN; i++)`
  loop would hit an undefined code; iterate the named values, not the range. [verified-by-code]

## Cross-refs
- [[ecpgtype.h]] — `ECPGd_di_code` descriptor item.
- `knowledge/files/src/interfaces/ecpg/ecpglib/typename.c.md` —
  `ecpg_dynamic_type` maps PG Oid → `SQL3_*`.
