# Proposed SKILL.md edits — iteration 1

Iteration 1 pass rate is already 21/21 with_skill vs 13/21 baseline. The
gaps where baseline still scored — basic lowercase/no-period style, the
goto-after-ereport dead-code observation, "can't"→"cannot", elog vs ereport
for cache-lookup — are widely known. The skill's real lift is in the less
obvious mechanics: `errcode_for_file_access`, `OpenTransientFile`,
`PG_FINALLY` vs `PG_CATCH`, `PG_ENSURE_ERROR_CLEANUP` for FATAL, and the
5-frame ERRORDATA_STACK_SIZE limit. Edits below tighten those edges.

---

## Edit 1 — surface `%m` for errno-string interpolation

The skill mentions `errcode_for_file_access()` consumes errno but never
shows the conventional `%m` format specifier that pulls strerror(errno)
into the message. This is the single most common file-error pattern in
the backend and worth one explicit line.

```json
{
  "old_string": "   `errcode_for_file_access()` / `errcode_for_socket_access()` right after the\n   syscall (they consume `errno`).",
  "new_string": "   `errcode_for_file_access()` / `errcode_for_socket_access()` right after the\n   syscall (they consume `errno`). Pair with `%m` in the `errmsg` format\n   string to splice `strerror(errno)` into the message, e.g.\n   `errmsg(\"could not open file \\\"%s\\\": %m\", path)`.",
  "rationale": "%m is the canonical PG idiom and never mentioned. Without it, model writes errmsg(\"open failed: %s\", strerror(errno)) which is wrong (errno may be clobbered before format)."
}
```

## Edit 2 — name `OpenTransientFile` as the ResourceOwner-tracked open()

The skill correctly says "let transaction abort handle ... fds" but
doesn't say *how* fds get registered. Without the name, baseline answers
wave hands at "raw open might leak". Add a one-liner.

```json
{
  "old_string": "It longjmps to the nearest `PG_TRY` or to PostgresMain. **You do not write\ncleanup code after it.** Anything reached \"after\" an ERROR in the source is\ndead code from a runtime perspective. Don't `goto cleanup`; let transaction\nabort handle memory contexts, locks, buffer pins, etc.",
  "new_string": "It longjmps to the nearest `PG_TRY` or to PostgresMain. **You do not write\ncleanup code after it.** Anything reached \"after\" an ERROR in the source is\ndead code from a runtime perspective. Don't `goto cleanup`; let transaction\nabort handle memory contexts, locks, buffer pins, etc.\n\nFor fds specifically, open via `OpenTransientFile()` (registers with the\ntransaction's ResourceOwner so it closes on abort) rather than raw `open(2)`.",
  "rationale": "Skill alludes to xact-abort cleanup but never names the wrapper. OpenTransientFile is the right answer for ~all backend file IO."
}
```

## Edit 3 — promote `PG_FINALLY` as the default, not an afterthought

Currently `PG_FINALLY` appears as one bullet under "When you do use it".
It is in fact the right answer most of the time someone reaches for
PG_TRY (symmetric resource cleanup). Reword to make that the default.

```json
{
  "old_string": "- For symmetric cleanup, prefer `PG_FINALLY` over `PG_CATCH`.",
  "new_string": "- **Prefer `PG_FINALLY` over `PG_CATCH`** whenever the cleanup is the same\n  on success and error (the common case). `PG_FINALLY` auto-rethrows; you\n  can't accidentally swallow the original error. Use `PG_CATCH` only when\n  the error path genuinely needs different work (e.g. converting to a\n  host-language exception).",
  "rationale": "Strengthens the default. Baseline picked PG_CATCH+PG_RE_THROW for the libxml2 case; PG_FINALLY is cleaner and the skill should push it harder."
}
```

## Edit 4 — surface the 5-frame ERRORDATA_STACK_SIZE limit explicitly

The skill says "errors inside CATCH recurse on a 5-frame stack before PANIC"
but doesn't name `ERRORDATA_STACK_SIZE` or its location. Cite location for
verifiability.

```json
{
  "old_string": "- Keep CATCH minimal — errors inside CATCH recurse on a 5-frame stack\n  before PANIC.",
  "new_string": "- Keep CATCH minimal — errors inside CATCH recurse on a 5-frame stack\n  (`ERRORDATA_STACK_SIZE` in `src/backend/utils/error/elog.c:154`) before\n  PANIC.",
  "rationale": "Pins the magic number to a file:line, matches the verification discipline in CLAUDE.md."
}
```

## Edit 5 — call out `%m` interaction with errno-clobbering work

Adjacent to Edit 1: many bugs come from doing extra work (palloc, syscalls)
between the failing call and `ereport`, which clobbers errno. Worth a
one-line warning.

```json
{
  "old_string": "8. **Use `errmsg_internal` for messages that should not be translated**\n   (developer-only \"can't happen\" cases). `elog` already does this.",
  "new_string": "8. **Use `errmsg_internal` for messages that should not be translated**\n   (developer-only \"can't happen\" cases). `elog` already does this.\n9. **Don't clobber `errno` between the failing syscall and the `ereport`.**\n   Any palloc, syscall, or function call may overwrite it. Capture into a\n   local (`int save_errno = errno;`) if you need to do work first, or\n   restore via `errno = save_errno;` before the `ereport`.",
  "rationale": "Common subtle bug. Not in skill today. errcode_for_file_access() and %m both read errno; clobbering breaks both silently."
}
```
