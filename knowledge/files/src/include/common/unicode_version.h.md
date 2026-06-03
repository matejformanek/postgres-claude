# unicode_version.h

One-line define of the Unicode version the in-tree generated
tables target. (`source/src/include/common/unicode_version.h:14`)
[verified-by-code]

## Purpose

Single source of truth for `PG_UNICODE_VERSION` (currently
`"17.0"`), referenced by docs and by Unicode-aware code paths that
want to advertise their compliance level.

## Key declarations

- `#define PG_UNICODE_VERSION "17.0"`

The file is itself written by hand (not generated) but is updated
in lockstep with the regeneration scripts under
`src/common/unicode/`, driven by
`src/common/unicode/generate-unicode_version.pl`.
[from-comment]

## Phase D notes

None.
