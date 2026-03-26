from typing import Dict, List

REQUIRED_FIELDS = ['event_id', 'event_time', 'customer_id', 'source_system', 'amount', 'status', 'version', 'checksum']


def schema_validation(event: Dict) -> bool:
    return all(field in event for field in REQUIRED_FIELDS)


def null_check(event: Dict) -> bool:
    return all(event.get(field) is not None for field in REQUIRED_FIELDS)


def enforce_types(event: Dict) -> Dict:
    assert isinstance(event['event_id'], str)
    assert isinstance(event['event_time'], str)
    assert isinstance(event['customer_id'], str)
    event['amount'] = float(event['amount'])
    event['version'] = int(event['version'])
    return event


def checksum_check(events: List[Dict]) -> bool:
    from data_generator.order_events import compute_checksum
    for e in events:
        expected = compute_checksum(e)
        if e.get('checksum') != expected:
            return False
    return True


def duplicate_check(events: List[Dict]) -> bool:
    ids = [e['event_id'] for e in events]
    return len(ids) == len(set(ids))


def transformation_check(event: Dict) -> Dict:
    result = dict(event)
    if not isinstance(result['amount'], (int, float)):
        raise ValueError('invalid amount')
    result['total_tax'] = round(result['amount'] * 0.1, 2)
    return result


def reconciliation_check(source: List[Dict], target: List[Dict]) -> bool:
    source_ids = set(e['event_id'] for e in source)
    target_ids = set(e['event_id'] for e in target)
    return source_ids == target_ids


def out_of_order_check(source: List[Dict], target: List[Dict]) -> float:
    source_times = [e['event_time'] for e in source]
    target_times = [e['event_time'] for e in target]
    return float(sum(1 for i, t in enumerate(target_times) if t != source_times[i]) / max(1, len(source_times)))
