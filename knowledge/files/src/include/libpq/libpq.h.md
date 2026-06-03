# libpq.h

- **Source path:** `source/src/include/libpq/libpq.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"POSTGRES LIBPQ buffer structure definitions" — declarations for the
backend-side `pqcomm.c` send/receive primitives, the `PQcommMethods`
dispatch table (normal socket vs parallel worker shm_mq), and the SSL/
secure-transport entry points implemented in `be-secure*.c` [from-comment].

## Public API surface

- `PQcommMethods` struct: `comm_reset`, `flush`, `flush_if_writable`,
  `is_send_pending`, `putmessage`, `putmessage_noblock`. Backed by the
  global `PqCommMethods *` pointer plus a set of `pq_*()` macros that
  invoke through it [verified-by-code].
- Message-size constants: `PQ_SMALL_MESSAGE_LIMIT (10000)`,
  `PQ_LARGE_MESSAGE_LIMIT (MaxAllocSize-1)` — convention for
  `pq_getmessage` callers [from-comment].
- `WaitEventSet *FeBeWaitSet` and positional macros `FeBeWaitSetSocketPos`
  (0), `FeBeWaitSetLatchPos` (1), `FeBeWaitSetNEvents` (3).
- pqcomm.c prototypes: `ListenServerPort`, `AcceptConnection`,
  `TouchSocketFiles`, `RemoveSocketFiles`, `pq_init`, `pq_getbytes`,
  `pq_startmsgread`/`endmsgread`, `pq_is_reading_msg`, `pq_getmessage`,
  `pq_getbyte`, `pq_peekbyte`, `pq_getbyte_if_available`,
  `pq_buffer_remaining_data`, `pq_putmessage_v2`, `pq_check_connection`.
- be-secure.c prototypes: `secure_initialize`, `secure_loaded_verify_locations`,
  `secure_destroy`, `secure_open_server`, `secure_close`, `secure_read`,
  `secure_write`, `secure_raw_read`, `secure_raw_write`.
- SSL globals / GUCs: `ssl_library`, `ssl_ca_file`, `ssl_cert_file`,
  `ssl_crl_file`, `ssl_crl_dir`, `ssl_key_file`, `ssl_min_protocol_version`,
  `ssl_max_protocol_version`, `ssl_passphrase_command`,
  `ssl_passphrase_command_supports_reload`, `ssl_dh_params_file`,
  `ssl_sni`, `SSLCipherSuites`, `SSLCipherList`, `SSLECDHCurve`,
  `SSLPreferServerCiphers`, `ssl_loaded_verify_locations` (USE_SSL).
- Compile-time constants: `SSL_LIBRARY` (`"OpenSSL"` or `""`),
  `DEFAULT_SSL_CIPHERS` (`"HIGH:MEDIUM:+3DES:!aNULL"` under OpenSSL),
  `DEFAULT_SSL_GROUPS` (`"X25519:prime256v1"` under USE_SSL).
- `ssl_protocol_versions` enum (PG_TLS_ANY ... PG_TLS1_3_VERSION).
- `HostsFileLoadResult` enum and `load_hosts(List **, char **)`,
  `check_ssl_key_file_permissions`, `run_ssl_passphrase_command`.
- GSS open: `secure_open_gssapi(Port *)` under ENABLE_GSS.

## Cross-refs

- Related backend: `src/backend/libpq/pqcomm.c`,
  `src/backend/libpq/be-secure.c`, `src/backend/libpq/be-secure-openssl.c`,
  `src/backend/libpq/be-secure-common.c`, `src/backend/libpq/be-secure-gssapi.c`.
- Related: `knowledge/files/src/include/libpq/libpq-be.h.md` (Port),
  `knowledge/files/src/include/libpq/pqcomm.h.md` (wire constants).

## Potential issues

- **[ISSUE-undocumented-invariant: 3DES is in the default cipher list]**
  `libpq.h:132` — `DEFAULT_SSL_CIPHERS "HIGH:MEDIUM:+3DES:!aNULL"` keeps
  3DES in the default cipher allowlist. 3DES (Sweet32 birthday-bound
  problem) is deprecated by NIST since 2023; the comment does not justify
  the inclusion. Phase D hardening candidate. Severity: maybe.
- **[ISSUE-stale-todo: FeBeWaitSetNEvents = 3 with named positions for 2]**
  `libpq.h:66-68` — `FeBeWaitSetSocketPos=0`, `FeBeWaitSetLatchPos=1`,
  `FeBeWaitSetNEvents=3`. The third slot is unnamed in the header (it is
  the postmaster-death event, but you have to read `pqcomm.c` to know
  that). Worth a comment. Severity: maybe.
- **[ISSUE-leak: passphrase command result buffer size from caller]**
  `libpq.h:171-173` — `run_ssl_passphrase_command(cmd, prompt, server,
  buf, size)` reads the passphrase into a caller-supplied buffer. The
  header does not state whether `buf` is required to be locked memory or
  whether the function `explicit_bzero`s on error. Verify in
  `be-secure-common.c`. Severity: maybe.

## Tally

`[verified-by-code]=6 [from-comment]=2 [inferred]=2`
