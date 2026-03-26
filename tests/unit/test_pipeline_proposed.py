from data_generator.order_events import generate_base_orders, inject_corruption
from pipelines.proposed.pipeline import run_batch


def test_proposed_detects_corruption():
    data = generate_base_orders(10, seed=2)
    faulty = inject_corruption(data, 0.5)
    metrics = run_batch(faulty)
    assert metrics['proposed_detected_issues'] is not None
    assert metrics['proposed_stored_rows'] <= metrics['source_count']
