import duckdb
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import List, Dict, Tuple, Any
from datetime import datetime
from .validation import (
    REQUIRED_FIELDS,
    schema_validation,
    null_check,
    duplicate_check,
    checksum_check,
    checksum_mismatch_count,
    transformation_check,
    reconciliation_check,
    enforce_types,
    out_of_order_check,
)
from .sector_targets import evaluate_sector_targets


CORE_DIMENSIONS = [
    'accuracy',
    'completeness',
    'consistency',
    'validity',
    'uniqueness',
    'timeliness',
    'integrity',
    'reliability',
    'traceability_governance',
]

DEFAULT_RESILIENCE_POLICY = {
    'enabled': True,
    'max_retries': 2,
    'max_quarantine_samples': 25,
}

SPARK_ALT_PYTHON_ENV = 'SPARK_PYTHON_EXECUTABLE'
SPARK_EXTERNAL_RUNNER_ACTIVE_ENV = 'SPARK_EXTERNAL_RUNNER_ACTIVE'
SPARK_FORCE_IN_PROCESS_ENV = 'SPARK_FORCE_IN_PROCESS'


def _configure_spark_python_runtime() -> str:
    python_executable = sys.executable
    os.environ['PYSPARK_PYTHON'] = python_executable
    os.environ['PYSPARK_DRIVER_PYTHON'] = python_executable
    return python_executable


def _safe_event_time(value: str):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _record_semantics(record: Dict[str, Any]) -> str:
    return str(record.get('record_semantics', 'event')).lower()


def _resolve_external_spark_python() -> str | None:
    alt_python = os.environ.get(SPARK_ALT_PYTHON_ENV)
    if alt_python and Path(alt_python).exists():
        return alt_python
    if sys.version_info < (3, 14) and Path(sys.executable).exists():
        return sys.executable
    return None


def _should_use_external_spark_runner() -> bool:
    if os.environ.get(SPARK_EXTERNAL_RUNNER_ACTIVE_ENV) == '1':
        return False
    if os.environ.get(SPARK_FORCE_IN_PROCESS_ENV) == '1':
        return False
    return True


def get_engine_capabilities() -> Dict[str, Dict[str, Any]]:
    alt_python = _resolve_external_spark_python()
    alt_python_exists = bool(alt_python) and Path(alt_python).exists()
    configured_alt_python = os.environ.get(SPARK_ALT_PYTHON_ENV)
    prefer_external_runner = _should_use_external_spark_runner()
    current_python_version = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
    recommended_python = '3.11/3.12'
    pyspark_installed = False
    try:
        import pyspark  # noqa: F401
        pyspark_installed = True
    except Exception:
        pyspark_installed = False

    python_supported = sys.version_info < (3, 14)
    spark_available = (python_supported and pyspark_installed) or alt_python_exists

    if spark_available and alt_python_exists and prefer_external_runner:
        if configured_alt_python is not None:
            spark_reason = f'Using alternate Spark Python runtime from {alt_python}.'
        else:
            spark_reason = f'Using external Spark execution with Python runtime {alt_python}.'
        spark_mode = 'external_python'
    elif spark_available and python_supported and pyspark_installed:
        spark_reason = f'PySpark is available in the current Python {current_python_version} runtime.'
        spark_mode = 'in_process'
    elif not python_supported:
        spark_reason = (
            f'Current backend Python runtime is {current_python_version}; '
            f'Spark adapter requires Python {recommended_python} or SPARK_PYTHON_EXECUTABLE '
            f'to point to a compatible interpreter.'
        )
        spark_mode = 'unavailable'
    else:
        spark_reason = (
            f'PySpark is not installed in the current Python {current_python_version} runtime. '
            f'Use Python {recommended_python} for the Spark adapter.'
        )
        spark_mode = 'unavailable'

    return {
        'python': {
            'available': True,
            'mode': 'in_process',
            'reason': 'Default reference execution engine.',
            'current_python': current_python_version,
        },
        'spark': {
            'available': spark_available,
            'mode': spark_mode,
            'reason': spark_reason,
            'alternate_python': alt_python if spark_mode == 'external_python' else None,
            'current_python': current_python_version,
            'recommended_python': recommended_python,
        },
    }


