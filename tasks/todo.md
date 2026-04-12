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
