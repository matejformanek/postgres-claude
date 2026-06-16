# ltxtquery_io.c

## One-line summary

I/O for `ltxtquery` (boolean text-query language with `&`, `|`, `!`, parentheses, and `@%*` operand modifiers — like tsquery but matching against ltree labels). Implements a hand-rolled recursive-descent parser (`makepol` + `gettoken_query`) that emits reverse-polish notation into a linked list, then a second recursive pass (`findoprnd`) computes the left-operand back-link for every operator. Both passes call `check_stack_depth()`. The output deparser (`infix`) is also recursive.

## Public API / entry points

- `Datum ltxtq_in(PG_FUNCTION_ARGS)` (line 443, `PG_FUNCTION_INFO_V1`) — text → `ltxtquery`.
- `Datum ltxtq_out(PG_FUNCTION_ARGS)` (line 607) — `ltxtquery` → infix-notation text.
- `Datum ltxtq_send(PG_FUNCTION_ARGS)` (line 638) — wire: `int8 version=1 + pq_sendtext(deparsed)`.
- `Datum ltxtq_recv(PG_FUNCTION_ARGS)` (line 463) — wire: `int8 version + pq_getmsgtext` → re-parse through `queryin`.

Internal:

- `static int32 gettoken_query(QPRS_STATE *state, int32 *val, int32 *lenval, char **strval, uint16 *flag)` (line 60) — lexer state machine, returns `VAL` / `OPR` / `OPEN` / `CLOSE` / `END` / `ERR`.
- `static bool pushquery(...)` (line 154) — append to reverse-polish linked list.
- `static bool pushval_asis(...)` (line 181) — append a VAL token + grow the operand buffer.
- `static int32 makepol(QPRS_STATE *state)` (line 213) — **recursive** descent for parenthesized sub-expressions with a shift-reduce stack (max depth 32 via `STACKDEPTH`).
- `static bool findoprnd(QPRS_STATE *state, ITEM *ptr, int32 *pos)` (line 311) — **recursive** post-order walk filling `ITEM.left` back-links.
- `static ltxtquery *queryin(char *buf, struct Node *escontext)` (line 368).
- `static void infix(INFIX *in, bool first)` (line 507) — **recursive** infix deparser.

## Key invariants

- INV-LTXTQUERY-SIZE-CAPS: `LTXTQUERY_TOO_BIG(size, lenofoperand)` (`ltree.h:162`) caps `size * sizeof(ITEM) + lenofoperand ≤ MaxAllocSize - HDRSIZEQT`. Enforced at line 402. `[verified-by-code]`
- INV-DISTANCE-U16: per-operand byte offset into the operand string is stored in `ITEM.distance` (`uint16`); parser rejects `distance > 0xffff` at line 162 in `pushquery`. `[verified-by-code]`
- INV-OPLEN-U8: per-operand byte length is stored in `ITEM.length` (`uint8`); parser rejects `lenval > 0xff` at line 166. `[verified-by-code]`
- INV-WORD-U16: `pushval_asis` enforces `lenval ≤ 0xffff` (line 184) — stricter is already done by `pushquery` at u8. Redundant safety check; not unreachable because some callers may compute different lenvals (not in current source though).
- INV-LEFT-U16-OFFSET: `findoprnd` (line 311) computes the binary-operator left-link as `delta = *pos - mypos` and rejects `delta > PG_INT16_MAX` at line 351. `[verified-by-code]`
- INV-PARENS-BALANCED: `state->count` tracks open-paren depth; `gettoken_query` returns `ERR` if `count < 0` (line 129) and `queryin` errors on unbalanced via `state.count` check (line 133).
- INV-NONEMPTY-QUERY: `queryin` rejects empty query with `errmsg("syntax error"), errdetail("Empty query.")` at line 396. `ltxtq_out` and `ltxtq_send` also check `query->size == 0` (lines 613, 646) to defend against on-disk-corrupted empty queries.
- INV-STACKDEPTH-32: the per-call shift-reduce stack in `makepol` is `int32 stack[STACKDEPTH]` (line 220) with `STACKDEPTH = 32` (line 209). Overflow raises `elog(ERROR, "stack too short")` at line 252. **Note: this is per-recursive-call**; recursion happens for parens, so total operator nesting is bounded by `max_stack_depth` × 32-per-frame. `[verified-by-code]`
- INV-CHECK-STACK-IN-RECURSIVE-FUNCS: `makepol` (line 225), `findoprnd` (line 317), `infix` (line 511) all call `check_stack_depth()` on entry. `[verified-by-code]`
- INV-RECV-VERSION-1: `ltxtq_recv` rejects anything but version 1 at line 472. `[verified-by-code]`

