# _int_bool.c

`source/contrib/intarray/_int_bool.c` (715 lines).

## One-line summary

The `query_int` boolean-query data type's input/output/evaluation engine: tokenizer + recursive-descent parser that produces postfix `ITEM[]`, plus the `execute()` walker that runs a query against either an `int4[]` (exact) or a signature bit-vector (lossy).

## Public API / entry points

- `bqarr_in(cstring) → query_int` — `source/contrib/intarray/_int_bool.c:9,514-589` [verified-by-code]
- `bqarr_out(query_int) → cstring` — `source/contrib/intarray/_int_bool.c:10,687-706`
- `boolop(int4[], query_int) → bool` — `source/contrib/intarray/_int_bool.c:11,416-435`
- `rboolop(query_int, int4[]) → bool` — `source/contrib/intarray/_int_bool.c:12,407-414`
- `querytree` — error stub, removed long ago — `source/contrib/intarray/_int_bool.c:710-715`
- Internal evaluators called by GiST/GIN:
  - `signconsistent(query, sign, siglen, calcnot)` — lossy signature check — `source/contrib/intarray/_int_bool.c:297-303`
  - `execconsistent(query, array, calcnot)` — exact array check — `source/contrib/intarray/_int_bool.c:306-317`
  - `gin_bool_consistent(query, check[])` — GIN consistent helper — `source/contrib/intarray/_int_bool.c:333-359`
  - `query_has_required_values(query)` — used by `ginint4_queryextract` to choose GIN search mode — `source/contrib/intarray/_int_bool.c:396-402`

## Key invariants

- `ITEM.left` is the signed 16-bit offset from current to the LEFT operand; right operand is always at `curitem - 1`. For unary `!` left = -1; for VAL left = 0. — `source/contrib/intarray/_int_bool.c:451-508` [verified-by-code]
- Parser stack depth `STACKDEPTH = 16`. Beyond that, `ereturn(... ERRCODE_STATEMENT_TOO_COMPLEX ...)`. — `source/contrib/intarray/_int_bool.c:147,181-184` [verified-by-code]
- Numeric token buffer `nnn[16]` — any token longer than 16 characters returns `ERR` (syntax error). Means `query_int` can represent integers up to about 15 decimal digits but `strtol` then casts to `int32` and validates round-trip — `source/contrib/intarray/_int_bool.c:50-99` [verified-by-code]
- `findoprnd` enforces `delta >= PG_INT16_MIN`; otherwise `ERRCODE_PROGRAM_LIMIT_EXCEEDED` "query_int expression is too complex" — `source/contrib/intarray/_int_bool.c:494-501` [verified-by-code]
- `makepol`, `execute`, `contains_required_value`, `findoprnd`, and `infix` all call `check_stack_depth()` — `source/contrib/intarray/_int_bool.c:161,268,365,457,614` [verified-by-code]
- Empty queries rejected at input time with `ERRCODE_INVALID_PARAMETER_VALUE` — `source/contrib/intarray/_int_bool.c:541-544`

## Notable internals

