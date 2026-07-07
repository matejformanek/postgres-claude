# contrib-tablefunc (crosstab + connectby SRFs)

- **Source path:** `source/contrib/tablefunc/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `tablefunc.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

Two table-shape transformations as set-returning functions:

- **`crosstab` family** — pivot rows into columns (the SQL
  pivot operation, before window-functions made it less
  necessary).
- **`connectby` family** — recursive hierarchy walks (parent-
  child traversal, before recursive CTEs).

Both predate the SQL features that largely replace them.
Still useful for legacy schemas and certain edge cases where
the recursive CTE form is awkward.

The single 1575-LOC `tablefunc.c` [verified-by-code
`wc -l source/contrib/tablefunc/tablefunc.c`].

## 2. The crosstab family

`crosstab(sql)` — pivot SQL returning (row_id, category, value)
into a result with row_id + N value columns:

```sql
-- Input rows:
-- ('Foo', 'A', 1), ('Foo', 'B', 2), ('Bar', 'A', 3), ('Bar', 'B', 4)

SELECT * FROM crosstab(
    'SELECT row_id, cat, val FROM source ORDER BY row_id, cat'
) AS ct(row_id text, A int, B int);

-- Result:
-- row_id | A | B
-- Foo    | 1 | 2
-- Bar    | 3 | 4
```

The number of value columns must be known at parse time —
that's why the `AS ct(...)` is required.

## 3. The crosstab variants

| Variant | Behavior |
|---|---|
| `crosstab(sql)` | 3-arg input, output columns implicit by position |
| `crosstab(sql, sql_categories)` | 3-arg input + categories query for explicit column ordering |
| `crosstab2`, `crosstab3`, `crosstab4` | Fixed 2/3/4 value-column results |

The `crosstab(sql, sql_categories)` form is the most useful
in practice — pass an explicit category-list SQL and the
output has predictable column ordering.

## 4. The connectby family

`connectby(table, key_col, parent_key_col, start_key, ...)` —
recursive parent-child walk:

```sql
-- Tree table:
-- key | parent
-- 1   | NULL
-- 2   | 1
-- 3   | 1
-- 4   | 2

SELECT * FROM connectby(
    'tree', 'key', 'parent', '1', 0, '~'
) AS t(key int, parent int, level int, branch text);

-- Result:
-- key | parent | level | branch
-- 1   | NULL   | 0     | 1
-- 2   | 1      | 1     | 1~2
-- 4   | 2      | 2     | 1~2~4
-- 3   | 1      | 1     | 1~3
```

Walks from the start key downward, recording level and a
branch path. The `branch` column is the chain of keys joined
by the separator (default `~`).

## 5. Why these were added pre-recursive-CTE

When tablefunc was added (PG 7.3 era), recursive CTEs
(`WITH RECURSIVE`) didn't exist. crosstab + connectby were
the contrib answer.

Modern equivalents:
- **crosstab** → `FILTER (WHERE ...)` aggregates +
  conditional expressions + window functions.
- **connectby** → `WITH RECURSIVE` queries.

The CTE form is more flexible (custom recursion termination,
arbitrary tree shapes, joinable with other CTEs). The contrib
functions remain easier for the common-case pivot.

## 6. SPI usage

`crosstab` and `connectby` both call into SPI
(`SPI_connect` / `SPI_execute`) to run their input queries.
This is the canonical example of an SPI-using contrib
function:

```c
SPI_connect();
ret = SPI_execute(sql, true, 0);
// ... process results ...
SPI_finish();
```

[from tablefunc.c structure]

The SPI call uses a temp tuplestore to assemble the pivoted /
walked result. Memory is bounded by `work_mem`.

## 7. Crosstab edge cases

- **Missing category** in some rows → null in the
  corresponding output column.
- **Extra categories** beyond the AS clause → silently dropped.
- **Duplicate (row_id, category) pairs** → the LAST one wins
  (depends on input ORDER BY).

The `crosstab(sql, sql_categories)` 2-arg form is more
predictable: the category-query determines exactly which
columns appear.

## 8. Connectby cycle handling

Default behavior on cycles: infinite loop. The
`connectby_int` / `connectby_text` variants accept an optional
`max_depth` parameter:

```sql
SELECT * FROM connectby('tree', 'key', 'parent', '1',
                        5 /* max depth */, '~') AS ...;
```

5 levels max. Used as a safety net for trees that may have
cycles or unbounded depth.

## 9. Production-use guidance

- **For new code, prefer WITH RECURSIVE** over connectby.
- **For new code, prefer `FILTER (WHERE)` aggregates** over
  crosstab.
- **For legacy code**, tablefunc remains supported.
- **Crosstab's "must-know-output-columns" limitation**
  is unfixable — alternatives like jsonb_object_agg avoid it.

## 10. Invariants

- **[INV-1]** Output column count fixed by `AS x(...)`.
- **[INV-2]** SPI is used internally; runs in caller's
  transaction.
- **[INV-3]** Max-depth parameter prevents infinite recursion
  in connectby.
- **[INV-4]** Trusted extension; no superuser required.
- **[INV-5]** Duplicate (row_id, category) → undefined
  output column value.

## 11. Useful greps

- The entry points:
  `grep -n 'PG_FUNCTION_INFO_V1\|connectby\|crosstab' source/contrib/tablefunc/tablefunc.c | head -10`
- SPI usage:
  `grep -n 'SPI_connect\|SPI_execute' source/contrib/tablefunc/tablefunc.c | head -10`

## 12. Cross-references

- `.claude/skills/fmgr-and-spi.md` — SPI-from-C pattern.
- `knowledge/subsystems/parser-and-rewrite.md` — WITH
  RECURSIVE is the modern alternative to connectby.
- `knowledge/subsystems/executor.md` — set-returning
  functions in the executor.
- `source/contrib/tablefunc/tablefunc.c` — implementation.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/tablefunc/tablefunc`](../files/contrib/tablefunc/tablefunc.md) |

<!-- /files-owned:auto -->
