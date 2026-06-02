# Proposed edits — iteration 1

Do NOT apply. Discuss with user first.

## Edit 1 — Make the Plan-tag vs PlanState-tag asymmetry explicit

**Where**: SKILL.md, Part A.2 ("Wiring into the central dispatch"), right
after the numbered list of three switches.

**Add a callout box** (or a single sentence) such as:

> **Tag asymmetry**: `ExecInitNode` switches on the **Plan** tag (`T_Foo`)
> because its input is a `Plan *`. `ExecEndNode` and `ExecReScan` switch
> on the **PlanState** tag (`T_FooState`) because their input is a
> `PlanState *`. Mixing them is the most common cause of "unrecognized
> node type" after adding a new node.

**Why**: Eval-3 attempt A only implicitly distinguished them; an explicit
callout removes the ambiguity. Both attempts spent words deriving this
asymmetry from the function signatures — the skill should hand it over
pre-derived.

## Edit 2 — Strengthen MultiExecProcNode visibility

**Where**: SKILL.md Part A.2, the existing `MultiExecProcNode` sentence.

**Current**:

> If your node returns something other than tuples (a hashtable, a bitmap),
> also add a case to **`MultiExecProcNode`** (`execProcnode.c:488`).

**Proposed**: keep the sentence but elevate it from a trailing remark to
its own short bullet "(4)" in the numbered list of switches, with a
counterexample line like:

> 4. **`MultiExecProcNode`** (`execProcnode.c:488`) — **only if** the node
>    returns something other than tuples (Hash builds a hashtable, Bitmap
>    nodes build a TIDBitmap). Tuple-returning scans and joins do NOT
>    need a case here.

**Why**: Eval-3 attempt A forgot to mention it. Listing it as a 4th
switch with an explicit "skip if you return tuples" makes both directions
of the check natural.

## Edit 3 — Add an explicit setrefs.c cite path

**Where**: SKILL.md, "Common mistakes", the `set_plan_references` bullet.

**Current text** ends with:

> A new plan node that holds expressions must be added to
> `fix_*_references_walker` cases or your Vars will not resolve at run time.

**Proposed addition**:

> Concretely: see `set_plan_refs` (`setrefs.c:~1100`, the big switch on
> `nodeTag`) and the `fix_scan_expr` / `fix_join_expr` / `fix_upper_expr`
> walkers below it. New scan-like nodes plug into `fix_scan_expr`; new
> join-like nodes plug into `fix_join_expr`; new nodes operating above
> joins (Agg/Window/Sort-like) use `fix_upper_expr`.

**Why**: The skill flags the issue but doesn't tell Claude where to
look. With this addition the answer to "now how do I actually wire
it?" is in the skill instead of requiring a grep round-trip. Note:
the exact line number should be verified before committing this edit.

## Edit 4 — Tiny: link to the parser-and-nodes skill from A.1 too

**Where**: A.1 table, after the row about implementing functions.

**Why**: The skill mentions `gen_node_support.pl` in A.6 but a forward
reference earlier (e.g., "see parser-and-nodes skill for what NodeTag
machinery you'll need before any of this compiles") would help readers
who land on A.1 cold.

This is a nice-to-have; the existing A.6 mention is already adequate.

## Non-edits considered and rejected

- **Adding a worked example for a tuple-returning custom node**. The
  skill already cites `nodeSeqscan.c` as the template and `nodeNestloop.c`
  for joins. Adding a synthetic example would inflate the skill without
  buying calibration accuracy.
- **Restructuring Part B around the planner**. Both eval-2 attempts
  produced correct answers — the existing pipeline diagram + Path/Plan
  split was sufficient. Leave alone.
