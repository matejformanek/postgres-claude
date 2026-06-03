# `src/bin/initdb/initdb.c`

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

`initdb` creates a fresh PostgreSQL cluster on disk: lays out the
`PGDATA` directory tree, writes the `PG_VERSION` file, runs the
backend in bootstrap mode (`postgres --boot`) to populate
`pg_catalog`, then runs it again in single-user mode to apply
`information_schema.sql`, `system_views.sql`, `system_functions.sql`,
the snowball dictionaries, and `pg_authid` setup. Final step is a
disk sync of the new directory. `[from-comment]` (no top-of-file
docstring; behavior pieced together from function comments).

## Role in the pipeline

```
initdb <PGDATA>
   ├── pg_mkdir_p(PGDATA, pg_dir_create_mode)              # 2915-2968
   ├── write_version_file()                                # 277
   ├── postgres --boot -X <walsegsz> [-k] [-d 5]           # 1635 bootstrap_template1
   │      stdin <-- postgres.bki (token-substituted)
   ├── postgres --single                                   # PG_CMD_OPEN in setup_*
   │      stdin <-- setup_auth, setup_depend,
   │                setup_run_file(system_constraints.sql, ...),
   │                setup_collation, setup_privileges,
   │                setup_schema, load_plpgsql, vacuum_db,
   │                make_template0, make_postgres
   └── sync_pgdata()                                       # 3537
```

## Key functions

| Function                          | Lines       | Notes |
|-----------------------------------|-------------|-------|
| `main`                            | 3183-3589  | Option parse, top-level driver, prints "Success." banner. |
| `setup_pgdata`                    | 2634-2667  | Reads `$PGDATA` env var as fallback; `setenv("PGDATA", …)` for child backends. |
| `setup_bin_paths`                 | 2671-2705 | Finds `postgres` via `find_other_exec` (uses argv[0] dir, not PATH). |
| `setup_locale_encoding`           | 2708-2811 | Validates LC_* / ICU. |
| `setup_data_file_paths`           | 2815-     | Locates `postgres.bki`, sample `*.conf`, `system_*.sql`. |
| `create_data_directory`           | 2915-2968 | `pg_check_dir` 4-way switch; refuses non-empty. |
| `create_xlog_or_symlink`          | 2973-3052 | `-X waldir` → mkdir absolute + `symlink(xlog_dir, "$PGDATA/pg_wal")`. |
| `initialize_data_directory`       | 3069-     | Orchestrates the bootstrap+single-user phases. |
| `bootstrap_template1`             | 1571-1657 | Token-substitutes the .bki, pipes into `postgres --boot`. |
| `setup_auth`                      | 1663-1674 | Issues `REVOKE ALL ON pg_authid` then `ALTER USER … PASSWORD E'…'`. |
| `get_su_pwd`                      | 1680-1733 | Reads password from prompt (`simple_prompt`) or `--pwfile`. |
| `cleanup_directories_atexit`      | 776-821   | On failure, rmtree the dirs we created. |
| `escape_quotes` / `escape_quotes_bki` | 407-440 | E-string escape for SQL/BKI. |
| `check_locale_name`               | 2225-2280 | `setlocale()` round-trip; rejects non-ASCII names. |
| `check_input` / `set_input`       | 1000-1040 | Validates required input files exist. |
| `replace_token`                   | 475-     | Line-by-line token swap in the readfile'd `.bki`. |

## State / globals

A wall of file-scope `static` config in lines 145-260 (paths,
locales, auth methods, flags). Notable ones:

- `pg_data`, `pgdata_native` — canonicalised and raw PGDATA paths.
- `superuser_password` — set by `get_su_pwd`, consumed by `setup_auth`.
- `pwprompt`, `pwfilename` — mutually exclusive (checked line 3479).
- `pg_dir_create_mode`, `pg_mode_mask` — set by `SetDataDirectoryCreatePerm` (default 0700; line 3385 flips to 0750 for `--allow-group-access`).
- `made_new_pgdata`, `found_existing_pgdata`, `made_new_xlogdir`,
  `found_existing_xlogdir` — drive `cleanup_directories_atexit`.
- `success` (set just before `return 0;` line 3587) — gates the
  atexit rollback.

## Phase D notes

### First-superuser creation & password handling

The interesting site is `setup_auth` at line 1663-1674:

```c
PG_CMD_PUTS("REVOKE ALL ON pg_authid FROM public;\n\n");
if (superuser_password)
    PG_CMD_PRINTF("ALTER USER \"%s\" WITH PASSWORD E'%s';\n\n",
                  username, escape_quotes(superuser_password));
```

- Plaintext password is written into the SQL stream piped to
  `postgres --single` on stdin. It does NOT touch a temp file; it
  goes pipe → backend → MD5/SCRAM hash → `pg_authid`. So no
  filesystem residue. `[verified-by-code]`
