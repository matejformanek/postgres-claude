# Iteration-2 edits applied to `.claude/skills/debugging/SKILL.md`

## Applied

- **E1** — Added "Project shortcuts" callout at top of §2 referencing
  `/pg-attach` and `/pg-tail-log`.
- **E2** — Promoted SIGUSR1 silencing to its own `### First command after
  every attach` sub-heading under the gdb→lldb table, with both lldb and
  gdb forms shown explicitly.
- **E3** — Added §5.1 "Trapping every error (the universal ereport
  breakpoint)" with explicit lldb + gdb commands. Used `ERROR = 21`
  (verified against `source/src/include/utils/elog.h:53`), **not** the
  `20` value the proposal suggested. Proposal's `20` was wrong; verified
  the constant before publishing as the proposal itself instructed.
- **E4** — Restructured §8 into "Prerequisites" (numbered steps with
  expected output) and "Caveats" (Apple-signed binaries + missing-sysctl
  fallback). Replaced the vague "verify on your box" with the concrete
  `unknown oid` diagnostic.
- **E5** — Inserted a 4-row decision-rule table at the top of §3 mapping
  symptoms (pre-shmem / forked-backend startup / worker / live query) to
  tools (--single / -W / spin-loop / lldb -p attach).

## Skipped

- **E6** — Pinning line citations to `progress/files-examined.md` is
  tracking/maintenance work outside the SKILL.md surface; the current
  `[verified-by-code]` cites with explicit file:line are already adequate
  for the eval surface. Skip rationale: not a behavior change visible to
  the evals.
- **E7** — Cross-link to a `knowledge/idioms/log_min_messages.md` doc:
  that doc does not exist in `knowledge/idioms/` (checked). No file to
  link to. Skip.
