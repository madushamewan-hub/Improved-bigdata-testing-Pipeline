from data_generator.order_events import generate_base_orders
from pipelines.proposed.pipeline import run_batch


def test_e2e_end_to_end_flow():
    data = generate_base_orders(20, seed=5)
    metrics = run_batch(data)
    assert metrics['downstream_reconciliation'] is True