- The SQL is escaped via `escape_single_quotes_ascii` (line 409) and
  emitted as an E-string. Embedded `'` is doubled to `''`. Quoting
  is correct for E-strings.
- `username` is interpolated raw with `"%s"` inside `"…"` — if
  username contains a literal `"` it breaks the SQL. But `main`
  blocks usernames starting with `"pg_"` (line 3503-3504); there's
  no validation against quotes. The username defaults to the OS
  user; if you set `-U 'evil"name'`, you get a broken `ALTER USER`.
  `[ISSUE-wire-protocol: -U username not escaped into ALTER USER quoted identifier (low)]`
- `escape_quotes` calls `pg_fatal("out of memory")` on NULL return
  (412). It does NOT scrub the password buffer on exit. The plaintext
  lives in `superuser_password` for the lifetime of the process
  (since `get_su_pwd` sets it at line 1732 and never frees), and in
  the freshly-allocated `escape_quotes` result. Same scrubbing gap
  as A2/B4 found in libpq — initdb does not `memset` cleartext
  buffers before exit; a core dump or swap during the
  `postgres --single` exchange contains the plaintext.
  `[ISSUE-secret-scrub: superuser_password never zeroed (maybe)]` —
  **YES, same gap as libpq A2 finding**.

### `--pwfile` handling

Block at line 1712-1730:

```c
FILE *pwf = fopen(pwfilename, "r");
...
pwd1 = pg_get_line(pwf, NULL);
...
fclose(pwf);
(void) pg_strip_crlf(pwd1);
```

- **No permission check on the pwfile.** The code comment at lines
  1706-1711 explicitly says: *"Ideally this should insist that the
  file not be world-readable. However, this option is mainly
  intended for use on Windows where file permissions may not exist
  at all, so we'll skip the paranoia for now."*
  `[from-comment]` `[ISSUE-trust-boundary: --pwfile read with no permission check; world-readable pwfile silently accepted (maybe)]` — explicit stale-TODO from upstream.
- Trailing CR/LF stripped via `pg_strip_crlf`. Only the *first* line
  is read; later lines silently ignored. `[verified-by-code]`
- If file is empty, `pg_fatal` (line 1724). No retry, no scrub of the
  failed buffer.

### BKI execution & trust boundary

`bootstrap_template1` (line 1571):

- Reads `postgres.bki` (default
  `<sharedir>/postgres.bki`, set in `setup_data_file_paths`).
- Substitutes `POSTGRES`, `ENCODING`, `LC_COLLATE`, `LC_CTYPE`,
  `DATLOCALE`, `ICU_RULES`, `LOCALE_PROVIDER` via plain string
  replace. The substituted values go through `escape_quotes_bki`
  (BKI single-quote escape, line 423) so a locale like
  `'; DROP TABLE` would be doubled to `''…`.
- Spawns `<bindir>/postgres --boot <boot_options> <extra_options>
  -X <walsegsz> [-k] [-d 5]` via `popen_check` (popen "w" mode).
- `boot_options` is a compiled-in literal constant; `extra_options`
  starts empty and gets `-c debug_discard_caches=1` appended for
  `--discard-caches` (line 3388). It is *not* user-supplied except
  through that one flag. `[verified-by-code]`
- The trust boundary: initdb runs as the OS user invoking it;
  `postgres --boot` reads its commands from initdb's pipe; the data
  dir was just created with `pg_dir_create_mode` (0700 by default).
  If `--share-path` is shared/writable, an attacker could substitute
  `postgres.bki`. The check is only `check_input` (exists +
  readable), no integrity check. `[ISSUE-trust-boundary: postgres.bki integrity not verified beyond first-line PG_MAJORVERSION header check (low)]`
  — guard at line 1590 only compares the `# PostgreSQL <ver>`
  banner.

### Locale validation

`check_locale_name` (line 2225):

- Rejects non-ASCII locale names (line 2231) both on input and
  canonicalized output (line 2277-2279). Defends against Windows
  locale names with weird code-page bytes.
- Validation is "did `setlocale()` accept it" — round-trips through
  the C library. Locale string itself is NEVER passed to a shell;
  the only env-var write is `setenv("PGDATA", …)` at line 2665.
  Locale flows into the BKI via `escape_quotes_bki`, so injection
  into the BKI stream is blocked. `[verified-by-code]`

### `pg_authid` initialization order

- `setup_auth` runs *after* `bootstrap_template1`, in
  `initialize_data_directory` (line 3069 ff — uses `PG_CMD_OPEN` to
  spawn `postgres --single`). At that point `pg_authid` exists from
  `.bki` content. The REVOKE+ALTER USER is the very first SQL fed.
