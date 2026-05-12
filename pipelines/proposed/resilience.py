from datetime import datetime
from typing import Any, Dict, List, Tuple

from .metrics import _count_duplicate_event_ids
from .validation import MalformedRecordError, enforce_types, transformation_check

DEFAULT_RESILIENCE_POLICY = {
    'enabled': True,
    'max_retries': 2,
    'max_quarantine_samples': 25,
}


def _snapshot_checkpoint(stage: str, records: List[Dict[str, Any]], record_count: int | None = None) -> Dict[str, Any]:
    sample_ids = [r.get('event_id') for r in records[:5]]
    return {
        'stage': stage,
        'record_count': len(records) if record_count is None else int(record_count),
        'sample_event_ids': sample_ids,
        'captured_at': datetime.utcnow().isoformat(),
    }


def _record_quarantine(quarantine: List[Dict[str, Any]], policy: Dict[str, Any], stage: str, reason: str, record: Dict[str, Any], error: str, attempts: int):
    if len(quarantine) >= int(policy.get('max_quarantine_samples', 25)):
        return
    quarantine.append({
        'stage': stage,
        'reason': reason,
        'error': error,
        'attempts': attempts,
        'event_id': record.get('event_id'),
    })


def _apply_with_retries(fn, record: Dict[str, Any], max_retries: int) -> Tuple[bool, Any, int, Exception | None]:
    attempts = 0
    last_error: Exception | None = None
    while attempts <= max_retries:
        attempts += 1
        try:
            return True, fn(record), attempts, None
        except Exception as exc:
            last_error = exc
    return False, None, attempts, last_error


def _preprocessing_resilient(records: List[Dict], policy: Dict[str, Any], resilience_metrics: Dict[str, Any], quarantine: List[Dict[str, Any]]) -> Tuple[List[Dict], Dict]:
    metrics = {'type_mismatches': 0, 'malformed': 0}
    cleaned = []
    for r in records:
        success, row, attempts, error = _apply_with_retries(enforce_types, r, int(policy.get('max_retries', 2)))
        resilience_metrics['retry_attempts'] += max(0, attempts - 1)
        if attempts > 1:
            resilience_metrics['recovery_attempts'] += 1
        if success:
            if attempts > 1:
                resilience_metrics['successful_recoveries'] += 1
            cleaned.append(row)
        else:
            reason = 'type_enforcement_failed'
            if isinstance(error, MalformedRecordError):
                metrics['malformed'] += 1
                reason = 'malformed_record'
            else:
                metrics['type_mismatches'] += 1
            resilience_metrics['quarantined_records'] += 1
            _record_quarantine(
                quarantine,
                policy,
                stage='preprocessing',
                reason=reason,
                record=r,
                error=str(error) if error else '',
                attempts=attempts,
            )
    return cleaned, metrics


def _transform_resilient(records: List[Dict], policy: Dict[str, Any], resilience_metrics: Dict[str, Any], quarantine: List[Dict[str, Any]]) -> Tuple[List[Dict], Dict]:
    metrics = {'transformation_failures': 0, 'mapping_issues': 0}
    transformed = []
    for r in records:
        success, row, attempts, error = _apply_with_retries(transformation_check, r, int(policy.get('max_retries', 2)))
        resilience_metrics['retry_attempts'] += max(0, attempts - 1)
        if attempts > 1:
            resilience_metrics['recovery_attempts'] += 1
        if success:
            if attempts > 1:
                resilience_metrics['successful_recoveries'] += 1
            transformed.append(row)
        else:
            metrics['transformation_failures'] += 1
            resilience_metrics['quarantined_records'] += 1
            _record_quarantine(
                quarantine,
                policy,
                stage='transformation',
                reason='transformation_failed',
                record=r,
                error=str(error) if error else '',
                attempts=attempts,
            )
    metrics['mapping_issues'] = _count_duplicate_event_ids(transformed)
    return transformed, metrics
