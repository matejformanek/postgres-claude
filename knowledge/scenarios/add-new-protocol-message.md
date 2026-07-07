---
scenario: add-new-protocol-message
when_to_use: I want to add a new byte-tagged libpq wire message — frontend libpq emit/parse + backend dispatch + `protocol.sgml` — and bump `PG_PROTOCOL_LATEST` to gate it behind a version handshake.
companion_skills: ["replication-overview"]
related_scenarios: ["add-new-replication-message"]
canonical_commit: bbf9c282ce9
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new libpq protocol message

## Scope — what's in / out

**In scope:** the FULL sweep of touching the wire format itself.

- A new byte-tag in `src/include/libpq/protocol.h` (the `PqMsg_*` /
  `PqReplMsg_*` enumeration) `[verified-by-code]`
  (`src/include/libpq/protocol.h:17-91`).
- Backend emit site — `pq_beginmessage` / `pq_endmessage` /
  `pq_putmessage` against the new tag (e.g. in
  `src/backend/tcop/postgres.c`, `src/backend/libpq/auth.c`,
  `src/backend/tcop/backend_startup.c`, or wherever the new exchange
  fires). `[verified-by-code]`
  (`src/backend/tcop/backend_startup.c:964`).
- Backend dispatch — adding the new tag to the `PostgresMain`
  read-loop `switch (firstchar)` in
  `src/backend/tcop/postgres.c:4838` (or to `WalSndLoop` /
  `auth.c` if the message arrives outside the normal command cycle).
  `[verified-by-code]` (`src/backend/tcop/postgres.c:4838-5119`,
  `src/backend/replication/walsender.c:783-820`).
- Frontend emit — `pqPutMsgStart(PqMsg_<New>, conn)` somewhere in
  `src/interfaces/libpq/fe-exec.c` or `fe-connect.c` if the client
  originates the message. `[verified-by-code]`
  (`src/interfaces/libpq/fe-exec.c:1472`,
  `src/interfaces/libpq/fe-exec.c:1613`).
- Frontend parse — a new `case PqMsg_<New>:` in one of the two big
  switches in `src/interfaces/libpq/fe-protocol3.c` (the async
  `pqParseInput3` switch at line 202 and the auth/startup switch at
  line 1895). `[verified-by-code]`
  (`src/interfaces/libpq/fe-protocol3.c:202`,
  `src/interfaces/libpq/fe-protocol3.c:1895`).
- Tracing — a new `case PqMsg_<New>:` in `pqTraceOutputMessage` in
  `src/interfaces/libpq/fe-trace.c:653` plus a one-line dumper.
  `[verified-by-code]` (`src/interfaces/libpq/fe-trace.c:624-820`).
- Protocol version bump in `src/include/libpq/pqcomm.h`
  (`PG_PROTOCOL_LATEST`) — required if the new message is sent
  unsolicited or its absence breaks an existing exchange.
  `[verified-by-code]` (`src/include/libpq/pqcomm.h:95`).
- Negotiation handling — backend `backend_startup.c` decides which
  protocol minor version to honor (`PG_PROTOCOL_LATEST` clamp at
  `src/backend/tcop/backend_startup.c:734`) and replies with
  `NegotiateProtocolVersion` (B `'v'`) if the client asked for less.
  Frontend tracks acceptable range via `min_protocol_version` /
  `max_protocol_version` GUCs read at
  `src/interfaces/libpq/fe-connect.c:340-356`.
  `[verified-by-code]`.
- `doc/src/sgml/protocol.sgml` — both the **message-flow** narrative
  (sect1 "Message Flow" at line 397) and the **Message Formats**
  reference (sect1 at line 3807, varlistentry pattern at line 5426).
  `[verified-by-code]` (`doc/src/sgml/protocol.sgml:5426-5460`).

**Out of scope:**

- New logical-decoding callback or output-plugin message wrapped in
  `CopyData` — own scenario `add-new-replication-message`.
- New auth sub-method (an `AUTH_REQ_*` code under the
  `PqMsg_AuthenticationRequest` tag) — that does NOT change the byte
  tag, only the integer subtype at
  `src/include/libpq/protocol.h:94-109`. Bumps `AUTH_REQ_MAX`, not
  `PG_PROTOCOL_LATEST`. Treat as a localized auth.c change, not a
  full protocol scenario.
