# `src/bin/pgevent/pgmsgevent.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~46
- **Source:** `source/src/bin/pgevent/pgmsgevent.h`

Header defining the single Windows event-log MessageId used by the
postmaster's `write_eventlog()` function on Windows: `PGWIN32_EVENTLOG_MSG
= 0x00000000L`. The bulk of the file is the standard Microsoft `mc.exe`
comment block describing the 32-bit MessageId encoding (Sev / C / R /
Facility / Code). [from-comment]

## API / entry points

- `#define PGWIN32_EVENTLOG_MSG  0x00000000L` — the lone MessageId.
  `Sev = 00 (Success)`, no Facility, Code 0. Message text is `%1`, i.e.
  whatever string the caller passes through. [verified-by-code]

## Notable invariants / details

- All `ReportEvent` calls in `pg_ctl.c` (`write_eventlog`) and in the
  server backend's Windows logging path use this single MessageId with
  the actual log line in the insertion string. There's no per-severity
  / per-facility MessageId, so the *severity* parameter of
  `ReportEvent` (EVENTLOG_ERROR_TYPE / WARNING / INFORMATION) is the
  only differentiator visible in Event Viewer. [inferred]
- The MessageId structure comments (lines 4-31) are boilerplate emitted
  by `mc.exe`; they describe the bitfield layout but no PG-specific
  fields are defined. [verified-by-code]
- The empty "Define the facility codes" and "Define the severity codes"
  comment headers (lines 30, 35) are placeholders left in from the
  `mc.exe` output template. [verified-by-code]

## Potential issues

- `pgmsgevent.h:46` — only one MessageId means the Event Viewer always
  shows "the entire log line", which loses Windows-side category and
  i18n hooks. A larger facility/code matrix would let admins filter
  more cleanly, at the cost of having to keep the .mc file in sync
  with `errcode`/severity sets. [ISSUE-style: single MessageId loses
  Event Viewer filtering granularity (nit)]
- The `_d.h` / catalog conventions don't apply here; this is a
  Windows-resource-compiler artifact, not a PG header.
  [verified-by-code]
