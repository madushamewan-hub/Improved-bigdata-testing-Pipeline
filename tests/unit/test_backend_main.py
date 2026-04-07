from types import SimpleNamespace

from data_generator.order_events import generate_base_orders, inject_missing
from backend.main import (
    _compute_scenario_amended_count,
    _derive_proposed_result_metrics,
    _normalize_record_for_pipeline,
    _resolve_dataset_file_format,
    _scenario_detection_label,
)


def test_resolve_dataset_file_format_prefers_supported_type():
    dataset = SimpleNamespace(
        name='orders',
        type='csv',
        file_path='uploads/orders.csv',
        schema_json={},
    )

    assert _resolve_dataset_file_format(dataset) == 'csv'


def test_resolve_dataset_file_format_falls_back_from_custom_to_extension():
    dataset = SimpleNamespace(
        name='legacy-custom-dataset',
        type='custom',
        file_path='uploads/orders.xlsx',
        schema_json={},
    )

    assert _resolve_dataset_file_format(dataset) == 'xlsx'


def test_resolve_dataset_file_format_uses_schema_metadata_when_available():
    dataset = SimpleNamespace(
        name='legacy-custom-dataset',
        type='custom',
        file_path='uploads/orders.unknown',
        schema_json={'source_format': 'json'},
    )

    assert _resolve_dataset_file_format(dataset) == 'json'


def test_normalize_record_for_pipeline_maps_orders_aliases():
    dataset = SimpleNamespace(
        name='orders',
        type='custom',
        file_path='uploads/orders.csv',
        schema_json={},
    )
    row = {
        'order_id': 7,
        'created_at': '2012-03-20 17:03:41',
        'user_id': 241,
        'price_usd': 49.99,
    }

    normalized = _normalize_record_for_pipeline(row, row_index=0, dataset=dataset)

    assert normalized['event_id'] == '7'
    assert normalized['event_time'] == '2012-03-20 17:03:41'
    assert normalized['customer_id'] == '241'
    assert normalized['source_system'] == 'csv'
    assert normalized['amount'] == 49.99
    assert normalized['status'] == 'observed'
    assert normalized['version'] == 1
    assert normalized['checksum'] is not None


def test_normalize_record_for_pipeline_fills_defaults_for_sparse_rows():
    dataset = SimpleNamespace(
        name='patients',
        type='custom',
        file_path='uploads/patients.csv',
        schema_json={},
    )
    row = {
        'Id': 'abc-123',
        'BIRTHDATE': '1977-03-19',
    }

    normalized = _normalize_record_for_pipeline(row, row_index=5, dataset=dataset)

    assert normalized['event_id'] == 'abc-123'
    assert normalized['event_time'] == '1977-03-19'
    assert normalized['customer_id'] == 'abc-123'
    assert normalized['source_system'] == 'csv'
    assert normalized['amount'] == 0.0
    assert normalized['status'] == 'observed'
    assert normalized['version'] == 1
    assert normalized['record_semantics'] == 'reference'


def test_normalize_record_for_pipeline_marks_order_records_as_event_semantics():
    dataset = SimpleNamespace(
        name='orders',
        type='csv',
        file_path='uploads/orders.csv',
        schema_json={},
    )
    row = {
        'order_id': 42,
        'created_at': '2024-01-01T10:00:00',
        'user_id': 7,
        'price_usd': 12.5,
    }

    normalized = _normalize_record_for_pipeline(row, row_index=0, dataset=dataset)

    assert normalized['record_semantics'] == 'event'


def test_scenario_detection_label_is_human_readable():
    assert _scenario_detection_label('duplicated') == 'duplication detected'
    assert _scenario_detection_label('dropped') == 'dropped data detected'
    assert _scenario_detection_label('corrupted') == 'corruption detected'


def test_inject_missing_preserves_rows_and_introduces_missing_values():
    base = generate_base_orders(30, seed=42)
    dropped = inject_missing(base, 0.4)

    assert len(dropped) == len(base)
    assert any(
        row.get('event_time') is None
        or row.get('customer_id') is None
        or row.get('amount') is None
        or row.get('status') is None
        for row in dropped
    )
    assert _compute_scenario_amended_count(base, dropped, 'dropped') > 0


def test_derive_proposed_result_metrics_uses_schema_drift_signals_for_inconsistency_count():
    derived = _derive_proposed_result_metrics(
        {
            'proposed_detected_issues': 9,
            'stored_rows': 100,
            'false_positives': 0,
            'nulls': 0,
            'type_mismatches': 9,
            'transformation_failures': 0,
            'row_count_mismatch': 0,
            'invalid_schema': 0,
            'checksum_mismatch': 0,
            'dimension_findings': {'consistency': 0, 'uniqueness': 0},
        },
        row_count=100,
        latency_ms=10.0,
    )

    assert derived['detected_inconsistency'] == 9