---
source_url: https://www.postgresql.org/docs/current/protocol-message-types.html
chapter: "54.6 Message Data Types"
fetched_at: 2026-06-15
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# Wire-protocol message data types — §54.6

Distilled from §54.6. This is the notation legend for reading every
per-message format in [[knowledge/docs-distilled/protocol-message-formats.md]]
— short but load-bearing: pg-user-question-harvester repeatedly flagged
"wire-protocol" as a recurring corpus gap, and the field-notation
conventions are what newcomers misread.

## Non-obvious claims

- **Everything multi-byte is big-endian.** `Intn(i)` is an *n*-bit
  integer in **network byte order** (most significant byte first); `i`,
  if given, is the exact constant value (e.g. `Int32(196608)` for the
  protocol-3.0 version field). [from-docs §54.6]
- `Intn[k]` is an array of *k* *n*-bit ints, and **`k` is always
  supplied by an earlier field in the same message** — the protocol never
  uses an inline length prefix on these arrays; you must have already
  parsed the count field. [from-docs §54.6]
- `String(s)` is a **null-terminated C string** with **no predefined
  length limit**. The doc explicitly advises frontends to use
  *expandable buffers* rather than fixed ones, because a server can send
  an arbitrarily long string (error fields, NOTICE text, etc.).
  [from-docs §54.6]
- `Byten(c)` is exactly *n* raw bytes; when *n* is not a literal constant
  it is **determinable from an earlier field**. `c`, if given, is the
  exact byte value (e.g. `Byte1('Q')` is the Simple-Query message type
  byte). [from-docs §54.6]
- `Byten[k]` (array of *k* *n*-byte fields) follows the same
  earlier-field-determines-length rule as `Intn[k]`. [from-docs §54.6]
- **Consequence for parsers:** the format is *not* self-describing — you
  cannot skip a field without knowing the message grammar, because
  variable-length fields (`Byten`, `Intn[k]`) get their length from
  *previously parsed* fields, and `String` is delimited only by its NUL.
  A length-prefixed message header (the Int32 length after the type byte)
  bounds the whole message, but the internal fields are positional.
  [from-docs §54.6, inferred]

## Links into corpus

- The formats this legend decodes:
  [[knowledge/docs-distilled/protocol-message-formats.md]].
- Message flow / startup handshake:
  [[knowledge/docs-distilled/protocol-flow.md]],
  [[knowledge/docs-distilled/protocol-overview.md]].
- Error/Notice field codes (a heavy `String` consumer):
  [[knowledge/docs-distilled/protocol-error-fields.md]].
- Logical-replication payloads layered on these primitives:
  [[knowledge/docs-distilled/protocol-logicalrep-message-formats.md]].

## Caveats / verification

- `[from-docs §54.6]`. Pure protocol-spec prose (no source line to
  pin); the `Byten[k]` form is described tersely in the source and is
  marked `(implied)` by the fetch. Chapter number (54.6) per the current
  docs ToC at anchor `b78cd2bda5b1a306e2877059011933de1d0fb735`.
