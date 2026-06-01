# jsonlog.c

- **Source path:** `source/src/backend/utils/error/jsonlog.c`
- **Lines:** 301
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `error/elog.c`, `error/csvlog.c` (sibling), `utils/adt/jsonfuncs.c::escape_json`, `postmaster/syslogger.c`

## Purpose

Formats an `ErrorData` as a single newline-terminated JSON object and ships it to the syslogger pipe (or directly to file if the current process *is* the syslogger). Parallel to csvlog.c, but uses key-value form so columns can be omitted instead of emitting empty positional fields. Keys are always JSON-escaped; values are JSON-escaped except for known-safe numeric fields. [from-comment, jsonlog.c:105-107]

## Top-of-file comment (verbatim)

> "jsonlog.c — JSON logging." [from-comment, jsonlog.c:1-13]

The substantive prose is at the function comments for `appendJSONKeyValue` (line 35) and `write_jsonlog` (line 105).

## Public surface

- `write_jsonlog(ErrorData *edata)` (108) — only public entry. Called by `send_message_to_server_log` (elog.c) when `LOG_DESTINATION_JSONLOG` is set in `Log_destination`.

## Static helpers

- `appendJSONKeyValue(buf, key, value, escape_value)` (42) — append `,"key":<value>` (with comma prefix so callers don't need to track first-element state). Key always escaped via `escape_json`; value optionally escaped. **NULL value → emit nothing**, allowing fields to be omitted naturally.
- `appendJSONKeyValueFmt(buf, key, escape_key, fmt, ...)` (69) — sprintf-style value builder using `pvsnprintf` with grow-loop. Used for numeric and composite formatted values (PID, vxid, line_num, query_id).

## JSON keys produced (order is fixed in source, consumers should treat as keyed not positional)

`timestamp`, `user`, `dbname`, `pid`, `remote_host`, `remote_port`, `session_id`, `line_num`, `ps`, `session_start`, `vxid`, `txid`, `error_severity`, `state_code`, `message`, `detail` (uses `detail_log` if set), `hint`, `internal_query`, `internal_position`, `context` (suppressed if `hide_ctx`), `statement`, `cursor_position`, `func_name`/`file_name`/`file_line_num` (only when `Log_error_verbosity >= PGERROR_VERBOSE`), `application_name`, `backend_type`, `leader_pid` (only for parallel workers), `query_id`. [verified-by-code, jsonlog.c:134-289]

## Key invariants

- **First field (`timestamp`) is emitted WITHOUT the leading comma** that `appendJSONKeyValue` would prepend; it's hand-written as `escape_json(...,"timestamp"); ':'; escape_json(...,log_time)`. [verified-by-code, jsonlog.c:142-148]
- **Null/empty fields are omitted entirely** (no `"key":null` or `"key":""`), making the output sparse and easy to filter. csvlog.c by contrast emits empty positional fields.
- **Per-process line counter behavior matches csvlog.c**: reset on `MyProcPid` change, also resets formatted_start_time. [verified-by-code, jsonlog.c:126-131]
- **Sink dispatch identical to csvlog.c**: direct file write if `MyBackendType == B_LOGGER`, else `write_pipe_chunks` with `LOG_DESTINATION_JSONLOG` tag. [verified-by-code, jsonlog.c:295-298]
- **`detail_log` shadows `detail`** in the `detail` field — same precedence as csvlog. Server-side-only detail wins when both are set.
- **`vxid` format must match `lockfuncs.c`** (`pg_locks` view) — comment at line 197.

## Cross-references

- Same helper sources as csvlog.c (elog.c: get_formatted_log_time, error_severity, etc.).
- `escape_json` lives in `utils/adt/json.c`.
- Output is documented as a stable format consumable by log shippers; the schema is implicit in the source rather than a separate spec.

## Open questions

- Whether `appendJSONKeyValueFmt`'s grow-loop has an upper bound — it currently doubles forever based on the `pvsnprintf` return value, which would OOM via `palloc` if a single value were absurdly long. In practice not exploitable because errmsg etc. go through the standard error string size limits. [unverified — low risk]

## Confidence tag tally

`[verified-by-code]=5 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
