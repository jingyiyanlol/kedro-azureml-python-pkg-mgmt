# Python Package Dependency Management

An experiment using Claude to automate Python package dependency tracing and conflict detection.

## Overview

Managing a large `requirements.in` with hundreds of pinned packages across many ecosystems (Azure ML, Kedro, FastAPI, Jupyter, spaCy, etc.) is tedious and error-prone. This project automates the full dependency tracing workflow using a GitHub Actions bot, so that any change to `requirements.in` automatically produces three derived files and opens a PR for review.

## How it works

```
requirements.in  ──(push to main)──►  GitHub Actions bot
                                              │
                          ┌───────────────────┼───────────────────┐
                          ▼                   ▼                   ▼
               detailed_requirements   requirements.txt   reverse_dependency.txt
                     .txt
                          └───────────────────┴───────────────────┘
                                              │
                                      Opens a PR to review
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

## Repository structure

```
.
├── requirements.in                        # Source of truth — edit this
├── detailed_requirements.txt              # Generated: full dependency graph
├── requirements.txt                       # Generated: flat pinned list
├── reverse_dependency.txt                 # Generated: reverse dependency tree
├── pipdeptree_reverse.sh                  # Local script to regenerate all three files
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

Required repository permissions (automatically granted via `GITHUB_TOKEN`):
- `contents: write` — commit generated files to a branch
- `pull-requests: write` — open the PR
- `issues: write` — open a conflict Issue
