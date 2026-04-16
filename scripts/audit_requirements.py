#!/usr/bin/env python3
"""
Audit requirements files and produce two reports:

1. ORPHAN CANDIDATES
   Packages listed in the "Transitive Libraries" sections of requirements.in
   whose only pip-compile attribution is "# via -r requirements.in" — meaning
   no upstream package declares them as a dependency any more.  These are
   candidates for removal to slim the Docker image.

   Packages annotated with "# runtime-override:" are excluded; that tag
   signals a package that is genuinely needed at runtime but not visible to
   pip-compile (e.g. an undeclared runtime dependency of a third-party lib).

2. NEW / UNTRACKED PACKAGES
   Packages that pip-compile resolved into detailed_requirements.txt but that
   are not listed anywhere in requirements.in.  A sub-set is highlighted as
   "newly appeared" — packages not present in the previous committed version
   of detailed_requirements.txt (passed as --old-detailed).

Usage:
    python scripts/audit_requirements.py \\
        --detailed  detailed_requirements.txt \\
        --req-in    requirements.in \\
        [--old-detailed detailed_requirements_old.txt] \\
        --orphan-out   orphan_report.txt \\
        --new-pkg-out  new_packages_report.txt
"""

import argparse
import importlib.metadata
import pathlib
import re
import sys


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    """Canonicalise a package name: lowercase, underscores → hyphens."""
    return re.sub(r"[_.]", "-", name.strip().lower())


# ---------------------------------------------------------------------------
# Parse pip-compile output
# ---------------------------------------------------------------------------

def parse_detailed(path: str) -> dict[str, str]:
    """
    Parse a pip-compile output file.

    Returns {normalised_name: raw_via_block} for every package.
    The via block is the indented comment that follows the version line,
    e.g. "    # via -r requirements.in".
    """
    packages: dict[str, str] = {}
    with open(path) as f:
        content = f.read()

    # Each entry looks like:
    #   pkgname[extras]==version
    #       # via
    #       #   upstream-pkg
    # or the compact form:
    #   pkgname==version
    #       # via -r requirements.in

    block_re = re.compile(
        r"^([A-Za-z0-9][\w.\-]*(?:\[[^\]]*\])?)==[^\n]+\n((?:[ \t]+#[^\n]*\n?)*)",
        re.MULTILINE,
    )

    for m in block_re.finditer(content):
        raw_name = re.sub(r"\[.*\]", "", m.group(1))
        via_block = m.group(2)
        packages[_norm(raw_name)] = via_block

    return packages


# ---------------------------------------------------------------------------
# Parse requirements.in (Tailored for this requirements.in format only)
# ---------------------------------------------------------------------------

def parse_req_in(path: str) -> tuple[set[str], set[str], dict[str, bool]]:
    """
    Parse requirements.in.

    Returns:
        base_pkgs      – normalised names in the Base Libraries section
        transitive_pkgs – normalised names in the Transitive Libraries sections
        overrides       – {name: True} for packages marked # runtime-override:
    """
    base_pkgs: set[str] = set()
    transitive_pkgs: set[str] = set()
    overrides: dict[str, bool] = {}

    section = "base"          # start before any header
    current_pkg: str | None = None
    is_override = False

    with open(path) as f:
        lines = f.readlines()

    def _save_current():
        nonlocal current_pkg, is_override
        if current_pkg is None:
            return

        # record override regardless of section
        if is_override:
            overrides[current_pkg] = True

        if section == "transitive":
            transitive_pkgs.add(current_pkg)
        else:
            base_pkgs.add(current_pkg)

        current_pkg = None
        is_override = False

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()

        # ---- MAJOR SECTION HEADERS ----
        if "BASE LIBRARIES" in upper:
            _save_current()
            section = "base"
            continue

        if "TRANSITIVE" in upper:
            _save_current()
            section = "transitive"
            continue

        # ---- DECORATIVE SEPARATORS (#####) ----
        if stripped.startswith("#") and set(stripped) <= {"#"}:
            continue

        # ---- SUBSECTION HEADERS (## ...) ----
        if stripped.startswith("##"):
            continue

        # ---- BLANK ----
        if not stripped:
            continue

        # ---- COMMENT (package annotation) ----
        if stripped.startswith("#"):
            if current_pkg and "runtime-override" in stripped.lower():
                is_override = True
            continue

        # ---- PACKAGE LINE ----
        _save_current()
        raw = re.split(r"[=\[]", stripped)[0].strip()
        current_pkg = _norm(raw)
        is_override = False

    _save_current()
    return base_pkgs, transitive_pkgs, overrides


