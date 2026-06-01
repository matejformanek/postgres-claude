# nodeNestloop.c

- **Source:** `source/src/backend/executor/nodeNestloop.c` (401 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (full file is small)

## Purpose

Classic nest-loop join. The simplest of PG's three join executor
nodes — for each outer tuple, rescan the inner subplan and emit
qualifying (outer, inner) pairs. Also the canonical home for
**parameterized inner scans**: nestloop is the only join that can
push outer-row values into the inner subplan as Param values, which
is what makes nestloop-with-inner-index-scan fast. [from-comment] `:15-58`

The file is a single self-contained ~400-line state machine, no
helpers, no headers worth citing beyond `executor/nodeNestloop.h`.

## Entry points

| Function | File:line | Role |
|---|---|---|
| `ExecNestLoop` | `:60` | The `for(;;)` tuple-pull loop; installed as `ExecProcNode` |
| `ExecInitNestLoop` | `:262` | Build NestLoopState, init children, set up null-inner slot |
| `ExecEndNestLoop` | `:362` | `ExecEndNode` on both children |
| `ExecReScanNestLoop` | `:382` | Reset outer if no chgParam, mark NeedNewOuter, NEVER rescan inner here |

## State carried on `NestLoopState`

- `js.jointype` — INNER / LEFT / SEMI / ANTI (others ERROR'd in init).
- `js.single_match` — true for SEMI or planner-proved `inner_unique`;
  after first match for a given outer we stop scanning inner. `:322`
- `nl_NeedNewOuter` — when true, top of loop pulls the next outer
  tuple. Set true at init `:346` and whenever inner returns EOS `:167`.
- `nl_MatchedOuter` — tracks whether the current outer found any
  inner match; drives LEFT/ANTI unmatched-row emission. `:169`
- `nl_NullInnerTupleSlot` — pre-built all-NULL inner slot for LEFT /
  ANTI unmatched rows. `:333`

## The main loop `ExecNestLoop` `:60`

Single `for(;;)`:

1. **Need outer?** `:106-153` Pull outer via `ExecProcNode(outerPlan)`;
   if NULL → return NULL (join EOS). Save into
   `econtext->ecxt_outertuple`, set `NeedNewOuter=false`,
   `MatchedOuter=false`.

   **NestParams pass-down** `:129-146`: walk `nl->nestParams`. Each
   `NestLoopParam` carries a planner-assigned `paramno` and a Var
   pointing at the outer tuple. Copy the outer attribute value into
   `econtext->ecxt_param_exec_vals[paramno]` and add `paramno` to
   `innerPlan->chgParam`. This is the mechanism by which an inner
   IndexScan sees the outer's join-key as a runtime key.

   Then `ExecReScan(innerPlan)` — rewinds inner with the new params.
   `:152`

2. **Pull next inner tuple** `:160`. If inner EOS:
   - Set `NeedNewOuter=true`. `:167`
   - If LEFT/ANTI and `!MatchedOuter`: synthesize the null-inner row
     `:179`, check `otherqual` `:183`, emit if it passes (LEFT) or
     emit-as-is (ANTI also returns the outer-with-nulls per the
     standard's representation, then loops). `:192`
   - `continue` (back to top of loop, will pull new outer).

3. **Have an (outer, inner) pair** `:214-247`:
   - Evaluate `joinqual` (the ON clause). Failure → loop. `:214`
   - On joinqual=true: `MatchedOuter=true`. `:216`
   - **ANTI** → discard this match, set `NeedNewOuter` and loop. `:218-223`
   - **single_match (SEMI / inner_unique)** → set `NeedNewOuter` so we
     stop after this row. `:230`
   - Evaluate `otherqual` (the WHERE clauses pushed into the join).
     If pass → `ExecProject` and return. Otherwise count filtered and
     loop. `:233-247`

4. `ResetExprContext(econtext)` and loop. `:252`

## Init `ExecInitNestLoop` `:262`

Notable: nestloop forbids `EXEC_FLAG_BACKWARD | EXEC_FLAG_MARK`
(asserted `:268`). Build outer first, then **decide inner eflags**:

```
if (node->nestParams == NIL)
    eflags |= EXEC_FLAG_REWIND;
else
    eflags &= ~EXEC_FLAG_REWIND;
```
`:298-301`

Rationale [from-comment] `:291-296`: if inner is independent of outer,
tell it cheap rescans are useful (so e.g. inner Material can cache).
If inner depends on outer (nestParams present), REWIND is pointless
because every rescan brings new param values, so don't ask for it.

Null-inner slot is built only for LEFT / ANTI; SEMI / INNER never
need it. `:326-341`

## ReScan `ExecReScanNestLoop` `:382`

The comment block at `:393-397` is load-bearing: **inner is NOT
rescanned here**, only outer (and only if `outerPlan->chgParam ==
NULL` — if it's set, the first `ExecProcNode(outerPlan)` will rescan
itself). The inner is rescanned per outer tuple inside `ExecNestLoop`,
and rescanning it from here "would get troubles from inner index
scans when outer Vars are used as run-time keys" because the param
values for the FIRST outer haven't been computed yet.

Reset `NeedNewOuter=true, MatchedOuter=false` and return.

## Invariants

- `NeedNewOuter=true` at init and after every inner EOS — outer is
  pulled at top of loop, never elsewhere. [verified-by-code] `:106, 167, 346`
- `MatchedOuter` is set **only** when `joinqual` passes, not when
  `otherqual` passes. The two quals serve different purposes:
  joinqual decides match status (drives outer-join NULL emission),
  otherqual filters output. [from-comment] `:209-211`
- `nestParams` Vars are always `OUTER_VAR` and `varattno > 0` —
  asserted at `:137-139`. [verified-by-code]
- For SEMI / inner_unique: `single_match` short-circuits inner scan
  after first match per outer. `:230`
- ANTI never returns a matched row, only the unmatched-outer
  with-nulls row at inner EOS. `:219, 169-196`
- `JOIN_RIGHT`, `JOIN_FULL`, `JOIN_RIGHT_ANTI`, `JOIN_RIGHT_SEMI` are
  NOT supported by NestLoop — `ExecInitNestLoop` `:339` ERRORs on any
  jointype outside the four cases above. The planner only emits
  hashjoin/mergejoin for those.
- No mark/restore; no backward scan. Asserted at init. [verified-by-code] `:268`

## What's not here (and why it matters)

- No buffering, no inner caching → if the inner is expensive to
  rescan, plan a `Material` above it (planner's job, see
  `match_unsorted_outer` in `joinpath.c`).
- No parallelism beyond what `Gather` above provides — nestloop
  itself is fully serial.

## Cross-refs

- `knowledge/architecture/executor.md` — uses NestLoop as the
  canonical join-node template.
- `.claude/skills/executor-and-planner/SKILL.md` — same.
- `knowledge/files/src/backend/executor/nodeMergejoin.c.md` and
  `nodeHashjoin.c.md` — the other two join nodes; contrast with
  nestloop's "rescan inner per outer" simplicity.
- `knowledge/files/src/backend/executor/execMain.c.md` — EvalPlanQual
  rechecks may run a parallel plan that contains a nestloop.

## Tags

- [verified-by-code] every entry point, state field, and join-type
  branch above.
- [from-comment] the "old comments" specification at `:33-58`, the
  EXEC_FLAG_REWIND comment at `:291-296`, and the ReScan
  inner-not-rescanned comment at `:393-397`.
