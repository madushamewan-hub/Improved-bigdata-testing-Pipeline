from experiments.run_experiment import run_experiments


def test_experiment_generates_reports():
    df = run_experiments()
    assert 'scenario' in df.columns
    assert df.shape[0] >= 7
