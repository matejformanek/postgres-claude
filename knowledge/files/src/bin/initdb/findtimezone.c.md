# `src/bin/initdb/findtimezone.c`

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

Picks the default `timezone` (and `log_timezone`) GUC value that
initdb writes into `postgresql.conf`. Source priority:

1. `$TZ` env var if it names a recognised zone.
2. On Unix: read `/etc/localtime`, then score every file under the
   tz database (`<sharedir>/timezone/` or `SYSTEMTZDIR`) by
   simulating offsets at many timestamps.
3. On Windows: map the C-library's `%Z` against a baked-in
   `win32_tzmap[]` and the registry's
   `SOFTWARE\Microsoft\Windows NT\CurrentVersion\Time Zones` keys.

Returns a zone name string or NULL → caller falls back to GMT.
`[from-comment]` (lines 1751-1755).

## Role in the pipeline

```
initdb → select_default_timezone(share_path)
            ├── getenv("TZ") + validate_zone()                            # 1767-1769
            └── identify_system_timezone()
                   ├── Unix: check_system_link_file("/etc/localtime", …)  # 406
                   │         + scan_available_timezones(<tzdir>, …)       # recursive
                   └── Win32: %Z lookup + registry walk                   # 1565
```

The result string is written verbatim into `postgresql.conf.sample`
substitutions. Only invoked by initdb.

## Key functions

| Function                       | Lines       | Notes |
|--------------------------------|-------------|-------|
| `select_default_timezone`      | 1756-1777  | Top-level entry. |
| `identify_system_timezone` (Unix) | 331-      | Builds a 100-year-spanning `tztry`, runs `check_system_link_file`, then `scan_available_timezones`. |
| `identify_system_timezone` (Win32) | 1565-1720 | `%Z` → registry → win32_tzmap table. |
| `check_system_link_file`       | 543-607   | `readlink("/etc/localtime")` → walk path components, score each as a zone name. |
| `scan_available_timezones`     | 656-      | Recursive descent of `<tzdir>` calling `score_timezone` per file. |
| `pg_open_tzfile`               | 64-79     | `strcat`-based path build. |
| `pg_load_tz`                   | 90-120    | Wraps `tzload` / `tzparse`. |
| `score_timezone`               | 234-     | Compares zone's offsets at probe timestamps with the system's `localtime()`. |
| `zone_name_pref`               | 615-635   | Tie-breakers (UTC > Etc/UTC > localtime/posixrules). |
| `validate_zone`                | 1728-     | Round-trip through `pg_load_tz`. |
| `pg_TZDIR`                     | 36-46     | `SYSTEMTZDIR` macro or compiled-in share path. |

## State / globals

- `tzdirpath[MAXPGPATH]` — file-scope buffer; only when *not*
  `SYSTEMTZDIR` (line 27). Populated by `select_default_timezone`
  line 1763 with `"<share_path>/timezone"`.
- `pg_load_tz` returns a pointer to a `static pg_tz tz` (line 93) —
  only one timezone in memory at a time. `[from-comment]` (line 88).

## Phase D notes

### System timezone probing (`/etc/localtime`)

`check_system_link_file` (line 543):

- `readlink("/etc/localtime", link_target, sizeof(link_target))` —
  no recursion, just one hop. If `/etc/localtime` is itself a regular
  file (e.g. tzdata copied not symlinked), the readlink returns -1
  and the function falls through to the recursive scan. `[verified-by-code]`
- `link_target` is `MAXPGPATH` (1024) bytes. `len >= sizeof` is
  treated as failure (line 557). No overflow risk.
- Parsing strategy (lines 573-599): walk path components, try each
  *suffix* as a zone name. Stops early if a component starts with
  `.` (the comment at line 588-589 specifically mentions defending
  against `..`).
- The zone-name extraction uses `perfect_timezone_match` — which
  internally calls `pg_load_tz`, which calls `tzload(name, NULL,
  &tz.state, true)`. `tzload` in turn opens `<tzdir>/<name>`. Since
  the `name` here came from a path suffix, an `/etc/localtime`
  pointing to e.g. `/etc/passwd` would cause `tzload("etc/passwd")`
  which would open `<tzdir>/etc/passwd` — a path INSIDE the tz dir.
  No traversal escape. `[verified-by-code]` (via `pg_open_tzfile`
  line 64-79 — `strcat(fullname, "/")` then `strcat(fullname,
  name)`; no `..` filter).
