import duckdb
from typing import List, Dict, Tuple
from datetime import datetime
from .validation import (
    schema_validation,
    null_check,
    duplicate_check,
    checksum_check,
    transformation_check,
    reconciliation_check,
    enforce_types,
    out_of_order_check,
)


def ingestion(orders: List[Dict], mode: str = 'batch') -> Tuple[List[Dict], Dict]:
    metrics = {'ingested': 0, 'invalid_schema': 0, 'nulls': 0, 'freshness_issues': 0}
    valid = []
    now = datetime.utcnow()
    for o in orders:
        metrics['ingested'] += 1
        if not schema_validation(o):
            metrics['invalid_schema'] += 1
            continue
        if not null_check(o):
            metrics['nulls'] += 1
            continue
        event_time = datetime.fromisoformat(o['event_time'])
        if (now - event_time).total_seconds() > 86400:
            metrics['freshness_issues'] += 1
        valid.append(o)
    return valid, metrics


def preprocessing(records: List[Dict]) -> Tuple[List[Dict], Dict]:
    metrics = {'type_mismatches': 0, 'malformed': 0}
    cleaned = []
    for r in records:
        try:
            row = enforce_types(r)
            cleaned.append(row)
        except Exception:
            metrics['type_mismatches'] += 1
    return cleaned, metrics


def transform(records: List[Dict]) -> Tuple[List[Dict], Dict]:
    metrics = {'transformation_failures': 0, 'mapping_issues': 0}
    transformed = []
    for r in records:
        try:
            row = transformation_check(r)
            transformed.append(row)
        except Exception:
            metrics['transformation_failures'] += 1
    if not duplicate_check(transformed):
        metrics['mapping_issues'] += 1
    return transformed, metrics


def storage(records: List[Dict], db_path: str = ':memory:') -> Tuple[Dict, Dict]:
    metrics = {'stored': 0, 'row_count_mismatch': 0, 'checksum_mismatch': 0}
    conn = duckdb.connect(database=db_path, read_only=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS orders_curated (
                    event_id VARCHAR,
                    event_time VARCHAR,
                    customer_id VARCHAR,
                    source_system VARCHAR,
                    amount DOUBLE,
                    status VARCHAR,
                    version INT,
                    checksum VARCHAR,
                    total_tax DOUBLE
                    )''')
    conn.execute('DELETE FROM orders_curated')
    for r in records:
        conn.execute('''INSERT INTO orders_curated VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (r['event_id'], r['event_time'], r['customer_id'], r['source_system'],
                      float(r['amount']), r['status'], int(r['version']), r['checksum'], float(r['total_tax'])))
        metrics['stored'] += 1
    results = conn.execute('SELECT COUNT(*) FROM orders_curated').fetchone()[0]
    if results != len(records):
        metrics['row_count_mismatch'] = 1
    if not checksum_check(records):
        metrics['checksum_mismatch'] = 1
    conn.close()
    return metrics, {'stored_rows': results}


def downstream_validation(records: List[Dict], source_records: List[Dict]) -> Dict:
    reconciled = reconciliation_check(source_records, records)
    ooo = out_of_order_check(source_records, records)
    return {'reconciliation': reconciled, 'out_of_order': ooo}


def run_batch(orders: List[Dict], db_path: str = ':memory:') -> Dict:
    stage_metrics = {}
    source_count = len(orders)
    ingested, ingestion_metrics = ingestion(orders, mode='batch')
    preprocessed, preprocess_metrics = preprocessing(ingested)
    transformed, transform_metrics = transform(preprocessed)
    storage_metrics, storage_info = storage(transformed, db_path=db_path)
    downstream_metrics = downstream_validation(transformed, orders)

    stage_metrics.update(ingestion_metrics)
    stage_metrics.update(preprocess_metrics)
    stage_metrics.update(transform_metrics)
    stage_metrics.update(storage_metrics)
    stage_metrics['downstream_reconciliation'] = downstream_metrics['reconciliation']
    stage_metrics['out_of_order'] = downstream_metrics['out_of_order']
    stage_metrics['source_count'] = source_count
    stage_metrics['stored_rows'] = storage_info['stored_rows']
    stage_metrics['proposed_stored_rows'] = storage_info['stored_rows']
    stage_metrics['proposed_detected_issues'] = (ingestion_metrics.get('invalid_schema', 0)
                                                 + ingestion_metrics.get('nulls', 0)
                                                 + preprocess_metrics.get('type_mismatches', 0)
                                                 + transform_metrics.get('transformation_failures', 0)
                                                 + storage_metrics.get('row_count_mismatch', 0)
                                                 + storage_metrics.get('checksum_mismatch', 0))
    return stage_metrics


def run_streaming(orders: List[Dict], db_path: str = ':memory:') -> Dict:
    # Simulation of streaming: process in small batches with ordering checks.
    batch_size = 20
    final_metrics = {}
    for i in range(0, len(orders), batch_size):
        batch = orders[i:i + batch_size]
        metrics = run_batch(batch, db_path=db_path)
        for k, v in metrics.items():
            final_metrics[k] = final_metrics.get(k, 0) + (v if isinstance(v, (int, float)) else 0)
    return final_metrics