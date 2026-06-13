# Queue: pg-quality-auditor — issue-register triage side

Format: `[status] <subsystem>.md <file:line> | <type>/<severity> | seeded=<YYYY-MM-DD>`
Seed rule: auto-seed from `knowledge/issues/<subsystem>.md` registers — any
`open` row whose **Date** column is older than 30 days. Refilled when empty.

ISSUE mode (day-of-year mod 3 == 2) pops the head `[pending]` row, re-fetches
the cited `<path>:<line>` at the anchor SHA, and triages: still-present →
bump `triaged:`; fixed-upstream → mark `landed` + `git log -S`; reproducer
drifted → patch the file:line + inline tag.

## Entries

<!--
NOTE (2026-06-13, pg-quality-auditor): seeded empty. The issue corpus is young
— the earliest `open` register row is dated 2026-06-02. The >30-day staleness
threshold (rows dated on/before 2026-05-14) matches ZERO rows today, so the
ISSUE-mode queue is structurally empty until ~2026-07-02, when the 2026-06-02
cluster crosses 30 days. Until then ISSUE-mode runs rotate to AUDIT mode per
_loader.md §5 ("rotate to the next mode and continue"). The seed will populate
itself on the first run after the threshold is crossed.
-->