- BUT `pg_open_tzfile` (line 64-79) builds the path with bare
  `strcat`. If `name` starts with `/` it would escape to absolute
  (because the second `strcat` after `"/"` is a no-op). For
  `tzload(name)` from the readlink path walker, the names are path
  suffixes starting with a directory component (no leading `/` —
  `cur_name++` past the slashes at line 583). So safe in the actual
  call path. A hypothetical caller passing `"/etc/passwd"` could,
  however, traverse — but no such caller exists.
  `[ISSUE-path-traversal: pg_open_tzfile uses bare strcat; safe only because all callers strip leading slashes (low)]`

### Time-zone name → file path mapping

`pg_open_tzfile` line 64-79:

```c
strlcpy(fullname, pg_TZDIR(), sizeof(fullname));
if (strlen(fullname) + 1 + strlen(name) >= MAXPGPATH)
    return -1;
strcat(fullname, "/");
strcat(fullname, name);
return open(fullname, O_RDONLY | PG_BINARY, 0);
```

- Length check prevents buffer overrun. `[verified-by-code]`
- `name` is *not* validated to lack `..` or leading `/`. As above,
  all current callers feed sanitized names, so this is a footgun for
  future callers, not a live bug.
- Open is `O_RDONLY`; no `O_NOFOLLOW`. The tzdir is under share_path
  (read-only, packaged at install) so symlink shenanigans require
  attacker write access to `/usr/share/postgresql/<ver>/timezone/`
  — at which point you own the install.

### `$TZ` handling

`select_default_timezone` line 1767:

- `getenv("TZ")` is fed straight into `validate_zone` → `pg_load_tz`
  → `tzload`. Same path-suffix safety as above; `tzload` itself (in
  src/timezone/) has its own bounds checks.
- If TZ is something like `:Europe/Prague` (POSIX-style leading
  colon), `pg_load_tz` (line 111) checks `name[0] == ':'` AFTER
  `tzload` fails and skips `tzparse` for it → returns NULL. So
  colon-prefixed TZ from the env will silently fail validation and
  the system-probe fallback runs. `[from-comment]` and `[verified-by-code]`.

### Recursive tzdir scan

`scan_available_timezones` (line 656):

- `pgfnames(tzdir)` lists the directory. The function modifies
  `tzdir` in place (writes `'/'` + child name) and recurses if
  `S_ISDIR`. The `tzdir_orig_len` save/restore (lines 660, 686) is
  correct.
- Hidden files (`name[0] == '.'`) are skipped at line 674. Defends
  against `.` and `..`, also `lost+found` indirectly via dot-prefix
  test (but `lost+found` is NOT dotted so it would be scanned;
  `pg_load_tz` would reject it as non-tz content).
- Recursion depth is bounded by directory depth in the tz database
  (usually 3: `region/sub/file`). No explicit depth limit, but
  pathological symlink loops in the tzdir would blow the stack.
  Since the tzdir is part of the install, this is not an attack
  surface in practice. `[ISSUE-dos: scan_available_timezones has no recursion-depth limit; symlink loops in tzdir hang (low)]`

### Windows registry walk

`identify_system_timezone` (Win32, line 1565):

- Walks `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Time
  Zones`, calling `RegEnumKeyEx` / `RegQueryValueEx("Std")` /
  `RegQueryValueEx("Dlt")`.
- Buffer sizes: `tzname[128]`, `localtzname[256]`, `keyname[256]`,
  `zonename[256]`. `namesize = sizeof(buf)` is passed to the API
  which sets it to actual length on return — proper Win32 idiom.
- `strcpy(localtzname, keyname)` at line 1670 — both are 256-byte
  buffers, and `keyname` was filled by `RegEnumKeyEx` capped at
  `sizeof(keyname)`. Safe.
- Falls back to NULL → GMT if nothing matches.

### Leap-seconds rejection

`score_timezone` rejects zones that use leap seconds (line 252) —
documented behavior; would otherwise mismatch the system's
non-leap-second behavior.

## Potential issues

- `[ISSUE-path-traversal: pg_open_tzfile uses bare strcat with no leading-/ or .. filter (low)]` — safe only because current callers sanitize.
- `[ISSUE-dos: scan_available_timezones has no recursion-depth limit (low)]` — install-trusted tzdir means not exploitable in practice.
- `[ISSUE-undocumented-invariant: pg_load_tz returns pointer to file-scope static — second call invalidates first result (maybe)]` — comment at line 88 says so but callers should know.
- `[ISSUE-info-disclosure: DEBUG_IDENTIFY_TIMEZONE writes every probed path to stderr (low)]` — off by default.
- `[ISSUE-trust-boundary: $TZ honored without validating that the named zone is in our tzdir vs system tzdir (low)]` — `validate_zone` → `pg_load_tz` → `tzload` will accept system TZ files when SYSTEMTZDIR is configured, so result depends on build-time choice.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `initdb`](../../../../issues/initdb.md)
<!-- issues:auto:end -->
