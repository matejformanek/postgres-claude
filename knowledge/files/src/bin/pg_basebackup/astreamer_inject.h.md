# astreamer_inject.h

## Purpose

Declares the recovery-config injector — a chained `astreamer` that
rewrites a base-backup tar stream on the fly to add `postgresql.auto.conf`
content and create a `standby.signal` file, so the resulting backup can
boot as a standby.

## Public API

- `astreamer_recovery_injector_new(next, is_recovery_guc_supported, recoveryconfcontents)`
  — wraps `next` with an injector that handles three cases based on
  server version (recovery.conf vs. postgresql.auto.conf). See
  `astreamer_inject.c` for the case analysis.
  `source/src/bin/pg_basebackup/astreamer_inject.h:18`
- `astreamer_inject_file(streamer, pathname, data, len)` — synthesizes a
  member header + content + trailer for an arbitrary `pathname` into
  `streamer`. Used to inject `standby.signal`, `recovery.conf`,
  `backup_manifest`, and `postgresql.auto.conf`.
  `source/src/bin/pg_basebackup/astreamer_inject.h:21`

## Phase D notes

- The injected pathnames (`standby.signal`, `postgresql.auto.conf`,
  `recovery.conf`) are hard-coded string literals — no attacker influence
  over what gets injected from this header layer. [verified-by-code]
- Caller controls `data`/`len` of the recovery-config content; that data
  ultimately comes from `GenerateRecoveryConfig()` (see
  `fe_utils/recovery_gen.c`) built from connection options known to the
  user. [inferred]
