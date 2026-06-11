# Issue register — `pg_verifybackup`

Covers `src/bin/pg_verifybackup/pg_verifybackup.c`, `astreamer_verify.c`,
and `pg_verifybackup.h`.

Sweep A20 bucket D, verified at `e18b0cb7344`.

## Security

- **Shell injection via crafted `-w / --wal-path`** —
  `pg_verifybackup.c:1232-1237`. `system(3)` is given a printf'd
  command that embeds `wal_path` and `pg_waldump_path` (from
  `find_other_exec`, trusted) with no shell-quoting. A WAL path
  containing `;` or `$(…)` is interpreted by /bin/sh. (likely)

- **Path traversal in tar member names tolerated by streamer** —
  `astreamer_verify.c:182-186`. `canonicalize_path` resolves `..` but
  in the non-tablespace branch we explicitly prepend `./`. The
  resulting normalized path is used ONLY for hash lookup against the
  manifest, NOT for filesystem access — so any traversal just
  produces "file not in manifest" errors. Worth noting because future
  refactors that use this path for fs access would expand the surface.
  (nit)

## Correctness

- **`pg_checksum_init` failure leads to silent skip** —
  `astreamer_verify.c:232-243`. If checksum context init fails for a
  tar-member file, `verify_checksum` is set false and the file is
  marked `matched` but not `bad`. `should_verify_checksum` returns
  false, so the manifest pass treats it as fine. An error is reported
  but exit status only reflects errors via `saw_any_error`, which IS
  set, so the exit status is correct — but the per-file diagnostic
  is suppressed. (likely)

- **OID-named tablespace tars not cross-checked** —
  `pg_verifybackup.c:954-967`. Accepts any OID that parses; doesn't
  verify the OID corresponds to a real tablespace. Manifest entries
  catch content mismatches, but the metadata isn't validated. (nit)

- **`prev` pointer on `manifest_wal_range` is unused** —
  `pg_verifybackup.h:68-69`. Set on insert, never read. Dead weight
  unless someone adds backward iteration. (nit)

- **Path-canonicalization on `-i` arg accepts `..`** —
  `pg_verifybackup.c:198-203`. After `canonicalize_path` the result
  may still contain `..` if it was outside the backup directory.
  Lookups via `should_ignore_relpath` are prefix-bounded by `/`, so
  no traversal exploit, but the ignore list ends up with a useless
  entry. (nit)

- **Hardcoded `"pg_tblspc"` literal** — `astreamer_verify.c:183`. Should
  use `PG_TBLSPC_DIR` macro. Drift risk. (nit)

- **`should_verify_checksum` macro is order-sensitive** —
  `pg_verifybackup.h:40-41`. `matched && !bad && type != NONE`. If
  callers ever set `bad` before `matched`, the second clause silently
  shifts semantics. (nit)

## Style

- **`report_backup_error` is not `pg_noreturn` despite "fatal"
  semantics in many sites** — `pg_verifybackup.h:98-100`. Whether it
  returns depends on `context->exit_on_error`. Callers must not
  assume control transfer. Acceptable but easy to misread. (nit)

- **`(int)` cast in control-file-size error message** —
  `astreamer_verify.c:386-389`. Acknowledged via comment to match
  pg_rewind's format string. (nit)
