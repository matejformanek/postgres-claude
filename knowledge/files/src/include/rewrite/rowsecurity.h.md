# rowsecurity.h

- **Source:** `source/src/include/rewrite/rowsecurity.h` (~50 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

API + in-relcache structures for Row-Level Security.

## Types

- `RowSecurityPolicy` — one policy row from `pg_policy`, in
  in-memory shape (parsed qual + with-check, command type, role list,
  PERMISSIVE/RESTRICTIVE flag).
- `RowSecurityDesc` — per-relation cache attached to `Relation.rd_rsdesc`
  containing the list of `RowSecurityPolicy` entries.

## Exported entry

```c
extern void get_row_security_policies(Query *root,
                                      RangeTblEntry *rte, int rt_index,
                                      List **securityQuals,
                                      List **withCheckOptions,
                                      bool *hasRowSecurity,
                                      bool *hasSubLinks);
```

Called from `rewriteHandler.c:fireRIRrules` per RTE. Returns the quals
to prepend to the RTE's `securityQuals` and the with-check options to add
to the Query.

## Composition rule (recap from `rowsecurity.c.md`)

`(any PERMISSIVE matches) AND (all RESTRICTIVE match)` — no matching
PERMISSIVE policy means default-deny.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
