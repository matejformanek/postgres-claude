# tablefunc.c

`source/contrib/tablefunc/tablefunc.c` (1575 lines).

## One-line summary

Five SRFs that take **caller-supplied SQL text** and execute it via SPI: `crosstab(text)` and `crosstab(text,N)` pivot row-major into column-major, `crosstab_hash` uses a categories-SQL to pre-discover columns, `connectby_text` / `connectby_text_serial` walk a hierarchical (parent/child) table recursively. Plus `normal_rand(int, float8, float8)` (Gaussian random generator, no SPI).

## Public API / entry points

- `normal_rand(int numvals, float8 mean, float8 stddev)` — `source/contrib/tablefunc/tablefunc.c:176-275` [verified-by-code]
- `crosstab(text sql)` — `tablefunc.c:358-599`
- `crosstab_hash(text source_sql, text cats_sql)` — `tablefunc.c:636-701`
- `connectby_text(text relname, text key_fld, text parent_key_fld, text start_with, int max_depth, [text branch_delim])` — `tablefunc.c:973-1053`
- `connectby_text_serial(text relname, text key_fld, text parent_key_fld, text orderby_fld, text start_with, int max_depth, [text branch_delim])` — `tablefunc.c:1055-1132`
- internal `load_categories_hash` — `tablefunc.c:706-787`
- internal `get_crosstab_tuplestore` — `tablefunc.c:792-937`
- internal `connectby` + `build_tuplestore_recursively` — `tablefunc.c:1138-1403`
- internal `compatCrosstabTupleDescs`, `compatConnectbyTupleDescs`, `validateConnectbyTupleDesc` — `tablefunc.c:1409-1575`

## Key invariants

- Functions require `rsinfo->allowedModes & SFRM_Materialize` — fail otherwise — `tablefunc.c:385-388,653-657,1000-1004,1079-1083` [verified-by-code]
- `crosstab` source SQL **must return exactly 3 columns** (`rowid, category, value`); otherwise `ERRCODE_INVALID_PARAMETER_VALUE` — `tablefunc.c:421-425`
- `crosstab_hash` source SQL must return **at least 3 columns**, last two = (category, value); excess prefix columns ≥2..N-2 are passed through from the FIRST occurrence of each rowid — `tablefunc.c:837-864`
- `load_categories_hash`: categories SQL must return exactly 1 column; NULL category → `ERRCODE_NULL_VALUE_NOT_ALLOWED`; duplicate category name → `ERRCODE_DUPLICATE_OBJECT` — `tablefunc.c:747-779`, macro at `tablefunc.c:147-160`
- Category name is **truncated to `NAMEDATALEN-1`** by `snprintf(key, MAX_CATNAME_LEN-1, ...)` inside the hash macros — categories longer than 63 bytes collide if they share a prefix! — `tablefunc.c:130-160` [verified-by-code]
- `connectby` builds SQL via `appendStringInfo` and `quote_literal_cstr(start_with)` — only `start_with` is literal-quoted; `key_fld`, `parent_key_fld`, `relname`, `orderby_fld`, `branch_delim` are **interpolated raw** — `tablefunc.c:1227-1247`
- `connectby` infinite-recursion guard: if the current key already appears in the branch string (delimited by `branch_delim`), `ERRCODE_INVALID_RECURSION` "infinite recursion detected" — `tablefunc.c:1335-1343` [verified-by-code]
- `max_depth = 0` means unlimited recursion; `> 0` is the actual cap — `tablefunc.c:1219-1220`
- `build_tuplestore_recursively` does NOT call `check_stack_depth()` — only the `max_depth` argument and the cycle-via-branch-string guard prevent runaway. — `tablefunc.c:1189-1403` [verified-by-code]
- `normal_rand` rejects negative `num_tuples` with `ERRCODE_INVALID_PARAMETER_VALUE` — `tablefunc.c:205-208`

## Notable internals

- `crosstab` uses SPI as caller's role (no SECURITY DEFINER) — invoked SQL sees the caller's privileges, not the function owner's — `tablefunc.c:393,396` [verified-by-code]
- Result tupdesc comes from `get_call_result_type(fcinfo, NULL, &tupdesc)` — the **CALLER picks the composite type** of the result (`AS (col1 type1, col2 type2, ...)`). Type coercion is by `BuildTupleFromCStrings → attinmeta` (the input function of each declared column type runs on each value). — `tablefunc.c:428-446,473`
- `compatCrosstabTupleDescs` checks that SQL[0] type == return[0] type and SQL[2] type == every return[1..N] type — but it does **not** check column NAMES. Caller can label columns whatever they want. — `tablefunc.c:1521-1575`
- `crosstab_hash` `load_categories_hash` runs SPI *first*, then `get_crosstab_tuplestore` runs SPI a SECOND time — two round-trips to the planner — `tablefunc.c:730-786,809-815`
- `connectby` SQL template (no orderby): `SELECT %s, %s FROM %s WHERE %s = <literal> AND %s IS NOT NULL AND %s <> %s` — six raw `%s` insertions, one quoted literal — `tablefunc.c:1227-1233`
- `validateConnectbyTupleDesc` enforces: col3 = INT4 (depth), col4 = TEXT if `show_branch`, col5 (or col4 if no branch) = INT4 if `show_serial` — column NAMES are ignored — `tablefunc.c:1408-1463`
- `connectby` uses `strstr(chk_branchstr.data, chk_current_key.data)` for the cycle check — substring match wrapped by `branch_delim` on both sides — `tablefunc.c:1339`
- `get_normal_pair` is Knuth's polar Box-Muller using `pg_prng_double(&pg_global_prng_state)` — `tablefunc.c:288-319`. `pg_global_prng_state` is process-wide; not cryptographically secure but suitable for `normal_rand` use case.

