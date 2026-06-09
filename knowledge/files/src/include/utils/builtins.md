# utils/builtins.h — grab-bag of built-in type helpers

Source: `source/src/include/utils/builtins.h` (140 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Catch-all header for cross-cutting helpers that don't fit a single type header. Declares: bool parsing, domain check, encode/decode (hex), int<->string conversion (numutils), name string ops, oidvector helpers, regex prefix, identifier quoting, varchar truelen, the cstring<->text bridge, network conversion, and format_type machinery.

## Public API (selected high-traffic)

- **Conversion (numutils.c)**: `pg_strtoint16/32/64`, `pg_strtoint16_safe/32_safe/64_safe`, `uint32in_subr`, `uint64in_subr`, `pg_itoa`, `pg_ultoa_n`, `pg_lltoa`, `pg_ultostr_zeropad`, `pg_ultostr` (`builtins.h:51-67`).
- **Hex encode/decode**: `hex_encode`, `hex_decode`, `hex_decode_safe` (`builtins.h:38-41`).
- **text <-> cstring**: `cstring_to_text`, `cstring_to_text_with_len`, `text_to_cstring`, `text_to_cstring_buffer` (`builtins.h:93-99`).
- **The famous macros**: `CStringGetTextDatum(s)` and `TextDatumGetCString(d)` (`builtins.h:98-99`) — most used pair in the codebase.
- **Identifier quoting**: `quote_identifier`, `quote_qualified_identifier`, `quote_literal_cstr` (`builtins.h:81-83, 138`), and `quote_all_identifiers` GUC (`builtins.h:80`).
- **format_type flags**: `FORMAT_TYPE_TYPEMOD_GIVEN`, `_ALLOW_INVALID`, `_FORCE_QUALIFY`, `_INVALID_AS_NULL` (`builtins.h:125-128`) for `format_type_extended`.
- **Domain check**: `domain_check`/`domain_check_safe` (`builtins.h:29-33`).
- **`MAXINT8LEN = 20`** (`builtins.h:22`): sign + max digits of int64.

## Invariants

- **INV-pg_strtoint*_safe-soft-error** [verified-by-code, `builtins.h:51-60`]: every integer parser has a `_safe` variant taking `Node *escontext`. New code on user-input paths MUST use the `_safe` form.
- **INV-MAXINT8LEN-includes-sign** [verified-by-code, `builtins.h:21-22`]: sized for `-9223372036854775808` + NUL. Buffers smaller than this risk overflow.
- **INV-CStringGetTextDatum-allocates** [from-implementation]: macro palloc's a fresh text*; not a no-op cast despite the name. Callers in tight loops should consider `cstring_to_text_with_len` directly.
- **INV-format_type-flag-INVALID_AS_NULL-vs-throw** [verified-by-code, `builtins.h:125-128`]: `FORMAT_TYPE_ALLOW_INVALID` returns "???" or "-"; `FORMAT_TYPE_INVALID_AS_NULL` returns NULL. Easy to confuse; pick one based on caller's null-handling.

## Notable internals

- `clean_ipv6_addr` (`builtins.h:117`) is for stripping scope-id from IPv6 strings; not widely known.
- `convert_network_to_scalar` (`builtins.h:114`) is what powers cross-type comparison-cost estimates for INET/CIDR.
- `bpchartruelen(s, len)` (`builtins.h:90`) trims trailing spaces to find the "true" length of a BPCHAR.

## Trust-boundary / Phase-D surface

- **`hex_decode` vs `hex_decode_safe`** (`builtins.h:39-41`): hard-error vs soft. bytea_in's hex path must use the safe variant.
- **`pg_strtoint*` family must use `_safe` on user input**: hard variants ereport, which breaks the soft-error contract for binary recv / SQL parse paths.
- **`quote_identifier` does NOT quote everything** — only when needed (keyword / non-lowercase / non-ident-char). Callers building DDL strings for replication must understand this; `quote_all_identifiers` GUC forces always-quote for ruleutils output.
- **`CStringGetTextDatum`** does not validate the input string is UTF-8 or in the server encoding. Misuse with non-server-encoding bytes lands invalid bytes in a text datum (caller's responsibility).

## Cross-refs

- `source/src/backend/utils/adt/{bool,domains,encode,int,name,numutils,oid,regexp,ruleutils,varchar,varlena,xid,network,format_type,quote}.c` — implementation sites grouped under the section comments.
- A7 finding cluster: anything reading SQL/binary input ints should use `_safe` variants.

## Issues

- `[ISSUE-DOC: file is a grab-bag, no overview (low)]` — the header is split by section comments but lacks a top-level index of what lives where; adding it would shorten "where does X live" lookups.
- `[ISSUE-INVARIANT: hard-error parser variants still ambient (medium)]` — `pg_strtoint*` non-safe versions exist mainly for catalog/bootstrap use; on user paths they're a foot-gun. A grep enforcement (or deprecation comment) would help.
