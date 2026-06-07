# Issues — `port` (src/port platform shims)

Per-subsystem issue register. See `knowledge/issues/README.md` for the
tag convention, severity scale, and workflow.

**Parent docs:** `knowledge/files/src/port/*.md` (no single subsystem synthesis
doc yet; `src/port` is the platform-compatibility shim layer linked into
`libpgport`).

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-06 | path.c:577-645 | undocumented-invariant | maybe | `path_is_safe_for_extraction`'s correctness depends on the input being canonicalized first; `path_contains_parent_reference` only inspects the leading component and gives a wrong answer if called directly on un-canonicalized input. Precondition is in comments, not asserted. | open | knowledge/files/src/port/path.c.md §Potential issues |
| 2026-06-06 | pg_strong_random.c:159 | leak | nit | `/dev/urandom` fallback opens the fd without `O_CLOEXEC`; inherited across any concurrent `exec()` during the open window. fd is closed on the normal path, so not an in-process leak; security-sensitive draws are at fork-not-exec points, so low impact. | open | knowledge/files/src/port/pg_strong_random.c.md §Potential issues |
| 2026-06-06 | quotes.c:35,38 | correctness | nit | `int len = strlen(src)` then `malloc(len * 2 + 1)`: a >INT_MAX input would truncate `len` and undersize the allocation vs the doubling loop. Not reachable today (inputs are short config-string values) but an undocumented size assumption. | open | knowledge/files/src/port/quotes.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

- **Theme: `src/port` hosts the in-tree secret/crypto primitives** the Phase-D
  SecretBuf and constant-time-compare proposals build on: `explicit_bzero.c`
  (scrub), `pg_strong_random.c` (CSPRNG), `timingsafe_bcmp.c` (constant-time
  compare). These are the *correct* mechanisms; the corpus's open secret-scrub
  and timing-attack issues are almost all at the *callers* (A2 libpq, A4 psql,
  A5 common, A11 pgcrypto), not in these primitives themselves.
- **Theme: path-traversal defense.** `path.c` provides the canonicalize +
  parent-reference guard (`path_is_safe_for_extraction`), but deliberately does
  NOT defend against symlink following — that is the A6 pg_rewind/pg_upgrade
  `O_NOFOLLOW` gap, which lives at the `open`/`mkdir` call sites. The two
  findings compose into the Phase-D path-hardening pitch.
- `getaddrinfo.c` was **deleted upstream** before anchor `4b0bf0788b0` (404 at
  the pinned SHA); the ~22 `win32*.c` shims remain undocumented (low priority).
