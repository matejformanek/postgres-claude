---
name: jsonpath-and-jsonb
description: PostgreSQL's SQL/JSON support — jsonpath (SQL:2016 path language) + jsonb (binary-encoded JSON) + the SQL/JSON operators like `->`, `->>`, `@?`, `@@`, `jsonb_path_query`. Covers `src/backend/utils/adt/jsonb*.c` (jsonb storage + operators + GIN opclass + subscripting) and `jsonpath*.c` (path language parser + executor). Loads when the user asks about jsonpath semantics, path variables ($, @, current), lax vs strict mode, predicate expressions, `jsonb_path_query` / `jsonb_path_exists`, JSON_TABLE (SQL:2023 / PG 17+), jsonb_gin operator class, memory management in jsonpath_exec (Tom Lane's 5a2043bf713 rewrite), or "why is my JSON search slow" (usually GIN or path complexity). Skip when the ask is about the older `json` type (`json.c` is separate — text representation) or about JSON output formats (that's `format_type` territory).
when_to_load: Extend jsonpath / jsonb operators; debug JSON query performance; understand jsonpath memory management (see planning/jsonpath_leak for the calibration story); add support for a new SQL/JSON feature.
companion_skills:
  - memory-contexts
  - fmgr-and-spi
  - error-handling
---

# jsonpath-and-jsonb — SQL/JSON path language and binary JSON

PG has TWO JSON types:

- **`json`** — text storage. Preserves formatting/whitespace/key-order. Slow to query (parsed every access).
- **`jsonb`** — binary storage. Deduped/sorted keys, faster to query, indexable via GIN. Almost always what you want.

Plus **`jsonpath`** — a query language type (SQL:2016). Compiled path expressions used by `jsonb_path_query`, `jsonb_path_exists`, `@@` operator, `JSON_TABLE`.

## The file map

| File | KB | Role |
|---|---:|---|
| `utils/adt/jsonb.c` | 47 | Public `jsonb` operators + I/O — `jsonb_in`, `jsonb_out`, `jsonb_object`, `->`, `->>`, key existence `?`, containment `@>`. |
| `utils/adt/jsonb_util.c` | 58 | Internal serialization + traversal. `JsonbIterator`, `findJsonbValueFromContainer`, packing helpers. Contains ordering/deduplication rules. |
| `utils/adt/jsonb_gin.c` | 35 | GIN opclass for jsonb — extract-value / extract-query / consistent functions. Multiple index shapes: default, path_ops. |
| `utils/adt/jsonb_op.c` | 7 | Small operator wrappers. |
| `utils/adt/jsonbsubs.c` | 12 | Array/object subscripting — `jsonb['key']` (PG 14+). |
| `utils/adt/jsonpath.c` | 38 | jsonpath type support — parser (via `jsonpath_scan.l` + `jsonpath_gram.y`), I/O, tree walks. |
| `utils/adt/jsonpath_exec.c` | **127** | jsonpath EXECUTOR. `executeItem`, `executePredicate`, `executeBinaryArithmExpr` — traverses the jsonpath tree against a jsonb value. **This is where the leak fix landed** — see `planning/jsonpath_leak/`. |
| `include/utils/jsonb.h`, `jsonapi.h`, `jsonpath.h` | — | Public APIs. |

## jsonb storage layout

A jsonb is a varlena with:

- **Header** — 4 bytes VARSIZE_ANY + 4 bytes JEntry-array-count for the root container.
- **JEntry array** — one per top-level element, encoding type + length/offset.
- **Serialized values** — the raw bytes for scalars, or nested containers with their own JEntry arrays.
- **Recursive** — a jsonb OBJECT's value is a nested container repeating the pattern.

Keys are sorted lexically (bytewise UTF-8) and deduped (last-wins semantics). This is why:
- `'{"a": 1, "a": 2}'::jsonb` returns `{"a": 2}`.
- `->` on a large object is O(log n) via binary search on sorted keys.

## jsonpath language basics

Path expressions like `$.employees[*] ? (@.name == "Alice")` mean:

- `$` — the root (the jsonb value passed in).
- `.name` — field access.
- `[*]` — all array elements.
- `? (predicate)` — filter — keep only elements where predicate is true.
- `@` — the current element in a filter context.

Two modes:

- **lax** (default) — missing paths return "no result" instead of erroring. Auto-unwraps arrays. Auto-wraps scalars. Forgiving.
- **strict** — errors on missing paths / type mismatches. Strict RFC compliance.

Set at query time: `SELECT jsonb_path_query(v, 'strict $.a')`.

## The executor's key structures

From `jsonpath_exec.c`:

- **`JsonPathExecContext`** — walks state: current position, mode, variables map.
- **`JsonValueList`** — accumulates result values. **This is the struct Tom Lane's `5a2043bf713` redesigned inline** to eliminate the executePredicate memory leak. See `planning/jsonpath_leak/comparison.md` for the pattern comparison.
- **`JsonPathItem`** — one node in the compiled path tree.
- **`JsonbValue`** — the value being examined.

The executor does DFS over the jsonpath tree, executing predicates, applying arithmetic, accumulating results into a `JsonValueList`.

## GIN index on jsonb

Two operator classes:

- **`jsonb_ops`** (default) — index each unique key/value combo. Supports `@>`, `?`, `?&`, `?|`. Bigger index; more query flexibility.
- **`jsonb_path_ops`** — hash each path-to-value. Only supports `@>`. Smaller; faster; strict subset.

Choose `path_ops` for pure containment queries (JSON-Blob search). Choose default for key-existence + containment.

## Common patch shapes

### Add a new jsonpath function

- Extend `jsonpath_gram.y` for the syntax.
- Add case in `executeItem` (jsonpath_exec.c) — implement the semantics.
- If the function returns multiple values, decide lax vs strict behavior.
- Regress in `src/test/regress/sql/jsonpath.sql`.

### Add a new jsonb operator

- Add C function in `jsonb.c` or `jsonb_op.c`.
- pg_operator.dat entry (with commutator / negator / restrict / join fns).
- Consider GIN opclass support — a new operator without index support is a footgun.

### Optimize a jsonb query

- EXPLAIN — is the GIN index being used?
- If not: `path_ops` may not support your operator; switch to default. Or your predicate has too much post-index work.
- If yes but slow: consider a **partial index** on the specific path shape.
- Container-emit vs path-emit — the executor may be materializing large intermediate results. Consider strict mode + explicit path.

### Fix a jsonpath memory leak

Been done. See `planning/jsonpath_leak/`:
- The blind-trilogy calibration reproduced Tom Lane's leak fix (5a2043bf713) with a different mechanism but identical RSS envelope (32 MB vs 32 MB).
- The bug pattern: `JsonValueList` accumulated results without per-call context cleanup. Fixes: struct redesign (Tom's) OR per-call AllocSetContext wrap (calibration's approach). Both work.
- Lesson: for iterator-style accumulator structs, ownership of the elements matters as much as ownership of the containers.

## Pitfalls

- **`json` vs `jsonb` type — pick jsonb** — unless you have a specific reason (preserving formatting, key order), always jsonb. json is a "text with syntax check", not a queryable structure.
- **Key deduplication in jsonb** — `'{"a":1,"a":2}'::jsonb` silently keeps the last. Applications that generate jsonb should not rely on duplicate keys.
- **jsonpath variables need explicit passing** — `jsonb_path_query(v, '$var', '{"var": 5}'::jsonb)`. Beginners often try to embed variables inline.
- **`->` returns jsonb; `->>` returns text** — using `->` when you want a text scalar leaves you with a jsonb-encoded scalar (e.g. `"hello"` with quotes).
- **`@?` vs `@@`** — `@?` returns bool (path exists); `@@` returns bool (path returns truthy). Common mixup.
- **`jsonb_path_ops` is more restrictive than you think** — no `?` operator, no `->` (that's the wrong tool anyway).
- **Deep jsonpath is quadratic** — a path like `$.a.b.c...z` on a deeply nested jsonb is O(depth × object-size). Consider caching sub-values.
- **jsonpath_exec.c is a memory hotspot** — see `planning/jsonpath_leak/` for a real bug fixed at scale (5.7 GB → 32 MB RSS on the reproducer). New iterator-style code paths should apply the per-call context pattern.
- **JSON_TABLE (PG 17+) is jsonpath at heart** — its columns are jsonpath expressions. Same performance considerations.
- **JIT doesn't help jsonb operations** — jsonpath executor is interpreter-only. JIT compiles ExprState machinery, not the jsonpath tree.

## Related corpus

- **Idioms**: `error-handling` (jsonpath errors in strict mode), `heap-tuple-decompression-pattern` (jsonb is toasted → detoast + traverse).
- **Subsystems**: `utils-mmgr` (jsonpath_exec is a memory hotspot — hence the leak), `parser-and-rewrite` (jsonpath grammar is separate but sits in the same layer).
- **Scenarios**: `add-new-builtin-function` (for adding jsonb / jsonpath fns), `fix-memory-leak` (jsonpath_leak is the canonical calibration).
- **Planning**: `planning/jsonpath_leak/` — 3-phase blind calibration reproducing Tom Lane's fix. Read `comparison.md` for the mechanism comparison (inline storage vs per-call context).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/utils/adt/jsonpath_exec.c
python3 scripts/corpus-chain.py --file src/backend/utils/adt/jsonb.c
python3 scripts/corpus-chain.py --idiom heap-tuple-decompression-pattern
```

## Boundary

**Use this skill** for jsonb + jsonpath + related operators + JSON_TABLE.

**Don't use** for:
- **`json` type (text-based)** — separate `json.c`; use only for compatibility.
- **`hstore`** — contrib module, different data model.
- **`hstore_plpython` / `hstore_plperl`** — different transformers.
- **XML type** — `xml.c` etc., separate subsystem.
- **JSON parsing at the SQL boundary** — that's `jsonapi.c`'s pull-based parser, used by many callers; often you don't need to touch it.
