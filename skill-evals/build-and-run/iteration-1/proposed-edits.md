# Proposed edits to .claude/skills/build-and-run/SKILL.md

## Edit 1 — Add "restart after install" to the rebuild cycle

**Rationale:** The most common surprise after editing backend C and running
`ninja install` is that `psql` still hits the *old* code. The running
postmaster is mapped to the previous `postgres` image; every fresh backend
it forks is also old. You must `pg_ctl restart` to pick up the new binary.
This is mentioned obliquely under "Linker errors after switching branches"
but not as a first-class step of the rebuild cycle. Eval 1 baseline missed
it; eval 1 with_skill had to infer it.

```json
{
  "old_string": "## Initialize a cluster and start it\n\n```bash\nexport PGDATA=$PWD/dev/data-debug\nexport PATH=$PWD/dev/install-debug/bin:$PATH\n\ninitdb -D \"$PGDATA\" --locale=C --encoding=UTF8\npg_ctl -D \"$PGDATA\" -l \"$PGDATA/server.log\" start\npsql -h /tmp -d postgres\n# ...\npg_ctl -D \"$PGDATA\" stop -m fast\n```",
  "new_string": "## Initialize a cluster and start it\n\n```bash\nexport PGDATA=$PWD/dev/data-debug\nexport PATH=$PWD/dev/install-debug/bin:$PATH\n\ninitdb -D \"$PGDATA\" --locale=C --encoding=UTF8\npg_ctl -D \"$PGDATA\" -l \"$PGDATA/server.log\" start\npsql -h /tmp -d postgres\n# ...\npg_ctl -D \"$PGDATA\" stop -m fast\n```\n\n## The edit -> rebuild -> retest cycle\n\nAfter editing any backend C file:\n\n```bash\nninja -C dev/build-debug install       # incremental — ninja recompiles only what changed\npg_ctl -D \"$PGDATA\" restart            # CRITICAL — see below\npsql -h /tmp -d postgres -c 'SELECT 1;'\n```\n\n**Why the restart is mandatory:** the running postmaster is still mapped to\nthe previous `postgres` image, and every backend it forks for new\nconnections inherits that image. `ninja install` only updates the on-disk\nbinary — without a restart, your edits are invisible. The same applies to\nshared libraries / extensions under `dev/install-debug/lib/` and\n`dev/install-debug/share/`.\n\nSlash-command wrappers that automate this: `/setup-pg` (build+install),\n`/pg-restart` (stop -m fast + start), `/pg-psql` (psql -h /tmp).\nSee `.claude/commands/`."
}
```

## Edit 2 — Show the lldb-launches-single-user idiom

**Rationale:** The skill mentions single-user mode and mentions attaching
lldb to a backend PID, but never connects the two. The best way to debug
startup code is to launch the single-user backend *under* lldb so you're
at instruction 0 with no race. Eval 3 baseline knew the pieces but didn't
combine them; eval 3 with_skill had to invent the syntax. Adding the
exact invocation eliminates the gap.

```json
{
  "old_string": "## Single-user mode\n\n```bash\npostgres --single -D \"$PGDATA\" postgres\n```\n\nRuns the backend in the foreground bound to your terminal. No SQL frontend,\nno fork. Useful for debugging code that runs early in backend startup or for\nrunning short SQL non-interactively under a debugger.",
  "new_string": "## Single-user mode\n\n```bash\npostgres --single -D \"$PGDATA\" postgres\n```\n\nRuns the backend in the foreground bound to your terminal. No SQL frontend,\nno fork. Useful for debugging code that runs early in backend startup or for\nrunning short SQL non-interactively under a debugger.\n\n### Launching single-user mode under lldb\n\nFor startup paths (`InitPostgres`, recovery, GUC bootstrap, shmem init)\nthat run before any client connects, launch the backend *under* the\ndebugger so you're at instruction 0 with no fork race:\n\n```bash\nlldb -- $PWD/dev/install-debug/bin/postgres --single -D \"$PGDATA\" postgres\n(lldb) breakpoint set --name InitPostgres\n(lldb) run\n```\n\nThis sidesteps the per-connection fork problem entirely — there is no\npostmaster, no fork, just one process you control end-to-end.\n\nFor *post-startup* query debugging, attach to a live backend by PID instead\n— see `.claude/commands/pg-attach.md`, which automates the\n`SELECT pg_backend_pid()` + `lldb -p <pid>` flow."
}
```

## Edit 3 — Cross-reference the slash commands inline

**Rationale:** The skill doesn't list the `/pg-*` slash commands that wrap
its own bash recipes. A user who has the skill loaded but doesn't know
about `/pg-test`, `/pg-attach`, `/pg-fresh`, etc., reimplements the wrapper
by hand. Adding a one-line index at the top points future readers at the
batteries-included path.

```json
{
  "old_string": "# build-and-run\n\n## Repo split — important",
  "new_string": "# build-and-run\n\n## Slash-command wrappers (use these first)\n\nThe recipes in this skill are also exposed as slash commands under\n`.claude/commands/`. Prefer them — they encode the right flags and\nguardrails:\n\n- `/setup-pg` — first-time meson setup + build + install (idempotent;\n  `--force` to reconfigure).\n- `/pg-start`, `/pg-stop`, `/pg-restart` — lifecycle.\n- `/pg-psql` — `psql -h /tmp -d postgres` against the dev cluster.\n- `/pg-test [--suite NAME] [--test PAT]` — meson test, always prepends\n  `--suite setup` so the initdb-template trap can't bite.\n- `/pg-attach` — get a backend PID and print the `lldb -p` line.\n- `/pg-tail-log` — follow `dev/data-debug/server.log`.\n- `/pg-fresh --yes` — wipe `data-debug/`, re-initdb (preserves the build).\n- `/pg-reclone-dev` — nuclear: re-clone the whole dev tree from the\n  read-only reference.\n\nThe rest of this file is the underlying mechanics, for cases where you need\nto deviate from the wrappers.\n\n## Repo split — important"
}
```

## Edit 4 — Move/strengthen the rebuild-then-restart warning

**Rationale (lower priority):** the "Linker errors after switching branches"
bullet is the closest existing mention of restart-after-install, but it
buries the issue. Edit 1 above makes it primary; this bullet can stay as a
secondary symptom.

(No change proposed in this iteration — Edit 1 covers it.)
