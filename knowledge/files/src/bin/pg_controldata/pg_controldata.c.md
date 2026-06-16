# `src/bin/pg_controldata/pg_controldata.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~355
- **Source:** `source/src/bin/pg_controldata/pg_controldata.c`

Read-only dumper of `$PGDATA/global/pg_control`. Decodes the
`ControlFileData` struct to a human-readable report: version numbers,
system identifier, current cluster state, latest checkpoint location and
its TLI, NextXID/NextOID/NextMulti, WAL-segment / block sizes, the
`max_*` settings recorded at startup, data-page checksum version, mock
authentication nonce, etc. Most non-trivial tools (`pg_resetwal`,
`pg_rewind`, `pg_upgrade`) rely on the same parser
(`common/controldata_utils.c` `get_controlfile`). [verified-by-code]

## API / entry points

- `main` — `-D / --pgdata` or first positional or `$PGDATA`; calls
  `get_controlfile(DataDir, &crc_ok)` then a long sequence of `printf`s.
  [verified-by-code]
- `dbState(state)` — pretty-prints `DBState` enum. Returns "unrecognized
  status code" for unknown values. [verified-by-code]
- `wal_level_str(WalLevel)` — pretty-prints WAL_LEVEL_{MINIMAL,REPLICA,LOGICAL}.
  [verified-by-code]

## Notable invariants / details

- Uses `#define FRONTEND 1` then `#include "postgres.h"` because the WAL
  includes need backend macros. Header comment calls this an "ugly hack"
  (lines 12-17). [from-comment]
- CRC mismatch and pg_control_version mismatch produce warnings, not
  errors: the dump proceeds with stern "results below are untrustworthy"
  detail messages. This is deliberate — the tool's reason for existence
  is forensic, so refusing to print a corrupt control file would be
  unhelpful. [from-comment]
- `WalSegSz > 0` guard at line 230 protects the `XLByteToSeg` division
  in case of a corrupted control file with zero or negative segment size.
  Fallback prints `???` for the REDO WAL filename. [from-comment]
- The mock_authentication_nonce is hex-dumped (32 bytes → 64 hex chars).
  [verified-by-code]
- The `--char-signedness` field is shown but always-on PG datatypes
  (Date/time type storage) are still listed as "64-bit integers" even
  though they're no longer configurable, "users may still expect to see
  it" (line 343). [from-comment]
- Two timestamps are read from the control file (the file's own modify
  time `ControlFile->time` and the checkpoint `checkPointCopy.time`).
  Both via plain `localtime`; if either returns NULL we fall back to
  `???`. The "chintzy" comment at line 197-205 acknowledges that
  control-file timestamps within `time_t` range is assumed but not
  enforced. [from-comment]

## Potential issues

- `pg_controldata.c:170-176` — version mismatch produces a warning but
  continues to interpret bytes that may not match the struct layout. If
  field offsets shifted between versions the subsequent prints read
  arbitrary memory. The warning is the only safety net.
  [ISSUE-correctness: continues to interpret across struct-layout change
  (maybe)]
- `pg_controldata.c:230-239` — `WalSegSz > 0` accepted as "valid enough";
  a corrupted but small positive value still divides cleanly and yields
  a misleading WAL filename. [ISSUE-correctness: weak validation of
  xlog_seg_size before division (nit)]
- `pg_controldata.c:206-220` — uses `localtime` (not thread-safe),
  acceptable here because pg_controldata is single-threaded.
  [verified-by-code]
- Header `dbState` returns `"unrecognized status code"` for the default
  case but never logs which integer was seen. Forensic value reduced.
  [ISSUE-style: unrecognized enum should include the numeric value (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `bin-singletons`](../../../../issues/bin-singletons.md)
<!-- issues:auto:end -->
