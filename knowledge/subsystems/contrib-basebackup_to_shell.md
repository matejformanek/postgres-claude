# contrib-basebackup_to_shell (basebackup output to shell pipe)

- **Source path:** `source/contrib/basebackup_to_shell/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Loading model:** `shared_preload_libraries` (no `.control`)
- **Surface:** zero SQL functions; one `pg_basebackup` target

## 1. Purpose

Pipe the output of `pg_basebackup` to a shell command. Lets
pg_basebackup stream archives (tar files + manifest) into an
arbitrary processing pipeline — encryption, compression,
remote upload — without ever materializing intermediate
files. The reference implementation of the
**custom basebackup target** API introduced in PG 15.

Like `basic_archive`, it's a teaching reference more than a
production tool. The shell-template approach has the same
quoting + safety caveats as the legacy `archive_command`.

## 2. The sink interface

[verified-by-code `basebackup_to_shell.c:55-68`]

```c
static const bbsink_ops bbsink_shell_ops = {
    .begin_backup        = bbsink_forward_begin_backup,
    .begin_archive       = bbsink_shell_begin_archive,
    .archive_contents    = bbsink_shell_archive_contents,
    .end_archive         = bbsink_shell_end_archive,
    .begin_manifest      = bbsink_shell_begin_manifest,
    .manifest_contents   = bbsink_shell_manifest_contents,
    .end_manifest        = bbsink_shell_end_manifest,
};
```

A `bbsink` is the output target for a base backup. Each
piece of data (per-archive tar file, per-archive manifest)
fires the callbacks in order: begin → contents (many calls)
→ end.

`basebackup_to_shell` implements them by forking the shell
command and piping data to its stdin.

## 3. The bbsink_shell struct

[verified-by-code `basebackup_to_shell.c:25-43`]

```c
typedef struct bbsink_shell
{
    bbsink   base;                  /* inherits from bbsink */
    char    *target_detail;         /* user-supplied detail */
    char    *shell_command;         /* template */
    char    *current_command;       /* expanded for this archive */
    FILE    *pipe;                  /* fork+pipe handle */
} bbsink_shell;
```

The first field `base` allows polymorphic chaining — the
shell sink wraps an underlying sink, and `bbsink_forward_*`
delegates piece-by-piece.

## 4. The shell-command template

The GUC `basebackup_to_shell.command` accepts a template:

```ini
basebackup_to_shell.command = 'gzip > /backup/%f.gz'
```

Template variables:
- **`%f`** — archive name (e.g. `base.tar`, `oid_16384.tar`).
- **`%d`** — target detail (user-supplied option).
- **`%%`** — literal `%`.

Per archive, the template is expanded and forked. The
backup stream is written to the pipe.

## 5. Usage

```sql
-- via pg_basebackup CLI:
pg_basebackup --target=shell --target-detail='upload-id-42' -D /dev/null
```

`-D /dev/null` because the data isn't being written to a
client-side directory — it's flowing through the server-side
shell pipe instead.

`--target-detail` populates the template's `%d` variable —
useful for per-backup state (encryption key id, upload
session id, etc.).

## 6. The permission gate

The GUC `basebackup_to_shell.command` can only be set in
`postgresql.conf` (or via `ALTER SYSTEM`). Per-session SET
is rejected.

In addition, the `target_detail` must validate against the
sink's check function `shell_check_detail` — extension can
restrict which details are acceptable.

## 7. Production-use guidance

- **DON'T use this in production.** The shell-template
  approach has the same security + reliability issues as
  legacy `archive_command`.
- **For real backup-to-cloud**: write a custom `bbsink`
  that calls cloud-storage APIs directly (no shell).
- **For local backup with compression**, `pg_basebackup
  --gzip` is built-in.
- **The reference value**: study this code to understand
  `bbsink_ops` before writing your own sink.

## 8. The shell pitfalls

- **No `fsync` on the destination** — the shell command must
  add its own.
- **Pipe buffer is finite** — slow downstream consumers
  block the basebackup.
- **Errors from the shell** are reported via pipe-close
  status; intermediate failures may not be noticed until
  end-of-archive.

## 9. Invariants

- **[INV-1]** No SQL surface; activated via
  `shared_preload_libraries` + `--target=shell`.
- **[INV-2]** Sink-op chain: begin → contents → end per
  archive.
- **[INV-3]** Template variables: `%f`, `%d`, `%%`.
- **[INV-4]** Detail validation via `shell_check_detail`
  callback.
- **[INV-5]** Reference implementation; not for production.

## 10. Useful greps

- The sink-op registrations:
  `grep -n 'bbsink_shell_ops\|bbsink_shell_begin' source/contrib/basebackup_to_shell/basebackup_to_shell.c | head -10`
- The base API:
  `grep -n 'bbsink_ops\|BaseBackupTargetMethod' source/src/include/backup/basebackup_target.h | head -10`
- Other sinks (built-in):
  `find source/src/backend/backup -name 'basebackup_*' | head -10`

## 11. Cross-references

- `knowledge/subsystems/contrib-basic_archive.md` —
  sister reference: archive_library reference impl.
- `knowledge/subsystems/replication.md` — base backup is
  part of the replication-setup story.
- `knowledge/idioms/archive-command-fallback.md` — companion
  shell-template caveats.
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL + backup
  contracts.
- `source/src/include/backup/basebackup_target.h` — the
  target API.
- `source/contrib/basebackup_to_shell/basebackup_to_shell.c` —
  implementation (376 LOC).
