#!/usr/bin/env python3
"""Build the scenario ↔ idiom bidirectional linkage.

For each scenario, compute its set of invoked idioms by union of:

  A. Direct in-prose references to `knowledge/idioms/<slug>.md`.
  B. `companion_skills:` frontmatter entries that match an idiom slug
     (some scenarios use companion_skills for both skills AND idioms —
     3 slugs overlap: catalog-conventions, error-handling, memory-contexts).
  C. Transitive: for every `source/<path>` file the scenario mentions
     (via §Files table, §Pre-flight, §Sites-touched, prose), any idiom
     whose Call sites table includes that file. This is evidence-based
     — the idiom already documented that pattern lives in that file.

Emit:

  1. Per scenario: a `## Idioms invoked` section (bracketed by
     `<!-- idioms-invoked:auto -->` markers) with a table.
  2. Per idiom: a `## Scenarios that use me` section (bracketed by
     `<!-- scenarios:auto -->` markers) with the reverse list.
  3. Central `progress/scenario-idiom-matrix.md` — a big join table.

Idempotent — re-runs replace blocks between markers.
"""
from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent,
            text=True,
        )
        return Path(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path(__file__).resolve().parent.parent


ROOT = _repo_root()
SCENARIOS = ROOT / "knowledge" / "scenarios"
IDIOMS = ROOT / "knowledge" / "idioms"
FILES_DOCS = ROOT / "knowledge" / "files"
MATRIX_OUT = ROOT / "progress" / "scenario-idiom-matrix.md"

# Match either `source/src/foo.c` or bare `src/foo.c` / `contrib/foo.c`.
# The negative-lookbehind avoids matching `.../src/foo.c` (e.g. absolute paths).
SOURCE_PATH_PREFIXED = re.compile(r"`?source/([A-Za-z0-9_./+-]+?\.[A-Za-z0-9_+-]+)(?::\d+(?:-\d+)?)?`?")
SOURCE_PATH_BARE = re.compile(r"(?<![/\w])`?((?:src|contrib)/[A-Za-z0-9_./+-]+?\.[A-Za-z0-9_+-]+)(?::\d+(?:-\d+)?)?`?")


def _collect_source_paths(text: str) -> set[str]:
    return set(SOURCE_PATH_PREFIXED.findall(text)) | set(SOURCE_PATH_BARE.findall(text))


# Legacy alias used elsewhere in this module.
SOURCE_PATH = SOURCE_PATH_PREFIXED
IDIOM_MD_REF = re.compile(r"knowledge/idioms/([A-Za-z0-9_-]+)\.md")
IDIOM_BACKTICK = re.compile(r"`([a-z][a-z0-9-]+)`")

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
COMPANION_SKILLS = re.compile(r"^companion_skills:\s*\[(.*?)\]\s*$", re.M)

IDIOMS_INVOKED_BLOCK = re.compile(
    r"\n?## Idioms invoked\s*\n<!-- idioms-invoked:auto -->.*?<!-- /idioms-invoked:auto -->\n?",
    re.DOTALL,
)
SCENARIOS_USING_BLOCK = re.compile(
    r"\n?## Scenarios that use me\s*\n<!-- scenarios:auto -->.*?<!-- /scenarios:auto -->\n?",
    re.DOTALL,
)

# Insertion point in scenarios (before these headings).
SCENARIO_INSERT_BEFORE = re.compile(
    r"\n(## (Related scenarios|References|Historical commits|See also|Pitfalls|Open questions)\b[^\n]*)"
)
# In idioms — put after Call sites, or before Open questions if no Call sites.
IDIOM_INSERT_BEFORE = re.compile(
    r"\n(## (Open questions|Unverified|Cross-references|Related idioms|See also)\b[^\n]*)"
)


def idiom_slugs() -> set[str]:
    return {
        p.stem
        for p in IDIOMS.glob("*.md")
        if p.name.lower() not in {"readme.md", "_index.md", "template.md"}
    }


def scenario_slugs() -> list[Path]:
    return sorted(
        p
        for p in SCENARIOS.glob("*.md")
        if p.name.lower() not in {"readme.md", "_index.md", "template.md", "_template.md"}
    )


def parse_idiom_callsites(path: Path) -> set[str]:
    """Extract the set of source paths in this idiom's `## Call sites` table."""
    text = path.read_text()
    m = re.search(
        r"## Call sites\s*\n<!-- callsites:auto -->(.*?)<!-- /callsites:auto -->",
        text,
        re.DOTALL,
    )
    if not m:
        return _collect_source_paths(text)
    return _collect_source_paths(m.group(1))


def build_file_to_idioms() -> dict[str, set[str]]:
    """Reverse index: source path → set of idiom slugs whose Call sites include it."""
    idx: dict[str, set[str]] = defaultdict(set)
    for path in IDIOMS.glob("*.md"):
        if path.name.lower() in {"readme.md", "_index.md", "template.md"}:
            continue
        for src in parse_idiom_callsites(path):
            idx[src].add(path.stem)
    return dict(idx)


def scenario_direct_idiom_refs(text: str, all_idiom_slugs: set[str]) -> set[str]:
    """Idiom slugs referenced explicitly in this scenario's text."""
    direct = set(IDIOM_MD_REF.findall(text))
    # companion_skills frontmatter values that match idiom slugs.
    fm = FRONTMATTER.match(text)
    if fm:
        for m in COMPANION_SKILLS.finditer(fm.group(1)):
            items = [x.strip().strip('"').strip("'") for x in m.group(1).split(",") if x.strip()]
            for it in items:
                if it in all_idiom_slugs:
                    direct.add(it)
    return direct


def scenario_source_paths(text: str) -> set[str]:
    """Every `source/…` or bare `src/…` / `contrib/…` file path referenced."""
    return _collect_source_paths(text)


def render_link(target_slug: str, kind: str) -> str:
    """Return a markdown link from a scenario/idiom doc to another under knowledge/."""
    if kind == "idiom":
        return f"[`{target_slug}`](../idioms/{target_slug}.md)"
    if kind == "scenario":
        return f"[`{target_slug}`](../scenarios/{target_slug}.md)"
    return f"`{target_slug}`"


def render_scenario_idioms_section(idioms_direct: set[str], idioms_transitive: dict[str, set[str]]) -> str:
    """idioms_transitive: idiom_slug → set of source-file paths that triggered inclusion."""
    lines = [
        "## Idioms invoked",
        "<!-- idioms-invoked:auto -->",
        "",
        "*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*",
        "*Refresh via `scripts/build-scenario-idiom-matrix.py`.*",
        "",
    ]
    all_idioms = set(idioms_direct) | set(idioms_transitive.keys())
    if not all_idioms:
        lines.append("_(none detected)_")
        lines.append("")
        lines.append("<!-- /idioms-invoked:auto -->")
        return "\n".join(lines) + "\n"
    lines.append("| Idiom | Evidence |")
    lines.append("|---|---|")
    for slug in sorted(all_idioms):
        evidence_parts: list[str] = []
        if slug in idioms_direct:
            evidence_parts.append("direct reference")
        if slug in idioms_transitive:
            files = sorted(idioms_transitive[slug])
            if len(files) <= 3:
                evidence_parts.append("shares files: " + ", ".join(f"`{f}`" for f in files))
            else:
                evidence_parts.append(f"shares {len(files)} files (e.g. `{files[0]}`, `{files[1]}`)")
        lines.append(f"| {render_link(slug, 'idiom')} | {'; '.join(evidence_parts)} |")
    lines.append("")
    lines.append("<!-- /idioms-invoked:auto -->")
    return "\n".join(lines) + "\n"


def render_idiom_scenarios_section(scenarios: set[str]) -> str:
    lines = [
        "## Scenarios that use me",
        "<!-- scenarios:auto -->",
        "",
        "*Auto-derived from direct references + transitive file-overlap.*",
        "*Refresh via `scripts/build-scenario-idiom-matrix.py`.*",
        "",
    ]
    if not scenarios:
        lines.append("_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_")
        lines.append("")
        lines.append("<!-- /scenarios:auto -->")
        return "\n".join(lines) + "\n"
    for slug in sorted(scenarios):
        lines.append(f"- {render_link(slug, 'scenario')}")
    lines.append("")
    lines.append("<!-- /scenarios:auto -->")
    return "\n".join(lines) + "\n"


def upsert(text: str, section: str, block_re: re.Pattern, before_re: re.Pattern) -> str:
    if block_re.search(text):
        return block_re.sub("\n\n" + section, text)
    m = before_re.search(text)
    if m:
        return text[: m.start()] + "\n\n" + section + text[m.start():]
    return text.rstrip() + "\n\n" + section


def build_matrix_doc(
    scenario_to_idioms: dict[str, dict[str, set[str]]],
    idiom_to_scenarios: dict[str, set[str]],
    direct_map: dict[str, set[str]],
) -> str:
    lines = [
        "# Scenario ↔ Idiom matrix",
        "",
        "Bidirectional linkage between scenarios (change-class playbooks under `knowledge/scenarios/`) and idioms (cross-cutting patterns under `knowledge/idioms/`).",
        "",
        "**Refresh via `scripts/build-scenario-idiom-matrix.py`.** Both this file and the per-doc sections in scenarios/idioms are regenerated from the same run.",
        "",
        "## How the linkage is derived",
        "",
        "For each scenario, we compute its invoked-idiom set as the union of:",
        "",
        "1. **Direct references** — the scenario body contains a `knowledge/idioms/<slug>.md` link, or its `companion_skills:` frontmatter names a slug that matches an idiom.",
        "2. **Transitive file-overlap** — the scenario mentions a `source/<path>` file, and that same file appears in an idiom's `## Call sites` table. This means the corpus already documented that the idiom's pattern lives in that file.",
        "",
        "The transitive edge is the leverage-heavy one: as long as scenarios name their files and idioms name their call sites, the matrix maintains itself.",
        "",
        "## Table",
        "",
        "| Scenario | # idioms | Idioms (top 8 by direct + transitive strength) |",
        "|---|---:|---|",
    ]
    for sc in sorted(scenario_to_idioms.keys()):
        entries = scenario_to_idioms[sc]
        # entries is idiom_slug → set(files); direct_map[sc] is set of direct refs
        all_ids = set(entries.keys()) | direct_map.get(sc, set())
        # Rank: direct + transitive-file-count
        def score(sl):
            return (
                (10 if sl in direct_map.get(sc, set()) else 0)
                + len(entries.get(sl, set()))
            )
        ranked = sorted(all_ids, key=lambda s: (-score(s), s))
        top = ranked[:8]
        cells = []
        for slug in top:
            tag = ""
            if slug in direct_map.get(sc, set()):
                tag = "*"
            cells.append(f"[`{slug}`](../knowledge/idioms/{slug}.md){tag}")
        more = f" +{len(ranked)-8}" if len(ranked) > 8 else ""
        lines.append(f"| [`{sc}`](../knowledge/scenarios/{sc}.md) | {len(all_ids)} | {', '.join(cells)}{more} |")

    lines.append("")
    lines.append("`*` = direct reference (idiom named in scenario prose or companion_skills). Others are transitive via shared files.")
    lines.append("")
    lines.append("## Reverse: which scenarios each idiom supports")
    lines.append("")
    lines.append("| Idiom | # scenarios | Scenarios |")
    lines.append("|---|---:|---|")
    for idm in sorted(idiom_to_scenarios.keys()):
        scs = sorted(idiom_to_scenarios[idm])
        cells = [f"[`{sc}`](../knowledge/scenarios/{sc}.md)" for sc in scs[:6]]
        more = f" +{len(scs)-6}" if len(scs) > 6 else ""
        lines.append(f"| [`{idm}`](../knowledge/idioms/{idm}.md) | {len(scs)} | {', '.join(cells)}{more} |")

    lines.append("")
    lines.append("Idioms with zero scenario references are cross-cutting infrastructure (memory-contexts, ereport patterns, WAL construction) or internal helper patterns — they still appear in file docs via idiom call-sites, but no single change-class scenario invokes them exclusively.")
    return "\n".join(lines) + "\n"


def main() -> int:
    all_idiom_slugs = idiom_slugs()
    file_to_idioms = build_file_to_idioms()

    scenario_to_idioms: dict[str, dict[str, set[str]]] = {}
    direct_map: dict[str, set[str]] = {}
    idiom_to_scenarios: dict[str, set[str]] = defaultdict(set)

    scenarios = scenario_slugs()
    for path in scenarios:
        text = path.read_text()
        slug = path.stem
        direct = scenario_direct_idiom_refs(text, all_idiom_slugs)
        files = scenario_source_paths(text)
        transitive: dict[str, set[str]] = defaultdict(set)
        for f in files:
            for idm in file_to_idioms.get(f, ()):
                transitive[idm].add(f)
        # Don't double-count direct entries in the transitive-only bucket.
        transitive_only = {
            k: v for k, v in transitive.items() if k not in direct
        }
        scenario_to_idioms[slug] = transitive_only
        direct_map[slug] = direct
        for idm in set(direct) | set(transitive.keys()):
            idiom_to_scenarios[idm].add(slug)

    # Write per-scenario sections
    updated_scenarios = 0
    for path in scenarios:
        text = path.read_text()
        slug = path.stem
        section = render_scenario_idioms_section(
            direct_map.get(slug, set()),
            scenario_to_idioms.get(slug, {}),
        )
        new = upsert(text, section, IDIOMS_INVOKED_BLOCK, SCENARIO_INSERT_BEFORE)
        if new != text:
            path.write_text(new)
            updated_scenarios += 1

    # Write per-idiom sections
    updated_idioms = 0
    for path in IDIOMS.glob("*.md"):
        if path.name.lower() in {"readme.md", "_index.md", "template.md"}:
            continue
        text = path.read_text()
        slug = path.stem
        section = render_idiom_scenarios_section(idiom_to_scenarios.get(slug, set()))
        new = upsert(text, section, SCENARIOS_USING_BLOCK, IDIOM_INSERT_BEFORE)
        if new != text:
            path.write_text(new)
            updated_idioms += 1

    # Write central matrix
    MATRIX_OUT.parent.mkdir(parents=True, exist_ok=True)
    matrix = build_matrix_doc(scenario_to_idioms, idiom_to_scenarios, direct_map)
    MATRIX_OUT.write_text(matrix)

    # Stats
    total_edges = sum(
        len(direct_map.get(sc, set()) | set(scenario_to_idioms.get(sc, {}).keys()))
        for sc in scenario_to_idioms
    )
    print(f"Scenarios processed:     {len(scenarios)}")
    print(f"Scenarios updated:       {updated_scenarios}")
    print(f"Idioms updated:          {updated_idioms}")
    print(f"Total scenario→idiom edges: {total_edges}")
    print(f"Scenarios with zero idioms: {sum(1 for sc in scenario_to_idioms if not (direct_map.get(sc, set()) | set(scenario_to_idioms.get(sc, {}).keys())))}")
    print(f"Idioms with zero scenario refs: {sum(1 for i in all_idiom_slugs if i not in idiom_to_scenarios)}")
    print(f"Matrix written to:       {MATRIX_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