- New `CancelRequestPacket` / `NEGOTIATE_SSL_CODE` style startup-time
  packet — those go through a completely different code path in
  `backend_startup.c` and never hit the `PostgresMain` switch.
- New parallel-worker shm_mq message (`PqMsg_Progress 'P'`) — uses a
  different transport; only adds a tag in `protocol.h` and a handler
  in `src/backend/access/transam/parallel.c`. Adjacent but not the
  same playbook.

## Pre-flight

- **Companion skill:** load
  `.claude/skills/replication-overview/SKILL.md` for the wire-protocol
  framing rules (`pq_beginmessage` / `pq_endmessage` / `pq_getmsg*`
  cadence, `StringInfo` ownership, network byte order, message length
  including self). Same framing applies to non-replication wire
  messages. `[from-README]`
  (`.claude/skills/replication-overview/SKILL.md`).
- **Canonical commit:** `bbf9c282ce9` — *"libpq: Handle
  NegotiateProtocolVersion message"* (Heikki Linnakangas, 2024). The
  reference example: it added the `'v'` tag to `protocol.h`, the emit
  site in `backend_startup.c`, the parse case in `fe-protocol3.c`
  (both startup and async switches), the trace case in `fe-trace.c`,
  AND the `protocol.sgml` block at `protocol-message-formats-NegotiateProtocolVersion`.
  Read it before starting; every row in the checklist below maps to a
  hunk in that commit. Pair with `516b87502dc` ("Do not hardcode
  PG_PROTOCOL_LATEST in NegotiateProtocolVersion") for the
  version-negotiation invariants. `[verified-by-code]`
  (`git -C source show bbf9c282ce9`).
- **Common pitfalls (one-line each):**
  - Reusing a byte-tag that already exists for the other direction —
    `'p'` is overloaded for `PasswordMessage` / `GSSResponse` /
    `SASLInitialResponse` / `SASLResponse` because they're all
    frontend→backend and the context disambiguates. Reusing a tag
    that's already used in the SAME direction is fatal. `[from-comment]`
    (`src/include/libpq/protocol.h:30-33`,
    `src/interfaces/libpq/fe-trace.c:713-716`).
  - Forgetting the `PG_PROTOCOL_LATEST` bump in
    `src/include/libpq/pqcomm.h:95` — old libpq won't ask for the
    feature, backend dutifully omits it, no error, silent feature
    miss. `[verified-by-code]`.
  - Sending the new message inside a Sync/Ready window without a
    `NegotiateProtocolVersion` cover — pre-bump clients will see an
    unknown tag in `pqParseInput3` and disconnect.
    `[verified-by-code]` (`src/interfaces/libpq/fe-protocol3.c:202`).
  - Documenting in `protocol.sgml` only the format and not the flow
    — readers can't tell *when* the message arrives. The two sections
    are sibling-edits. `[from-docs]`
    (`doc/src/sgml/protocol.sgml:397`,
    `doc/src/sgml/protocol.sgml:3807`).

## File checklist (the FULL sweep)

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/libpq/protocol.h` | Add `#define PqMsg_<New>  '<byte>'` in the correct directional block (FE→BE, BE→FE, or shared). Bump `AUTH_REQ_MAX` only if this is a new auth subtype. | [protocol.h.md](../files/src/include/libpq/protocol.h.md) | replication-overview |
| 2 | `src/include/libpq/pqcomm.h` | Bump `PG_PROTOCOL_LATEST` to the new minor (and possibly `PG_PROTOCOL_EARLIEST` if dropping a major). Skip `PG_PROTOCOL_RESERVED_31` (collides with pgbouncer). | [pqcomm.h.md](../files/src/include/libpq/pqcomm.h.md) | replication-overview |
| 3 | `src/backend/tcop/backend_startup.c` | If sent during startup OR if `NegotiateProtocolVersion` must advertise the new minor: edit `ProcessStartupPacket` clamp at line 734 + the `pq_beginmessage(&buf, PqMsg_NegotiateProtocolVersion)` site at line 964. | [backend_startup.c.md](../files/src/backend/tcop/backend_startup.c.md) | replication-overview |
| 4 | `src/backend/tcop/postgres.c` | Add `case PqMsg_<New>:` to the `PostgresMain` read-loop `switch (firstchar)` at line 4838. Decide if `forbidden_in_wal_sender` applies (line 5122). Reject during `ignore_till_sync` if appropriate. | [postgres.c.md](../files/src/backend/tcop/postgres.c.md) | replication-overview |
| 5 | `src/backend/libpq/pqcomm.c` | Usually NO edit — `pq_beginmessage` / `pq_putmessage` are tag-agnostic. Only touch if the new message needs a non-standard length prefix or framing (rare). | [pqcomm.c.md](../files/src/backend/libpq/pqcomm.c.md) | replication-overview |
| 6 | `src/backend/replication/walsender.c` | Only if the new message can arrive while the backend is acting as a walsender — add `case PqMsg_<New>:` to the loops at lines 785 and 813, OR an explicit reject under `forbidden_in_wal_sender`. | — | replication-overview |
| 7 | `src/interfaces/libpq/fe-connect.c` | If sent during startup: extend the `beresp` switch around line 4028 (`PqMsg_AuthenticationRequest` / `PqMsg_ErrorResponse` / `PqMsg_NegotiateProtocolVersion` is the allowed set today). Also update `min_protocol_version` / `max_protocol_version` defaults if applicable (line 340). | [fe-connect.c.md](../files/src/interfaces/libpq/fe-connect.c.md) | replication-overview |
| 8 | `src/interfaces/libpq/fe-exec.c` | If the client originates the message: add a `pqPutMsgStart(PqMsg_<New>, conn)` emit site (pattern: line 1472 for Query, 1613 for Sync). Plumb a new `PQ<verb>` public API if user-facing. | [fe-exec.c.md](../files/src/interfaces/libpq/fe-exec.c.md) | replication-overview |
| 9 | `src/interfaces/libpq/fe-protocol3.c` | Add a `case PqMsg_<New>:` to the async parser at line 202 AND/OR the auth/startup parser at line 1895. Update the "complete-message" predicate at lines 39-45 if the new tag needs known-length pre-check. | [fe-protocol3.c.md](../files/src/interfaces/libpq/fe-protocol3.c.md) | replication-overview |
| 10 | `src/interfaces/libpq/fe-trace.c` | Add a `case PqMsg_<New>:` in `pqTraceOutputMessage` at line 653 with a one-line dumper. If the tag collides with a same-byte-different-direction message, add an `Assert(PqMsg_X == PqMsg_Y)` comment line per pattern at lines 684/696/704/714. | [fe-trace.c.md](../files/src/interfaces/libpq/fe-trace.c.md) | replication-overview |
| 11 | `src/interfaces/libpq/libpq-int.h` | Add any new conn-state fields the message handler needs (e.g. `negotiated_min_protocol_version` for `NegotiateProtocolVersion`). | [libpq-int.h.md](../files/src/interfaces/libpq/libpq-int.h.md) | replication-overview |
| 12 | `src/interfaces/libpq/exports.txt` | Append (NEVER renumber) any new `PQ<verb>` public API at the next sequential ordinal. Symbol ABI is append-only. | — | replication-overview |
| 13 | `src/interfaces/libpq/libpq-fe.h` | Public prototype for any new `PQ<verb>` exported above. | [libpq-fe.h.md](../files/src/interfaces/libpq/libpq-fe.h.md) | replication-overview |
| 14 | `doc/src/sgml/protocol.sgml` — Message Flow sect1 | Narrate WHEN the message arrives. Edit the sub-sect (Start-up, Simple Query, Extended Query, Pipelining, Replication, etc.) that owns the exchange. Lines 397, 412, 726, 1028, 1257, 1593, 2184. | — | replication-overview |
| 15 | `doc/src/sgml/protocol.sgml` — Message Formats sect1 | Add a `<varlistentry id="protocol-message-formats-<New>">` block at line 3807 following the pattern at line 5426 (`Byte1('x')` + `Int32` length + per-field entries). | — | replication-overview |
| 16 | `doc/src/sgml/protocol.sgml` — Protocol Versions sect2 | If `PG_PROTOCOL_LATEST` bumped: update lines 192-318 ("Protocol Versions" / "Supported Protocol Versions") and the protocol-extensions section at line 318 if the message is gated behind one. | — | replication-overview |
| 17 | `src/test/modules/libpq_pipeline/libpq_pipeline.c` + `traces/*.trace` | Add a regression case that exercises the new message and capture its trace. The `.trace` files at `src/test/modules/libpq_pipeline/traces/` are golden-output checked. | — | replication-overview |
| 18 | `src/test/perl/PostgreSQL/Test/Cluster.pm` callers (TAP) | If the message participates in connect/startup, add a TAP test that runs against both `max_protocol_version=3.0` and `=latest` to confirm graceful degradation. | — | replication-overview |
| 19 | `src/tools/pgindent/typedefs.list` | Add any new typedef (struct/enum) introduced for the message payload — required for pgindent to format consistently. | — | coding-style |

## Phases — suggested split for `pg-feature-plan`

The tree must build at the end of each phase.

1. **Phase 1 — Wire constants + version bump.** Files: [1, 2, 19].
   Add the `PqMsg_<New>` tag, bump `PG_PROTOCOL_LATEST`, register
   typedefs. No emit / no parse yet. Phase-end check: `meson compile
   -C dev/build-debug` clean; no behavior change yet (the tag is
   defined but unused). `[inferred]`.
2. **Phase 2 — Backend emit + dispatch.** Files: [3, 4, 5, 6].
   Implement the server side of the new exchange end-to-end. Existing
   libpq won't see the new tag yet because no current client asks for
   `max_protocol_version >= <new>`. Phase-end check: `meson test -C
   dev/build-debug --suite regress` green; a hand-written `psql
   --set=PROTOCOL_VERSION=3.<new>` round-trip (if user-tunable)
   exchanges the message.
3. **Phase 3 — Frontend libpq emit / parse / trace.** Files: [7, 8, 9,
   10, 11, 12, 13]. Wire up libpq to actually send/receive. Bump
   `exports.txt` for any new `PQ<verb>`. Phase-end check: `meson test
   -C dev/build-debug --suite interfaces` plus the
   `libpq_pipeline.trace` files re-baseline cleanly.
4. **Phase 4 — Tests + docs.** Files: [14, 15, 16, 17, 18]. SGML
   for both flow and format; TAP for backward compat. Phase-end
   check: `meson test -C dev/build-debug --suite recovery --suite
   subscription` (since replication touches protocol.sgml too), plus
   `meson compile -C dev/build-debug doc/postgres-A4.pdf` or `html`
   to lint the SGML. `[verified-by-code]`
   (`doc/src/sgml/Makefile`).

## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`bgworker-and-parallel`](../idioms/bgworker-and-parallel.md) | shares files: `src/backend/access/transam/parallel.c` |
| [`error-handling`](../idioms/error-handling.md) | direct reference |
| [`memory-contexts`](../idioms/memory-contexts.md) | direct reference |
| [`parallel-context-and-dsm`](../idioms/parallel-context-and-dsm.md) | shares files: `src/backend/access/transam/parallel.c` |
| [`parallel-state-propagation`](../idioms/parallel-state-propagation.md) | shares files: `src/backend/access/transam/parallel.c` |
| [`parallel-worker-coordination`](../idioms/parallel-worker-coordination.md) | shares files: `src/backend/access/transam/parallel.c` |
| [`parallel-worker-launch-wait-and-errors`](../idioms/parallel-worker-launch-wait-and-errors.md) | shares files: `src/backend/access/transam/parallel.c` |
| [`snapshot-export-historic-parallel`](../idioms/snapshot-export-historic-parallel.md) | shares files: `src/backend/access/transam/parallel.c` |
| [`utility-stmt-planning`](../idioms/utility-stmt-planning.md) | shares files: `src/backend/tcop/postgres.c` |
| [`walsender-state-machine`](../idioms/walsender-state-machine.md) | shares files: `src/backend/replication/walsender.c` |

<!-- /idioms-invoked:auto -->
## Pitfalls

- **Tag collision in the same direction.** `protocol.h` lets you
  reuse a byte for different-direction messages (`'p'` is overloaded
  4 ways FE→BE). Reusing a byte that's already FE→BE — or BE→FE —
  silently corrupts the dispatch switch. Grep
  `src/include/libpq/protocol.h` for the byte literal before
  defining. `[verified-by-code]`
  (`src/include/libpq/protocol.h:30-33`).
- **`PG_PROTOCOL_LATEST` not bumped.** Old clients won't request
  the new minor, so they'll never see the message. The risk is
  *inverse* — backends MUST clamp to what the client asked for at
  `backend_startup.c:734`. Adding an unsolicited message at minor
  3.2 to a 3.0 client is a protocol violation.
  `[verified-by-code]` (`src/backend/tcop/backend_startup.c:734-745`).
- **Skipped reserved minor.** `PG_PROTOCOL_RESERVED_31 = (3, 1)` is
  deliberately unused to avoid pgbouncer collision. Use 3.2 → 3.3,
  not 3.2 → 3.1. `[from-comment]`
  (`src/include/libpq/pqcomm.h:101-105`).
- **Forgetting `forbidden_in_wal_sender`.** A message that's
  meaningful to `PostgresMain` but nonsense to a walsender process
  must be rejected explicitly at `src/backend/tcop/postgres.c:5122`
  or it'll trip an Assert. `[verified-by-code]`
  (`src/backend/tcop/postgres.c:5122-5141`).
- **Trace dumper missing.** `fe-trace.c` is required for every new
  tag — without it `PQtrace` shows `Unknown message: id=<x>` and the
  golden `.trace` files in `libpq_pipeline/traces/` will fail to
  regenerate. `[verified-by-code]`
  (`src/interfaces/libpq/fe-trace.c:653-820`).
- **`exports.txt` renumbered instead of appended.** `libpq.so` ABI
  is positional. New `PQ<verb>` symbols MUST go at the next
  sequential ordinal — never renumber existing entries.
  `[from-comment]` (`src/interfaces/libpq/exports.txt:1`).
- **Synchronization traps** (sibling files that must change
  together):
  - `protocol.h` ↔ `fe-trace.c` (every new tag needs a trace case).
  - `protocol.h` ↔ `fe-protocol3.c` (every BE→FE tag needs a parse
    case in BOTH the async switch line 202 and, if startup-time,
    the line-1895 switch).
  - `pqcomm.h` `PG_PROTOCOL_LATEST` ↔ `backend_startup.c:734`
    clamp ↔ `fe-connect.c:340` `min/max_protocol_version` ↔
    `protocol.sgml` "Protocol Versions" section.
  - `protocol.sgml` Message Flow ↔ Message Formats — never edit one
    without the other.

## Verification (exact test invocations)

```bash
# Core regression — startup / simple-query / extended-query exchanges
meson test -C dev/build-debug --suite regress

# libpq pipeline regression — exercises the parse-side switch and
# regenerates trace files
meson test -C dev/build-debug --suite libpq_pipeline

# Authentication paths — only if the new message touches auth
meson test -C dev/build-debug --suite authentication

# Recovery + subscription — protocol.sgml also documents replication
# message flow, and walsender shares the dispatch
meson test -C dev/build-debug --suite recovery
meson test -C dev/build-debug --suite subscription

# SGML doc build (catches malformed varlistentry IDs)
meson compile -C dev/build-debug html

# Backwards-compat smoke: connect with explicit older protocol
PGMAXPROTOCOLVERSION=3.0 dev/install-debug/bin/psql -c "SELECT 1"
PGMINPROTOCOLVERSION=3.<new> dev/install-debug/bin/psql -c "SELECT 1"
```

If the change adds a brand-new test, name it explicitly under
`src/test/modules/libpq_pipeline/t/` (TAP) or extend
`src/test/modules/libpq_pipeline/libpq_pipeline.c` (C harness).

## Cross-refs

- Companion skills:
  `.claude/skills/replication-overview/SKILL.md` (wire-framing
  cadence, even for non-replication messages).
- Related scenarios: `scenarios/add-new-replication-message.md`
  (logical-decoding output-plugin / walsender command messages —
  same framing rules, different transport).
- Idioms: `knowledge/idioms/error-handling.md` (an unknown tag must
  raise `PROTOCOL_VIOLATION` not a bare `elog`),
  `knowledge/idioms/memory-contexts.md` (StringInfo lifetime around
  `pq_beginmessage` / `pq_endmessage`).
- Subsystems: `knowledge/subsystems/libpq-backend.md`,
  `knowledge/subsystems/tcop.md`,
  `knowledge/subsystems/replication.md` (for the walsender dispatch
  half).
- Issues: any new wire change must be socialized on pgsql-hackers
  before commit — protocol changes are explicitly called out in
  `.claude/skills/patch-submission/SKILL.md` as one of the
  highest-review-bar change-classes. `[from-README]`.
- Reference patch (canonical_commit): `git -C source show
  bbf9c282ce9` — *"libpq: Handle NegotiateProtocolVersion
  message"*. Pair with `516b87502dc` for the version-negotiation
  invariants and `f4b54e1ed98` for the `PqMsg_*` macro convention.
