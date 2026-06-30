# ginbtree.c

- **Source path:** `source/src/backend/access/gin/ginbtree.c` (835 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `ginentrypage.c` and `gindatapage.c` (provide the tree-specific `GinBtree` vtable used here — `beginPlaceToPage`, `execPlaceToPage`, `findChildPage`, `isMoveRight`, `getLeftMostChild`, `findChildPtr`, `fillRoot`, `prepareDownlink`); `ginxlog.c` (replay of `XLOG_GIN_INSERT`/`XLOG_GIN_SPLIT`).

## Purpose

The **abstract B-tree engine** for GIN — the framework used by both the entry tree and the posting tree. Implements descent (`ginFindLeafPage`), step-right (`ginStepRight`), insert (`ginInsertValue`), and split-finish (`ginFinishSplit`, `ginFinishOldSplit`). Tree-type specifics (entry vs data, leaf format, fillRoot) are dispatched via the `GinBtree` vtable. [from-comment, ginbtree.c:1-13]

## Vtable concept (`GinBtree`)

Defined in `gin_private.h`. Callers populate the vtable to point at either `ginentrypage.c::ginPrepareEntryScan`-style ops (entry tree) or `gindatapage.c::ginPrepareDataScan`-style ops (posting tree). The engine here doesn't know or care which it is.

## Public entry points

| Function | Line | Role |
|---|---|---|
| `ginTraverseLock` | 38 | Take share lock; on leaf in non-search mode, upgrade to exclusive (with the rare-root-became-non-leaf retry) |
| `ginFindLeafPage` | 82 | Descend from root, releasing parent before locking child *in search mode*; in insert mode keeps parent pins. Calls `ginFinishOldSplit` whenever it lands on `GIN_INCOMPLETE_SPLIT`. Move-right loop handles concurrent splits |
| `ginStepRight` | 176 | Lock new page **before** releasing current — the lock-coupling that protects against VACUUM deletion. Sanity-asserts new page has same kind (`isLeaf`, `isData`) |
| `freeGinBtreeStack` | 197 | Release pins + free stack |
| `ginInsertValue` | 815 | The single top-level insert API. Finishes any pre-existing incomplete split at the leaf, calls `ginPlaceToPage`, then `ginFinishSplit` if split returned false |

## Internal machinery

| Function | Line | Role |
|---|---|---|
| `ginFindParents` | 217 (static) | Re-walk the tree from root (whose pin is **never released**, line 232: "The root page is never released, to prevent conflict with vacuum process") to rebuild a parent stack when the cached parent moved due to concurrent splits |
| `ginPlaceToPage` | 336 (static) | The page-update engine: dispatches to vtable `beginPlaceToPage` (which decides INSERT vs SPLIT) and `execPlaceToPage`, manages CRIT section + WAL emission. Returns true if no parent action needed |
| `ginFinishSplit` | 671 (static) | Crawl up the parent stack inserting downlinks. Each iteration may itself split, recursing the loop |
| `ginFinishOldSplit` | 778 (static) | Wrapper that upgrades a share lock to exclusive before calling `ginFinishSplit`. Has explicit comment about why the lock-upgrade is safe during insert (VACUUM holds a cleanup lock on root) but **would not be safe during scan**. [from-comment, ginbtree.c:772-776] |

## Locking — the hot section [HIGH-RISK]

### Descent (`ginFindLeafPage`)

- **Search mode**: pin+share-lock one page at a time, release-before-acquire on descent. `stack->parent` is always NULL.
- **Insert mode**: pin retained on each ancestor; share-lock on the page being read, upgraded to exclusive at the leaf via `ginTraverseLock`. The pin-keeping is intentional: it lets `ginFindParents`-style re-walks find the parent buffer fast, AND prevents the root from being deleted under us. [verified-by-code, ginbtree.c:147-162]

### Step-right

`ginStepRight` (line 176) acquires the next page's lock **before** unlocking the current. This is the README's lock-coupling rule, and the comment explicitly names "concurrent VACUUM from deleting a page" as the threat. [from-comment, ginbtree.c:166-175]

### Split (`ginPlaceToPage`, GPTP_SPLIT branch, lines 451-647)

1. Allocate a new right page via `GinNewBuffer`.
2. Compute new left + new right page images in palloc'd temporaries (still outside CRIT).
3. If root split, also allocate a new left buffer and build a new-root image.
4. **Mark new left with `GIN_INCOMPLETE_SPLIT`** (line 543) for non-root splits — this is the "split, but parent downlink not yet inserted" state, exactly analogous to nbtree's split→parent-insert decoupling.
5. Take `PredicateLockPageSplit` if leaf.
6. Enter CRIT, copy temporaries into real buffers, clear childbuf's `GIN_INCOMPLETE_SPLIT` if this insert was a downlink-completion.
7. Emit `XLOG_GIN_SPLIT`. **Splits always log FORCE_IMAGE on all changed pages** (lines 608-616): "Splits are uncommon enough that it's not worth complicating the code to be more efficient." [from-comment, ginbtree.c:601-605]
8. Release right buffer (and left buffer if root split) UNLOCKED; keep stack->buffer + childbuf locked for parent action.
9. Return `result = (stack->parent == NULL)` — root splits are self-contained.

### Split-finish (`ginFinishSplit`)

Crawls up the parent stack, exclusive-locking each parent. On each iteration: if the parent itself is incomplete-split, finish that first; if the cached parent offset doesn't actually point at the child, step right (`findChildPtr` returns InvalidOffsetNumber until match) or `ginFindParents` if rightmost.

Crucially **the child remains exclusive-locked while the parent is locked** (line 736 — `ginPlaceToPage(... childbuf=stack->buffer ...)`). So the order is: **child exclusive → parent exclusive**. This is the opposite of nbtree's "release child before locking parent at insert" — possible here because GIN's split + parent-insert are not decoupled into separate WAL records by default. [verified-by-code, ginbtree.c:733-738; from-README, README:375-377]

### Incomplete-split recovery

`GIN_INCOMPLETE_SPLIT` flag is set on the **left** half of a non-root split before the parent downlink is inserted. If the parent insert is then deferred (because crash before `ginFinishSplit` runs, OR because we walked away holding only the child lock), a later descender will see the flag and call `ginFinishOldSplit`, which does the parent insert. This mirrors nbtree's `BTP_INCOMPLETE_SPLIT`. [verified-by-code, ginbtree.c:543, 113-115]

## Injection points

`gin-leave-leaf-split-incomplete`, `gin-leave-internal-split-incomplete`, `gin-finish-incomplete-split` (lines 686-690, 781). Used by isolation tests to simulate crash-during-split. [verified-by-code]

## Cross-references

- **Calls into:** vtable callbacks (`ginentrypage.c`/`gindatapage.c`), `GinNewBuffer` (in `ginutil.c`), `XLogBeginInsert`/`XLogRegisterBuffer`, `PredicateLockPageSplit`.
- **Called by:** `gininsert.c::ginInsertItemPointers`/`ginEntryInsert`, the read path in `ginget.c`, `ginfast.c` cleanup.

## Open questions

- Whether the comment at line 772 ("Upgrading the lock momentarily releases it. Doing that in a scan would not be OK") is enforced by an assertion or only by code review. [unverified]
- The interaction of `ginFindParents` with concurrent `ginPlaceToPage` re-parenting (both can call into the vtable's `findChildPtr` against the same parent) is asserted-safe by VACUUM's root cleanup lock. [from-comment, ginbtree.c:213-216, 232-234]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/gin-tree-structure.md](../../../../../idioms/gin-tree-structure.md)