## Notable internals

- The parser does the classic shift-reduce dance for boolean precedence: `!` and `&` are higher-precedence than `|`. On encountering a VAL after a `&`/`!`, the stack is popped while top is `&` or `!` (lines 234-240). On `|`, the OR is pushed onto the stack BUT also immediately emitted via `pushquery` (lines 243-247) — this is unusual: `|` is pushed AND output, effectively as a left-associative operator emitted in postfix order.
- `makepol` recurses on `OPEN` (`(...)`) at line 258. Inside the recursion the local `stack[32]` is fresh. Returning, the OUTER stack picks up where it was.
- The reverse-polish list (`state->str`) is built head-first (each `pushquery` prepends at line 172). The final `for` loop in `queryin` at line 414-424 copies the list into a flat `ITEM[]` array — items end up in postfix order (operator AFTER its operands).
- `findoprnd` walks the postfix array top-down: at each position, the entry-time `*pos` is the OPERATOR (or VAL); for binary ops it recurses to scan the RIGHT operand first (advancing `*pos`), then records `delta = *pos - mypos` as the offset to the LEFT operand's top, then recurses again into the left.
- `pushval_asis` (line 181) computes the CRC32 of the operand string via `ltree_crc32_sz(strval, lenval)` (line 189) and stores it in `ITEM.val`. This is what GiST signature lookups use (`ltree_gist.c:checkcondition_bit`).
- `infix` (line 507) is recursive: for binary operators it palloc's a fresh `INFIX nrm` (line 582), recurses to scan the right operand into `nrm.buf`, then recurses to scan the left into `in->buf`, then sprintf's the operator + nrm.buf. This is left-associative reconstruction from the postfix form. The recursion depth equals the tree height.

## Trust boundary / Phase D surface

- **Three recursive functions, all with `check_stack_depth()`**: contrast with the iterative `parse_ltree`/`parse_lquery` in `ltree_io.c`. **Stack depth is bounded by `max_stack_depth` GUC (default 2 MB; 100 KB per frame max → ~20K levels of nesting).** Cross-link to A5: jsonapi's incremental parser uses an explicit 6400-byte limit; ltxtquery uses `check_stack_depth` (which fires at `max_stack_depth` minus a safety margin). For typical configs this means ~10K nested parens are accepted before stack overflow protection kicks in. `[verified-by-code]`
- **Recursion in `infix` mirrors recursion in `makepol`** — any depth that survives parsing also survives deparsing. So a stored ltxtquery with 10K nested operators round-trips through `_out` without crash.
- **Binary protocol uses text format**: `ltxtq_recv` reads version byte + `pq_getmsgtext` + feeds to `queryin`. **No separate binary-format ABI to attack** — same defense as ltree/lquery recv. `[verified-by-code]`
- **`LTXTQUERY_TOO_BIG` is the only size cap** — bounds total `ITEM[]` count + operand bytes by `MaxAllocSize`. Per-ITEM `distance` is u16 (cap 65535) and `length` is u8 (cap 255). So per-call max items is ~10M and per-operand max bytes is 255. A query with millions of operands totalling many MB is possible; the parser handles it iteratively at the token level but recurses on parens.
- **`STACKDEPTH = 32` per-frame**: a single non-parenthesized expression cannot push more than 32 operators on the shift-reduce stack before a forced reduction. The error message "stack too short" (line 252) is reachable only when more than 32 RIGHT-pending operators accumulate — e.g. `!!!!!...` (32 `!`s) before a VAL. Then it errors out. Bounded.
- **No CHECK_FOR_INTERRUPTS in parser loops**: a 1-GB ltxtquery text input would parse for many seconds without responding to Ctrl-C. Less concerning than lquery_op's backtracking (which IS interruptible) because parser cost is linear.
- **CRC32 collision class**: see `crc32.c.md`. `ltree_crc32_sz` produces 32-bit fingerprints that index into the GiST signature; two operands with the same CRC give identical signature contributions. Not a security boundary but a precision bound.

## Cross-references

