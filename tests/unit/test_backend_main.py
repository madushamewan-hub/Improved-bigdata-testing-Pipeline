from types import SimpleNamespace

from backend.main import _normalize_record_for_pipeline, _resolve_dataset_file_format


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