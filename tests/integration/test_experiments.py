from experiments.run_experiment import run_experiments
from pathlib import Path


def test_experiment_generates_reports():
    df = run_experiments()
    assert 'scenario' in df.columns
    assert df.shape[0] >= 7
    assert Path('reports/engine_benchmark_results.csv').exists()
