from datetime import datetime
from typing import Any, Dict, List, Tuple

REQUIRED_FIELDS = ['event_id', 'event_time', 'customer_id', 'source_system', 'amount', 'status', 'version', 'checksum']


class ValidationClassificationError(Exception):
    """Base class for record validation classification errors."""


class TypeMismatchError(ValidationClassificationError):
    """Raised when a record has the required fields but incompatible types."""


class MalformedRecordError(ValidationClassificationError):
    """Raised when a record is structurally present but content is malformed."""


def schema_validation(event: Dict) -> bool:
    return isinstance(event, dict) and all(field in event for field in REQUIRED_FIELDS)


def null_check(event: Dict) -> bool:
    return all(event.get(field) is not None for field in REQUIRED_FIELDS)


def malformed_payload_check(event: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(event, dict):
        return False, 'payload is not a mapping'

    for field in ['event_id', 'event_time', 'customer_id', 'source_system', 'status', 'checksum']:
        value = event.get(field)
        if isinstance(value, str) and not value.strip():
            return False, f'{field} is blank'

    event_time = str(event.get('event_time', '')).strip()
    if not event_time:
        return False, 'event_time is blank'

    try:
        datetime.fromisoformat(event_time)
    except Exception:
        return False, 'event_time is invalid'

    return True, ''


def enforce_types(event: Dict) -> Dict:
    if not schema_validation(event):
        raise MalformedRecordError('missing required fields')
    if not null_check(event):
        raise MalformedRecordError('required field is null')

    payload_ok, reason = malformed_payload_check(event)
    if not payload_ok:
        raise MalformedRecordError(reason)

    result = dict(event)
    for field in ['event_id', 'event_time', 'customer_id', 'source_system', 'status', 'checksum']:
        if not isinstance(result[field], str):
            raise TypeMismatchError(f'{field} must be a string')

    try:
        result['amount'] = float(result['amount'])
    except (TypeError, ValueError) as exc:
        raise TypeMismatchError('amount must be numeric') from exc

    try:
        result['version'] = int(result['version'])
    except (TypeError, ValueError) as exc:
        raise TypeMismatchError('version must be an integer') from exc

    return result


def checksum_mismatch_count(events: List[Dict]) -> int:
    from data_generator.order_events import compute_checksum

    mismatches = 0
    for e in events:
        expected = compute_checksum(e)
        if e.get('checksum') != expected:
            mismatches += 1
    return mismatches


def checksum_check(events: List[Dict]) -> bool:
    return checksum_mismatch_count(events) == 0


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
