## Overview

Managing a large `requirements.in` with hundreds of pinned packages across many ecosystems is tedious and error-prone. This project is mainly used to manage the python dependencies for a typical Kedro Azureml Project. It automates the full dependency tracing workflow using a GitHub Actions bot, so that any change to `requirements.in` automatically produces three derived files, runs audits, and opens a PR for review.

This project is created with help of Claude Code to help write the automation for Python package dependency tracing and conflict detection for a Kedro Azure ML project.

## How it works

```
requirements.in  ──(push to main)──►  GitHub Actions bot
                                              │
                     ┌────────────────────────┼────────────────────────┐
                     ▼                        ▼                        ▼
          detailed_requirements.txt    requirements.txt    reverse_dependency.txt
                     └────────────────────────┴────────────────────────┘
                                              │
                               ┌──────────────┴──────────────┐
                               ▼                             ▼
                        Requirements audit            Kedro smoke test
                     (orphans + new packages)      (imports + local run)
                               └──────────────┬──────────────┘
                                              │
                                      Opens a PR with
                                    audit results in body
                                 (or an Issue on conflict)
```

### Generated files

| File | Tool | Description |
|------|------|-------------|
| `detailed_requirements.txt` | `pip-compile` | Full pinned dependency graph — shows which package pulled in each dependency |
| `requirements.txt` | derived from above | Flat pinned list, comments and extras (e.g. `[parquet]`) stripped — ready to `pip install` |
| `reverse_dependency.txt` | `pipdeptree --reverse` | For each package, shows which other packages depend on it — useful for understanding blast radius of an upgrade |

### Conflict detection

If `pip-compile` cannot resolve the dependencies (version conflict), the workflow:
- Does **not** create a PR
- Opens a GitHub Issue titled `⚠️ Requirements conflict detected` with the full error output
- Fails the workflow run visibly in CI

### Requirements audit

Each PR body contains two automated audit reports:

#### 1. Orphan candidates

After a package upgrade, some transitive packages in `requirements.in` may no longer be declared as a dependency by any upstream package. pip-compile signals these with `# via -r requirements.in` only. The audit surfaces them as removal candidates to keep the Docker image lean.

**False alarms** — packages that are needed at runtime but are not visible to pip-compile (undeclared runtime dependencies of third-party libraries) — can be suppressed by adding a `# runtime-override:` comment directly below the package line in `requirements.in`:

```
cachetools==5.5.2
    # runtime-override: needed by kedro-azureml at runtime, not detected by pip-compile
```

Tagged packages are excluded from the orphan report.

#### 2. New / untracked packages

Packages that pip-compile resolved into `detailed_requirements.txt` but that are not listed anywhere in `requirements.in`. Items marked `*** NEW THIS RUN ***` appeared for the first time in the current compile (not present in the previous committed `detailed_requirements.txt`). These are candidates to add to the appropriate `Transitive Libraries` section of `requirements.in`.

### Kedro smoke test

After installing the compiled requirements, a minimal smoke test runs at `tests/smoke/test_kedro_pipeline.py`. It:
1. Imports `kedro`, `kedro-azureml`, and their known runtime dependencies (e.g. `cachetools`, `cloudpickle`, `pyarrow`)
2. Runs a two-node kedro pipeline end-to-end with a local `SequentialRunner`

A smoke-test failure is surfaced prominently in the PR body. Do not merge a PR where the smoke test has failed.

## Repository structure

```
.
├── requirements.in                        # Source of truth — edit this
├── detailed_requirements.txt              # Generated: full dependency graph
├── requirements.txt                       # Generated: flat pinned list
├── reverse_dependency.txt                 # Generated: reverse dependency tree
├── pipdeptree_reverse.sh                  # Local script to regenerate all three files
├── scripts/
│   ├── audit_requirements.py             # Orphan + new-package audit
│   └── generate_pr_body.py               # Assemble PR body from audit reports
├── tests/
│   └── smoke/
│       └── test_kedro_pipeline.py        # Kedro + kedro-azureml smoke test
└── .github/
    └── workflows/
        └── update-requirements.yml        # GitHub Actions workflow
```

## Running locally

Prerequisites: Python 3.11, `pip-tools`, `pipdeptree`

```bash
pip install pip-tools pipdeptree
sh pipdeptree_reverse.sh
```

Run the audit scripts locally after regenerating:

```bash
python scripts/audit_requirements.py \
  --detailed  detailed_requirements.txt \
  --req-in    requirements.in \
  --orphan-out   orphan_report.txt \
  --new-pkg-out  new_packages_report.txt
```

> **Tip:** Run inside a Docker container to keep your local environment clean:
> ```bash
> docker run --rm -it \
>   --platform linux/amd64 \
>   -v "$(pwd)":/workspace \
>   -w /workspace \
>   mcr.microsoft.com/devcontainers/python:3.11 \
>   /bin/bash
> ```
> Note: ensure pip version is below 26 for compatibility with `pip-tools`.

## GitHub Actions bot

The workflow (`.github/workflows/update-requirements.yml`) triggers on any push to `main` that changes `requirements.in`.

Required repository permissions (To create a PAT and store in secrets for the repository, called with `secrets.WORKFLOW_PAT`):
- `contents: write` — commit generated files to a branch
- `pull-requests: write` — open the PR
- `issues: write` — open a conflict Issue
