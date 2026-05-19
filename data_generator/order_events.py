import random
from datetime import datetime, timedelta
from typing import List, Dict

BASE_ORDER = {
    'event_id': None,
    'event_time': None,
    'customer_id': None,
    'source_system': 'web',
    'amount': None,
    'status': 'created',
    'version': 1,
    'checksum': None,
}


def compute_checksum(event: Dict) -> str:
    payload = f"{event['event_id']}|{event['customer_id']}|{event['amount']}|{event['event_time']}"
    return str(abs(hash(payload)))


def generate_base_orders(n: int, start_time: datetime = None, seed: int = 42) -> List[Dict]:
    random.seed(seed)
    if start_time is None:
        start_time = datetime.utcnow() - timedelta(hours=1)
    orders = []
    for i in range(n):
        e = BASE_ORDER.copy()
        e['event_id'] = f'order-{i:06d}'
        e['event_time'] = (start_time + timedelta(seconds=10 * i)).isoformat()
        e['customer_id'] = f'cust-{random.randint(1, 100):03d}'
        e['amount'] = float(round(random.uniform(10.0, 500.0), 2))
        e['status'] = random.choice(['created', 'paid', 'shipped'])
        e['version'] = 1
        e['checksum'] = compute_checksum(e)
        orders.append(e)
    return orders


def inject_missing(orders: List[Dict], missing_rate: float = 0.1) -> List[Dict]:
    result = []
    candidate_fields = ['event_time', 'customer_id', 'amount', 'status']
    for o in orders:
        row = dict(o)
        if random.random() < missing_rate:
            field = random.choice(candidate_fields)
            row[field] = None
            row['checksum'] = None
        result.append(row)
    return result


def inject_duplicates(orders: List[Dict], duplicate_rate: float = 0.1) -> List[Dict]:
    result = orders.copy()
    for o in orders:
        if random.random() < duplicate_rate:
            result.append(dict(o))
    return result


def inject_corruption(orders: List[Dict], corrupt_rate: float = 0.1) -> List[Dict]:
    result = []
    for o in orders:
        if random.random() < corrupt_rate:
            corrupted = dict(o)
            if isinstance(corrupted.get('amount'), (int, float)):
                corrupted['amount'] = corrupted['amount'] * 10 + 1
            corrupted['checksum'] = 'invalid'
            result.append(corrupted)
        else:
            result.append(o)
    return result


def inject_schema_drift(orders: List[Dict], drift_rate: float = 0.1) -> List[Dict]:
    result = []
    for o in orders:
        row = dict(o)
        if random.random() < drift_rate:
            row['amount'] = 'N/A'
        result.append(row)
    return result


def inject_out_of_order(orders: List[Dict], delay_rate: float = 0.1) -> List[Dict]:
    result = orders.copy()
    if not result:
        return result
    n = max(1, int(len(result) * delay_rate))
    for i in range(n):
        idx = random.randint(0, len(result) - 1)
        target = random.randint(0, len(result) - 1)
        result[idx], result[target] = result[target], result[idx]
    return result