## Trust boundary / Phase D surface — THE BIG ONE

This module is the **highest-value Phase D target** in this slice. It executes user-supplied SQL text via SPI.

### `crosstab(text sql)` and `crosstab_hash(text source_sql, text cats_sql)`

- **The SQL string is executed as the CALLER**: `SPI_connect()` then `SPI_execute(sql, true, 0)` with `read_only=true` — `tablefunc.c:393-396, 730-733, 809-813` [verified-by-code]. So `crosstab` does NOT bypass row-level security or grant the function owner's privileges. **HOWEVER**:
- **SQL-injection sink** — any app passing untrusted text into `crosstab(...)` lets the user execute arbitrary read-only SQL. Patterns like `SELECT * FROM crosstab('SELECT id, cat, val FROM t WHERE user_id=' || $1)` are the dangerous shape. The PG docs warn about this; the module does nothing to defend. [verified-by-code] [ISSUE-INJECTION-CROSSTAB]
- **`read_only=true`**: prevents direct `UPDATE`/`INSERT`/`DELETE` and most catalog modifications, but does NOT prevent SELECT-side leaks (information_schema, pg_*, `pg_read_server_files()`, etc.) — `tablefunc.c:396,733,813`
- **Result composite type is CALLER-supplied**: the function's declared return type (`AS (...)`) dictates how SQL output gets coerced. Caller can declare any return shape; type compatibility is checked column-wise but **NO bound on row width / column count** — only at `compatCrosstabTupleDescs:1521-1575`. A caller declaring 10000 columns will cause `(1 + num_categories) * sizeof(char *)` palloc per row. With `num_categories ≈ 10⁵` and millions of source rows the pivot palloc'd state is O(rows × cols). — `tablefunc.c:478-490, 866-867` [ISSUE-DOS-PIVOT]
- **Categories hash key truncated to NAMEDATALEN-1 (63 bytes)** silently — two categories `"AAAA...AAAA1"` and `"AAAA...AAAA2"` with the same 63-byte prefix are merged. If the second insert is detected (`hentry found`), the macro errors with `ERRCODE_DUPLICATE_OBJECT`, so this is *detected* not *silently wrong* — but only on the SECOND of two equal-prefix categories. Single rows with a 64+ byte category get silently truncated in the lookup hash but presumably also in insert, so they still match. — `tablefunc.c:130-160` [verified-by-code] [ISSUE-TRUNCATION]
- **Tuplestore lives in `per_query_ctx`**, so memory is freed at end of query — bounded by `work_mem` only for spill-to-disk; in-memory tuplestore can exceed `work_mem` for the categories-hash variant before it spills. — `tablefunc.c:463-465, 807, 1163`
- **`SPI_tuptable->vals[]` is indexed without bound-check in crosstab loop**: `call_cntr < max_calls` is the guard at `tablefunc.c:484`, and `proc = SPI_processed` is the bound — safe. — `tablefunc.c:484-506`

### `connectby_text(text relname, text key_fld, text parent_key_fld, text start_with, int max_depth, [text branch_delim])`

