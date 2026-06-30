# Queue: pg-quality-auditor — skill-regression side

Format: `[status] <skill-slug> last_passrate=<pct|never>`
Refill rule: list `.claude/skills/*/SKILL.md`; entries whose
last-rerun date in this file is > 30 days old go back to `[pending]`.

**Queue repair 2026-06-30 (pg-quality-auditor SKILL mode):** the live
`.claude/skills/` set is **30** skills, but this queue tracked only 21,
and one tracked slug — `gucs-bgworker-parallel` — no longer exists: it
was split upstream into three real skills (`gucs-config`,
`bgworker-and-extensions`, `parallel-query`). The stale slug is retired
below and the **10 untracked skills** are enrolled. The four that carry
`source/<path>:<line>` cites (`gucs-config`, `bgworker-and-extensions`,
`parallel-query`, `pg-feature-plan`) were reran this run via the cloud
cite-verification path against anchor `02f699c14163` — all cites hold
(41/41), so they enter `[done]` at 100%. The six process/meta skills
carry **zero** source cites, so the cloud rerun (which re-verifies
`source/` cites by URL) is not applicable; they are enrolled `[pending]`
with `last_passrate` carried from their `skill-evals/<slug>/FINAL.md`
and a `no-source-cites` note, to be reran in an interactive (not cloud)
SKILL pass.

## Entries

[done:2026-06-09] locking last_passrate=100% reran=2026-06-09
[done:2026-06-09] memory-contexts last_passrate=100% reran=2026-06-09
[done:2026-06-09] memory-keeping last_passrate=100% reran=2026-06-09
[done:2026-06-09] parser-and-nodes last_passrate=100% reran=2026-06-09
[done:2026-06-09] patch-submission last_passrate=100% reran=2026-06-09
[done:2026-06-09] pg-claude last_passrate=100% reran=2026-06-09
[done:2026-06-09] replication-overview last_passrate=96.3% reran=2026-06-09
[done:2026-06-09] review-checklist last_passrate=100% reran=2026-06-09
[done:2026-06-09] testing last_passrate=100% reran=2026-06-09
[done:2026-06-09] wal-and-xlog last_passrate=100% reran=2026-06-09
[done:2026-06-03] access-method-apis last_passrate=100% reran=2026-06-03
[done:2026-06-06] build-and-run last_passrate=100% reran=2026-06-06
[done:2026-06-06] catalog-conventions last_passrate=100% reran=2026-06-06
[done:2026-06-06] coding-style last_passrate=100% reran=2026-06-06
[done:2026-06-06] commit-message-style last_passrate=100% reran=2026-06-06
[done:2026-06-06] debugging last_passrate=100% reran=2026-06-06
[done:2026-06-06] error-handling last_passrate=100% reran=2026-06-06
[done:2026-06-06] executor-and-planner last_passrate=100% reran=2026-06-06
[done:2026-06-06] extension-development last_passrate=100% reran=2026-06-06
[done:2026-06-06] fmgr-and-spi last_passrate=100% reran=2026-06-06

## Retired slug (2026-06-30)

<!--
[retired:2026-06-30] gucs-bgworker-parallel — split upstream into
gucs-config + bgworker-and-extensions + parallel-query (all three
enrolled below). The old combined eval suite lives at
skill-evals/gucs-bgworker-parallel/ (historical); the three successor
skills each have their own skill-evals/<slug>/ suite.
-->

## Enrolled 2026-06-30 (queue repair)

[done:2026-06-30] gucs-config last_passrate=100% reran=2026-06-30 cite-verify=13/13@02f699c14163
[done:2026-06-30] bgworker-and-extensions last_passrate=100% reran=2026-06-30 cite-verify=13/13@02f699c14163
[done:2026-06-30] parallel-query last_passrate=100% reran=2026-06-30 cite-verify=13/13@02f699c14163
[done:2026-06-30] pg-feature-plan last_passrate=100% reran=2026-06-30 cite-verify=2/2@02f699c14163
[pending] meta-commit-style last_passrate=100% no-source-cites (cloud cite-verify n/a; needs interactive rerun)
[pending] pg-feature-brainstorm last_passrate=100% no-source-cites (cloud cite-verify n/a; needs interactive rerun)
[pending] pg-implement last_passrate=100% no-source-cites (FINAL.md iter-2 31/31; cloud cite-verify n/a; needs interactive rerun)
[pending] pg-patch-review last_passrate=100% no-source-cites (FINAL.md iter-2 32/32; cloud cite-verify n/a; needs interactive rerun)
[pending] pg-shadow-implement last_passrate=100% no-source-cites (FINAL.md iter-2 32/32; cloud cite-verify n/a; needs interactive rerun)
[pending] psql last_passrate=100% no-source-cites (FINAL.md iter-2 30/30; cloud cite-verify n/a; needs interactive rerun)
