---
source_url: https://www.postgresql.org/docs/current/runtime-config-custom.html
fetched_at: 2026-07-02T20:49:00Z
anchor_sha: b542d5566705
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Customized Options (§20.16)

The half-page that explains how extension GUCs and the placeholder mechanism
work — the user-facing counterpart to the `gucs-config` skill's
`DefineCustom*Variable` machinery.

## The two-part dotted-name rule

- **A custom GUC MUST have a two-part `extension.parameter` name** (e.g.
  `plpgsql.variable_conflict`). PostgreSQL accepts a setting for *any* two-part
  name — this is deliberate, so config can name a parameter the defining module
  hasn't loaded yet. Single-part unknown names are rejected. [from-docs]

## Placeholders — set-before-load, resolved-at-load

- Exact quote: *"Because custom options may need to be set in processes that
  have not loaded the relevant extension module, PostgreSQL will accept a
  setting for any two-part parameter name. Such variables are treated as
  **placeholders** and have no function until the module that defines them is
  loaded."* [from-docs]
- On module load: *"it will add its variable definitions and **convert any
  placeholder values according to those definitions**. If there are any
  unrecognized placeholders that begin with its extension name, warnings are
  issued and those placeholders are removed."* [from-docs]

## Why this matters to an extension author (`gucs-config` cross-ref)

- The placeholder is stored as an untyped string; the real type
  (bool/int/real/enum) is applied only when `DefineCustom*Variable` runs in
  `_PG_init`. A mistyped value in `postgresql.conf` therefore surfaces as an
  error at **load time**, not config-parse time — a common "my GUC won't take"
  footgun. [inferred-from-docs]
- The "unrecognized placeholder beginning with its extension name → warning +
  removed" rule means a **typo in your own prefix** (`myext.fooo` vs
  `myext.foo`) is silently dropped with a warning once your module loads, not
  kept as a live placeholder. [from-docs]
- The page does NOT document `MarkGUCPrefixReserved` (which upgrades unknown
  `prefix.*` names from accepted-placeholder to rejected — the skill covers
  that) nor the historical `custom_variable_classes` GUC (removed in 9.2).
  Those live in the `gucs-config` skill / `guc.c`. [from-docs — absence noted]

## Links into corpus

- [[knowledge/docs-distilled/runtime-config-developer.md]] — sibling §20 page.
- Skill: `gucs-config` — `DefineCustomBoolVariable` … `EnumVariable`,
  `MarkGUCPrefixReserved`, the check/assign/show hook trio, placeholder lifecycle.

## Confidence note

Placeholder + two-part-name claims are direct `[from-docs]` quotes. The
type-resolution-at-load-time and prefix-typo consequences are `[inferred]` from
the quoted load-time-conversion behavior; the authoritative mechanism is
`define_custom_variable()` / `find_option()` in `guc.c`.