- Invariant: the password ALTER must precede any later GRANT-issuing
  SQL, otherwise default privileges leak. Driven by `initialize_data_directory`
  call order. `[inferred]`

### Permission / umask

- Default: `SetDataDirectoryCreatePerm` initialized to 0700 (owner
  only); changed to 0750 (`PG_DIR_MODE_GROUP`) when `-g` /
  `--allow-group-access` is passed (line 3384-3386).
- `pg_check_dir` ret==1 (present but empty) → `chmod(pg_data,
  pg_dir_create_mode)` at line 2941 *overrides* the existing
  directory's perms. So if you ran `mkdir -m 0755 /var/lib/pg` then
  `initdb -D /var/lib/pg`, you get 0700 (or 0750 with -g), silently.
  `[verified-by-code]`

### PGDATA path safety

- `setup_pgdata` reads `$PGDATA` env var only as a fallback
  (line 2640). `canonicalize_path` (line 2657) is the path-cleanup
  call — strips trailing slashes, collapses `..` lexically (not via
  realpath), no symlink resolution.
- `create_data_directory` refuses non-empty directories (returns
  cases 2/3/4 from `pg_check_dir` → exit 1 at line 2962). Cases 2/3
  hint at mount-point use; case 4 is the generic "non-empty" path.
- No symlink-target check. If `/var/lib/pg` is a symlink to
  `/some/other/place`, initdb will populate `/some/other/place`.
  Documented behavior in PG; not a vulnerability.

### Environment variables read

- `PGDATA` (line 2640) — fallback for `-D`.
- Locale env vars implicitly read by `setlocale(LC_ALL, "")` (called
  from `set_pglocale_pgservice`). `check_locale_name` ASCII-only
  guard limits damage.
- `TZ` — not read here; consumed by findtimezone.c.
- `PGCLIENTENCODING` is explicitly `unsetenv`'d before spawning the
  bootstrap backend (line 1631). `[verified-by-code]`
- `setenv("PGDATA", pg_data, 1)` at line 2665 propagates the
  canonicalised path to child backends; intentional, avoids
  Windows-quoting issues.

### Postmaster binary lookup

`setup_bin_paths` (line 2671):

- `find_other_exec(argv0, "postgres", PG_BACKEND_VERSIONSTR,
  backend_exec)` — looks in `dirname(argv[0])` and rejects version
  mismatch. Does NOT walk `$PATH`. So initdb runs the `postgres`
  that ships with itself; an attacker would need to control the
  install dir, which already grants game-over. `[verified-by-code]`
  This is the "exec_install_root" pattern: argv0-relative, not
  PATH-relative.

### `--set` / `-c` GUC pass-through

- `extra_guc_names` / `extra_guc_values` collected (lines 3304-3305)
  and pasted into `postgresql.conf` by `setup_config`.
- No validation of GUC name or value at parse time. A
  `-c log_min_messages='); …` would inject into the config file.
  `setup_config` (line 1299+) is where escaping happens — out of
  scope for this batch but worth a glance from B-series corpus.
  `[ISSUE-wire-protocol: -c NAME=VALUE pass-through to postgresql.conf — escaping responsibility delegated (low)]`

### Cleanup on failure

`cleanup_directories_atexit` (line 776):

- If `success` was not set, `rmtree(pg_data, true)` *if* initdb
  created the directory (`made_new_pgdata`), or `rmtree(pg_data,
  false)` if it merely populated an existing empty one.
- `--no-clean` (`-n`) keeps the partial state. Useful for
  post-mortem; documented in the startup banner (line 3327).
- `rmtree` follows symlinks? It does not — `rmtree` from
  `common/rmtree.c` uses `lstat` and unlinks symlinks rather than
  following. (See A2/A4 sibling docs.) `[inferred from external file]`

## Potential issues

- `[ISSUE-secret-scrub: superuser_password and pwfile buffer never zeroed (maybe)]` — same gap as libpq A2.
- `[ISSUE-trust-boundary: --pwfile read with no permission check; explicit stale TODO at line 1706-1711 (maybe)]`
- `[ISSUE-wire-protocol: -U username not escaped into ALTER USER quoted identifier; embedded " breaks SQL (low)]`
- `[ISSUE-trust-boundary: postgres.bki integrity verified only by first-line major-version banner (low)]`
- `[ISSUE-wire-protocol: -c NAME=VALUE not validated at parse time (low)]`
- `[ISSUE-info-disclosure: -s/--show prints VERSION/PGDATA/share_path/PGPATH banner including resolved paths (low)]`
- `[ISSUE-stale-todo: pwfile permission check comment at line 1706-1711 ("paranoia for now") never resolved (maybe)]`
- `[ISSUE-undocumented-invariant: chmod silently downgrades a pre-existing empty PGDATA from 0755 to 0700 (maybe)]`
