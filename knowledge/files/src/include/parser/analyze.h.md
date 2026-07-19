# analyze.h

- **Source:** `source/src/include/parser/analyze.h` (~70 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Public API surface of `parse_analyze_*` and related predicates.

## Exported entries

```c
extern PGDLLIMPORT post_parse_analyze_hook_type post_parse_analyze_hook;

extern Query *parse_analyze_fixedparams(RawStmt *, const char *,
                                        const Oid *paramTypes, int numParams,
                                        QueryEnvironment *);
extern Query *parse_analyze_varparams(RawStmt *, const char *,
                                      Oid **paramTypes, int *numParams,
                                      QueryEnvironment *);
extern Query *parse_analyze_withcb(RawStmt *, const char *,
                                   ParserSetupHook, void *,
                                   QueryEnvironment *);

extern Query *parse_sub_analyze(Node *, ParseState *,
                                CommonTableExpr *, bool, bool);

extern bool stmt_requires_parse_analysis(RawStmt *);
extern bool analyze_requires_snapshot(RawStmt *);
extern bool query_requires_rewrite_plan(Query *);

extern List *transformInsertRow(...);
extern List *transformUpdateTargetList(...);
extern List *transformReturningList(...);
extern OnConflictExpr *transformOnConflictClause(...);
extern void  applyLockingClause(Query *, Index, LockClauseStrength,
                                LockWaitPolicy, bool pushedDown);
extern List *BuildOnConflictExcludedTargetlist(Relation, Index);
extern SortGroupClause *makeSortGroupClauseForSetOp(Oid rescoltype,
                                                   bool require_hash);
```

## post_parse_analyze_hook

```c
typedef void (*post_parse_analyze_hook_type)(ParseState *, Query *,
                                             JumbleState *);
```

Fired once per analyzed query (and given the jumble state for query-id
computation). `pg_stat_statements` is the canonical user.

## Note

A few names that *look* like they belong in `analyze.c` (e.g.
`applyLockingClause`, `transformReturningList`) actually live there
because they need access to internal statics. The header is the integration
point.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
