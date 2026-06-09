# `utils/ps_status.h` — `ps`/`top` process-title management

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/ps_status.h`)

## Role

Sets the process-title string visible to `ps`/`top` on Unix (using
`argv[0]` clobbering or `PR_SET_NAME`-style mechanisms in
`ps_status.c`). Backend's `init_ps_display` sets the fixed part
(`postgres dbname username [host]`), and `set_ps_display` is called
throughout the executor / tcop to advertise current activity ("idle",
"SELECT", "VACUUM", …).

## Public API

- `DEFAULT_UPDATE_PROCESS_TITLE` — true on non-Windows, false on
  Windows (perf overhead). `source/src/include/utils/ps_status.h:16-20`.
- `extern PGDLLIMPORT bool update_process_title` — `:22`. The runtime
  GUC; default per above.
- `char **save_ps_display_args(int argc, char **argv)` — `:24`. Called
  by main() to grab the argv block before someone else trashes it.
- `void init_ps_display(const char *fixed_part)` — `:26`. Sets the
  "anchor" prefix on backend startup.
- `void set_ps_display_suffix(const char *suffix)` / `void
  set_ps_display_remove_suffix(void)` — `:28, 30`. For temporary
  status decorations.
- `void set_ps_display_with_len(const char *activity, size_t len)` — `:32`.
  The workhorse setter.
- `static inline void set_ps_display(const char *activity)` — `:39-43`.
  Inlined so `strlen` evaluates at compile time for string literals.
- `const char *get_ps_display(int *displen)` — `:45`.

## Invariants

- `update_process_title` controls runtime PS updates; when false,
  `set_ps_display` is a no-op. [inferred from name + Windows default]
- The "fixed part" set by `init_ps_display` is never overwritten by
  later `set_ps_display` calls — those only update the suffix region.
  [inferred from naming]
- `save_ps_display_args` must be called before any other code reads
  argv/environ, because the implementation may clobber argv to make
  space for the title. [from-comment in ps_status.c, inferred]

## Notable internals

The actual PS-title mechanism varies by OS — Linux clobbers argv[],
macOS uses `setproctitle` or a similar call. The header hides that.

## Trust-boundary / Phase D surface

- **Does the PS string ever contain query text?** YES — when
  `track_activities` and `update_process_title` are both on (defaults
  true on Unix), `set_ps_display` is called with the current query
  string (truncated). This means a `ps` from another OS user can see
  parts of the running SQL — including query parameter values if they
  appear literally in the text. [ISSUE-security: PS title can leak
  literal query text (including passwords in SQL) to other OS users
  who can run `ps` (confirmed; documented behaviour but worth flagging)]
- `set_ps_display(activity)` takes a `const char *` with no
  sanitisation — null bytes, control chars are passed through to the
  OS PS mechanism. Most platforms truncate at the first NUL but the
  behaviour is platform-specific. [ISSUE-correctness: control chars in
  PS title may render oddly in `ps` output across platforms (nit)]
- The `update_process_title` GUC is `PGC_SUSET` (not exported here
  but it's the default for GUCs without an explicit context). Any
  superuser can flip it. [ISSUE-defense-in-depth: PS title disable is
  PGC_SUSET, not POSTMASTER (nit)]
- Header doesn't expose the maximum title length — the implementation
  truncates silently. A caller that depends on the title surviving
  intact will lose data. [ISSUE-documentation: max PS title length
  undocumented (nit)]

## Cross-refs

- `knowledge/files/src/include/utils/guc.h.md` — `update_process_title`
  GUC, declared via guc_tables.c.
- `source/src/backend/utils/misc/ps_status.c` — the implementation.

## Issues

1. [ISSUE-security: PS title can leak literal query text (incl. password
   strings if pasted in SQL) to any OS user running `ps` (confirmed)] —
   `source/src/include/utils/ps_status.h:32`.
2. [ISSUE-correctness: control characters in PS title behave
   platform-specifically (nit)] —
   `source/src/include/utils/ps_status.h:32`.
3. [ISSUE-defense-in-depth: `update_process_title` is PGC_SUSET, not
   PGC_POSTMASTER (nit)] —
   `source/src/include/utils/ps_status.h:22`.
4. [ISSUE-documentation: max PS title length undocumented (nit)] —
   `source/src/include/utils/ps_status.h:32`.
