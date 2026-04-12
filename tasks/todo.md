# Requirements Auto-Update GitHub Workflow

## Plan

Create a GitHub Actions workflow that:
- Triggers on push to `main` when `requirements.in` changes
- Runs `pip-compile` to regenerate `detailed_requirements.txt`
- Derives `requirements.txt` (stripped of comments/extras)
- Installs packages and runs `pipdeptree` to regenerate `reverse_dependency.txt`
- Opens a PR with the three generated files for review
- Opens a GitHub Issue with the full error output if `pip-compile` fails (conflict detected)

## Checklist

- [x] Create `.github/workflows/update-requirements.yml`
  - Trigger: `push` to `main`, path filter `requirements.in`
  - Steps: checkout → setup Python 3.11 → cache pip → install tools → pip-compile → handle conflict → generate files → create PR
- [x] Update `pipdeptree_reverse.sh` so it can also be run manually to reproduce what the workflow does

## Review

### Changes made

**`.github/workflows/update-requirements.yml`** (new file)
- Triggers on every push to `main` that touches `requirements.in`
- Installs `pip-tools` and `pipdeptree`
- Caches pip packages keyed on `requirements.in` hash to speed up repeated runs
- Runs `pip-compile`; on failure, opens a GitHub Issue with the full conflict log and exits the workflow
- On success, regenerates `requirements.txt` (strips comments and package extras) and `reverse_dependency.txt` (pipdeptree reverse output)
- Uses `peter-evans/create-pull-request@v7` to commit the three generated files onto branch `auto/update-requirements` and open a PR targeting `main`; if nothing changed, no PR is created

**`pipdeptree_reverse.sh`** (updated)
- Added a comment block explaining how the CI workflow mirrors this script
- Fixed `sed -i` to use the portable flag for both macOS (`sed -i ''`) and Linux

No application code was changed.

---

# Orphan Detection + Smoke Test

## Plan

- Add an orphan-detection script to surface transitive packages that pip-compile
  can no longer trace to any upstream package (`# via -r requirements.in` only),
  so they can be removed to keep the Docker image lean.
- Add a `# runtime-override:` comment convention in `requirements.in` to mark
  false alarms (packages genuinely needed at runtime but not detected by pip-compile).
- Add a kedro / kedro-azureml smoke test to catch broken runtime imports after
  removing a package.
- Wire both into the GitHub Actions workflow so the PR body reports orphan
  candidates and smoke-test results automatically.
- Update README.md to document the new workflow.

## Checklist

- [x] Create `scripts/audit_requirements.py` — two audits in one script:
      (1) orphan candidates: transitive packages in requirements.in that pip-compile
          no longer traces to any upstream (# via -r requirements.in only), excluding
          those tagged # runtime-override:
      (2) new/untracked packages: packages in the newly compiled
          detailed_requirements.txt that are absent from requirements.in, with a
          sub-highlight for ones not present in the previous committed version
- [x] Create `scripts/generate_pr_body.py` — combine orphan report + new-package
      report + smoke-test output into pr_body.md
- [x] Create `tests/smoke/test_kedro_pipeline.py` — import test + local pipeline run
- [x] Update `.github/workflows/update-requirements.yml` — save old
      detailed_requirements.txt before pip-compile, add audit, smoke-test, and
      dynamic PR body steps
- [x] Update `README.md` — document orphan detection, new-package detection,
      runtime-override convention, and smoke test

## Review

### Changes made

**`scripts/audit_requirements.py`** (new)
- Parses `detailed_requirements.txt` and `requirements.in`
- Orphan report: flags transitive packages whose only pip-compile attribution
  is `# via -r requirements.in`; packages with `# runtime-override:` are excluded
- New-package report: lists all packages resolved by pip-compile but absent
  from `requirements.in`; packages not in the previous committed
  `detailed_requirements.txt` are highlighted as `*** NEW THIS RUN ***`
- Exits non-zero only when there are newly appeared untracked packages

**`scripts/generate_pr_body.py`** (new)
- Reads the three report files and assembles `pr_body.md` with emoji status
  badges and collapsible `<details>` sections

**`tests/smoke/test_kedro_pipeline.py`** (new)
- Imports kedro core, kedro-azureml, and known runtime deps (cachetools, cloudpickle, pyarrow)
- Runs a two-node local pipeline to verify the framework is end-to-end functional

**`.github/workflows/update-requirements.yml`** (updated)
- Step 0: snapshots `detailed_requirements.txt` from HEAD before pip-compile
- Step 3: runs `audit_requirements.py` after the sed post-processing
- Step 4b: runs smoke tests after `pip install -r requirements.txt`
- Step 6: generates `pr_body.md` from audit + smoke results
- Step 7: uses `body-path: pr_body.md` instead of an inline static body

**`README.md`** (updated)
- Documents the orphan detection, `# runtime-override:` convention,
  new-package detection, and smoke test in new sections

---

# Orphan Runtime-Usage Scanning

## Plan

Enhance the orphan report to suggest whether each orphan is safe to remove or
possibly still needed at runtime, by scanning the installed packages' Python
source files for imports of the orphan's module(s).

- After `pip install`, use `importlib.metadata` to walk every installed
  distribution's `.py` files and search for `import <module>` / `from <module>`
  needle strings.
- If any installed package imports an orphan without declaring it as a metadata
  dependency (the case pip-compile misses), flag the orphan as
  **POSSIBLY NEEDED** and list the importers.
- If no package imports it, flag it as **SAFE TO REMOVE**.
- Wire into the workflow by moving the audit step to after `pip install` and
  passing `--scan-runtime`.

## Checklist

- [x] Add `get_top_level_modules()` and `scan_runtime_usage()` to `audit_requirements.py`
- [x] Add `--scan-runtime` CLI flag; update `write_orphan_report()` with suggestions
- [x] Move audit step after pip install in workflow; add `--scan-runtime` flag

## Review

### Changes made

**`scripts/audit_requirements.py`** (updated)
- `get_top_level_modules(pkg_name)` — resolves a distribution name to its
  importable module names via `top_level.txt`; falls back to replacing hyphens
  with underscores
- `scan_runtime_usage(orphans)` — walks every installed distribution's `.py`
  files looking for `import <module>` / `from <module>` needle strings; returns
  `{orphan: [importer_pkg, ...]}` for packages that import the orphan without
  declaring it as a metadata dependency
- `write_orphan_report()` — now accepts an optional `runtime_usage` dict and
  annotates each orphan with either `SAFE TO REMOVE` (no importer found) or
  `POSSIBLY NEEDED` (lists which packages import it) plus a concrete action
- `main()` — new `--scan-runtime` flag gates the scan; passes `runtime_usage`
  to the report writer when enabled

**`.github/workflows/update-requirements.yml`** (updated)
- Moved `pip install -r requirements.txt` before the audit step so site-packages
  are populated when `--scan-runtime` runs
- Added `--scan-runtime` to the audit step's command
