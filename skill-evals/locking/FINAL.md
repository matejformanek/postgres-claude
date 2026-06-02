# Locking skill — eval summary (iter-1 + iter-2)

## Headline numbers

| Iteration | With-skill | Baseline | Delta |
|---|---|---|---|
| 1 (3 prompts, 21 assertions) | 21/21 = 100% | 10/21 = 47.6% | +52.4 pp |
| 2 (3 harder prompts, 24 assertions) | 24/24 = 100% | 15/24 = 62.5% | +37.5 pp |

## Iter-1 verification

Spot-checked eval-1 (with_skill vs baseline) and eval-3 (baseline) against the grading.json assertions. All 7 of 7 with-skill ticks for eval-1 are supported by the answer text (atomics.h line ranges, BufferDesc.state at buf_internals.h:33-86, README.barrier reference, lwlocklist.h/wait_event_names.txt non-update, "no lock protects it should be documented"). Baseline eval-1 correctly gets 4 ticks: it recommends atomic, mentions that no lock protects it, but lacks any line-number cites and never references the BufferDesc.state gold-standard or the README.barrier prereq.

Eval-3 baseline does identify all four spinlock violations (subroutine call, ereport, CFI, long hold) and recommends ProcArrayLock. The skill's value-add on that prompt is purely citation precision (spin.h:26-29, s_lock.c NUM_DELAYS=1000, README:8-11).

**Iter-1 grading is accurate.** The 100% is real but the assertions skew toward "did you cite the right line range" rather than "did you reach the right conclusion".

## Iter-1 hidden weaknesses identified

1. **Assertion shape**: Most discriminating assertions are line-number trivia. The baseline often reached the correct conclusion in prose and was penalized for "src/include/port/atomics.h" instead of "src/include/port/atomics.h:107-112". This makes the skill look more load-bearing than it is for *correctness*; the real win is *precision*.
2. **No trap questions**: All three iter-1 prompts have the "right" answer aligned with a naive reading. A skilled but un-skill-augmented agent will guess right.
3. **No concrete-edit prompts**: All iter-1 prompts are "walk me through" / "explain". They don't test whether the skill helps with the *what files / what lines* decisions that real patch work requires.

## Iter-2 design

Three harder prompts:

1. **Parallel-aggregate / heavyweight advisory lock trap**: User proposes the "obviously cleanest" answer (advisory lock between leader and workers) and it silently no-ops because of lock-group conflict bypass.
2. **Concrete-edit "register a new built-in LWLock"**: Tests precise knowledge of `lwlocklist.h` append-only convention, `wait_event_names.txt` parallel edit, and the three named-lock patterns (PG_LWLOCK vs RequestNamedLWLockTranche vs DSM-resident).
3. **Code-review trap — ProcArrayLock + syscache**: Commit message uses a true-but-irrelevant justification ("LWLocks are error-safe"). The real bug is lock ordering: SearchSysCache1 takes heavyweight locks + BufMapping LWLocks, so the implicit order is ProcArrayLock -> heavyweight -> BufMapping -> content_lock, which deadlocks silently against any other path.

## Iter-2 results

- All three with-skill answers passed every assertion (24/24).
- Baseline reached the right conclusions on eval-1 (recognized the lock-group trap conceptually) and eval-3 (correctly rejected the error-safety justification and identified the ordering bug), but missed precise line cites (lock.c:1610-1618, README:629-634, README:39-45) and the RELATION_EXTEND exception. Baseline eval-2 missed the lwlocklist.h header-comment cite and the README-update step.
- Net: baseline went from 47.6% to 62.5% on harder prompts, which is the *expected* direction — the harder traps are also more conceptually famous (lock groups, syscache complexity) and a smart baseline catches them.

## Methodology notes

- The grader (me, post-hoc) cannot fully simulate "no-skill" recall — I had to actively avoid referencing lines I'd just read for the with-skill answer. Baseline answers were written first or in a separate mental pass, but bias is non-zero.
- All assertions are objective (a phrase appears or doesn't, a cite includes line numbers or doesn't). No "vibe" assertions.
- 3 prompts is small. The pattern across iter-1 and iter-2 (skill always 100%, baseline 48-62%) is consistent but the variance is large.

## Recommendations

1. **Adopt proposed-edits.md item 4** (the DSM-resident LWLock pattern) — this is a real gap that the skill should cover; iter-2 eval-1 exposed it.
2. **Adopt proposed-edits.md item 2** (promote the heavyweight-lock no-op trap to its own paragraph) — the project plan flags confidently-wrong locking claims as the #1 failure mode, and this is exactly such a trap.
3. The skill is already strong. Items 1 and 3 in proposed-edits.md are nice-to-have but not required.
4. **Future iterations should test multi-step patch work** (e.g. "produce the diff to add FooBarLock and use it"), not just prose answers — that's where line-number precision actually pays off in real patches.

## Artifacts

- `iteration-1/` — original eval (verified accurate).
- `iteration-2/evals.json`, `iteration-2/eval-{1,2,3}/{with_skill,baseline}/answer.md`, `iteration-2/grading.json` — this round.
- `iteration-2/proposed-edits.md` — concrete SKILL.md edits (not applied).
