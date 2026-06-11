# Issues — `src/include/` (misc small dirs)

Combined issue register for the small include subdirectories not
big enough to warrant their own register:
`portability/`, `datatype/`, `mb/`, `archive/`, `bootstrap/`.

**Parent docs:** `knowledge/files/src/include/{portability,datatype,mb,archive,bootstrap}/*.h.md`.

## Open / Triaged

### portability/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/portability/instr_time.h:21-25 | doc-drift | nit | `INSTR_TIME_SET_CURRENT_FAST` vs `INSTR_TIME_SET_CURRENT` (OOO vs fenced) is easy to confuse for benchmarks | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/instr_time.h:152-153 | question | nit | `pg_set_timing_clock_source(TSC)` false-return on unavailability — should frontends ereport on fallback? | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/instr_time.h:160-162 | undocumented-invariant | nit | `timing_tsc_frequency_khz = -1` sentinel on `int32` — would break on signed→unsigned migration | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/instr_time.h:227-239 | correctness | nit | `pg_get_ticks_system` uses `Assert(timing_initialized)`; release builds skip the check, returning a pre-init clock read | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/instr_time.h:170-174 | question | nit | `TscClockSourceInfo.frequency_source[128]` — fixed-size buffer for CPUID strings could truncate | open | files/.../portability/instr_time.h.md |
| 2026-06-11 | src/include/portability/mem.h:41-44 | stale-todo | nit | `MAP_FAILED` fallback comment says "really old systems"; unreachable on any modern POSIX target | open | files/.../portability/mem.h.md |
| 2026-06-11 | src/include/portability/mem.h:28-31 | doc-drift | nit | `MAP_HASSEMAPHORE` current-platform impact not stated | open | files/.../portability/mem.h.md |
| 2026-06-11 | src/include/portability/mem.h:15 | style | nit | `IPCProtection = 0600` octal literal — could be `S_IRUSR|S_IWUSR` for clarity | open | files/.../portability/mem.h.md |

### datatype/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/datatype/timestamp.h:115-118 | question | nit | `DAYS_PER_MONTH = 30` and `DAYS_PER_YEAR = 365.25` foot-gun in EXTRACT(epoch FROM interval); not flagged in user docs | open | files/.../datatype/timestamp.h.md |
| 2026-06-11 | src/include/datatype/timestamp.h:47-53 | undocumented-invariant | likely | `Interval` is 16 bytes (time:8 + day:4 + month:4); cannot change without breaking on-disk compat | open | files/.../datatype/timestamp.h.md |
| 2026-06-11 | src/include/datatype/timestamp.h:41 | stale-todo | likely | `fsec_t` is int32 microseconds — "beware of overflow if many seconds"; foot-gun in callers | open | files/.../datatype/timestamp.h.md |
| 2026-06-11 | src/include/datatype/timestamp.h:227-231 | undocumented-invariant | nit | `IS_VALID_JULIAN` is intentionally looser than `IS_VALID_DATE`; ordering must be maintained | open | files/.../datatype/timestamp.h.md |

### mb/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/mb/pg_wchar.h:401-420 | correctness | likely | `utf8_to_unicode` returns `0xffffffff` on invalid input; callers must check (inline signature doesn't enforce) | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:65-72 | undocumented-invariant | likely | `pg_enc` numbering is pinned to libpq major version 5-era ABI — no compile-time check | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:148-155 | security | maybe | `MAX_CONVERSION_GROWTH=4` is a global cap; a user-defined conversion that exceeds it would overrun output buffers sized `4*srclen` | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:618-620 | security | maybe | `local2local` takes `tab` pointer without length argument; table size is caller-provided convention | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:550 | undocumented-invariant | likely | `pg_database_encoding_character_incrementer()` returns fn pointer; caller must keep current-DB-encoding context aligned | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/pg_wchar.h:481-487 | style | nit | libpq-shim macros redirect `pg_char_to_encoding` etc. — historical baggage that's correct but dense | open | files/.../mb/pg_wchar.h.md |
| 2026-06-11 | src/include/mb/stringinfo_mb.h:21 | doc-drift | nit | `maxlen` unit (chars vs bytes) not documented in header | open | files/.../mb/stringinfo_mb.h.md |

### archive/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/archive/archive_module.h:43-49 | undocumented-invariant | likely | `ArchiveModuleCallbacks` ABI has no version field; reorder = silent miscall | open | files/.../archive/archive_module.h.md |
| 2026-06-11 | src/include/archive/archive_module.h:32-41 | doc-drift | nit | Callback semantics referenced via "the archive modules documentation" but no in-header link | open | files/.../archive/archive_module.h.md |
| 2026-06-11 | src/include/archive/archive_module.h:63-65 | style | nit | `arch_module_check_errdetail` is a comma-expression macro; misuse is silent | open | files/.../archive/archive_module.h.md |
| 2026-06-11 | src/include/archive/shell_archive.h:14-22 | doc-drift | nit | `archive_library = ''` sentinel for in-tree shell archiver not in header | open | files/.../archive/shell_archive.h.md |

### bootstrap/

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/bootstrap/bootstrap.h:26 | undocumented-invariant | likely | `MAXATTR = 40` is a silent ceiling for system-table column counts | open | files/.../bootstrap/bootstrap.h.md |
| 2026-06-11 | src/include/bootstrap/bootstrap.h:33 | question | nit | `attrtypes[MAXATTR]` is statically sized; is there ereport on overflow in DefineAttr? | open | files/.../bootstrap/bootstrap.h.md |

## Wontfix / Submitted / Landed

(empty)

## Notes

- **`portability/`** is mostly historical-clean-up / minor
  documentation gaps. The TSC clock-source path (`instr_time.h`) is
  the only place with non-trivial concurrency contract
  (`ticks_per_ns_scaled` mutating mid-measurement).
- **`datatype/timestamp.h`** carries on-disk-compat invariants that
  prevent any meaningful change; the issues filed are
  documentation-grade.
- **`mb/pg_wchar.h`** is the highest Phase-D leverage in this misc
  bucket: encoding conversion is a frequent CVE surface area, and
  the `MAX_CONVERSION_GROWTH` and `local2local` invariants are
  externally relied on without compile-time checks.
- **`archive/archive_module.h`** has the same ABI-version-field
  weakness as `fdwapi.h`'s `FdwRoutine` — pattern worth tracking
  across all "plug in a function-pointer struct" interfaces.
- **`bootstrap/bootstrap.h`** is small but `MAXATTR=40` is a
  catalog-design hard ceiling worth flagging in any
  `catalog-conventions` skill update.
