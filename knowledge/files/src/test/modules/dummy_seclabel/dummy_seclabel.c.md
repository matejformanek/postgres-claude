---
path: src/test/modules/dummy_seclabel/dummy_seclabel.c
anchor_sha: e18b0cb7344
loc: 60
depth: read
---

# src/test/modules/dummy_seclabel/dummy_seclabel.c

## Purpose

Tiny security-label provider for regression-testing the `SECURITY LABEL ...
FOR ...` machinery without depending on platform-specific MAC providers like
sepgsql/SELinux. Registers a `"dummy"` provider that accepts a fixed
vocabulary: `unclassified`, `classified` (anyone), `secret`, `top secret`
(superuser only); anything else errors with `ERRCODE_INVALID_NAME`.
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `dummy_seclabel.c:46` | `register_label_provider("dummy", dummy_object_relabel)` |
| `dummy_seclabel_dummy` | `:56` | Trivial PG_FUNCTION_INFO_V1 stub — exists so the extension has at least one SQL function and the `.so` is loaded by `CREATE EXTENSION` |
| `dummy_object_relabel` (static) | `:24` | Provider callback: accept/deny based on label string |

## Internal landmarks

- The provider callback signature is `(const ObjectAddress *, const char *
  seclabel)` — `seclabel == NULL` means "unset label" and is always allowed
  (`:27-30`).
- Privilege check: `secret`/`top secret` require `superuser()` (`:32-39`);
  the comparison is plain `strcmp` — case-sensitive, exact match.

## Invariants & gotchas

- **Test module — never load in production.**
- The companion `.sql` script registers the extension with appropriate
  `pg_seclabel.provider` rows; this C file is just the callback.
- `dummy_seclabel_dummy` exists only so the extension has SQL surface area;
  the comment at `:53-54` says so.

## Cross-refs

- `source/src/backend/commands/seclabel.c` — `register_label_provider`,
  `ExecSecLabelStmt`.
- `source/contrib/sepgsql/` — the real MAC provider this skeleton models.
