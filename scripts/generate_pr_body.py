#!/usr/bin/env python3
"""
Assemble the pull-request body from the three audit reports.

Usage:
    python scripts/generate_pr_body.py \\
        --sha           <commit-sha> \\
        --orphan-report orphan_report.txt \\
        --new-pkg-report new_packages_report.txt \\
        --smoke-output  smoke_test_output.txt \\
        --smoke-exit    <0|1> \\
        --out           pr_body.md
"""

import argparse


def _read(path: str) -> str:
    try:
        return open(path).read().strip()
    except FileNotFoundError:
        return "(report not found)"


def _badge(text: str, ok: bool) -> str:
    return f"{'✅' if ok else '⚠️'} {text}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", default="unknown")
    parser.add_argument("--orphan-report", default="orphan_report.txt")
    parser.add_argument("--new-pkg-report", default="new_packages_report.txt")
    parser.add_argument("--smoke-output", default="smoke_test_output.txt")
    parser.add_argument("--smoke-exit", type=int, default=0)
    parser.add_argument("--out", default="pr_body.md")
    args = parser.parse_args()

    orphan_text = _read(args.orphan_report)
    new_pkg_text = _read(args.new_pkg_report)
    smoke_text = _read(args.smoke_output)
    smoke_ok = args.smoke_exit == 0

    orphan_ok = "No orphan candidates found" in orphan_text
    new_pkg_ok = "All resolved packages are already listed" in new_pkg_text

    body = f"""\
Automated update to requirements files following changes to `requirements.in` \
in commit {args.sha}.

**Files updated:**
- `detailed_requirements.txt` — full pinned dependency graph (pip-compile output)
- `requirements.txt` — flat pinned list (comments and extras stripped)
- `reverse_dependency.txt` — reverse dependency tree (pipdeptree output)

Review the diff and the three audit sections below, then merge.

---

## {_badge("Orphan candidates", orphan_ok)}

Transitive packages in `requirements.in` that pip-compile can no longer trace \
to any upstream package — candidates for removal to slim the Docker image. \
Tag with `# runtime-override: <reason>` to suppress if needed at runtime.

<details>
<summary>Details</summary>

```
{orphan_text}
```

</details>

---

## {_badge("New / untracked packages", new_pkg_ok)}

Packages that pip-compile resolved but that are not listed anywhere in \
`requirements.in`. Items marked `*** NEW THIS RUN ***` appeared for the first \
time in this compile. Add them to the appropriate Transitive Libraries section.

<details>
<summary>Details</summary>

```
{new_pkg_text}
```

</details>

---

## {"✅ Kedro smoke tests passed" if smoke_ok else "❌ Kedro smoke tests FAILED — do not merge"}

A minimal kedro pipeline and kedro-azureml import test ran against the compiled \
requirements to catch missing runtime dependencies.

<details>
<summary>Test output</summary>

```
{smoke_text}
```

</details>
"""

    with open(args.out, "w") as f:
        f.write(body)
    print(f"PR body written to {args.out}")


if __name__ == "__main__":
    main()
