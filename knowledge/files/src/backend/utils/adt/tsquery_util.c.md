# `src/backend/utils/adt/tsquery_util.c`

## Purpose

QTNode (Query Tree Node) helpers. QTNode is the tree representation
used for tsquery cleanup and rewriting; QueryItem is the on-disk
polish-notation representation. This file converts between them
and provides tree manipulations (sort, ternary normalize, free,
copy, compare). 448 lines.

## Key functions

- `QT2QTN` — `tsquery_util.c:25`. Build QTNode tree from
  polish-notation. Recursive; `check_stack_depth` at `:30`.
- `QTNFree` — `:65`. Recursive free; `check_stack_depth` at `:70`.
- `QTNSort` — `:95`. Sort children of commutative operators (AND/OR)
  for canonical comparison. Recursive; `check_stack_depth` at `:100`.
- `QTNEq` — `:160`. Recursive tree comparison; `check_stack_depth`
  at `:168`.
- `QTNTernary` — `:200`. Flatten nested binary AND/OR to n-ary
  children. Recursive; `check_stack_depth` at `:206`.
- `QTNBinary` — `:250`. Reverse of ternary — split n-ary back to
  binary tree. Recursive; `check_stack_depth` at `:255`.
- `QTN2QT` — `:290`. Tree → polish-notation; computes operand-string
  layout. Recursive; `check_stack_depth` at `:295`, `:326`.
- `QTNCopy` — `:395`. Deep copy; `check_stack_depth` at `:401`.
- `QTNClearFlags` — `:430`. Clear flags; `check_stack_depth` at `:437`.

## Phase D notes

Every recursive function checks the stack. This is the most
recursion-prevention-heavy file in the tsearch ADT layer — 11
`check_stack_depth` calls.

The flag `QTN_NEEDFREE` controls whether `QTNFree` recurses into a
node's QueryItem; nodes that point into a borrowed array (e.g. from
the on-disk tsquery) must NOT set this flag. Forgetting it is a
common bug source historically.

`QTNTernary` and `QTNBinary` are inverses but **not perfectly** —
ternary loses information about original tree shape. Rewrite uses
ternary canonicalisation so that `(a AND b) AND c` and
`a AND (b AND c)` compare equal.

## Potential issues

- [ISSUE-undocumented-invariant: `QTN_NEEDFREE` semantics not
  documented in this file (must `grep` ts_utils.h). Easy to forget
  to set/clear when transferring ownership of subtrees. (low)]
- [ISSUE-dead-code: None visible.]
