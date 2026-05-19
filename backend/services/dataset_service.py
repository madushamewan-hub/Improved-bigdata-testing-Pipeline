from datetime import datetime

from backend.database import Dataset
from backend.file_parser import FileParser
from data_generator.order_events import compute_checksum


def _infer_record_semantics(row: dict, dataset: Dataset) -> str:
    dataset_name = str(getattr(dataset, 'name', '') or '').lower()
    dataset_path = str(getattr(dataset, 'file_path', '') or '').lower()
    row_keys = {str(key).lower() for key in row.keys()}

    if any(token in dataset_name or token in dataset_path for token in ['patient', 'master', 'reference', 'lookup', 'dimension']):
        return 'reference'

    reference_indicators = {'birthdate', 'deathdate', 'gender', 'race', 'ethnicity', 'address', 'city', 'state', 'zip', 'marital'}
    if row_keys & reference_indicators:
        return 'reference'

    return 'event'


def _resolve_dataset_file_format(dataset: Dataset) -> str:
    schema_json = dataset.schema_json if isinstance(dataset.schema_json, dict) else {}
    candidates = [
        schema_json.get('source_format'),
        schema_json.get('format'),
        dataset.type,
        FileParser.get_file_format(dataset.file_path or ''),
        FileParser.get_file_format(dataset.name or ''),
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.lower() in FileParser.SUPPORTED_FORMATS:
            return candidate.lower()

    supported = ', '.join(FileParser.SUPPORTED_FORMATS)
    raise ValueError(
        f"Could not resolve a supported file format for dataset '{dataset.name}'. "
        f"Stored type was '{dataset.type}'. Supported: {supported}"
    )


def _pick_first_value(row: dict, aliases) -> object:
    lowered = {str(key).lower(): key for key in row.keys()}
    for alias in aliases:
        actual_key = lowered.get(alias.lower())
        if actual_key is None:
            continue
        value = row.get(actual_key)
        if value is not None and value != '':
            return value
    return None


def _normalize_record_for_pipeline(row: dict, row_index: int, dataset: Dataset) -> dict:
    event_id = _pick_first_value(row, ['event_id', 'order_id', 'id'])
    event_time = _pick_first_value(row, ['event_time', 'created_at', 'timestamp', 'date', 'birthdate'])
    customer_id = _pick_first_value(row, ['customer_id', 'user_id', 'patient_id', 'website_session_id', 'first', 'customer'])
    amount = _pick_first_value(row, ['amount', 'price_usd', 'price', 'total', 'cogs_usd'])
    status = _pick_first_value(row, ['status', 'state', 'marital'])
    version = _pick_first_value(row, ['version'])
    source_system = _pick_first_value(row, ['source_system', 'source', 'channel'])
    record_semantics = _infer_record_semantics(row, dataset)

    normalized = {
        'event_id': str(event_id) if event_id is not None else f"{dataset.name or 'dataset'}-{row_index}",
        'event_time': str(event_time) if event_time is not None else datetime.utcnow().isoformat(),
        'customer_id': str(customer_id) if customer_id is not None else str(event_id if event_id is not None else f"entity-{row_index}"),
        'source_system': str(source_system) if source_system is not None else (_resolve_dataset_file_format(dataset) or 'uploaded_file'),
        'amount': amount if amount is not None else 0.0,
        'status': str(status) if status is not None else 'observed',
        'version': version if version is not None else 1,
        'record_semantics': record_semantics,
    }
    normalized['checksum'] = compute_checksum(normalized)
    return normalized


def _normalize_dataset_records(records, dataset: Dataset):
    return [
        _normalize_record_for_pipeline(row, row_index=index, dataset=dataset)
        for index, row in enumerate(records)
    ]


def _load_dataset_records(dataset: Dataset, sample_rate: float | None = None, max_workers: int | None = None):
    """Load and normalize dataset records.

    Supports optional sampling (`sample_rate` 0..1) and `max_workers` to pass
    down to the file parser for parallel chunk processing.
    """
    file_format = _resolve_dataset_file_format(dataset)

    # Derive max_rows to request from the parser when sampling is requested.
    parser_kwargs = {}
    if sample_rate is not None and 0.0 < float(sample_rate) < 1.0:
        try:
            total = int(getattr(dataset, 'row_count', 0) or 0)
            if total > 0:
                parser_kwargs['max_rows'] = max(1, int(total * float(sample_rate)))
            else:
                # fall back to FileParser.MAX_ROWS_TO_LOAD
                parser_kwargs['max_rows'] = int(FileParser.MAX_ROWS_TO_LOAD * float(sample_rate))
        except Exception:
            parser_kwargs['max_rows'] = int(FileParser.MAX_ROWS_TO_LOAD * float(sample_rate))

    if max_workers is not None:
        parser_kwargs['max_workers'] = int(max_workers)

    df, _, _ = FileParser.parse_file(dataset.file_path, file_format, **parser_kwargs)
    raw_records = df.to_dict(orient='records')
    return _normalize_dataset_records(raw_records, dataset)
