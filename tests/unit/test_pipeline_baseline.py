import pytest
from data_generator.order_events import generate_base_orders
from pipelines.baseline.pipeline import run_batch


def test_baseline_pipeline_passes_clean_data():
    data = generate_base_orders(10, seed=1)
    metrics = run_batch(data)
    assert metrics['record_count'] == 10
