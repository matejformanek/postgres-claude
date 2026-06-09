---
path: src/backend/access/rmgrdesc/logicalmsgdesc.c
anchor_sha: 4b0bf0788b0
loc: 52
depth: deep
---

# logicalmsgdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/logicalmsgdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 52

## Purpose

rmgr descriptor routines for the logical-decoding message resource
manager (`RM_LOGICALMSG_ID`, records from
`replication/logical/message.c`). Renders the single `XLOG_LOGICAL_MESSAGE`
opcode — the WAL representation of `pg_logical_emit_message()` — for
`pg_waldump`. [from-comment, logicalmsgdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `logicalmsg_desc(buf, record)` | `logicalmsgdesc.c:18` | render the message prefix + hex payload |
| `logicalmsg_identify(info)` | `logicalmsgdesc.c:45` | opcode → `"MESSAGE"` or `NULL` |

## Internal landmarks

- The record body is `xl_logical_message`: a `prefix_size`-byte
  null-terminated prefix string immediately followed by a
  `message_size`-byte payload. `logicalmsg_desc` prints
  `transactional`/`non-transactional`, the prefix as a quoted `%s`, then
  the payload as space-separated `%02X` hex bytes (logicalmsgdesc.c:33-41).

## Invariants & gotchas

- **Prefix null-termination is asserted, not enforced.**
  `Assert(prefix[xlrec->prefix_size - 1] == '\0')` (logicalmsgdesc.c:31)
  only fires in assert-enabled builds; the subsequent `%s` of `prefix`
  trusts that terminator. The prefix and payload are *user-supplied*
  (the SQL caller of `pg_logical_emit_message` chooses both), so this
  desc renders attacker-influenced bytes — but into `pg_waldump`'s text
  output, not into SQL, and the payload is hex-escaped. Prefix is
  printed raw via `%s`. See Potential issues.
- **Payload is always hex-dumped** — no length cap; a multi-megabyte
  message produces a correspondingly huge `pg_waldump` line.

## Cross-refs

- `xl_logical_message` + `XLOG_LOGICAL_MESSAGE`:
  `[[src/include/replication/message.h]]`.
- Replication overview: `.claude/skills/replication-overview/SKILL.md`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
- Corpus theme — `appendStringInfo("%s", untrusted)` sinks: see
  `knowledge/issues/include-utils.md` (stringinfo.h trust notes).

## Potential issues

- **[ISSUE-question: user-controlled prefix rendered raw via %s into
  waldump]** `logicalmsgdesc.c:33` — the logical-message prefix comes
  from the SQL-level `pg_logical_emit_message(prefix => ...)` caller and
  is printed with `%s` (after an assert-only null-termination check).
  The payload beside it is hex-escaped, but the prefix is not. Output
  sink is `pg_waldump`'s terminal text (an offline DBA tool), so this is
  not an injection vector in the SQL sense; flagged `nit` because it is
  the one descriptor rendering caller-controlled text unescaped, fitting
  the corpus's stringinfo-%s-untrusted tracking. Mirrored to
  `knowledge/issues/access-rmgrdesc.md`.
