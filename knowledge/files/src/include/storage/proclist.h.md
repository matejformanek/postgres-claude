# `src/include/storage/proclist.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~220
- **Source:** `source/src/include/storage/proclist.h`

Doubly-linked list **of PGPROCs** identified by `pgprocno` (a small int)
rather than by pointer, so the same list header can sit in shared
memory and be safely walked from any backend regardless of where its
PGPROC array is mapped. Used by LWLock wait queues, condition
variables, and similar inter-backend wait structures. Functionally a
PGPROC-flavoured analogue of `lib/ilist.h`'s `dlist`. [from-comment]

## API / declarations

All functions are `static inline`. The types live in `proclist_types.h`
to break a header dep cycle with `proc.h`. [from-comment]

- `proclist_init(list)` — set head/tail to `INVALID_PROC_NUMBER`. [verified-by-code]
- `proclist_is_empty(list)` — true iff head is `INVALID_PROC_NUMBER`. [verified-by-code]
- `proclist_node_get(procno, node_offset)` — fetch the
  `proclist_node` embedded in PGPROC at `node_offset`. The
  per-call node_offset lets one PGPROC carry several proclist node
  fields (LWLock waiter, condition-variable waiter, etc.) on a single
  struct. [verified-by-code] [from-comment]
- `proclist_push_head_offset(list, procno, node_offset)` —
  prepend. Asserts the node is not currently in any list. [verified-by-code]
- `proclist_push_tail_offset(list, procno, node_offset)` — append.
  Same not-in-any-list precondition. [verified-by-code]
- `proclist_delete_offset(list, procno, node_offset)` — unlink. Caller
  must know the node is in *this* list (`prev`/`next` is consulted
  unguarded). [verified-by-code]
- `proclist_contains_offset(list, procno, node_offset)` — `O(1)`
  best-effort check: returns false definitively only if the node is
  in *no* list (next == prev == 0); otherwise it Asserts the
  head/tail are consistent and returns true. [verified-by-code]
  [from-comment]
- `proclist_pop_head_node_offset(list, node_offset)` — pop+return
  `PGPROC *`. [verified-by-code]
- Convenience wrappers: `proclist_delete`,
  `proclist_push_head`, `proclist_push_tail`,
  `proclist_pop_head_node`, `proclist_contains` — each takes a
  `link_member` name and computes `offsetof(PGPROC, link_member)`. [verified-by-code]
- `proclist_foreach_modify(iter, lhead, link_member)` — for-loop
  macro using `proclist_mutable_iter`. Pre-fetches `next` so the
  loop body may delete `iter.cur`. [verified-by-code] [from-comment]

## Notable invariants / details

- **Sentinel encoding.** `INVALID_PROC_NUMBER` marks "no neighbour".
  But the *not-in-any-list* state is encoded as
  `next == prev == 0` (procno 0 itself is a legal procno),
  NOT as `INVALID_PROC_NUMBER`. The pre-insert assert
  `Assert(node->next == 0 && node->prev == 0)` and the post-delete
  reset `node->next = node->prev = 0` are how
  `proclist_contains_offset` can do an O(1) negative answer. [verified-by-code] [from-comment]
  [ISSUE-undocumented-invariant: the "not in any list" sentinel is
  literal `0`, not `INVALID_PROC_NUMBER` — subtle distinction load-bearing
  for `proclist_contains_offset`'s O(1) fast-path (nit)]
- The "node belongs to at most one proclist at a time" rule is the
  user's responsibility, enforced only by `proclist_contains_offset`'s
  documentation. Two simultaneous proclist memberships would corrupt
  both lists silently. [from-comment]
  [ISSUE-undocumented-invariant: at-most-one-list rule has no assert
  enforcement (nit)]
- `proclist_contains_offset` deliberately does NOT walk the list
  because callers typically hold a spinlock (LWLock wait queue, CV
  queue). Asserts only verify head/tail consistency, not full
  containment. [from-comment]
- `proclist_foreach_modify` allows ONLY deletion of `iter.cur`; insertions
  during iteration would not be visited consistently. The macro
  doesn't enforce this — purely by convention. [from-comment]
  [ISSUE-undocumented-invariant: macro silently misbehaves if loop body
  does anything other than delete iter.cur (nit)]
- The `node_offset` approach means a single PGPROC can host multiple
  list memberships side-by-side (LWLock, condition variable, parallel
  worker waitlist, etc.) without separate allocation. [inferred]

## Potential issues

- Lines 145-167. `proclist_contains_offset` is documented as relying
  on the caller's "not in any other list using the same node_offset"
  precondition. There is no static-analysis tag, no naming convention
  forcing each node_offset to be tied to exactly one proclist owner. A
  buggy extension that reuses one PGPROC node field across two
  proclists would corrupt silently. [verified-by-code]
  [ISSUE-correctness: extension-hook reuse of a PGPROC proclist_node
  across two lists would silently corrupt (maybe)]
- Lines 206-217. `proclist_foreach_modify` uses a comma-expression-in-
  for-init pattern with `StaticAssertVariableIsOfTypeMacro` chained
  through commas. Works but is a documented PG idiom that's confusing
  to first readers; coverage by external static analyzers is
  inconsistent. [style]
  [ISSUE-style: comma-chained StaticAssert idiom is opaque to readers
  unfamiliar with PG ilist conventions (nit)]