# ---------------------------------------------------------------------------
# Runtime-usage scanning
# ---------------------------------------------------------------------------

def get_top_level_modules(pkg_name: str) -> list[str]:
    """Return the importable top-level module names for an installed package.
    Reads the dist-info ``top_level.txt`` when present; falls back to
    replacing hyphens with underscores in the distribution name.
    """
    try:
        dist = importlib.metadata.distribution(pkg_name)
        top_level = dist.read_text("top_level.txt")
        if top_level:
            return [m.strip() for m in top_level.strip().splitlines() if m.strip()]
    except importlib.metadata.PackageNotFoundError:
        pass
    return [pkg_name.replace("-", "_")]


def scan_runtime_usage(orphans: list[str]) -> dict[str, list[str]]:
    """Scan every installed package's Python source for imports of each orphan.
    Uses simple substring matching (``import <module>`` / ``from <module>``)
    which is fast and catches both direct and lazy imports.
    Returns ``{orphan_name: [pkg_name_that_imports_it, ...]}``.  Only packages
    that import the orphan *without* declaring it as a metadata dependency are
    surfaced — exactly the cases pip-compile misses.
    """
    if not orphans:
        return {}

    orphan_set = set(orphans)

    # Build needle strings for each orphan based on its importable module names
    orphan_needles: dict[str, list[str]] = {}
    for orphan in orphans:
        mods = get_top_level_modules(orphan)
        orphan_needles[orphan] = (
            [f"import {m}" for m in mods] +
            [f"from {m}" for m in mods]
        )

    results: dict[str, list[str]] = {o: [] for o in orphans}

    for dist in importlib.metadata.distributions():
        raw_name = (dist.metadata.get("Name") or "").strip()
        if not raw_name:
            continue

        dist_name = _norm(raw_name)
        if dist_name in orphan_set:
            continue  # don't let an orphan "import itself"

        files = dist.files or []
        py_files = [dist.locate_file(f) for f in files if str(f).endswith(".py")]

        for orphan, needles in orphan_needles.items():
            if dist_name in results[orphan]:
                continue # already recorded this importer

            for py_path in py_files:
                try:
                    content = pathlib.Path(py_path).read_text(errors="replace")
                except OSError:
                    continue

                if any(needle in content for needle in needles):
                    results[orphan].append(dist_name)
                    break  # one match per dist is enough

    return results


# ---------------------------------------------------------------------------
# Audit 1: Orphan candidates
# ---------------------------------------------------------------------------

def find_orphans(
    detailed: dict[str, str],
    transitive_pkgs: set[str],
    overrides: dict[str, bool],
) -> list[str]:
    """
    Return transitive packages that pip-compile attributes only to
    '-r requirements.in' and that are not marked runtime-override.
    """
    orphans = []

    for pkg in transitive_pkgs:
        if pkg not in detailed:
            continue

        via = detailed[pkg]

        # Extract sources from via block
        lines = [
            l.strip()
            for l in via.strip().splitlines()
            if l.strip().startswith("#")
        ]

        sources = []
        for l in lines:
            l = l.lstrip("#").strip()
            if l.startswith("via"):
                continue
            sources.append(l)

        sources = [s.strip() for s in sources if s.strip()]

        if sources == ["-r requirements.in"]:
            if not overrides.get(pkg):
                orphans.append(pkg)

    return sorted(orphans)


# ---------------------------------------------------------------------------
# Audit 2: New / untracked packages
# ---------------------------------------------------------------------------