- Tokenizer is a hand-rolled DFA with 3 states (`WAITOPERAND`/`WAITENDOPERAND`/`WAITOPERATOR`), single-char lookahead — `source/contrib/intarray/_int_bool.c:47-130` [verified-by-code]
- Operators recognized: `&` (AND), `|` (OR), `!` (NOT, prefix unary), parens `(` `)`. Precedence handled in `makepol` by aggressive flush-on-VAL of `&`/`!` stack entries — `source/contrib/intarray/_int_bool.c:167-187` [verified-by-code]
- Output is **reverse postfix** in memory: rightmost operand has lowest index, root has highest. `execute` starts at `query->size - 1` and walks down — `source/contrib/intarray/_int_bool.c:300-303,314-316,428-430` [verified-by-code]
- `signconsistent` calls `execute` with `calcnot=false` (the `calcnot` argument is named after callers' "calculate NOT") so an `!` subtree returns true regardless — see `execute:274-277` — meaning the GiST signature pass treats `!42` as "anything" (correct for lossy upper-bound check); the exec/leaf path passes `calcnot=true` — `source/contrib/intarray/_int_bool.c:264-292,297-317`
- `gin_bool_consistent` re-maps the GIN-supplied `check[]` array onto the original VAL positions, then runs the same `execute()` — `source/contrib/intarray/_int_bool.c:336-358` [verified-by-code]
- `infix` (out function) doubles its output buffer via `RESIZEBUF` macro — repalloc-based growth, no upper bound — `source/contrib/intarray/_int_bool.c:603-684` [verified-by-code]

## Trust boundary / Phase D surface

This is the **most attacker-reachable parser** in this slice. A `query_int` value flows in as text via `bqarr_in`, gets parsed into a tree, and is later evaluated against indexed/queried `int4[]`.

- **Recursion depth in `makepol`** — recurses into a parenthesised sub-expression at `_int_bool.c:190`. `check_stack_depth()` at line 161 gates it. Cross-link to **A5 jsonapi** finding: jsonapi made a similar architectural choice (per-call stack-depth guard). Here the guard is at the start of every recursive call, so an attacker has to send ~`max_stack_depth/stackframe_size` open-parens. With a typical 2MB stack and ~200-byte frames, that's roughly 10k parens — well within `query_int` size limits → reachable. The guard *should* fire first, but the message will be the generic "stack depth limit exceeded" rather than a `query_int`-specific limit. [verified-by-code] `source/contrib/intarray/_int_bool.c:152-221`
- **`execute()` recursion** — same risk on the evaluation side. Once a `query_int` has been parsed and stored on disk, every search over a GiST/GIN-indexed `int4[]` column walks the tree recursively. The tree depth was bounded at input time by stack-depth and `STACKDEPTH=16` operator-stack; this means the resulting postfix has at most ~16 nested binary ops, so eval recursion is bounded too. **BUT**: `findoprnd` and `contains_required_value` walk the same tree with their own recursion, all gated by `check_stack_depth()`. [verified-by-code] `source/contrib/intarray/_int_bool.c:264-292,361-394,451-508`
- **Operator stack overflow → wrong message**: `STACKDEPTH=16` is hit by deeply LEFT-associative chains like `1 & 2 & 3 & ... & 16 & 17`. The 16-limit is for **unflushed** `&`/`!` operators waiting for the next VAL; since `&` flushes on VAL, normal expressions never approach it. But an all-`!` chain `! ! ! ! ... ! 1` will trigger `lenstack == STACKDEPTH` → `ERRCODE_STATEMENT_TOO_COMPLEX`. [verified-by-code] `source/contrib/intarray/_int_bool.c:147,181-184`
- **`bqarr_out` runaway memory**: `infix()` doubles the buffer each time. For a maximally-large stored `query_int` (~134M ITEM entries, see `_int.md`), the output string could exceed `MaxAllocSize`, but `repalloc` errors out before that. No buffer overflow because `RESIZEBUF` checks `cur-buf + addsize + 1 >= buflen` BEFORE every write. [verified-by-code] `source/contrib/intarray/_int_bool.c:603-608`
- **`pushquery` palloc per token**: `makepol` allocates one `NODE` struct per token in `state->str` (a linked list), then `bqarr_in` walks the list freeing each as it copies into the contiguous `ITEM[]`. Peak memory ≈ `2 * num_tokens * sizeof(NODE+ITEM)` while the list and array coexist. Adversary can blow `CurrentMemoryContext` by sending many small tokens — bounded by `QUERYTYPEMAXITEMS = (MaxAllocSize - HDRSIZEQT)/sizeof(ITEM)` ≈ 134M items ≈ ~3 GB peak. `check_stack_depth` won't catch this; `palloc` will OOM. [verified-by-code] `source/contrib/intarray/_int_bool.c:135-145,538-551`
- **`gin_bool_consistent` mapped_check sizing**: `palloc_array(bool, query->size)` — bounded by stored `query->size`, which was bounded at input. Safe. — `source/contrib/intarray/_int_bool.c:349`
- **NO collation/locale dependency** — `query_int` is pure-numeric, no string compare. So unlike `citext` it doesn't have the A7 `pg_locale_icu` "rules" pathway.
- **`querytree` SQL function**: kept only to emit an error. Useful — old SQL referencing it gets a clear `elog(ERROR)`. — `source/contrib/intarray/_int_bool.c:710-715`

## Cross-references

- `access/gist/*`, `access/gin/*` — invoke the `*consistent` helpers
- A5 jsonapi recursion-depth finding — analogous stack-depth gating pattern
- `_int_gist.c` (signature-tree consistent), `_int_gin.c` (GIN consistent), `_int_selfuncs.c` (uses the same tree walker structure)

## Issues spotted

- [ISSUE-DOS: `bqarr_in` can palloc ~3 GB for a max-size query (134M ITEM); single backend can be made to OOM by parsing 1 carefully-sized text (Low — bounded by MaxAllocSize)]
- [ISSUE-STACK: `makepol` recursion guard is `check_stack_depth()` only; depth bound depends on `max_stack_depth` GUC, not on a hard `query_int`-specific limit (Low — cross-link to A5)]
- [ISSUE-ERRMSG: `STACKDEPTH=16` overflow message is "statement too complex"; user has no way to know it's an intarray-specific limit unrelated to the planner's "statement too complex" (Low)]
- [ISSUE-DOC: `boolop` deliberately ignores the `calcnot=false` semantics on signature-tree leaf checks; the boundary between exact (`execconsistent`, `calcnot=true`) and lossy (`signconsistent`, `calcnot=false`) is subtle and undocumented inside execute() (Info)]
