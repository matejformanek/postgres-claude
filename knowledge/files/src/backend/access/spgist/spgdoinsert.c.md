# spgdoinsert.c

- **Source path:** `source/src/backend/access/spgist/spgdoinsert.c` (2352 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `spginsert.c` (top-level wrappers), `spgutils.c` (page allocation, last-used-page cache), `spgxlog.c` (replay), opclass files.

## Purpose

The insertion engine. Implements the README §"Insertion Algorithm" with `chooseFn` dispatch (`MatchNode` / `AddNode` / `SplitTuple`), leaf-page picksplit, and the conditional-locking + restart deadlock-avoidance. [from-comment, spgdoinsert.c:1-13]

## Key data structures

- `SPPageDesc` (~line 28) — per-page state tracker: buffer, blkno, page, opaque pointer, was-just-extended flag. Used as scratch state through the insert loop.
- Stacks of `SPPageDesc` for parent + child while descending.

## Top entry: `spgdoinsert`

Loop:
1. Read root (main tree or nulls tree depending on input).
2. While not done:
   - If page is leaf: if room → `addLeafTuple` and exit; else `doPickSplit`.
   - Else (inner page): call opclass `chooseFn`. Switch on result:
     - `spgMatchNode` → descend (release current, lock child).
     - `spgAddNode` → call `addNode` on current inner tuple; retry chooseFn.
     - `spgSplitTuple` → call `doSplitTuple` to break prefix into prefix+postfix; retry chooseFn.

## Key sub-routines

| Function | Role |
|---|---|
| `addLeafTuple` | Add a new leaf tuple to a chain on a leaf page (or initialize a single-tuple chain). May need to extend the page-chain via `moveLeafs` |
| `moveLeafs` | Move an entire chain to a new leaf page (write a REDIRECT in place). Emits `XLOG_SPGIST_MOVE_LEAFS` |
| `doPickSplit` | Page-full case: invoke opclass `pickSplit` to repartition leaf tuples into multiple chains, allocate new inner tuple + new leaf pages, redirect old chain head. The most complex routine in the file (~600 lines). Emits `XLOG_SPGIST_PICKSPLIT` |
| `addNode` | Extend an inner tuple's node array. May overflow the page → move inner tuple to another inner page, leave PLACEHOLDER. Emits `XLOG_SPGIST_ADD_NODE` |
| `doSplitTuple` | The radix-tree split: split inner tuple into a "prefix" tuple (stays in place) and a "postfix" tuple (new). Emits `XLOG_SPGIST_SPLIT_TUPLE`. README walkthrough at lines 158-194 |
| `spgPageIndexMultiDelete` | Multi-delete helper that preserves placeholder semantics |

## Conditional locking + restart [HIGH-RISK]

The descent calls `ConditionalLockBuffer` when grabbing the child page while holding the parent. If it would block, both locks are released and the descent restarts from root. Per README §"Concurrency", this is the deadlock-avoidance — combined with the triple-parity page assignment heuristic (in `spgutils.c::SpGistGetBuffer`) to make restarts rare. [from-README, README:217-244; verified-by-code]

The restart is `goto`-driven: a label at the top of the descent loop. Comments warn that the restart must reset all stack state and re-pin from scratch.

## WAL records emitted (from spgdoinsert.c paths)

- `XLOG_SPGIST_ADD_LEAF` — simple leaf insertion (with optional parent-downlink fixup).
- `XLOG_SPGIST_MOVE_LEAFS` — chain migration + redirect.
- `XLOG_SPGIST_ADD_NODE` — extend inner tuple (possibly moving it to new page).
- `XLOG_SPGIST_SPLIT_TUPLE` — prefix/postfix split.
- `XLOG_SPGIST_PICKSPLIT` — leaf-page repartition.

## Cross-references

- **Called from:** `spginsert.c::spginsert`.
- **Calls into:** opclass procs (chooseFn, pickSplit, leafConsistent), `spgutils.c` (page allocation, redirect helpers), `spgxlog.c` (WAL emit helpers).

## Open questions

- The restart-from-root mechanism in the presence of *very* frequent conflicts could in principle livelock; backoff is implicit (other backends complete their inserts and free pages). Whether there's a hard livelock guard is not clear. [unverified]
- `doPickSplit` interaction with concurrent VACUUM's pending-list mechanism: pickSplit may create REDIRECTs that VACUUM must then chase. Comments at top of spgvacuum.c reference this. [from-README, README:347-368]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/spgist-insert-and-picksplit.md](../../../../../idioms/spgist-insert-and-picksplit.md)
- [idioms/spgist-tree-and-tuples.md](../../../../../idioms/spgist-tree-and-tuples.md)

