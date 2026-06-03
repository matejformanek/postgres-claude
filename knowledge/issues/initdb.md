# Issues — `initdb` (src/bin/initdb/)

Per-subsystem issue register for initdb. See `knowledge/issues/README.md`
for tag taxonomy.

**Parent docs:** `knowledge/files/src/bin/initdb/*` (2 docs).

**Source:** 20 entries surfaced 2026-06-03 by the A4 foreground sweep
(batch B5). Each is mirrored in the corresponding per-file doc's
`## Potential issues` block.

initdb is **the first-superuser-creation moment**: it bootstraps the
cluster, creates `pg_authid` with the bootstrap superuser, and sets the
permissions of every catalog file going forward. Any mishandling of the
superuser password during init is a **process-memory + on-disk
credential-exposure vector** parallel to the libpq A2 findings.

---

## P0 — Phase D candidates

### Secret-scrub gap (mirror of A2 libpq + A4 psql/streamutil findings)

This directory's headline. The bootstrap password lives in process
memory for the whole initialization phase and is never zeroed.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | initdb.c:1732 (get_su_pwd) | secret-scrub | likely | `superuser_password` (file-scope `static char *`) set once, never freed/zeroed; plaintext lives in process memory for the entire bootstrap + single-user phase | open | knowledge/files/src/bin/initdb/initdb.c.md |
| 2026-06-03 | initdb.c (escape_quotes copy) | secret-scrub | likely | E-string copy of `superuser_password` for SQL embedding also leaked into process memory until `exit(0)` | open | knowledge/files/src/bin/initdb/initdb.c.md |

**Phase D pitch — coordinate with the libpq/psql/streamutil patch series:**
`explicit_bzero(superuser_password, strlen(superuser_password))` before
the final exit + the matching `escape_quotes` cleanup. This is the
**fourth occurrence** of the same gap in our corpus (libpq A2 in 60+
files, psql A4 in `\password` + `main()`, streamutil A4, initdb A4).
Each can land independently but a single `SecretBuf`-style helper
across `src/common` would be the cleanest fix.

### `--pwfile` permission check — explicit stale TODO

The most egregious finding: upstream **explicitly acknowledged the gap
in a code comment and said "we'll skip the paranoia for now"** — that
"for now" has shipped for years.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | initdb.c:1706-1711 | trust-boundary | likely | `--pwfile` reads bootstrap password with no permission check. Comment says: *"Ideally this should insist that the file not be world-readable. However... we'll skip the paranoia for now."* World-readable pwfile silently accepted | open | knowledge/files/src/bin/initdb/initdb.c.md |
| 2026-06-03 | initdb.c:1706-1711 | stale-todo | maybe | "Paranoia for now" comment never resolved; the right fix is `stat(pwfile)` + reject world/group readable, matching ssh's `~/.ssh/config` discipline | open | knowledge/files/src/bin/initdb/initdb.c.md |

**Phase D pitch — single-line patch:**
`stat()` the pwfile; refuse with a hard error if mode has any bits set
beyond `0600` (or `0640` if `--allow-group-access` was passed). This
matches the discipline psql uses for history file (echo: psql's
`saveHistory` is 0600 by intent) and pg_basebackup uses for `.pgpass`
(via libpq).

### Wire-protocol / SQL-assembly invariants

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | initdb.c | wire-protocol | maybe | `-U username` not escaped into the bootstrap `ALTER USER` quoted identifier; embedded `"` breaks SQL | open | knowledge/files/src/bin/initdb/initdb.c.md |
| 2026-06-03 | initdb.c | wire-protocol | nit | `-c NAME=VALUE` pass-through to `postgresql.conf` — escaping responsibility delegated, not validated at parse time | open | knowledge/files/src/bin/initdb/initdb.c.md |
| 2026-06-03 | initdb.c | trust-boundary | nit | `postgres.bki` integrity verified only by first-line `PG_MAJORVERSION` header check — no checksum, no signature | open | knowledge/files/src/bin/initdb/initdb.c.md |
| 2026-06-03 | initdb.c | undocumented-invariant | maybe | `chmod` silently downgrades a pre-existing empty PGDATA from `0755` to `0700` — the security action is invisible to the operator | open | knowledge/files/src/bin/initdb/initdb.c.md |
| 2026-06-03 | initdb.c | info-disclosure | nit | `-s`/`--show` prints `VERSION`/`PGDATA`/`share_path`/`PGPATH` banner including resolved filesystem paths | open | knowledge/files/src/bin/initdb/initdb.c.md |

