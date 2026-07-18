---
path: src/backend/libpq/be-secure-common.c
anchor_sha: 4b0bf0788b0
loc: 438
depth: deep
---

# be-secure-common.c

- **Source path:** `source/src/backend/libpq/be-secure-common.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 438

## Purpose

Implementation-independent helpers that any TLS backend
(`be-secure-openssl.c` today; conceivably others later) can reuse.
Specifically: running `ssl_passphrase_command` to unlock private
keys, validating the file-system permissions on those keys, and
parsing the **pg_hosts.conf** file (the per-hostname SNI config
file added in PG 18). [from-comment, be-secure-common.c:1-18]

The split exists so a future Rustls / GnuTLS / LibreSSL backend
wouldn't have to re-implement these pieces.

## Public API surface

- `int run_ssl_passphrase_command(const char *cmd, const char *prompt, bool is_server_start, char *buf, int size)`
  — `be-secure-common.c:46`. Runs `cmd` (with `%p` replaced by
  `prompt`) via `OpenPipeStream`, reads one line into `buf`. Loglevel
  is `ERROR` at server start (so postmaster doesn't half-start),
  `LOG` on reload. **Calls `explicit_bzero(buf, size)` on every error
  path** (be-secure-common.c:75, 87, 97) before bailing — the only
  PG path that consistently scrubs a passphrase buffer.
- `bool check_ssl_key_file_permissions(const char *ssl_key_file, bool isServerStart)`
  — `be-secure-common.c:121`. Refuses to load a key file that's not
  a regular file, not owned by user-or-root, or with group/world
  permission bits set. Rules: owned-by-us → must be ≤ 0600;
  owned-by-root → ≤ 0640 (allow group read for shared system certs).
  No-op on Windows / Cygwin. [verified-by-code, be-secure-common.c:120-184]
- `HostsFileLoadResult load_hosts(List **hosts, char **err_msg)` —
  `be-secure-common.c:365`. Reads `pg_hosts.conf` via the
  generic-auth-file machinery (`open_auth_file`, `tokenize_auth_file`),
  parses each line via `parse_hosts_line` (static, line 194). Returns
  `HOSTSFILE_LOAD_OK` / `HOSTSFILE_LOAD_FAILED` / `HOSTSFILE_MISSING`
  / `HOSTSFILE_EMPTY`. The parsed `HostsLine` list contains
  hostnames, ssl_cert, ssl_key, optional ssl_ca, optional
  passphrase_cmd + reload-bool. [verified-by-code]

## Internal landmarks

- **`parse_hosts_line`** (be-secure-common.c:194) — column order:
  `<hostnames> <ssl_cert> <ssl_key> [ssl_ca] [passphrase_cmd
  [passphrase_reload_bool]]`. Special hostnames `*` and `/no_sni/`
  cannot be mixed with regular names on the same line
  (be-secure-common.c:217-225).
- **Permission rule rationale** — the two-tier 0600/0640 split
  (be-secure-common.c:145-160) supports the deployment pattern where
  the cert/key bundle is owned by root and the PG user has it via a
  group; that's how distro packagers tend to ship system certs.
  Comment also notes the parallel check in
  `src/interfaces/libpq/fe-secure-openssl.c` (client-side) that has
  to stay in sync.
- **`%p` placeholder substitution** via `replace_percent_placeholders`
  (be-secure-common.c:59) — common across PG's "configurable
  external-command" GUCs (archive_command, restore_command,
  ssl_passphrase_command). The set of allowed % placeholders is
  the third argument; here just `"p"`.

## Invariants & gotchas

- **The passphrase buffer is scrubbed on EVERY error path** — but
  *not* on the success path (be-secure-common.c:108-114). That's a
  deliberate handoff: the caller (the OpenSSL passwd callback in
  `be-secure-openssl.c::ssl_external_passwd_cb`) is responsible for
  whatever happens next. The pattern: error → erase + bail; success
  → caller's problem.
- **Windows can't check key-file perms.** The `#if !defined(WIN32) &&
  !defined(__CYGWIN__)` gate (be-secure-common.c:161) means a
  PG-on-Windows deployment cannot enforce private-key permissions.
  Comment at be-secure-common.c:157-159: "Ideally we would do
  similar permissions checks on Windows, but it is not clear how
  that would work since Unix-style permissions may not be available."
- **`is_server_start` controls log severity, not return value.** All
  the loglevel ternaries (be-secure-common.c:49, 123) escalate to
  `ERROR`/`FATAL` only at startup so a bad config aborts the
  postmaster; reload is best-effort.
- **`pg_hosts.conf` lines do NOT cascade to `pg_hba.conf` rules** —
  this file only configures the TLS cert/key per SNI hostname;
  authentication still goes through hba.
- **`hostnames` is a *list* per line** (be-secure-common.c:215-228) —
  one cert can be served for multiple SNI hostnames (think SAN-style
  multi-name certs) by listing them on one line.

## Cross-refs

- Header: `knowledge/files/src/include/libpq/libpq.h.md` (defines
  `HostsLine`, `HostsFileLoadResult`).
- Auth-file machinery: `src/backend/libpq/hba.c::open_auth_file`,
  `tokenize_auth_file`.
- Consumer: `be-secure-openssl.c::be_tls_init` (the only caller of
  `load_hosts`), `init_host_context`,
  `ssl_external_passwd_cb`.
- Client-side mirror: `src/interfaces/libpq/fe-secure-openssl.c` (the
  permission check).

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-leak: passphrase not scrubbed on the success path]**
  `be-secure-common.c:107-114` — only error paths
  `explicit_bzero(buf, size)`. The success path returns the
  passphrase to the OpenSSL callback in cleartext; the callback
  copies it into OpenSSL's internal buffer and the original
  `buf` (stack-allocated in `ssl_external_passwd_cb`) just falls
  out of scope. Probably fine because OpenSSL owns the lifetime
  after, but document. Severity: maybe.
- **[ISSUE-undocumented-invariant: pg_hosts.conf line cannot mix
  `*` / `/no_sni/` with regular names]** be-secure-common.c:217-225
  — enforced but the rationale isn't in the sample file's
  documentation. Severity: nit.
- **[ISSUE-question: Windows path skips permission check silently]**
  `be-secure-common.c:161-181` — a key file with world-readable
  ACLs on NTFS will be loaded without warning. Comment acknowledges
  this is a TODO. Severity: maybe (long-standing).
- **[ISSUE-correctness: `wait_result_to_str` is called for failed
  pclose even after explicit_bzero]** be-secure-common.c:96-105 —
  the scrub happens before `wait_result_to_str`, which is correct
  ordering (don't leave the buffer alive while doing more work).
  Just noting. Severity: nit (no bug).
- **[ISSUE-doc-drift: comment says "future TODO might be to rename
  the supporting code with a more generic name"]** be-secure-common.c:387-391
  — refers to `open_auth_file` etc. being reused for hosts file.
  Stale-TODO candidate. Severity: nit.

## Tally

`[verified-by-code]=12 [from-comment]=5 [inferred]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/libpq-backend.md](../../../../subsystems/libpq-backend.md)
