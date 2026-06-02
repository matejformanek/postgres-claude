# Issues — `<subsystem-name>`

Per-subsystem issue register. See `knowledge/issues/README.md` for the
tag convention, severity scale, and workflow.

**Parent subsystem doc:** `knowledge/subsystems/<subsystem-name>.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | path/to/file.c:NNN | leak / correctness / doc-drift / style / stale-todo / dead-path / undocumented-invariant / question | nit / maybe / likely / confirmed / critical | One-sentence summary of the concern | open / triaged | knowledge/files/.../file.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| YYYY-MM-DD | path/to/file.c:NNN | ... | ... | wontfix / submitted / landed | Rationale; or CF# / upstream-commit-sha |

## Notes

(Free-form. Anything that doesn't fit a row but is worth keeping for
this subsystem's issue triage. Examples: "the lock-ordering issues all
trace back to commit X"; "anything in this file with `_internal` is
expected to break across versions"; etc.)
