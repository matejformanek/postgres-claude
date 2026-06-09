# sepgsql.h

## One-line summary

Public header for `contrib/sepgsql`: defines the internal class-code/access-vector
constants (`SEPG_CLASS_*`, `SEPG_DB_*__*`) used to talk to SELinux, the mode enum
(`SEPGSQL_MODE_DEFAULT/PERMISSIVE/INTERNAL/DISABLED`), the label tag string, and
the extern decls for every cross-file entry point.

## Public API / entry points

This is a header — no SQL-callable functions live here, but it is the public ABI
within the module. Externs declared (file:line cites):

- GUC getters: `sepgsql_get_permissive`, `sepgsql_get_debug_audit` —
  `source/contrib/sepgsql/sepgsql.h:218-219` [verified-by-code]
- selinux.c facade: `sepgsql_is_enabled`, `sepgsql_get_mode`, `sepgsql_set_mode`,
  `sepgsql_getenforce`, `sepgsql_audit_log`, `sepgsql_compute_avd`,
  `sepgsql_compute_create` — `source/contrib/sepgsql/sepgsql.h:224-245`
- uavc.c: `sepgsql_avc_check_perms_label` (label-form check) and
  `sepgsql_avc_check_perms` (ObjectAddress-form), `sepgsql_avc_trusted_proc`,
  `sepgsql_avc_init` — `source/contrib/sepgsql/sepgsql.h:251-262`
- label.c: `sepgsql_get_client_label`, `sepgsql_init_client_label`,
  `sepgsql_get_label`, `sepgsql_object_relabel` —
  `source/contrib/sepgsql/sepgsql.h:267-272`
- dml.c: `sepgsql_dml_privileges` — `source/contrib/sepgsql/sepgsql.h:277-278`
- per-object-class entry points for database/schema/relation/proc — see lines
  283-322

## Key invariants

- `tclass < SEPG_CLASS_MAX` (= 18) — every routine that indexes
  `selinux_catalog[tclass]` asserts this in selinux.c. The class IDs are
  contiguous, starting from `SEPG_CLASS_PROCESS = 0`
  (`source/contrib/sepgsql/sepgsql.h:36-54`). [verified-by-code]
- The `SEPG_LABEL_TAG = "selinux"` string (`sepgsql.h:23`) is the discriminator
  used by `commands/seclabel.c` to multiplex among label providers
  (`register_label_provider`). The provider hook is wired in `hooks.c:469-470`.
  [verified-by-code]
- Permission bitmasks are 32-bit. Each class has up to 32 access vectors;
  `selinux_catalog[].av[32]` array bounds this hard (`selinux.c:38`).
  [verified-by-code]
- `SEPGSQL_AVC_NOAUDIT = ((void *)(-1))` — sentinel passed as `audit_name` to
  suppress audit logging for "speculative" checks (e.g. function-inlining
  permission probe in `label.c:297`). `sepgsql.h:250`. [verified-by-code]
- `SEPG_DB_TUPLE__*` is defined but only via the (presumably never-enabled)
  row-level path — uavc/dml.c does not currently issue per-tuple checks; the
  check is per-column, per-relation. [inferred]

## Notable internals

- The header pulls in `<selinux/selinux.h>` and `<selinux/avc.h>`
  (`sepgsql.h:17-18`) — every translation unit that includes `sepgsql.h`
  unconditionally requires libselinux. There is no `HAVE_LIBSELINUX` gate inside
  the module; the gate lives in the build system (`meson.build` /
  configure).
- The constant `SEPGSQL_MODE_DISABLED = 4` is set by `_PG_init` when
  `is_selinux_enabled() < 1`, and `sepgsql_is_enabled()` returns the inverse
  (`selinux.c:615-619`). [verified-by-code]

## Trust boundary / Phase D surface

- **Header-only ABI.** The macros baked into `SEPG_CLASS_*` and `SEPG_*__*` are
  **internal** codes — they are translated to the kernel's runtime codes by
  `selinux_catalog[]` in selinux.c. A mismatch between header values and the
  catalog table is a silent miscompile: every checked permission would refer to
  the wrong access vector. The Assert at `selinux.c:752`
  (`tclass == selinux_catalog[tclass].class_code`) is the only runtime guard.
  [verified-by-code]
- **Permission encoding is bit-position dependent.** `selinux_catalog` translation
  loops on `i` from 0 to NULL terminator and tests `audited & (1UL << i)` to map
  bit-position back to permission name (`selinux.c:699-705`). If a developer
  reorders entries in `selinux_catalog[X].av[]` without changing the bit shifts
  in the header, audit log messages will be wrong (`denied { select }` would
  print `denied { create }`) but enforcement would not be affected at the bit
  level — though *the kernel's external code* mapping might mismatch.
  [ISSUE-correctness: silent bit-vs-array-index coupling between sepgsql.h
  `SEPG_*__*` shifts and `selinux_catalog[]` order (likely)]

## Cross-references

- `source/src/include/commands/seclabel.h` — provider registration API,
  `register_label_provider`, `GetSecurityLabel`, `SetSecurityLabel`.
- `source/src/include/catalog/objectaccess.h` — `object_access_hook`,
  `ObjectAccessType` enum; the multiplex point sepgsql attaches to.
- libselinux headers — external dependency.

## Issues spotted

- `[ISSUE-correctness: SEPG_*__* bit positions in header are coupled to
  selinux_catalog[].av[] array order in selinux.c by index — a future
  contributor reordering AVs in either place breaks the translation silently
  (likely)]`
- `[ISSUE-api-shape: SEPGSQL_AVC_NOAUDIT is a (void*)(-1) sentinel cast to
  const char*, comparing pointers to an explicit numeric audit_name skips
  audit; if any caller passes an audit string equal to that pointer value
  (UB), audit is silently suppressed — practical risk is nil but typing is
  ugly (nit)]`
- `[ISSUE-documentation: no comment in the header explains the
  SEPGSQL_MODE_INTERNAL semantic ("permissive but silent") — only
  selinux.c:608 explains it (nit)]`