---

## P1 — `findtimezone.c` path-handling

Lower priority because the tzdir is install-trusted, but the patterns
are sloppy enough to flag.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | findtimezone.c | path-traversal | nit | `pg_open_tzfile` uses bare `strcat` with no leading-`/` or `..` filter; safe only because callers strip leading slashes | open | knowledge/files/src/bin/initdb/findtimezone.c.md |
| 2026-06-03 | findtimezone.c | dos | nit | `scan_available_timezones` has no recursion-depth limit — symlink loops in tzdir would hang; install-trusted tzdir means not exploitable | open | knowledge/files/src/bin/initdb/findtimezone.c.md |
| 2026-06-03 | findtimezone.c:88 | undocumented-invariant | maybe | `pg_load_tz` returns pointer to file-scope static — second call invalidates first result; comment exists but contract is fragile | open | knowledge/files/src/bin/initdb/findtimezone.c.md |
| 2026-06-03 | findtimezone.c | info-disclosure | nit | `DEBUG_IDENTIFY_TIMEZONE` writes every probed path to stderr — off by default | open | knowledge/files/src/bin/initdb/findtimezone.c.md |
| 2026-06-03 | findtimezone.c | trust-boundary | nit | `$TZ` honored without validating zone is in our tzdir vs system tzdir; `validate_zone`→`pg_load_tz`→`tzload` accepts system TZ files when `SYSTEMTZDIR` is configured — depends on build-time choice | open | knowledge/files/src/bin/initdb/findtimezone.c.md |

---

## Cross-corpus pattern — the four secret-scrub findings now form a series

| Source | What leaks | Where |
|---|---|---|
| A2 libpq | `PGconn`-held passwords, scram keys, pgpass, oauth tokens | full connection lifetime in process memory; `explicit_bzero` used in 2 of 60+ files |
| A4 psql | `\password` pw1/pw2 buffers; `main()` password arg; PSQL_HISTORY; `-L` logfile | command.c:2604-2607; startup.c:249-302; input.c:148-167; common.c:1158 |
| A4 streamutil | static-global `password` for replication tools | streamutil.c |
| A4 initdb | `superuser_password` + escape_quotes copy until exit | initdb.c:1732 |

**Single proposed mitigation across all four:** introduce a `SecretBuf`
type in `src/common` with `secret_alloc` / `secret_free` (the latter
calls `explicit_bzero` then `free`) and migrate the 5 specific call
sites named above. The corpus already has a `knowledge/idioms` slot
for cross-PG patterns; `knowledge/idioms/secret-buffer.md` would be the
natural home.

---

## Corpus gaps surfaced (out of batch)

- `src/backend/bootstrap/bootparse.y` + `bootscanner.l` — the BKI interpreter that initdb invokes via `postgres --boot`. Closes the "BKI integrity" question (initdb's first-line check is the only client-side validation).
- `src/include/catalog/pg_authid.dat` — the bootstrap entry that initdb populates with `superuser_password`. Where the password actually lands.

---

## Summary by tag type

| Type | Count |
|---|---:|
| secret-scrub | 2 |
| trust-boundary | 4 |
| wire-protocol | 2 |
| stale-todo | 1 |
| undocumented-invariant | 3 |
| path-traversal | 1 |
| info-disclosure | 2 |
| dos | 1 |
| **Total** | **16** (some entries have multiple tags) |

Severity headline: 3 `likely`, 4 `maybe`, rest `nit`. Headline density
(20 issues across 2 files) is **highest of any A4 batch per-file** —
expected for a tool whose entire job is "set up the security
boundary."
