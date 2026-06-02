# debugging skill — iteration 1 summary

## Scores

| | passed | total | rate |
|---|---|---|---|
| with_skill | 22 | 22 | 100% |
| baseline   | 15 | 22 | 68% |

Lift: +32 percentage points.

## Comparison to locking iteration 1

The locking skill scored 100% / 48% (lift +52pp). The debugging skill has a smaller lift because the baseline is stronger — generic gdb/lldb knowledge already covers pg_backend_pid(), lldb -p, --single, ulimit, and "don't attach to postmaster." The skill earns its keep on the PG-specific details: SIGUSR1 noise, errfinish as a universal ereport trap, pprint(Node*), the -j flag in single-user mode, the macOS Apple-signed-binary cores caveat, and pointers to the project's /pg-attach and /pg-tail-log slash commands.

## Where baseline failed

- Eval 1: missed the project slash commands (/pg-attach), SIGUSR1 silencing, and pprint — 3 of 8 misses.
- Eval 2: missed the macOS suppress-cores-for-signed-binaries caveat and naming errfinish specifically — 2 of 7 misses.
- Eval 3: missed the -j flag / newline-terminator quirk in --single, and the elog(LOG, ...) PID-discovery pattern inside a waitpoint — 2 of 7 misses.

These are exactly the spots the skill should be optimized for.

## Top proposed edits (see proposed-edits.md)

1. E1 — surface /pg-attach and /pg-tail-log at the top of section 2 (biggest miss in the baseline).
2. E2 — promote SIGUSR1 silencing out of the translation table into its own callout.
3. E3 — promote errfinish to a section 5.1 sub-section with a concrete elevel filter expression.
4. E5 — add a 4-row decision-tree table at the top of section 3 so readers pick --single vs -W vs spin-loop without re-reading.

## Observations on skill quality

- Confidence tags ([verified-by-code] / [from-wiki] / [inferred]) are used consistently and helpfully. The section 8 macOS cores section over-discloses uncertainty in a way that hurts readability — consolidate.
- The gdbpg.py non-existence note is a model citation: it tells you what isn't there, preventing wasted searches.
- The skill correctly cross-links build-and-run, error-handling, and locking skills.

## Next iteration

Apply E1–E5; re-run the same three evals; expect baseline pass-rate unchanged but with_skill answers tightened. Then design iteration-2 evals to probe edges the current evals miss — parallel-worker debugging, autovacuum, and the WAL recovery retry-loop case.
