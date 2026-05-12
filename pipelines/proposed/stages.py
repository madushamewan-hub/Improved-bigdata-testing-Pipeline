import os

import duckdb
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

from .metrics import _count_duplicate_event_ids, _record_semantics, _safe_event_time
from .validation import (
    MalformedRecordError,
    TypeMismatchError,
    checksum_mismatch_count,
    enforce_types,
    malformed_payload_check,
    null_check,
    out_of_order_check,
    reconciliation_check,
    schema_validation,
    transformation_check,
)


def ingestion(orders: List[Dict], mode: str = 'batch') -> Tuple[List[Dict], Dict]:
    metrics = {'ingested': 0, 'invalid_schema': 0, 'nulls': 0, 'malformed': 0, 'freshness_issues': 0, 'invalid_event_time': 0}
    valid = []
    now = datetime.utcnow()
    for o in orders:
        metrics['ingested'] += 1
        if not isinstance(o, dict):
            metrics['malformed'] += 1
            continue
        if not schema_validation(o):
            metrics['invalid_schema'] += 1
            continue
        if not null_check(o):
            metrics['nulls'] += 1
            continue

        payload_ok, reason = malformed_payload_check(o)
        if not payload_ok:
            metrics['malformed'] += 1
            if 'event_time' in reason:
                metrics['invalid_event_time'] += 1
            continue

        event_time = _safe_event_time(str(o.get('event_time', '')).strip())
        if event_time is None:
            metrics['invalid_event_time'] += 1
            metrics['malformed'] += 1
            continue
        if _record_semantics(o) != 'reference' and (now - event_time).total_seconds() > 86400:
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
        except MalformedRecordError:
            metrics['malformed'] += 1
        except (TypeMismatchError, AssertionError, TypeError, ValueError):
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
    metrics['mapping_issues'] = _count_duplicate_event_ids(transformed)
    return transformed, metrics


def storage(records: Iterable[Dict], db_path: str = ':memory:') -> Tuple[Dict, Dict]:
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

    batch_size = max(1000, int(os.environ.get('DUCKDB_INSERT_BATCH_SIZE', '10000')))
    insert_rows = []
    checksum_rows: List[Dict] = []

    for r in records:
        row = dict(r)
        insert_rows.append(
            (
                row['event_id'],
                row['event_time'],
                row['customer_id'],
                row['source_system'],
                float(row['amount']),
                row['status'],
                int(row['version']),
                row['checksum'],
                float(row['total_tax']),
            )
        )
        checksum_rows.append(row)

        if len(insert_rows) >= batch_size:
            conn.executemany('''INSERT INTO orders_curated VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', insert_rows)
            metrics['stored'] += len(insert_rows)
            metrics['checksum_mismatch'] += checksum_mismatch_count(checksum_rows)
            insert_rows.clear()
            checksum_rows.clear()

    if insert_rows:
        conn.executemany('''INSERT INTO orders_curated VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', insert_rows)
        metrics['stored'] += len(insert_rows)
        metrics['checksum_mismatch'] += checksum_mismatch_count(checksum_rows)

    results = conn.execute('SELECT COUNT(*) FROM orders_curated').fetchone()[0]
    if results != metrics['stored']:
        metrics['row_count_mismatch'] = abs(results - metrics['stored'])
    conn.close()
    return metrics, {'stored_rows': results}


def downstream_validation(records: List[Dict], source_records: List[Dict]) -> Dict:
    reconciled = reconciliation_check(source_records, records)
    ooo = out_of_order_check(source_records, records)
    return {'reconciliation': reconciled, 'out_of_order': ooo}