def find_new_packages(
    detailed: dict[str, str],
    base_pkgs: set[str],
    transitive_pkgs: set[str],
    old_detailed: dict[str, str] | None,
) -> tuple[list[str], list[str]]:
    """
    Return:
        untracked   – packages in detailed but absent from requirements.in
        newly_added – subset of untracked that were also absent from old_detailed
                      (i.e. they appeared for the first time in this compile run)
    """
    all_req_in = base_pkgs | transitive_pkgs
    untracked = sorted(p for p in detailed if p not in all_req_in)

    if old_detailed:
        newly_added = sorted(p for p in untracked if p not in old_detailed)
    else:
        newly_added = []

    return untracked, newly_added


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def write_orphan_report(
    orphans: list[str],
    out_path: str,
    runtime_usage: dict[str, list[str]] | None = None,
) -> None:
    lines: list[str] = []
    if not orphans:
        lines.append("No orphan candidates found.")
    else:
        lines.append(
            "Orphan candidates — in 'Transitive Libraries' of requirements.in but "
            "pip-compile cannot trace them to any upstream package:"
        )
        for p in orphans:
            lines.append(f"  - {p}")
            if runtime_usage is not None:
                importers = sorted(runtime_usage.get(p, []))
                if importers:
                    lines.append(
                        f"    Suggestion: POSSIBLY NEEDED — imported at runtime by: "
                        + ", ".join(importers)
                    )
                    lines.append(
                        f"    Action: add '# runtime-override: imported by "
                        + importers[0]
                        + " at runtime' to requirements.in"
                    )
                else:
                    lines.append(
                        "    Suggestion: SAFE TO REMOVE — no installed package imports it"
                    )
                    lines.append("    Action: remove from requirements.in")
        lines.append("")
        if runtime_usage is not None:
            lines.append(
                "Packages marked 'SAFE TO REMOVE' can be deleted from requirements.in. "
                "Packages marked 'POSSIBLY NEEDED' should be tagged with "
                "'# runtime-override: <reason>' to suppress this warning."
            )
        else:
            lines.append(
                "Consider removing them from requirements.in or adding "
                "'# runtime-override: <reason>' if they are needed at runtime."
            )
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def write_new_pkg_report(
    untracked: list[str],
    newly_added: list[str],
    out_path: str,
) -> None:
    lines: list[str] = []
    if not untracked:
        lines.append("All resolved packages are already listed in requirements.in.")
    else:
        lines.append(
            f"{len(untracked)} package(s) resolved by pip-compile are not listed "
            "in requirements.in:"
        )
        for p in untracked:
            tag = " *** NEW THIS RUN ***" if p in newly_added else ""
            lines.append(f"  - {p}{tag}")
        lines.append("")
        lines.append(
            "Add them to the appropriate 'Transitive Libraries' section of "
            "requirements.in to make the dependency explicit."
        )
        if newly_added:
            lines.append("")
            lines.append(
                f"Packages marked '*** NEW THIS RUN ***' ({len(newly_added)}) "
                "were not present in the previous compiled output."
            )
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detailed", default="detailed_requirements.txt")
    parser.add_argument("--req-in", default="requirements.in")
    parser.add_argument("--old-detailed", default=None)
    parser.add_argument("--orphan-out", default="orphan_report.txt")
    parser.add_argument("--new-pkg-out", default="new_packages_report.txt")
    parser.add_argument(
        "--scan-runtime",
        action="store_true",
        help=(
            "Scan installed packages' Python source files for imports of each orphan "
            "and annotate the report with SAFE TO REMOVE / POSSIBLY NEEDED suggestions. "
            "Requires the packages in requirements.txt to already be installed."
        ),
    )
    args = parser.parse_args()

    detailed = parse_detailed(args.detailed)
    base_pkgs, transitive_pkgs, overrides = parse_req_in(args.req_in)
    old_detailed = parse_detailed(args.old_detailed) if args.old_detailed else None

    orphans = find_orphans(detailed, transitive_pkgs, overrides)
    untracked, newly_added = find_new_packages(
        detailed, base_pkgs, transitive_pkgs, old_detailed
    )

    runtime_usage = scan_runtime_usage(orphans) if args.scan_runtime else None

    write_orphan_report(orphans, args.orphan_out, runtime_usage)
    write_new_pkg_report(untracked, newly_added, args.new_pkg_out)

    # Print summaries to stdout for CI logs
    print(f"Orphan candidates: {len(orphans)}")
    print(f"Untracked packages: {len(untracked)} ({len(newly_added)} new this run)")

    # Exit non-zero only when there are genuinely new packages this run,
    # so CI surfaces the report clearly without blocking on pre-existing gaps.
    if newly_added:
        sys.exit(1)


if __name__ == "__main__":
    main()
