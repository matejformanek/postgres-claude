---
source_url: https://www.postgresql.org/docs/current/libpq-notice-processing.html
fetched_at: 2026-07-20T19:50:00Z
anchor_sha: d451ca6917e3
title: "libpq §34.12 — Notice Processing (two-layer receiver→processor model, copy-at-PGresult-creation inheritance)"
maps_to_skill: wire-protocol
---

# libpq §34.12 — Notice Processing

How server `NOTICE`/`WARNING` messages (and libpq-internal warnings) reach the
application. Two layers exist "for historical reasons"; understanding which to
override is the whole point of the page.

## Non-obvious claims

- **Two layers: notice *receiver* then notice *processor*.** "The default
  behavior is for the notice receiver to format the notice and pass a string to
  the notice processor for printing. However, an application that chooses to
  provide its own notice receiver will typically ignore the notice processor
  layer and just do all the work in the notice receiver." [from-docs]
- **The receiver gets structured data; the processor gets a string.** Typedefs
  (`source/src/interfaces/libpq/libpq-fe.h:254-255`):
  `typedef void (*PQnoticeReceiver)(void *arg, const PGresult *res)` and
  `typedef void (*PQnoticeProcessor)(void *arg, const char *message)`. The
  receiver's `PGresult` is a `PGRES_NONFATAL_ERROR` result, so you can pull
  individual fields (SQLSTATE, detail, …) via `PQresultErrorField`. The
  processor only sees the preformatted text (with trailing newline). [verified-by-code][from-docs]
- **Default call chain:** on a notice, the (default) receiver extracts the message
  via `PQresultErrorMessage` and hands it to the processor; the default processor
  is literally `fprintf(stderr, "%s", message)` —
  `defaultNoticeProcessor` at `source/src/interfaces/libpq/fe-connect.c:7978`.
  [verified-by-code][from-docs]
- **Hooks are copied into each `PGresult` at creation, not looked up live.** "At
  creation of a `PGresult`, the `PGconn`'s current notice handling pointers are
  copied into the `PGresult`." So changing the connection's hooks does **not**
  retroactively affect already-created results — same inheritance rule as error
  verbosity (§34.11) and as `PQmakeEmptyPGresult` copying event procs. [from-docs]
- **Both setters return the previous pointer.** `PQsetNoticeReceiver`
  (`libpq-fe.h:469`) and `PQsetNoticeProcessor` (`:472`) "return the previous
  notice receiver or processor function pointer, and set the new value" — the
  standard save/restore or chaining idiom. Passing a NULL function pointer is a
  no-op that just returns the current one (used to *query* the current hook).
  [verified-by-code][from-docs]
- **`arg` is opaque pass-through.** libpq stores your `void *arg` and hands it back
  on every call, never dereferencing it — the standard C closure trick for
  threading application state into the callback. [from-docs]

## Links into corpus

- Passive delivery model (notices ride other calls, like NOTIFY):
  [[knowledge/docs-distilled/libpq-notify.md]],
  [[knowledge/docs-distilled/libpq-async.md]].
- The verbosity/context knobs that shape the message string the processor sees:
  [[knowledge/docs-distilled/libpq-control.md]].
- `PGRES_NONFATAL_ERROR` result + error fields:
  [[knowledge/docs-distilled/protocol-error-fields.md]],
  [[knowledge/docs-distilled/libpq-exec.md]].
- Backend origin of NOTICE/WARNING: `error-handling` skill (ereport elevel ladder).
- Source: [[knowledge/files/src/interfaces/libpq/fe-connect.c.md]]
  (defaultNoticeProcessor), [[knowledge/files/src/interfaces/libpq/libpq-fe.h.md]].
