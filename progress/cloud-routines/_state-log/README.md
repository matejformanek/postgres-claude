# `_state-log/` — per-routine STATE.md prepend staging

Sibling cloud routines write one file here per run:

```
progress/cloud-routines/_state-log/<routine>-<YYYY-MM-DD>.md
```

Content: one line (or a few), identical to what used to be prepended
directly to `progress/STATE.md`'s "Last activity" head. Schema:

```
**<routine>** <YYYY-MM-DD> — <summary> (PR #<n>).
```

Each night, `pg-evening-merger` reads every matching file, synthesises
ONE consolidated `**Last activity:** <date> (cloud) — ...` line, and
prepends that single line to `progress/STATE.md`. Sibling routines never
touch STATE.md themselves — that's what caused the recurring
multi-PR-of-the-night merge collisions on 2026-06-08, -09, -12.

See `.claude/cloud/_loader.md` §5.5 for the rule and
`.claude/cloud/pg-evening-merger.md` step 5 for the consolidation pass.

Files here are append-style log entries with no shared state across
routines — no collision surface, even when 8 routines write the same
night.