- **WORSE injection surface than `crosstab`**: relname / key_fld / parent_key_fld / orderby_fld / branch_delim are **all raw `%s`** in the constructed SQL. Only `start_with` is quoted via `quote_literal_cstr`. — `tablefunc.c:1227-1247` [verified-by-code]
- An adversary calling `connectby('foo; DROP TABLE secret; --', 'k', 'p', '1', 0)` would have the relname string become part of the SQL text: `SELECT k, p FROM foo; DROP TABLE secret; -- WHERE p = '1' ...`. Whether `SPI_execute` with `read_only=true` allows multi-statement injection is the key: SPI's `read_only=true` should reject any non-SELECT. **BUT**: `SPI_execute` allows multiple statements when separated by `;` — the read-only check is per-statement and might still execute SELECTs followed by sub-SELECTs that subvert intent (e.g. `SELECT pg_read_file('/etc/passwd')`). [verified-by-code] [ISSUE-INJECTION-CONNECTBY]
- **`read_only=true`** still allows reading arbitrary tables/system catalogs/`pg_read_server_files()`/`pg_ls_dir()` if the caller has those privileges.
- **Recursion depth**: `build_tuplestore_recursively` recurses C-stack-wise once per level. NO `check_stack_depth()` call. The only guards are `max_depth` (user-supplied) and the cycle-detect via `strstr(chk_branchstr.data, chk_current_key.data)`. With `max_depth=0` (unlimited) and a non-cyclic deep tree, the C stack will overflow before the cycle check fires. — `tablefunc.c:1189-1403` [verified-by-code] [ISSUE-STACK-CONNECTBY]
- **Cycle check is `strstr` substring** — only sound because the comparison strings are wrapped with `branch_delim` on both sides (`%s%s%s` template at `tablefunc.c:1337-1338`). If `branch_delim` is a substring of any key (e.g. delim=`"~"` and a key is `"a~b"`), the wrapping breaks down. Then cycles can either be missed or falsely detected. [verified-by-code] [ISSUE-CYCLE-CHECK]
- **`branch_delim` is also raw `%s` in nothing** — actually it isn't injected into SQL, only used in C-side string building. So this is a logic bug, not an injection vector. — `tablefunc.c:1320,1337,1346`
- **`level + 1` integer overflow**: `level` is an `int`; for ~`INT_MAX` levels you'd overflow. Stack overflow will fire FAR before that. — `tablefunc.c:1381`
- **`serial` is `int *`** and increments without bound — `INT_MAX` serial → overflow → wraps to INT_MIN. Tuple gets stored with negative serial. Functional bug, not a security issue. — `tablefunc.c:1274,1358`
- **`compatConnectbyTupleDescs` only checks columns 0 and 1** — middle/last columns (depth, branch, serial) are validated against fixed types in `validateConnectbyTupleDesc`, not against the SQL output — meaning if user supplies an SQL with 3 columns, columns 2+ are ignored — `tablefunc.c:1468-1516`

### Other

- **`normal_rand`** uses `pg_global_prng_state` — not seeded per-call; predictable from prior outputs. Fine for statistical use, NOT for crypto/security. — `tablefunc.c:299-301`

## Cross-references

- `executor/spi.h` — `SPI_connect`, `SPI_execute`, `SPI_processed`, `SPI_tuptable`, `SPI_getvalue`, `SPI_finish`
- `funcapi.h` — `SRF_*`, `FuncCallContext`, `AttInMetadata`, `TupleDescGetAttInMetadata`, `BuildTupleFromCStrings`
- `utils/builtins.h` — `quote_literal_cstr`
- `utils/tuplestore.h`, `utils/hsearch.h`
- A11 contrib top-4 — `dblink` is the other SPI-via-text-string contrib; similar trust issues, more documented
- `_int_bool.c` — same module's tree-walker shape (no relation; just shows the contrast: parsed types vs raw SQL text)

## Issues spotted

- [ISSUE-INJECTION-CROSSTAB: `crosstab(text)` and `crosstab_hash(text,text)` execute caller-supplied SQL via SPI; standard SQL-injection sink for any caller passing concatenated text (Med-High — well-known, but no in-module mitigation)]
- [ISSUE-INJECTION-CONNECTBY: `connectby_text` interpolates relname/key/parent_key/orderby/branch_delim RAW into SQL with `appendStringInfo("...%s...", relname, ...)`; only `start_with` is `quote_literal_cstr`'d (High — actively dangerous if any of those args is user-controlled)]
- [ISSUE-STACK-CONNECTBY: `build_tuplestore_recursively` has no `check_stack_depth()` — relies on user-supplied `max_depth` (0 = unlimited) and `strstr` cycle check; deep non-cyclic trees crash backend via C-stack overflow (Med)]
- [ISSUE-CYCLE-CHECK: connectby's cycle detection via `strstr` over `branch_delim`-wrapped strings breaks down when `branch_delim` substring appears inside a key (Med)]
- [ISSUE-DOS-PIVOT: `crosstab_hash` allocates O(rows × cols) pivot state with no `work_mem` enforcement; caller-controlled column count amplifies (Low)]
- [ISSUE-TRUNCATION: category names truncated to `NAMEDATALEN-1` (63 bytes) silently inside the hash table; long shared-prefix categories merge or trigger DUPLICATE_OBJECT depending on insert order (Low)]
- [ISSUE-RECHECK-COMPOSITE: caller-supplied composite return type is checked only column-wise (`compatCrosstabTupleDescs`); column names ignored, no width cap — opens room for "I declared 10k columns, please palloc them" (Low)]
- [ISSUE-READ-ONLY-SPI: `SPI_execute(sql, true, 0)` is read-only but does NOT prevent reads of sensitive catalogs (`pg_authid.rolpassword`, `pg_read_server_files`, etc.) — caller's privileges apply (Info — by design)]
- [ISSUE-SERIAL-OVERFLOW: `connectby_text_serial`'s `serial` int wraps at `INT_MAX` (Trivial)]
- [ISSUE-NORMAL-RAND-PRNG: `normal_rand` uses `pg_global_prng_state`; not crypto-safe and not stream-isolated per call (Info)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-tablefunc.md](../../../subsystems/contrib-tablefunc.md)
