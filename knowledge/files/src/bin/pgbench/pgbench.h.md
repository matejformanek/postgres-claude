# `src/bin/pgbench/pgbench.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~163
- **Source:** `source/src/bin/pgbench/pgbench.h`

Shared interface between `pgbench.c`, `exprparse.y` (bison), and
`exprscan.l` (flex). Lives separately because `pgbench.c` cannot see
flex's `yyscan_t` typedef nor bison's union YYSTYPE — those are
forward-typedef'd here as `void *` / opaque. [from-comment]

## API / entry points

- `PgBenchValueType` enum — `PGBT_NO_VALUE`, `PGBT_NULL`, `PGBT_INT`,
  `PGBT_DOUBLE`, `PGBT_BOOLEAN`. [verified-by-code]
- `PgBenchValue` — tagged union holding one of int64 / double / bool.
- `PgBenchExprType` — ENODE_CONSTANT / ENODE_VARIABLE / ENODE_FUNCTION.
- `PgBenchFunction` enum — the full vocabulary of pgbench expression
  builtins: arithmetic (ADD/SUB/MUL/DIV/MOD/POW/ABS),
  comparison (EQ/NE/LE/LT/IS), logical (AND/OR/NOT), bitwise
  (BITAND/BITOR/BITXOR/LSHIFT/RSHIFT), math (SQRT/LN/EXP/PI),
  conversions (INT/DOUBLE), random distributions (RANDOM /
  RANDOM_GAUSSIAN / RANDOM_EXPONENTIAL / RANDOM_ZIPFIAN), control
  (LEAST/GREATEST/CASE/DEBUG), hash (HASH_FNV1A / HASH_MURMUR2),
  PERMUTE. [verified-by-code]
- `PgBenchExpr` — tagged union with constant / variable / function
  shape. Function carries a `PgBenchFunction` and a linked
  `PgBenchExprLink *args` list.
- `PgBenchExprLink` / `PgBenchExprList` — singly linked list type used
  by the parser to accumulate function arguments. [verified-by-code]
- `expr_yyparse`, `expr_yylex`, `expr_yyerror`, `expr_yyerror_more` —
  bison-generated entry points; `_more` accepts an additional context
  string. Both yyerror variants are `pg_noreturn`. [verified-by-code]
- `expr_lex_one_word`, `expr_scanner_init`, `expr_scanner_finish`,
  `expr_scanner_get_substring` — helpers used by `process_backslash_command`
  in pgbench.c to share psqlscan state with the expression parser.
- `syntax_error(source, lineno, line, command, msg, more, column)` —
  `pg_noreturn` shared error reporter for both meta-command and
  expression parsing. [verified-by-code]
- `strtoint64(str, errorOK, *result)`, `strtodouble(str, errorOK, *dv)`
  — number parsers used by both the lexer and runtime variable
  conversion. [verified-by-code]

## Notable invariants / details

- The `yyscan_t = void *` typedef-trick is documented in lines 18-23:
  flex defines its own opaque pointer, this lets header consumers carry
  it without including flex's generated header. [from-comment]
- `union YYSTYPE` is forward-declared (line 29) similarly so that
  `expr_yyparse`'s signature can mention it without including the
  parser's generated header. [from-comment]
- Adding a new value type or function requires (a) appending to the
  respective enum here, (b) wiring it in `exprparse.y`, (c) implementing
  in `pgbench.c::evaluateExpr` / `evalStandardFunc`. The "/* add other
  types here */" comments at lines 41 and 52 hint at this contract.
  [from-comment]
- `PgBenchFunction` enum is dense and used as an index in some places
  in `pgbench.c`; reordering would break things.
  [inferred]

## Potential issues

- `pgbench.h:160-161` — `strtoint64` and `strtodouble` are declared in
  the pgbench *interface* header but their implementations live in
  `pgbench.c` (as static-globals would be, but they're extern here).
  Acceptable but smells of "one file, multiple roles". [ISSUE-style:
  number parsers live in pgbench.c, declared in shared header (nit)]
- `pgbench.h:38-42` — `PGBT_NO_VALUE = 0` is intentional so that
  zero-initialized memory means "no value", but `PGBT_NULL` is a distinct
  state; the difference matters because `\set` assigning NULL should
  not be confused with "uninitialized". [verified-by-code]
- No version guard on the function enum — adding/reordering will break
  any out-of-tree consumer (there are none in core, but extension authors
  occasionally vendor parts of pgbench). [ISSUE-style: ABI-fragile enum
  (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pgbench`](../../../../issues/pgbench.md)
<!-- issues:auto:end -->
