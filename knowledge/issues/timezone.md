# Issues — `timezone`

Per-subsystem issue register. See `knowledge/issues/README.md` for the
tag convention, severity scale, and workflow.

**Parent subsystem doc:** (none yet — `src/timezone` is vendored IANA tzcode
plus PG glue; see `knowledge/files/src/timezone/*.md`)

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-07 | localtime.c:104 | undocumented-invariant | nit | `pg_localtime`/`pg_gmtime` share one file-static `struct pg_tm`; non-reentrant contract documented only in-file, not at `pgtime.h` prototypes | open | knowledge/files/src/timezone/localtime.c.md §Potential issues |
| 2026-06-07 | localtime.c:591 | undocumented-invariant | nit | `tzload` scratch + GMT state use raw `malloc`/`free` deliberately (frontend+backend build); rationale not stated at the allocation sites | open | knowledge/files/src/timezone/localtime.c.md §Potential issues |
| 2026-06-07 | strftime.c:465 | undocumented-invariant | nit | `%Z` is the one untrusted-input path (`t->tm_zone` from TZif/POSIX-TZ string); bounded only by `_add`'s `ptlim` guard + overrun-returns-empty; trust boundary documented only in function-header comment | open | knowledge/files/src/timezone/strftime.c.md §Potential issues |
| 2026-06-07 | zic.c:928 | undocumented-invariant | nit | TZif trust boundary: `zic`'s `namecheck`/`writezone` validate on the producer side, but a hand-crafted TZif bypasses `zic` — `localtime.c::tzloadbody`'s load-side checks are the real security boundary; the split is undocumented | open | knowledge/files/src/timezone/zic.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

`src/timezone` is mostly a vendored import of IANA tzcode (`localtime.c`,
`strftime.c`, `zic.c`, `private.h`, `tzfile.h`), kept deliberately close to
upstream so future tzdb merges stay clean. Consequence: most "oddities" are
intentional upstream design (the static result buffer, the `malloc`-not-`palloc`
pattern, the `exit()`-based error model in `zic`), so issues here skew to
`undocumented-invariant`/`nit` — corpus-documentation fixes, not patches.

**What's working (not issues, recorded for triage context):**
- `pgtz.c::scan_directory_ci` skips `.`-prefixed entries — consumer-side
  path-traversal guard for the attacker-influenceable zone name (any role can
  `SET timezone`).
- `localtime.c::tzloadbody` hard-validates every TZif field against `TZ_MAX_*`
  ceilings and rejects malformed files with `EINVAL` rather than crashing.
- `localtime.c::pg_tz_acceptable` rejects leap-second-aware zones that would
  break PG date/time arithmetic.
- `pg_strftime` NUL-terminates and returns empty on overrun rather than emitting
  a truncated/mis-encoded multibyte string.
- `zic.c::namecheck` rejects `..`/`//`/leading-`/` output names; `main` forces a
  conservative umask given root may run it.
