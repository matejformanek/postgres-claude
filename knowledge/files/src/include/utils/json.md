# utils/json.h — JSON text-format helpers

Source: `source/src/include/utils/json.h` (35 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Thin header for the *text-form* JSON type (JSONB lives in `jsonb.h`). Declares `composite_to_json`, `escape_json[_with_len]`, `escape_json_text`, `JsonEncodeDateTime`, the `to_json` mutability check, builders, and `json_validate`.

## Public API

- `composite_to_json(datum, StringInfo *result, use_line_feeds)` (`json.h:20-21`).
- `escape_json(buf, str)` / `escape_json_with_len(buf, str, len)` / `escape_json_text(buf, txt)` (`json.h:22-24`).
- `JsonEncodeDateTime(buf, value, typid, tzp)` (`json.h:25-26`).
- `to_json_is_immutable(typoid)` (`json.h:27`).
- `json_build_object_worker` / `json_build_array_worker` (`json.h:28-32`).
- `json_validate(json, check_unique_keys, throw_error)` (`json.h:33`).

## Invariants

- **INV-json-is-varlena-text** [inferred]: SQL `json` type is a varlena holding the *original text* (whitespace + key order preserved). `jsonb` is the canonical binary form. Header doesn't state this — consequence is that comparison/index ops on `json` are slower and key-ordering-sensitive.
- **INV-escape_json-required-for-strings** [inferred]: any caller emitting JSON output must use `escape_json` for string values; doing manual quoting is a known foot-gun.

## Trust-boundary / Phase-D surface

- **A5 + A8 recursive-parser stack-depth** [from-corpus]: the actual recursive JSON parser lives in `common/jsonapi.c` (used by both backend and client). Header `json.h` doesn't surface stack-depth limits — callers using `json_validate` get the parser's own depth tracking, but anyone using `pg_parse_json` directly must trust the parser. A5 found that deeply-nested JSON input can be a stack-DoS surface.
- **`json_validate(check_unique_keys=true)`** — full-document scan; expensive on adversarial input. Header doesn't warn.

## Cross-refs

- `source/src/common/jsonapi.h` — the recursive parser (used here and in jsonb).
- `knowledge/files/src/include/utils/jsonfuncs.md` — companion for higher-level builders + JsonLexContext setup.
- `source/src/include/utils/jsonb.h` — JSONB binary format (separate header, not in A15-2 slice).

## Issues

- `[ISSUE-DOC: stack-depth defense not visible at this layer (medium)]` — A5/A8 found the recursive parser is the DoS anchor; this header should cross-link to common/jsonapi.h's depth limits.
- `[ISSUE-INVARIANT: json vs jsonb mental-model gap (low)]` — header doesn't restate that `json` preserves source text; matters for hash/order semantics.
