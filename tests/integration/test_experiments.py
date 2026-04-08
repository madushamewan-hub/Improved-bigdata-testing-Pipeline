from experiments.run_experiment import run_experiments
from pathlib import Path


def test_experiment_generates_reports():
    df = run_experiments()
    assert 'scenario' in df.columns
    assert 'defect_detection_rate' in df.columns
    assert 'false_positive_rate' in df.columns
    assert 'false_negative_rate' in df.columns
    assert 'transformation_rule_coverage' in df.columns
    assert 'completeness_check_effectiveness' in df.columns
    assert 'deduplication_accuracy' in df.columns
    assert 'recovery_success_rate' in df.columns
    assert 'latency_overhead_percent' in df.columns
    assert df.shape[0] >= 7
    assert Path('reports/engine_benchmark_results.csv').exists()