- `source/contrib/ltree/ltree.h:138-176` — `ITEM` struct + `ltxtquery` layout + `ISOPERATOR`/`END`/`VAL`/`OPR` constants.
- `source/contrib/ltree/ltxtquery_op.c:20` — `ltree_execute` evaluates the polish-notation tree.
- `source/contrib/ltree/ltree_gist.c:567-589` — `checkcondition_bit` uses `ITEM.val` (CRC32) for signature lookup; `gist_qtxt` invokes `ltree_execute` with that callback.
- `source/contrib/ltree/crc32.c` — `ltree_crc32_sz`.
- `source/src/include/miscadmin.h` — `check_stack_depth`.
- `source/src/include/nodes/miscnodes.h` — `SOFT_ERROR_OCCURRED`, `ereturn`.
- A5 jsonapi finding — recursive vs iterative parser stack discipline. ltxtquery follows the recursive + check_stack_depth pattern; lquery is iterative.

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `makepol` recurses on every `OPEN` token (line 258). With `(((((...)))))` of depth N, the C stack grows linearly. `check_stack_depth()` (line 225) catches before overflow, but the default `max_stack_depth = 2 MB` and frame size ~150 bytes give ~13000 nesting levels. A 1-MB input of `((((` would parse before erroring. Cancel via statement_timeout works at the token level only if `CHECK_FOR_INTERRUPTS` were called — and it isn't. (likely — slow-fail parser DoS)] — `source/contrib/ltree/ltxtquery_io.c:213-294`.
- [ISSUE-security: `findoprnd` (line 311) recurses post-order over the same tree. Same depth bound, same `check_stack_depth()` defense (line 317). Two-pass recursion means the depth is hit twice per parse but no double-deep recursion. (verification only)] — `source/contrib/ltree/ltxtquery_io.c:311-362`.
- [ISSUE-security: `infix` (line 507) recurses for output and also palloc's a fresh `INFIX nrm` buffer per recursion frame (line 582). Output of a 10K-nesting query would consume 10K × (16-byte buffer + grown via RESIZEBUF) = order-of-MB and 10K stack frames. Bounded but expensive. (nit)] — `source/contrib/ltree/ltxtquery_io.c:507-604`.
- [ISSUE-cost: no `CHECK_FOR_INTERRUPTS()` in `gettoken_query` / `makepol` / `findoprnd` / `infix`. A 1-GB malformed query input cannot be cancelled mid-parse; only at function-call boundary. (nit — generic to many PG parsers)] — `source/contrib/ltree/ltxtquery_io.c:60-149`.
- [ISSUE-correctness: line 209 `STACKDEPTH = 32`. The error `elog(ERROR, "stack too short")` at line 252 uses `elog` (NOT `ereport`/`ereturn`) — this is a hard error, not soft. So `COPY ... ON_ERROR ignore` on a row containing `!!!!!...` (>32 NOT operators) would fail the whole COPY. (nit — minor inconsistency with soft-error pathway elsewhere in this file)] — `source/contrib/ltree/ltxtquery_io.c:250-252`.
- [ISSUE-API-shape: `ltxtq_send` (line 638) round-trips the query through `infix` (line 657) — i.e. send re-deparses to text. The text form may not be byte-identical to the original input (e.g. parens canonicalized, whitespace normalized). A client doing `SELECT q::text FROM tab` and `SELECT q FROM tab` via binary may see two different strings for the same query value. (nit)] — `source/contrib/ltree/ltxtquery_io.c:644-662`.
- [ISSUE-correctness: line 351 `if (unlikely(delta > PG_INT16_MAX))` — checked once per binary operator. But ITEM.left is `int16` (signed); `delta` is always positive (operator points to LEFT operand at smaller index, but `delta = *pos - mypos` where `*pos > mypos`, so positive). The check is correct. The Assert at line 350 (`delta > 0`) backs this up. (verification only)] — `source/contrib/ltree/ltxtquery_io.c:348-355`.
- [ISSUE-correctness: line 282-285 `ereturn(state->escontext, ERR, ...)`. The `pg_fallthrough` at line 280 (preceded by an `if (SOFT_ERROR_OCCURRED(state->escontext))` early-return) handles the case where a soft error was already raised in `gettoken_query`. Clean handling, but the fallthrough into `default:` for the `ERR` case after soft-error-already-set is subtle. (nit — defensible)] — `source/contrib/ltree/ltxtquery_io.c:277-285`.
