Automated update to requirements files following changes to `requirements.in` in commit ab061d5e78115359129b487f837669063415acb8.

**Files updated:**
- `detailed_requirements.txt` — full pinned dependency graph (pip-compile output)
- `requirements.txt` — flat pinned list (comments and extras stripped)
- `reverse_dependency.txt` — reverse dependency tree (pipdeptree output)

Review the diff and the three audit sections below, then merge.

---

## ⚠️ Orphan candidates

Transitive packages in `requirements.in` that pip-compile can no longer trace to any upstream package — candidates for removal to slim the Docker image. Tag with `# runtime-override: <reason>` to suppress if needed at runtime.

<details>
<summary>Details</summary>

```
Orphan candidates — in 'Transitive Libraries' of requirements.in but pip-compile cannot trace them to any upstream package:
  - pysocks
    Suggestion: POSSIBLY NEEDED — imported at runtime by: httpcore, httpx, pip, urllib3
    Action: add '# runtime-override: imported by httpcore at runtime' to requirements.in
  - toposort
    Suggestion: SAFE TO REMOVE — no installed package imports it
    Action: remove from requirements.in

Packages marked 'SAFE TO REMOVE' can be deleted from requirements.in. Packages marked 'POSSIBLY NEEDED' should be tagged with '# runtime-override: <reason>' to suppress this warning.
```

</details>

---

## ⚠️ New / untracked packages

Packages that pip-compile resolved but that are not listed anywhere in `requirements.in`. Items marked `*** NEW THIS RUN ***` appeared for the first time in this compile. Add them to the appropriate Transitive Libraries section.

<details>
<summary>Details</summary>

```
3 package(s) resolved by pip-compile are not listed in requirements.in:
  - backoff *** NEW THIS RUN ***
  - python-dateutil *** NEW THIS RUN ***
  - six *** NEW THIS RUN ***

Add them to the appropriate 'Transitive Libraries' section of requirements.in to make the dependency explicit.

Packages marked '*** NEW THIS RUN ***' (3) were not present in the previous compiled output.
```

</details>

---

## ✅ Kedro smoke tests passed

A minimal kedro pipeline and kedro-azureml import test ran against the compiled requirements to catch missing runtime dependencies.

<details>
<summary>Test output</summary>

```
============================= test session starts ==============================
platform linux -- Python 3.11.15, pytest-9.0.2, pluggy-1.6.0 -- /usr/local/py-utils/venvs/pytest/bin/python
cachedir: .pytest_cache
rootdir: /__w/kedro-azureml-python-pkg-mgmt/kedro-azureml-python-pkg-mgmt
plugins: mock-2.0.0, cov-6.3.0, Faker-37.8.0, anyio-3.7.1
collecting ... collected 3 items

tests/smoke/test_kedro_pipeline.py::test_kedro_core_imports PASSED       [ 33%]
tests/smoke/test_kedro_pipeline.py::test_kedro_azureml_imports PASSED    [ 66%]
tests/smoke/test_kedro_pipeline.py::test_pipeline_runs_locally PASSED    [100%]

```

</details>
