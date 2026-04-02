import importlib.util
import sys

import pytest

from data_generator.order_events import generate_base_orders, inject_corruption
from pipelines.proposed.pipeline import run_batch, run_streaming


def test_proposed_detects_corruption():
    data = generate_base_orders(10, seed=2)
    faulty = inject_corruption(data, 0.5)
    metrics = run_batch(faulty)
    assert metrics['proposed_detected_issues'] is not None
    assert metrics['proposed_stored_rows'] <= metrics['source_count']


def test_proposed_sector_target_evaluation_exists():
    data = generate_base_orders(20, seed=3)
    metrics = run_batch(data, sector='finance')

    assert 'advanced_metric_scores' in metrics
    assert 'sector_target_evaluation' in metrics
    assert 'sector_compliance_score' in metrics
    assert metrics.get('sector') == 'finance'

    evaluation = metrics['sector_target_evaluation']
    assert evaluation.get('sector') == 'finance'
    assert 'metric_results' in evaluation
    assert 'defect_detection_rate' in evaluation.get('metric_results', {})
    assert 0.0 <= metrics.get('sector_compliance_score', -1.0) <= 1.0
    assert 0.0 <= metrics.get('dimension_average_score', -1.0) <= 1.0
    assert 0.0 <= metrics.get('composite_score', -1.0) <= 1.0
    assert 'composite_formula' in metrics


def test_proposed_resilience_quarantine_and_checkpoints():
    data = generate_base_orders(6, seed=11)
    # Force preprocessing/type conversion failures to trigger retry + quarantine.
    data[0]['amount'] = 'not-a-number'
    data[1]['version'] = 'invalid-int'

    metrics = run_batch(data, resilience_policy={'enabled': True, 'max_retries': 2, 'max_quarantine_samples': 10})

    assert 'checkpoint_flow' in metrics
    assert len(metrics['checkpoint_flow']) == 4
    assert metrics.get('retry_attempts', 0) >= 2
    assert metrics.get('quarantine_count', 0) >= 2
    assert len(metrics.get('quarantine_records', [])) >= 2


def test_proposed_streaming_resilience_rollup_exists():
    data = generate_base_orders(45, seed=13)
    data[0]['amount'] = 'bad-float'
    data[15]['version'] = 'bad-int'

    metrics = run_streaming(data, resilience_policy={'enabled': True, 'max_retries': 1})

    assert 'retry_attempts' in metrics
    assert 'quarantine_count' in metrics
    assert 'checkpoint_flow' in metrics
    assert 'quarantine_records' in metrics
    assert metrics.get('retry_attempts', 0) >= 2


def test_proposed_python_engine_label_exists():
    data = generate_base_orders(10, seed=17)
    metrics = run_batch(data, engine='python')
    assert metrics.get('engine') == 'python'


def test_proposed_invalid_engine_raises():
    data = generate_base_orders(5, seed=19)
    with pytest.raises(ValueError):
        run_batch(data, engine='invalid-engine')


@pytest.mark.skipif(importlib.util.find_spec('pyspark') is None or sys.version_info >= (3, 14), reason='pyspark unavailable or unsupported on this Python version')
def test_proposed_spark_engine_runs():
    data = generate_base_orders(8, seed=23)
    metrics = run_batch(data, engine='spark')
    assert metrics.get('engine') == 'spark'
    assert 'composite_score' in metrics
    assert metrics['proposed_stored_rows'] <= metrics['source_count']
