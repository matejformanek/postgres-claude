---
path: src/timezone/pgtz.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 497
depth: deep
---

# src/timezone/pgtz.c

## Purpose

The integration layer between PostgreSQL and the bundled IANA timezone library
(`localtime.c`/`zic.c`, vendored). It owns: locating the timezone data
directory, opening a named zone's data file **case-insensitively**, the
loaded-zone cache, the `TimeZone` / `log_timezone` GUC-backed session zones,
fixed-offset zone construction (`SET TIME ZONE INTERVAL`), early bootstrap
initialization, and enumeration of all installed zones (for the
`pg_timezone_names` view). The IANA C files do the actual TZif parsing; this
file is the PG-authored glue around them. `[verified-by-code]`

## Public symbols

| Symbol | Site | Role |
|---|---|---|
| `pg_tz *session_timezone` | `pgtz.c:28` | Current session zone (the `TimeZone` GUC) |
| `pg_tz *log_timezone` | `pgtz.c:31` | Current log zone (`log_timezone` GUC) |
| `int pg_open_tzfile(const char *name, char *canonname)` | `pgtz.c:76` | Open a zone's data file by (case-insensitive) name; report canonical spelling |
| `pg_tz *pg_tzset(const char *tzname)` | `pgtz.c:234` | Load-or-cache a named zone |
| `pg_tz *pg_tzset_offset(long gmtoffset)` | `pgtz.c:320` | Build a fixed-GMT-offset zone |
| `void pg_timezone_initialize(void)` | `pgtz.c:361` | Bootstrap `session_timezone`/`log_timezone` to GMT before GUCs init |
| `pg_tzenum *pg_tzenumerate_start(void)` | `pgtz.c:397` | Begin a recursive walk of the zone directory |
| `pg_tz *pg_tzenumerate_next(pg_tzenum *)` | `pgtz.c:426` | Next zone in the walk |
| `void pg_tzenumerate_end(pg_tzenum *)` | `pgtz.c:414` | Tear down the walk |

## Internal landmarks

- `pg_TZDIR` (`pgtz.c:43`) — returns `<sharedir>/timezone` (cached after first
  `get_share_path` call), or the compile-time `SYSTEMTZDIR` if PG was configured
  to use the system tz database.
- `pg_open_tzfile` (`:76-142`) — fast path tries `open()` of the name as-is when
  the caller doesn't need the canonical spelling; otherwise splits the name into
  directory levels and resolves each level case-insensitively via
  `scan_directory_ci`.
- `scan_directory_ci` (`:151-182`) — `AllocateDir` + `ReadDirExtended`,
  `pg_strncasecmp` match; **skips any entry whose name starts with `.`** as a
  deliberate security measure (see Invariants).
- `pg_tzset` (`:234-305`) — uppercases the name for a case-insensitive cache
  lookup; `"GMT"` is special-cased to `tzparse()` (never touches the
  filesystem); otherwise `tzload()`, falling back to POSIX-spec `tzparse()`.
  Result is cached in the `timezone_cache` HTAB keyed on the uppercased name.
- `pg_tzenumerate_next` (`:426-497`) — explicit directory stack (depth-capped at
  `MAX_TZDIR_DEPTH` = 10) that descends subdirectories, loads each zone with
  `tzload` (bypassing the cache), and skips leap-second zones via
  `pg_tz_acceptable`.

## Invariants & gotchas

- **`"GMT"` must never depend on the filesystem.** `pg_tzset` routes `"GMT"`
  straight to `tzparse()` (`pgtz.c:273-282`); the header comment lists three
  reasons (`:222-232`): guaranteed success (no bootstrap failure mode), it works
  before `my_exec_path` is known, and it's fast. `pg_timezone_initialize`
  (`:361`) relies on this to set `log_timezone` *before* GUC init, so that
  `log_line_prefix` timestamps have a valid zone from the very first log line.
- **Hidden-file skip is a path-traversal guard.** `scan_directory_ci` ignores
  every `.`-prefixed entry "to prevent access to files outside the timezone
  directory" (`pgtz.c:162-167`) — this is what stops a crafted zone name with
  `..` components from escaping the tz data dir, since the name is otherwise
  attacker-influenceable (any role can `SET timezone`).
- **Names are length-capped** at `TZ_STRLEN_MAX` (`pg_tzset` returns NULL for
  longer, `:242`) and `pg_open_tzfile` rejects names that won't fit in
  `MAXPGPATH` (`:87-88`) — both before any filesystem touch.
- The cache is **never invalidated**: once a zone is loaded it stays for the
  backend's life. Zones don't change underneath a running backend, so this is
  fine; but a tzdata package update is only picked up by new backends.
- `pg_tzenumerate_next` returns a pointer into the `pg_tzenum` struct valid only
  until the next call; the whole walk is palloc'd in the current context.

## Cross-refs

- `knowledge/files/src/port/path.c.md` — `get_share_path` locates the tz dir.
- `knowledge/files/src/backend/utils/adt/datetime.c.md` — primary consumer of
  the loaded `pg_tz` zones.
- `knowledge/idioms/guc-variables.md` — `TimeZone` / `log_timezone` wiring.
