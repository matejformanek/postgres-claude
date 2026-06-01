# `src/backend/utils/misc/ps_status.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~560
- **Source:** `source/src/backend/utils/misc/ps_status.c`

Update the `ps`/`top` display of backend processes ("postgres: user db
host SELECT"). Mechanism is OS-specific and ugly:
- **Linux/BSD-like**: overwrite `argv[0]` storage in place. To get room,
  `save_ps_display_args` (called from main) memcpy's argv and environ to
  fresh storage, then claims the original contiguous block.
- **macOS**: uses `_NSGetArgv` / `_NSGetEnviron`.
- **setproctitle()** path on platforms that have it (FreeBSD).
- **PS_USE_NONE** fallback: no-op.

API: `init_ps_display(activity)`, `set_ps_display(activity)`,
`get_ps_display(&displen)`. `update_process_title` GUC gates whether
`set_ps_display` actually writes — on by default. [from-comment]
(`ps_status.c:1-9`)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
