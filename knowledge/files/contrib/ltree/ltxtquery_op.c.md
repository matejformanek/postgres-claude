# ltxtquery_op.c

## One-line summary

Evaluates an `ltxtquery` boolean expression against an `ltree`: `ltree_execute` is the recursive polish-notation walker (used by both the leaf-level recheck here AND the GiST signature-based pre-filter in `ltree_gist.c:gist_qtxt`), and `checkcondition_str` is the leaf predicate — "does query operand `op` match ANY level of the ltree?".

## Public API / entry points

- `Datum ltxtq_exec(PG_FUNCTION_ARGS)` (line 82, `PG_FUNCTION_INFO_V1`) — `ltree @ ltxtquery` operator (strategy 14/15). Sets up `CHKVAL` and calls `ltree_execute`.
- `Datum ltxtq_rexec(PG_FUNCTION_ARGS)` (line 103) — commutator.

Exported:

- `bool ltree_execute(ITEM *curitem, void *checkval, bool calcnot, bool (*chkcond)(void *, ITEM *))` (line 20) — generic polish-notation walker; `calcnot` controls whether `!` is actually evaluated (false at GiST inner-node level, true at leaf).

Internal:

- `static bool checkcondition_str(void *checkval, ITEM *val)` (line 55) — for each ltree level, run `compare_subnode` (if `%`) or `ltree_label_match` against the operand. Returns true on FIRST matching level (existential).

## Key invariants

- INV-EXECUTE-CHECK-STACK: `ltree_execute` (line 20) calls `check_stack_depth()` on every recursive entry (line 23). Same defense as `ltxtquery_io.c` parsers. `[verified-by-code]`
- INV-CALCNOT-FALSE-AT-INNER-NODES: when `calcnot == false` (inner GiST node), `!` items return `true` unconditionally (line 30-32). The signature filter cannot prove a NOT, so it must conservatively pass it up — leaf check then evaluates `!` for real. `[verified-by-code]`
- INV-EXISTENTIAL-LEVEL-MATCH: `checkcondition_str` iterates ALL levels of the ltree and returns true on first match (lines 64-77). A single matching level satisfies the operand.
- INV-POLISH-LEFT-LINK: binary operators use `curitem + curitem->left` for left operand and `curitem + 1` for right (lines 35, 42). Set by `findoprnd` in `ltxtquery_io.c:311`. `[verified-by-code]`
- INV-SHORT-CIRCUIT-AND-OR: `&` evaluates left then short-circuits on false (line 35-38); `|` evaluates left then short-circuits on true (line 42-45). `[verified-by-code]`

## Notable internals

- `ltree_execute` is a 3-way switch on `curitem->type` (VAL → call callback; `!` → recurse and invert; `&`/`|` → recurse into both children).
- For operators, the LEFT operand is at `curitem + curitem->left` because `findoprnd` stores the offset. The RIGHT operand is at `curitem + 1` (the immediately following ITEM, since postfix order puts the right child immediately before the operator).
- `checkcondition_str` reuses `compare_subnode` and `ltree_label_match` from `lquery_op.c`. So the `%` (sublexeme) and `@` (case-insensitive) match semantics are exactly the same as in lquery.
- `calcnot` is the lever that allows the same `ltree_execute` to serve both leaf recheck AND GiST inner-node consistent checks. At inner-node level, the signature can prove "this operand IS in the signature" or "this operand might be in the signature (it's set, so true)"; but it cannot prove "this operand is NOT in the index for this subtree" without scanning leaves. So `!` must conservatively pass. The `calcnot=false` mode is used by `ltree_gist.c:gist_qtxt` (line 588).

## Trust boundary / Phase D surface

- **Recursive walker, bounded by ltxtquery's own validated tree shape**: `ltree_execute` recurses to depth = ltxtquery operator-tree height. The tree was validated by `findoprnd` in `ltxtquery_io.c` (which also calls `check_stack_depth`), so values that PARSED successfully will EVALUATE successfully on the same backend's stack. But a query parsed on a backend with `max_stack_depth = 8 MB` then SELECTed on a backend with `max_stack_depth = 1 MB` could potentially hit the lower limit during eval. `check_stack_depth()` at line 23 catches it. `[inferred + verified-by-code]`
- **`checkcondition_str` is O(numlevel)**: scans all ltree levels for a match. For an ltree of 65535 levels and a query of N operands, total leaf-level work is `O(numlevel × num_operands_evaluated)`. With short-circuiting on `&` and `|`, the actual work is typically << N × numlevel.
- **No interrupt check in `ltree_execute`**: a malicious ltxtquery against a 65535-level ltree could take significant time. `check_stack_depth` bounds depth but not breadth. Long expressions deep in a `&` chain run to completion before responding to cancel. Cross-link to `lquery_op.c.md` ISSUE — `lquery_op.c:checkCond` DOES have `CHECK_FOR_INTERRUPTS()` (line 191) but this matcher does not.
- **No quadratic in this file** — the matcher itself is O(query_size × ltree_levels). Quadratic comes from the `compare_subnode` (`%` mode) path in `lquery_op.c`.

## Cross-references

- `source/contrib/ltree/ltxtquery_io.c:368` — `queryin` produces the `ITEM[]` array consumed here.
- `source/contrib/ltree/lquery_op.c:43,80` — `compare_subnode` and `ltree_label_match` reused by `checkcondition_str`.
- `source/contrib/ltree/ltree_gist.c:567-589` — `checkcondition_bit` + `gist_qtxt` use `ltree_execute` with `calcnot=false` and a signature-bit callback.
- `source/contrib/ltree/_ltree_gist.c:415-437` — parallel path for `ltree[]` GiST.
- `source/contrib/ltree/ltree.h:138-176` — `ITEM` struct + `VAL`/`OPR`/`VALTRUE` type codes.

<!-- issues:auto:begin -->
- [Issue register — `ltree`](../../../issues/ltree.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-security: `ltree_execute` has no `CHECK_FOR_INTERRUPTS()`. With a deeply nested ltxtquery (depth N) against a long ltree (M levels), total node visits ≈ N × M leaf-callback invocations interleaved with operator-node visits, all uninterruptible at this level. (likely — uninterruptible eval inner loop)] — `source/contrib/ltree/ltxtquery_op.c:20-47`.
- [ISSUE-correctness: line 35 `&`-operator: `if (ltree_execute(curitem + curitem->left, ...)) return ltree_execute(curitem + 1, ...)` — evaluates LEFT first, then RIGHT only if LEFT is true. So short-circuit is correct. `|` at line 42 evaluates LEFT first, returns true on left-true, else RIGHT. Standard. (verification only)] — `source/contrib/ltree/ltxtquery_op.c:33-46`.
- [ISSUE-doc: line 56-79 `checkcondition_str` iterates ALL levels of `chkval->node`. The `@>` semantics aren't explicit — the operand `foo` matches the ltree `a.b.foo.c` because the third level matches. This is the documented "any-level" behavior, but a comment here would help. (nit)] — `source/contrib/ltree/ltxtquery_op.c:55-80`.
- [ISSUE-correctness: `calcnot` parameter passing is via signature (`bool calcnot`), with no enum / no documentation here. Cross-references show two values used: `true` at line 95 (leaf) and `false` at `ltree_gist.c:588`. Reader must trace both call sites to understand. (nit — minor API ergonomics)] — `source/contrib/ltree/ltxtquery_op.c:20`.
