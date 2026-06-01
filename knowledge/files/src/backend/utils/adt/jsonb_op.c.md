# `src/backend/utils/adt/jsonb_op.c`

- **File:** `source/src/backend/utils/adt/jsonb_op.c` (335 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

> "Special operators for jsonb only, used by various index access methods"
> (`:3-4` [from-comment]).

The fmgr entry points for jsonb's comparison, containment, existence,
and hash operators — i.e. everything that gets called either via
SQL operator syntax (`@>`, `?`, `?|`, `?&`) or via GIN / btree / hash
opclass support functions.

## Public surface (all are fmgr functions)

| Function | Strategy / role |
|---|---|
| `jsonb_exists` (`:21`) | `jsonb ? text` — top-level key/string exists |
| `jsonb_exists_any` (`:46`) | `jsonb ?\| text[]` |
| `jsonb_exists_all` (`:79`) | `jsonb ?& text[]` |
| `jsonb_contains` (`:112`) | `jsonb @> jsonb` |
| `jsonb_contained` (`:130`) | `jsonb <@ jsonb` |
| `jsonb_eq/ne/lt/le/gt/ge` (`:222, 149, 166, 194, 180, 208`) | btree opclass; all delegate to `compareJsonbContainers` |
| `jsonb_cmp` (`:236`) | btree support function 1 |
| `jsonb_hash` (`:253`) | hash opclass support |
| `jsonb_hash_extended` (`:295`) | extended-hash opclass support (for parallel hash) |

## Key behavior

- **`?` is restricted to top-level keys and string array elements.**
  > "We only match Object keys (which are naturally always Strings),
  > or string elements in arrays. In particular, we do not match
  > non-string [scalars]" (`:27-30` [from-comment]). This is the
  semantics GIN's `jsonb_ops` opclass mirrors.
- `jsonb_contains` and `jsonb_contained` just swap arguments and call
  `JsonbDeepContains` (defined in `jsonb_util.c`).
- `jsonb_cmp` returns `compareJsonbContainers(a, b)`; the result drives
  the per-type sort order documented in `jsonb_util.c` (Object >
  Array > Boolean > Number > String > Null; ties broken by
  length, then element-wise).
- Hash functions compute a single running uint32/uint64 by walking
  the iterator; same scheme as `JsonbHashScalarValue` but for an
  entire container.

## Why this file is separate from `jsonb.c`

`jsonb.c` is "I/O + constructors"; `jsonb_op.c` is "operators that
indexes care about". Keeping them apart makes GIN / btree review
contained: a new opclass strategy gets one new top-level Datum
function here, not scattered across the I/O file.

## Cross-references

- `source/src/backend/utils/adt/jsonb_util.c` — `JsonbDeepContains`,
  `compareJsonbContainers`, `JsonbHashScalarValue[Extended]`.
- `source/src/backend/access/gin/ginutil.c` and
  `source/src/backend/utils/adt/jsonb_gin.c` — GIN extractors that
  reuse these operators.
- `source/src/include/utils/jsonb.h:33-38` — the strategy-number
  constants this file's operators correspond to.

## Confidence tag tally

- `[verified-by-code]` × 3
- `[from-comment]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
