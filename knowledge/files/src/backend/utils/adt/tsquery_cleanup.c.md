# `src/backend/utils/adt/tsquery_cleanup.c`

## Purpose

Post-parse normalisation of tsquery trees. Pushes `NOT` operators
down, removes `QI_VALSTOP` nodes left by dictionary stopword
elimination, simplifies trivial trees. Used after `parse_tsquery` and
inside `tsquery_rewrite`. 446 lines.

## Key functions

- `maketree` — `tsquery_cleanup.c:33`. Build a binary NODE tree from
  polish-notation `QueryItem` array. Recursive; calls
  `check_stack_depth` at `:38`.
- `plainnode`, `plaintree` — `:90`, `:120`. Re-flatten NODE tree back
  to polish-notation array. Recursive; `check_stack_depth` at `:118`,
  `:139`.
- `clean_NOT_intree`, `clean_NOT` — push down or eliminate `NOT NOT`.
- `clean_stopword_intree`, `clean_fakeval_intree` — drop
  `QI_VALSTOP` placeholders left by dict-based stopword filtering;
  collapse children. Recursive; `check_stack_depth` at `:241`.

## Phase D notes

All tree-walks are guarded by `check_stack_depth`. Cleanup is
idempotent — running it twice does not change a normalised tree.

The functions take ownership of the input tree and may free
arbitrary sub-trees via `pfree`. Failures mid-walk leak the partial
tree, but since they're called in per-query contexts they're
reclaimed by `MemoryContextReset`.

`clean_NOT` may return a NULL tree (when the entire tree reduces to
NOT-stop) — callers must handle that.

## Potential issues

- [ISSUE-undocumented-invariant: Multiple cleanup passes are
  composed by callers (parse → clean_fakeval → clean_NOT →
  cleanup_split_words). The order matters but is documented only
  by usage. A misordered call sequence can leave invalid trees
  detected only at index time. (low)]
- [ISSUE-stale-todo: None visible; file is mature/stable.]
