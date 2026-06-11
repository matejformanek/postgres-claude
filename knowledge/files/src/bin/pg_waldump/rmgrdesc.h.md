# `src/bin/pg_waldump/rmgrdesc.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~23
- **Source:** `source/src/bin/pg_waldump/rmgrdesc.h`

Declares the frontend-side `RmgrDescData` struct and exports
`GetRmgrDesc`. The struct holds `{rm_name, rm_desc, rm_identify}` —
the description-relevant subset of the backend's `RmgrData`.
[verified-by-code]

## API / entry points

- `typedef struct RmgrDescData { const char *rm_name; void
  (*rm_desc)(StringInfo, XLogReaderState *); const char
  *(*rm_identify)(uint8); } RmgrDescData;`. [verified-by-code]
- `extern const RmgrDescData *GetRmgrDesc(RmgrId rmid)`.
  [verified-by-code]

## Notable invariants / details

- Pulls in `access/xlogreader.h` for `XLogReaderState` and
  `lib/stringinfo.h` for `StringInfo`. [verified-by-code]
- Deliberately mirrors but does not share with the backend's
  `RmgrData` — those have redo/decode/startup/cleanup function
  pointers that aren't safe to link in frontend.
  [verified-by-code]

## Potential issues

- None notable.
