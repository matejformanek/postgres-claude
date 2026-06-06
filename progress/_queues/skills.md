# Queue: pg-quality-auditor — skill-regression side

Format: `[status] <skill-slug> last_passrate=<pct|never>`
Refill rule: list `.claude/skills/*/SKILL.md`; entries whose
last-rerun date in this file is > 30 days old go back to `[pending]`.

## Entries

[pending] locking last_passrate=never
[pending] memory-contexts last_passrate=never
[pending] memory-keeping last_passrate=never
[pending] parser-and-nodes last_passrate=never
[pending] patch-submission last_passrate=never
[pending] pg-claude last_passrate=never
[pending] replication-overview last_passrate=never
[pending] review-checklist last_passrate=never
[pending] testing last_passrate=never
[pending] wal-and-xlog last_passrate=never
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
[done:2026-06-06] gucs-bgworker-parallel last_passrate=100% reran=2026-06-06