def _run_spark_via_external_python(orders: List[Dict], db_path: str, sector: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    alt_python = _resolve_external_spark_python()
    if not alt_python or not Path(alt_python).exists():
        raise RuntimeError('Spark engine requires SPARK_PYTHON_EXECUTABLE to point to a Python 3.11/3.12 interpreter.')

    runner_path = Path(__file__).with_name('spark_runner.py')
    payload = {
        'orders': orders,
        'db_path': db_path,
        'sector': sector,
        'resilience_policy': policy,
    }
    runner_env = dict(os.environ)
    runner_env[SPARK_EXTERNAL_RUNNER_ACTIVE_ENV] = '1'
    runner_env['PYSPARK_PYTHON'] = alt_python
    runner_env['PYSPARK_DRIVER_PYTHON'] = alt_python
    completed = subprocess.run(
        [alt_python, str(runner_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env=runner_env,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or 'Unknown Spark runner error'
        raise RuntimeError(f'External Spark runner failed: {stderr}')

    stdout_text = completed.stdout.strip()
    result_marker = '__SPARK_RESULT__'
    if result_marker in stdout_text:
        marker_payload = stdout_text.rsplit(result_marker, 1)[-1].strip()
        try:
            decoded_result, _ = json.JSONDecoder().raw_decode(marker_payload)
            return decoded_result
        except Exception as exc:
            raise RuntimeError(f'External Spark runner produced invalid marked JSON: {exc}')

    candidate_lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
    for candidate in reversed(candidate_lines):
        try:
            return json.loads(candidate)
        except Exception:
            continue

    try:
        return json.loads(stdout_text)
    except Exception as exc:
        raise RuntimeError(f'External Spark runner produced invalid JSON: {exc}')


def _count_duplicate_event_ids(records: List[Dict]) -> int:
    seen = set()
    duplicates = 0
    for row in records:
        event_id = row.get('event_id')
        if event_id in seen:
            duplicates += 1
        else:
            seen.add(event_id)
    return duplicates


def _run_dimension_rule_packs(context: Dict) -> Dict[str, Dict]:
    source_records = context.get('source_records', [])
    transformed_records = context.get('transformed_records', [])
    ingestion_metrics = context.get('ingestion_metrics', {})
    preprocess_metrics = context.get('preprocess_metrics', {})
    transform_metrics = context.get('transform_metrics', {})
    storage_metrics = context.get('storage_metrics', {})
    downstream_metrics = context.get('downstream_metrics', {})

    source_count = max(1, len(source_records))
    reference_majority = bool(source_records) and sum(1 for row in source_records if _record_semantics(row) == 'reference') >= (len(source_records) / 2)

    out_of_order_rate = float(downstream_metrics.get('out_of_order', 0.0))
    out_of_order_rows = 0 if reference_majority else int(round(out_of_order_rate * len(source_records)))
    timeliness_findings = 0 if reference_majority else int(ingestion_metrics.get('freshness_issues', 0)) + out_of_order_rows

    invalid_time_rows = 0
    invalid_amount_rows = 0
    missing_trace_rows = 0
    for row in transformed_records:
        if _safe_event_time(str(row.get('event_time', ''))) is None:
            invalid_time_rows += 1
        try:
            if float(row.get('amount', 0.0)) < 0:
                invalid_amount_rows += 1
        except Exception:
            invalid_amount_rows += 1
        if row.get('checksum') in (None, '') or row.get('event_id') in (None, ''):
            missing_trace_rows += 1

    dimension_findings = {
        'accuracy': (
            int(ingestion_metrics.get('invalid_schema', 0))
            + int(ingestion_metrics.get('nulls', 0))
            + int(preprocess_metrics.get('type_mismatches', 0))
            + int(transform_metrics.get('transformation_failures', 0))
        ),
        'completeness': int(ingestion_metrics.get('nulls', 0)),
        'consistency': int(storage_metrics.get('row_count_mismatch', 0)) + out_of_order_rows,
        'validity': invalid_time_rows + invalid_amount_rows,
        'uniqueness': _count_duplicate_event_ids(transformed_records),
        'timeliness': timeliness_findings,
        'integrity': int(storage_metrics.get('checksum_mismatch', 0)) + (0 if downstream_metrics.get('reconciliation', False) else 1),
        'reliability': int(preprocess_metrics.get('type_mismatches', 0)) + int(transform_metrics.get('transformation_failures', 0)),
        'traceability_governance': missing_trace_rows + int(ingestion_metrics.get('invalid_schema', 0)),
    }

    dimension_scores = {
        dim: max(0.0, 1.0 - (float(findings) / float(source_count)))
        for dim, findings in dimension_findings.items()
    }

    return {
        'findings': dimension_findings,
        'scores': dimension_scores,
        'rule_pack_version': 'v1.0.0',
        'core_dimensions': CORE_DIMENSIONS,
    }


def _build_check_evidence(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    source_count = max(1, int(context.get('source_count', 0)))
    ingestion_metrics = context.get('ingestion_metrics', {})
    preprocess_metrics = context.get('preprocess_metrics', {})
    transform_metrics = context.get('transform_metrics', {})
    storage_metrics = context.get('storage_metrics', {})
    downstream_metrics = context.get('downstream_metrics', {})

    checks: List[Dict[str, Any]] = []

    def add_count_check(check_id: str, dimension: str, findings: int, detail: str):
        confidence = max(0.0, 1.0 - (float(findings) / float(source_count)))
        checks.append({
            'check_id': check_id,
            'dimension': dimension,
            'status': 'pass' if findings == 0 else 'fail',
            'findings': int(findings),
            'confidence': confidence,
            'evidence': {
                'detail': detail,
                'source_count': source_count,
                'failure_ratio': float(findings) / float(source_count),
            },
        })

    add_count_check(
        'schema_validation',
        'traceability_governance',
        int(ingestion_metrics.get('invalid_schema', 0)),
        'Records rejected due to missing required fields.',
    )
    add_count_check(
        'null_check',
        'completeness',
        int(ingestion_metrics.get('nulls', 0)),
        'Records rejected due to required null values.',
    )
    add_count_check(
        'freshness_check',
        'timeliness',
        int(ingestion_metrics.get('freshness_issues', 0)),
        'Records older than freshness SLA window.',
    )
    add_count_check(
        'type_enforcement',
        'reliability',
        int(preprocess_metrics.get('type_mismatches', 0)),
        'Type conversion failures during preprocessing.',
    )
    add_count_check(
        'transformation_validation',
        'accuracy',
        int(transform_metrics.get('transformation_failures', 0)),
        'Transformation function failures.',
    )
    add_count_check(
        'duplicate_mapping_check',
        'uniqueness',
        int(transform_metrics.get('mapping_issues', 0)),
        'Duplicate mapping inconsistency indicators.',
    )
    add_count_check(
        'row_count_reconciliation',
        'consistency',
        int(storage_metrics.get('row_count_mismatch', 0)),
        'Source/target row-count mismatch at storage boundary.',
    )
    add_count_check(
        'checksum_integrity',
        'integrity',
        int(storage_metrics.get('checksum_mismatch', 0)),
        'Checksum verification mismatch for transformed records.',
    )

    out_of_order_rate = float(downstream_metrics.get('out_of_order', 0.0))
    out_of_order_rows = int(round(out_of_order_rate * source_count))
    out_of_order_confidence = max(0.0, 1.0 - out_of_order_rate)
    checks.append({
        'check_id': 'event_ordering_monitor',
        'dimension': 'timeliness',
        'status': 'pass' if out_of_order_rows == 0 else 'fail',
        'findings': out_of_order_rows,
        'confidence': out_of_order_confidence,
        'evidence': {
            'detail': 'Out-of-order event-time records after processing.',
            'out_of_order_rate': out_of_order_rate,
            'estimated_affected_rows': out_of_order_rows,
        },
    })

    reconciled = bool(downstream_metrics.get('reconciliation', False))
    checks.append({
        'check_id': 'downstream_reconciliation',
        'dimension': 'consistency',
        'status': 'pass' if reconciled else 'fail',
        'findings': 0 if reconciled else 1,
        'confidence': 1.0 if reconciled else 0.0,
        'evidence': {
            'detail': 'Source/target event-id reconciliation status.',
            'reconciled': reconciled,
        },
    })

    return checks


def _summarize_confidence(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_check: Dict[str, float] = {}
    by_dimension: Dict[str, List[float]] = {}
    for check in checks:
        check_id = check.get('check_id')
        dim = check.get('dimension')
        conf = float(check.get('confidence', 0.0))
        by_check[check_id] = conf
        by_dimension.setdefault(dim, []).append(conf)

    dimension_confidence = {
        dim: (sum(scores) / len(scores) if scores else 0.0)
        for dim, scores in by_dimension.items()
    }
    overall_confidence = (
        sum(dimension_confidence.values()) / len(dimension_confidence)
        if dimension_confidence else 0.0
    )
    return {
        'check_confidence': by_check,
        'dimension_confidence': dimension_confidence,
        'overall_confidence': overall_confidence,
    }


def _compute_composite_score(dimension_scores: Dict[str, Any], sector_compliance_score: float) -> Dict[str, float]:
    if isinstance(dimension_scores, dict) and dimension_scores:
        dimension_average = sum(float(v) for v in dimension_scores.values()) / float(len(dimension_scores))
    else:
        dimension_average = 0.0

    sector_score = float(sector_compliance_score)
    composite_score = (0.6 * dimension_average) + (0.4 * sector_score)

    return {
        'dimension_average_score': max(0.0, min(1.0, dimension_average)),
        'sector_compliance_score': max(0.0, min(1.0, sector_score)),
        'composite_score': max(0.0, min(1.0, composite_score)),
        'composite_formula': '0.6*dimension_average + 0.4*sector_compliance',
    }


def _snapshot_checkpoint(stage: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    sample_ids = [r.get('event_id') for r in records[:5]]
    return {
        'stage': stage,
        'record_count': len(records),
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


def _apply_with_retries(fn, record: Dict[str, Any], max_retries: int) -> Tuple[bool, Any, int, str]:
    attempts = 0
    last_error = ''
    while attempts <= max_retries:
        attempts += 1
        try:
            return True, fn(record), attempts, ''
        except Exception as exc:
            last_error = str(exc)
    return False, None, attempts, last_error


def _preprocessing_resilient(records: List[Dict], policy: Dict[str, Any], resilience_metrics: Dict[str, Any], quarantine: List[Dict[str, Any]]) -> Tuple[List[Dict], Dict]:
    metrics = {'type_mismatches': 0, 'malformed': 0}
    cleaned = []
    for r in records:
        success, row, attempts, error = _apply_with_retries(enforce_types, r, int(policy.get('max_retries', 2)))
        resilience_metrics['retry_attempts'] += max(0, attempts - 1)
        if success:
            cleaned.append(row)
        else:
            metrics['type_mismatches'] += 1
            resilience_metrics['quarantined_records'] += 1
            _record_quarantine(
                quarantine,
                policy,
                stage='preprocessing',
                reason='type_enforcement_failed',
                record=r,
                error=error,
                attempts=attempts,
            )
    return cleaned, metrics


def _transform_resilient(records: List[Dict], policy: Dict[str, Any], resilience_metrics: Dict[str, Any], quarantine: List[Dict[str, Any]]) -> Tuple[List[Dict], Dict]:
    metrics = {'transformation_failures': 0, 'mapping_issues': 0}
    transformed = []
    for r in records:
        success, row, attempts, error = _apply_with_retries(transformation_check, r, int(policy.get('max_retries', 2)))
        resilience_metrics['retry_attempts'] += max(0, attempts - 1)
        if success:
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
                error=error,
                attempts=attempts,
            )
    metrics['mapping_issues'] = _count_duplicate_event_ids(transformed)
    return transformed, metrics


def ingestion(orders: List[Dict], mode: str = 'batch') -> Tuple[List[Dict], Dict]:
    metrics = {'ingested': 0, 'invalid_schema': 0, 'nulls': 0, 'freshness_issues': 0, 'invalid_event_time': 0}
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
        event_time = _safe_event_time(str(o.get('event_time', '')))
        if event_time is None:
            metrics['invalid_event_time'] += 1
            metrics['invalid_schema'] += 1
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
    metrics['mapping_issues'] = _count_duplicate_event_ids(transformed)
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
        metrics['row_count_mismatch'] = abs(results - len(records))
    metrics['checksum_mismatch'] = checksum_mismatch_count(records)
    conn.close()
    return metrics, {'stored_rows': results}


def downstream_validation(records: List[Dict], source_records: List[Dict]) -> Dict:
    reconciled = reconciliation_check(source_records, records)
    ooo = out_of_order_check(source_records, records)
    return {'reconciliation': reconciled, 'out_of_order': ooo}


def _finalize_proposed_metrics(
    orders: List[Dict],
    transformed: List[Dict],
    ingestion_metrics: Dict[str, Any],
    preprocess_metrics: Dict[str, Any],
    transform_metrics: Dict[str, Any],
    storage_metrics: Dict[str, Any],
    storage_info: Dict[str, Any],
    downstream_metrics: Dict[str, Any],
    sector: str,
    engine: str,
    resilience_metrics: Dict[str, Any],
    checkpoint_flow: List[Dict[str, Any]],
    quarantine_records: List[Dict[str, Any]],
    resilience_policy: Dict[str, Any],
) -> Dict[str, Any]:
    stage_metrics = {}
    source_count = len(orders)

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
                                                 + transform_metrics.get('mapping_issues', 0)
                                                 + storage_metrics.get('row_count_mismatch', 0)
                                                 + storage_metrics.get('checksum_mismatch', 0))
    stage_metrics['checkpoint_flow'] = checkpoint_flow
    stage_metrics['quarantine_records'] = quarantine_records
    stage_metrics['quarantine_count'] = resilience_metrics['quarantined_records']
    stage_metrics['retry_attempts'] = resilience_metrics['retry_attempts']
    stage_metrics['checkpoint_recoveries'] = resilience_metrics['checkpoint_recoveries']
    stage_metrics['resilience_policy'] = resilience_policy
    stage_metrics['engine'] = engine

    dimension_summary = _run_dimension_rule_packs({
        'source_records': orders,
        'transformed_records': transformed,
        'ingestion_metrics': ingestion_metrics,
        'preprocess_metrics': preprocess_metrics,
        'transform_metrics': transform_metrics,
        'storage_metrics': storage_metrics,
        'downstream_metrics': downstream_metrics,
    })
    stage_metrics['dimension_findings'] = dimension_summary['findings']
    stage_metrics['dimension_scores'] = dimension_summary['scores']
    stage_metrics['rule_pack_version'] = dimension_summary['rule_pack_version']
    stage_metrics['core_dimensions'] = dimension_summary['core_dimensions']

    check_evidence = _build_check_evidence({
        'source_count': source_count,
        'ingestion_metrics': ingestion_metrics,
        'preprocess_metrics': preprocess_metrics,
        'transform_metrics': transform_metrics,
        'storage_metrics': storage_metrics,
        'downstream_metrics': downstream_metrics,
    })
    confidence_summary = _summarize_confidence(check_evidence)
    stage_metrics['check_evidence'] = check_evidence
    stage_metrics['check_confidence'] = confidence_summary['check_confidence']
    stage_metrics['dimension_confidence'] = confidence_summary['dimension_confidence']
    stage_metrics['overall_confidence'] = confidence_summary['overall_confidence']

    sector_eval = evaluate_sector_targets(stage_metrics, sector=sector)
    stage_metrics['sector'] = sector_eval['sector']
    stage_metrics['advanced_metric_scores'] = sector_eval['advanced_metric_scores']
    stage_metrics['sector_target_evaluation'] = sector_eval
    stage_metrics['sector_compliance_score'] = sector_eval['compliance_score']
    stage_metrics['sector_pass_rate'] = sector_eval['pass_rate']

    composite_summary = _compute_composite_score(
        stage_metrics.get('dimension_scores', {}),
        stage_metrics.get('sector_compliance_score', 0.0),
    )
    stage_metrics['dimension_average_score'] = composite_summary['dimension_average_score']
    stage_metrics['composite_score'] = composite_summary['composite_score']
    stage_metrics['composite_formula'] = composite_summary['composite_formula']

    return stage_metrics


def _run_python_batch_internal(orders: List[Dict], db_path: str, sector: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    resilience_metrics = {
        'retry_attempts': 0,
        'quarantined_records': 0,
        'checkpoint_recoveries': 0,
    }
    quarantine_records: List[Dict[str, Any]] = []
    checkpoint_flow: List[Dict[str, Any]] = []

    ingested, ingestion_metrics = ingestion(orders, mode='batch')
    checkpoint_flow.append(_snapshot_checkpoint('ingestion', ingested))

    if policy.get('enabled', True):
        preprocessed, preprocess_metrics = _preprocessing_resilient(ingested, policy, resilience_metrics, quarantine_records)
    else:
        preprocessed, preprocess_metrics = preprocessing(ingested)
    checkpoint_flow.append(_snapshot_checkpoint('preprocessing', preprocessed))

    if policy.get('enabled', True):
        transformed, transform_metrics = _transform_resilient(preprocessed, policy, resilience_metrics, quarantine_records)
    else:
        transformed, transform_metrics = transform(preprocessed)
    checkpoint_flow.append(_snapshot_checkpoint('transformation', transformed))

    storage_attempts = 0
    max_storage_retries = int(policy.get('max_retries', 2)) if policy.get('enabled', True) else 0
    while True:
        storage_attempts += 1
        try:
            storage_metrics, storage_info = storage(transformed, db_path=db_path)
            break
        except Exception:
            if storage_attempts > max_storage_retries + 1:
                raise
            resilience_metrics['checkpoint_recoveries'] += 1
    resilience_metrics['retry_attempts'] += max(0, storage_attempts - 1)
    checkpoint_flow.append(_snapshot_checkpoint('storage', transformed))

    downstream_metrics = downstream_validation(transformed, orders)

    return _finalize_proposed_metrics(
        orders=orders,
        transformed=transformed,
        ingestion_metrics=ingestion_metrics,
        preprocess_metrics=preprocess_metrics,
        transform_metrics=transform_metrics,
        storage_metrics=storage_metrics,
        storage_info=storage_info,
        downstream_metrics=downstream_metrics,
        sector=sector,
        engine='python',
        resilience_metrics=resilience_metrics,
        checkpoint_flow=checkpoint_flow,
        quarantine_records=quarantine_records,
        resilience_policy=policy,
    )


def _run_spark_batch_internal(orders: List[Dict], db_path: str, sector: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    if sys.version_info >= (3, 14):
        return _run_spark_via_external_python(orders, db_path=db_path, sector=sector, policy=policy)
    if _should_use_external_spark_runner():
        return _run_spark_via_external_python(orders, db_path=db_path, sector=sector, policy=policy)

    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
    except Exception as exc:
        raise RuntimeError(f'Spark engine requested but pyspark is unavailable: {exc}')

    resilience_metrics = {
        'retry_attempts': 0,
        'quarantined_records': 0,
        'checkpoint_recoveries': 0,
    }
    quarantine_records: List[Dict[str, Any]] = []
    checkpoint_flow: List[Dict[str, Any]] = []

    spark_python = _configure_spark_python_runtime()
    spark = (
        SparkSession.builder
        .master('local[1]')
        .appName('integrity-testing-proposed')
        .config('spark.pyspark.python', spark_python)
        .config('spark.pyspark.driver.python', spark_python)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel('ERROR')

    try:
        ingested, ingestion_metrics = ingestion(orders, mode='batch')
        checkpoint_flow.append(_snapshot_checkpoint('ingestion', ingested))

        if not ingested:
            preprocessed = []
            preprocess_metrics = {'type_mismatches': 0, 'malformed': 0}
            transformed = []
            transform_metrics = {'transformation_failures': 0, 'mapping_issues': 0}
            storage_metrics, storage_info = storage([], db_path=db_path)
            checkpoint_flow.append(_snapshot_checkpoint('preprocessing', preprocessed))
            checkpoint_flow.append(_snapshot_checkpoint('transformation', transformed))
            checkpoint_flow.append(_snapshot_checkpoint('storage', transformed))
            downstream_metrics = downstream_validation(transformed, orders)
        else:
            df = spark.createDataFrame(ingested)

            typed_df = df.select(
                *[F.col(field) for field in REQUIRED_FIELDS],
                F.col('amount').cast('double').alias('amount_cast'),
                F.col('version').cast('int').alias('version_cast'),
            )

            bad_type_df = typed_df.filter(
                (F.col('amount').isNotNull() & F.col('amount_cast').isNull()) |
                (F.col('version').isNotNull() & F.col('version_cast').isNull())
            )
            preprocess_metrics = {
                'type_mismatches': int(bad_type_df.count()),
                'malformed': 0,
            }

            good_type_df = typed_df.filter(
                F.col('amount_cast').isNotNull() & F.col('version_cast').isNotNull()
            ).drop('amount', 'version').withColumnRenamed('amount_cast', 'amount').withColumnRenamed('version_cast', 'version')

            preprocessed = [row.asDict() for row in good_type_df.collect()]
            checkpoint_flow.append(_snapshot_checkpoint('preprocessing', preprocessed))

            transformed_df = good_type_df.withColumn('total_tax', F.round(F.col('amount') * F.lit(0.1), 2))
            transformed = [row.asDict() for row in transformed_df.collect()]
            transform_metrics = {
                'transformation_failures': 0,
                'mapping_issues': _count_duplicate_event_ids(transformed),
            }
            checkpoint_flow.append(_snapshot_checkpoint('transformation', transformed))

            storage_metrics, storage_info = storage(transformed, db_path=db_path)
            checkpoint_flow.append(_snapshot_checkpoint('storage', transformed))
            downstream_metrics = downstream_validation(transformed, orders)

        return _finalize_proposed_metrics(
            orders=orders,
            transformed=transformed,
            ingestion_metrics=ingestion_metrics,
            preprocess_metrics=preprocess_metrics,
            transform_metrics=transform_metrics,
            storage_metrics=storage_metrics,
            storage_info=storage_info,
            downstream_metrics=downstream_metrics,
            sector=sector,
            engine='spark',
            resilience_metrics=resilience_metrics,
            checkpoint_flow=checkpoint_flow,
            quarantine_records=quarantine_records,
            resilience_policy=policy,
        )
    finally:
        try:
            spark.stop()
        except Exception:
            pass


def run_batch(orders: List[Dict], db_path: str = ':memory:', sector: str = 'cross_industry', resilience_policy: Dict[str, Any] = None, engine: str = 'python') -> Dict:
    policy = dict(DEFAULT_RESILIENCE_POLICY)
    if resilience_policy:
        policy.update(resilience_policy)

    if engine == 'python':
        return _run_python_batch_internal(orders, db_path=db_path, sector=sector, policy=policy)
    if engine == 'spark':
        return _run_spark_batch_internal(orders, db_path=db_path, sector=sector, policy=policy)
    raise ValueError(f'Unsupported engine: {engine}')


def run_streaming(orders: List[Dict], db_path: str = ':memory:', sector: str = 'cross_industry', resilience_policy: Dict[str, Any] = None, engine: str = 'python') -> Dict:
    # Simulation of streaming: process in small batches with ordering checks.
    batch_size = 20
    final_metrics = {}
    findings_accumulator = {dim: 0 for dim in CORE_DIMENSIONS}
    score_accumulator = {dim: 0.0 for dim in CORE_DIMENSIONS}
    check_confidence_accumulator: Dict[str, float] = {}
    check_confidence_counts: Dict[str, int] = {}
    dimension_confidence_accumulator = {dim: 0.0 for dim in CORE_DIMENSIONS}
    evidence_batches: List[Dict[str, Any]] = []
    advanced_metric_accumulator: Dict[str, float] = {}
    total_retry_attempts = 0
    total_quarantine_count = 0
    total_checkpoint_recoveries = 0
    checkpoint_batches: List[Dict[str, Any]] = []
    quarantine_batches: List[Dict[str, Any]] = []
    batches = 0
    for i in range(0, len(orders), batch_size):
        batch = orders[i:i + batch_size]
        metrics = run_batch(batch, db_path=db_path, sector=sector, resilience_policy=resilience_policy, engine=engine)
        batches += 1
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                final_metrics[k] = final_metrics.get(k, 0) + v
        for dim, findings in metrics.get('dimension_findings', {}).items():
            findings_accumulator[dim] = findings_accumulator.get(dim, 0) + int(findings)
        for dim, score in metrics.get('dimension_scores', {}).items():
            score_accumulator[dim] = score_accumulator.get(dim, 0.0) + float(score)
        for check_id, conf in metrics.get('check_confidence', {}).items():
            check_confidence_accumulator[check_id] = check_confidence_accumulator.get(check_id, 0.0) + float(conf)
            check_confidence_counts[check_id] = check_confidence_counts.get(check_id, 0) + 1
        for dim, conf in metrics.get('dimension_confidence', {}).items():
            dimension_confidence_accumulator[dim] = dimension_confidence_accumulator.get(dim, 0.0) + float(conf)
        evidence_batches.append({
            'batch_index': batches,
            'check_evidence': metrics.get('check_evidence', []),
        })
        for metric_key, metric_score in metrics.get('advanced_metric_scores', {}).items():
            advanced_metric_accumulator[metric_key] = advanced_metric_accumulator.get(metric_key, 0.0) + float(metric_score)
        total_retry_attempts += int(metrics.get('retry_attempts', 0))
        total_quarantine_count += int(metrics.get('quarantine_count', 0))
        total_checkpoint_recoveries += int(metrics.get('checkpoint_recoveries', 0))
        checkpoint_batches.append({
            'batch_index': batches,
            'checkpoint_flow': metrics.get('checkpoint_flow', []),
        })
        quarantine_batches.append({
            'batch_index': batches,
            'quarantine_records': metrics.get('quarantine_records', []),
        })

    if batches > 0:
        final_metrics['dimension_findings'] = findings_accumulator
        final_metrics['dimension_scores'] = {dim: score_accumulator[dim] / batches for dim in score_accumulator}
        final_metrics['check_confidence'] = {
            check_id: check_confidence_accumulator[check_id] / max(1, check_confidence_counts.get(check_id, 1))
            for check_id in check_confidence_accumulator
        }
        final_metrics['dimension_confidence'] = {
            dim: dimension_confidence_accumulator.get(dim, 0.0) / batches
            for dim in dimension_confidence_accumulator
        }
        final_metrics['overall_confidence'] = (
            sum(final_metrics['dimension_confidence'].values()) / len(final_metrics['dimension_confidence'])
            if final_metrics['dimension_confidence'] else 0.0
        )
        final_metrics['check_evidence'] = evidence_batches
        final_metrics['advanced_metric_scores'] = {
            metric_key: advanced_metric_accumulator[metric_key] / batches
            for metric_key in advanced_metric_accumulator
        }
        final_metrics['retry_attempts'] = total_retry_attempts
        final_metrics['quarantine_count'] = total_quarantine_count
        final_metrics['checkpoint_recoveries'] = total_checkpoint_recoveries
        final_metrics['checkpoint_flow'] = checkpoint_batches
        final_metrics['quarantine_records'] = quarantine_batches
        final_metrics['resilience_policy'] = dict(DEFAULT_RESILIENCE_POLICY) if resilience_policy is None else {**DEFAULT_RESILIENCE_POLICY, **resilience_policy}
        final_metrics['sector'] = sector
        final_metrics['engine'] = engine

        sector_eval = evaluate_sector_targets(final_metrics, sector=sector)
        final_metrics['sector_target_evaluation'] = sector_eval
        final_metrics['sector_compliance_score'] = sector_eval['compliance_score']
        final_metrics['sector_pass_rate'] = sector_eval['pass_rate']

        composite_summary = _compute_composite_score(
            final_metrics.get('dimension_scores', {}),
            final_metrics.get('sector_compliance_score', 0.0),
        )
        final_metrics['dimension_average_score'] = composite_summary['dimension_average_score']
        final_metrics['composite_score'] = composite_summary['composite_score']
        final_metrics['composite_formula'] = composite_summary['composite_formula']
        final_metrics['rule_pack_version'] = 'v1.0.0'
        final_metrics['core_dimensions'] = CORE_DIMENSIONS

    return final_metrics