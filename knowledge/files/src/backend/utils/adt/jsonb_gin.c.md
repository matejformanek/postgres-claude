# jsonb_gin.c — GIN opclasses for `jsonb`

## Purpose

Implements two GIN operator classes over `jsonb`:

1. **`jsonb_ops`** (default) — extracts every value and every key as a separate hashed GIN entry, supporting `@>`, `?`, `?&`, `?|`, plus jsonpath operators.
2. **`jsonb_path_ops`** — extracts only leaf values, hashed together with the full path from root; supports `@>` only, but with much smaller indexes for `@>` workloads.

Source: `source/src/backend/utils/adt/jsonb_gin.c` (1410 lines).

## Key functions

- `gin_compare_jsonb` — qsort-style comparator over hashed `text` entries. [verified-by-code jsonb_gin.c:203]
- `gin_extract_jsonb` — index-time extractor for `jsonb_ops`; walks the value with `JsonbIteratorNext` (iterative, no C-stack recursion). [verified-by-code jsonb_gin.c:229]
- `gin_extract_jsonb_query` — extracts query keys for `@>`/`?`/`?&`/`?|` and jsonpath ops; returns search keys + per-key strategy categories. [verified-by-code jsonb_gin.c:848]
- `gin_consistent_jsonb`, `gin_triconsistent_jsonb` — match logic; tri-consistent answers MAYBE for partial-match cases so the executor re-checks via the heap. [verified-by-code jsonb_gin.c:929,1013]
- `gin_extract_jsonb_path` / `gin_extract_jsonb_query_path` — `jsonb_path_ops` variants; the entry hash mixes ancestor keys into the leaf via `JsonbHashScalarValueExtended`. [verified-by-code jsonb_gin.c:1090,1180]
- `extract_jsp_*` helpers (around line 500-720) — walk a jsonpath AST to derive index conditions. `check_stack_depth()` invoked at lines 587 and 722 to bound recursion. [verified-by-code jsonb_gin.c:587,722]

## Phase D notes

- **Stack-depth gate present on jsonpath walk**. Two `check_stack_depth()` calls at jsonb_gin.c:587,722 protect the recursive jsonpath analysis. [verified-by-code]
- **Iterative jsonb walk**. The value walker uses `JsonbIterator`, not C-recursion, so a deeply nested jsonb document does not blow the C stack at index time. [verified-by-code]
- **`jsonb_path_ops` security feature**: harder for adversaries to provoke index bloat by spraying unique keys, because only leaves become entries.
- **Lossy-by-design**: hashes are 32-bit (`text` with first 4 bytes). False positives are filtered by recheck; not a correctness bug. [from-comment]

## Potential issues

- `[ISSUE-correctness: jsonpath extractor returns "true / maybe" answers that the executor must recheck; a stale extension hooking into GIN that forgets to set recheck=true could miss rows (maybe)]` Standard GIN contract.
- `[ISSUE-dos: extract_jsonb_path hashes (parent-key, value); a hostile document with many identical leaf scalars but distinct paths is still bounded by document size (low)]`.
- `[ISSUE-undocumented-invariant: 32-bit hash collisions in jsonb_path_ops can spuriously match @> queries before recheck; documented behavior but not in the .md docs (low)]`.

Confidence: `[verified-by-code]` for the function map and stack-depth gates.
