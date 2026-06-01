# rewriteHandler.h

- **Source:** `source/src/include/rewrite/rewriteHandler.h` (~30 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

External interface to the query rewriter — the file that everything
outside `rewrite/` includes to call `QueryRewrite`.

## Exported entries

```c
extern List *QueryRewrite(Query *parsetree);
extern void  AcquireRewriteLocks(Query *parsetree, bool forExecute,
                                 bool forUpdatePushedDown);
extern List *fireRIRrules_for_security(Query *parsetree, List *activeRIRs);
extern Node *build_column_default(Relation rel, int attrno);
extern void  fill_extraUpdatedCols(RangeTblEntry *target_rte, Relation rel);
extern Query *get_view_query(Relation view);
extern const char *view_query_is_auto_updatable(Query *viewquery,
                                                bool check_cols);
extern int    relation_is_updatable(Oid reloid,
                                    List *outer_reloids,
                                    bool include_triggers,
                                    Bitmapset *include_cols);
extern void   ExecCheckOneRtePermissions(RangeTblEntry *rte, ...);
```

(Exact set may evolve; the load-bearing ones are `QueryRewrite` and
`AcquireRewriteLocks`, both documented in detail in the
`rewriteHandler.c.md` doc.)

## When to AcquireRewriteLocks

- Always before processing a Query that came from `pg_rewrite` storage,
  the plan cache, or any other source older than the current command.
- *Not* needed for a Query that just came out of the parser — parse
  analysis already took those locks.
