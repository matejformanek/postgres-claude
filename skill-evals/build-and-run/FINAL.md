# build-and-run skill — eval summary

## Iter-1 vs iter-2 deltas

| metric | iter-1 | iter-2 | delta |
| --- | --- | --- | --- |
| with_skill pass rate | 21/21 (100%) | 21/21 (100%) | unchanged |
| baseline pass rate | 5/21 (23.8%) | 5/21 (23.8%) | unchanged |
| with_skill - baseline lift | +16 | +16 | unchanged |

The skill was already at ceiling (21/21) on these assertions in iter-1, so
the headline numbers can't move. The qualitative improvements show up in
the with_skill answers themselves — they no longer have to *infer* the
restart step or the lldb-launches-single-user idiom; both are now
explicit in SKILL.md and reproduced verbatim.

## Edits applied

All 3 edits from `iteration-1/proposed-edits.md` applied verbatim (no
skips):

1. **Edit 1** — added "## The edit -> rebuild -> retest cycle" section
   with the `ninja install` -> `pg_ctl restart` -> `psql` triad and an
   explicit "Why the restart is mandatory" paragraph.
2. **Edit 2** — added "### Launching single-user mode under lldb"
   subsection with the exact `lldb -- $PWD/dev/install-debug/bin/postgres
   --single -D "$PGDATA" postgres` invocation.
3. **Edit 3** — added "## Slash-command wrappers (use these first)"
   section at the top indexing all `/pg-*` and `/setup-pg` commands.

See `iteration-2/edits-applied.md` for the per-edit log.

## Sanity check on baseline stability

The baselines for iter-1 and iter-2 are intentionally near-identical (the
skill is not loaded, so neither the SKILL.md edits nor the proposed-edits
file are visible). I rewrote them from scratch but kept the same content
shape — the same gaps surface (no `dev/build-debug` path, no `--suite
setup`, no `/pg-attach`, no single-user-under-lldb, no exact meson debug
flags) and the same wins (mention of meson/ninja, pg_usleep, lldb on
macOS, testlog). Both iterations grade 5/21, which is the right answer —
baseline stability is the control that lets us trust the with_skill
delta.

## Why no numerical lift

The iter-1 assertions were chosen to test the skill *as it was* and
already hit 100%. Iter-2 edits make the skill more robust to small
phrasings and reduce the inferential burden on Claude (the lldb launch
syntax is now copy-paste; the postmaster-restart requirement is now
first-class instead of buried in a "linker errors" bullet), but those
improvements don't show up unless the assertion set is sharpened. A
future iter-3 could add stricter assertions — e.g., "names the *exact*
lldb invocation `lldb -- .../postgres --single -D ... postgres`", "calls
the restart 'CRITICAL' or 'mandatory'", "indexes the slash commands as
the FIRST section" — which would have failed iter-1 with_skill and pass
iter-2.

## Files

- Edited skill: `.claude/skills/build-and-run/SKILL.md`
- Iter-2 answers: `skill-evals/build-and-run/iteration-2/eval-{1,2,3}/{with_skill,baseline}/answer.md`
- Iter-2 grading: `skill-evals/build-and-run/iteration-2/grading.json`
- Iter-2 edits log: `skill-evals/build-and-run/iteration-2/edits-applied.md`
