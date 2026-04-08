from datetime import datetime
from typing import Any, Dict, List

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


def _safe_event_time(value: str):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _record_semantics(record: Dict[str, Any]) -> str:
    return str(record.get('record_semantics', 'event')).lower()


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
    malformed_count = int(ingestion_metrics.get('malformed', 0)) + int(preprocess_metrics.get('malformed', 0))
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
            + malformed_count
            + int(preprocess_metrics.get('type_mismatches', 0))
            + int(transform_metrics.get('transformation_failures', 0))
        ),
        'completeness': int(ingestion_metrics.get('nulls', 0)),
        'consistency': int(storage_metrics.get('row_count_mismatch', 0)) + out_of_order_rows,
        'validity': malformed_count + invalid_time_rows + invalid_amount_rows,
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
    malformed_count = int(ingestion_metrics.get('malformed', 0)) + int(preprocess_metrics.get('malformed', 0))

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

    add_count_check('schema_validation', 'traceability_governance', int(ingestion_metrics.get('invalid_schema', 0)), 'Records rejected due to missing required fields.')
    add_count_check('null_check', 'completeness', int(ingestion_metrics.get('nulls', 0)), 'Records rejected due to required null values.')
    add_count_check('malformed_payload_check', 'validity', malformed_count, 'Records rejected due to malformed but schema-present payload values.')
    add_count_check('freshness_check', 'timeliness', int(ingestion_metrics.get('freshness_issues', 0)), 'Records older than freshness SLA window.')
    add_count_check('type_enforcement', 'reliability', int(preprocess_metrics.get('type_mismatches', 0)), 'Type conversion failures during preprocessing.')
    add_count_check('transformation_validation', 'accuracy', int(transform_metrics.get('transformation_failures', 0)), 'Transformation function failures.')
    add_count_check('duplicate_mapping_check', 'uniqueness', int(transform_metrics.get('mapping_issues', 0)), 'Duplicate mapping inconsistency indicators.')
    add_count_check('row_count_reconciliation', 'consistency', int(storage_metrics.get('row_count_mismatch', 0)), 'Source/target row-count mismatch at storage boundary.')
    add_count_check('checksum_integrity', 'integrity', int(storage_metrics.get('checksum_mismatch', 0)), 'Checksum verification mismatch for transformed records.')

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
    stage_metrics['malformed'] = int(ingestion_metrics.get('malformed', 0)) + int(preprocess_metrics.get('malformed', 0))
    stage_metrics['proposed_detected_issues'] = (
        ingestion_metrics.get('invalid_schema', 0)
        + ingestion_metrics.get('nulls', 0)
        + stage_metrics['malformed']
        + preprocess_metrics.get('type_mismatches', 0)
        + transform_metrics.get('transformation_failures', 0)
        + transform_metrics.get('mapping_issues', 0)
        + storage_metrics.get('row_count_mismatch', 0)
        + storage_metrics.get('checksum_mismatch', 0)
    )
    stage_metrics['checkpoint_flow'] = checkpoint_flow
    stage_metrics['quarantine_records'] = quarantine_records
    stage_metrics['quarantine_count'] = resilience_metrics['quarantined_records']
    stage_metrics['retry_attempts'] = resilience_metrics['retry_attempts']
    stage_metrics['recovery_attempts'] = resilience_metrics.get('recovery_attempts', 0)
    stage_metrics['successful_recoveries'] = resilience_metrics.get('successful_recoveries', 0)
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
