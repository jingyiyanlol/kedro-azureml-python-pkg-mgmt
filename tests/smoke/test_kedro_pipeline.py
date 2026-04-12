"""
Smoke tests for the kedro + kedro-azureml stack.

Run these after modifying requirements.in to catch broken runtime imports
before the PR is merged.  No Azure credentials are required — the pipeline
runs entirely in-process with a local SequentialRunner.
"""


def test_kedro_core_imports():
    """Core kedro modules must be importable."""
    from kedro.io import DataCatalog, MemoryDataset  # noqa: F401
    from kedro.pipeline import Pipeline, node  # noqa: F401
    from kedro.runner import SequentialRunner  # noqa: F401


def test_kedro_azureml_imports():
    """kedro-azureml and its runtime dependencies must be importable.

    cachetools is a known runtime dependency of kedro-azureml that is not
    always surfaced by pip-compile — if it goes missing, this test will catch it.
    """
    import kedro_azureml  # noqa: F401
    import cachetools  # noqa: F401
    import cloudpickle  # noqa: F401
    import pyarrow  # noqa: F401


def test_pipeline_runs_locally():
    """A minimal two-node pipeline must execute end-to-end with a local runner."""
    from kedro.io import DataCatalog, MemoryDataset
    from kedro.pipeline import Pipeline, node
    from kedro.runner import SequentialRunner

    def double(x):
        return x * 2

    def add_one(x):
        return x + 1

    pipeline = Pipeline(
        [
            node(double, inputs="raw", outputs="doubled", name="double_node"),
            node(add_one, inputs="doubled", outputs="result", name="add_one_node"),
        ]
    )
    catalog = DataCatalog({"raw": MemoryDataset(5)})
    output = SequentialRunner().run(pipeline, catalog)

    # Extract the actual value from the MemoryDataset
    assert output["result"].load() == 11  # (5 * 2) + 1
