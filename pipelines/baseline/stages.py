import duckdb
from typing import Dict, List


def ingestion(orders: List[Dict], mode: str = 'batch') -> List[Dict]:
    """Baseline ingestion: no checks."""
    return orders


def preprocessing(records: List[Dict]) -> List[Dict]:
    """Baseline preprocessing: cast minimal fields and pass through."""
    return records


def transform(records: List[Dict]) -> List[Dict]:
    """Baseline transform: compute total_tax as 10% simple rule."""
    transformed = []
    for r in records:
        row = dict(r)
        try:
            amount = float(r.get('amount', 0))
        except (TypeError, ValueError):
            amount = 0.0
        row['amount'] = amount
        row['total_tax'] = round(amount * 0.1, 2)
        transformed.append(row)
    return transformed


def storage(records: List[Dict], db_path: str = ':memory:') -> None:
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
    conn.executemany(
        '''INSERT INTO orders_curated VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        [
            (
                r['event_id'],
                r['event_time'],
                r['customer_id'],
                r['source_system'],
                float(r.get('amount', 0)),
                r.get('status'),
                int(r.get('version', 1)),
                r.get('checksum'),
                float(r.get('total_tax', 0)),
            )
            for r in records
        ],
    )
    conn.close()


def downstream_validation(records: List[Dict]) -> Dict:
    """Baseline downstream validation: minimal sanity check."""
    return {'record_count': len(records)}


__all__ = [
    'downstream_validation',
    'ingestion',
    'preprocessing',
    'storage',
    'transform',
]
