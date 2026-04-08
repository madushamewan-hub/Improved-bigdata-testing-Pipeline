from collections import Counter

from backend.database import Dataset, ExperimentRun, PipelineResult, StageCheckResult
from data_generator.order_events import (
    inject_corruption,
    inject_duplicates,
    inject_missing,
    inject_out_of_order,
    inject_schema_drift,
)
from pipelines.proposed.validation import REQUIRED_FIELDS


SCENARIO_DETECTION_LABELS = {
    'real_world': 'real-world validation',
    'clean': 'no issue injected',
    'duplicated': 'duplication detected',
    'dropped': 'dropped data detected',
    'corrupted': 'corruption detected',
    'schema_drift': 'schema drift detected',
    'out_of_order': 'ordering issue detected',
    'mixed': 'multiple issues detected',
}

TRANSFORMATION_RULE_CHECKS = {
    'type_enforcement',
    'transformation_validation',
    'duplicate_mapping_check',
}


def _percentage(numerator: float, denominator: float, default: float = 100.0) -> float:
    if denominator <= 0:
        return round(default if numerator <= 0 else 0.0, 2)
    return round((float(numerator) / float(denominator)) * 100.0, 2)


def _count_incomplete_records(records) -> int:
    return int(
        sum(
            1
            for row in records
            if isinstance(row, dict) and any(row.get(field) is None for field in REQUIRED_FIELDS)
        )
    )


def _count_duplicate_cases(source_records, scenario_records) -> int:
    source_ids = Counter(str(r.get('event_id')) for r in source_records)
    scenario_ids = Counter(str(r.get('event_id')) for r in scenario_records)
    return int(sum(max(0, scenario_ids[key] - source_ids.get(key, 0)) for key in scenario_ids))


def _count_validated_transformation_rules(metrics: dict | None) -> int:
    if not isinstance(metrics, dict):
        return 0
    check_evidence = metrics.get('check_evidence', [])
    present = {str(check.get('check_id')) for check in check_evidence if isinstance(check, dict)}
    return int(len(TRANSFORMATION_RULE_CHECKS & present))


def _build_evaluation_context(
    source_records,
    scenario_records,
    scenario_name: str,
    metrics: dict | None = None,
    baseline_latency_ms: float | None = None,
    pipeline_type: str = 'proposed',
) -> dict:
    metrics = metrics or {}
    actual_integrity_issues = _compute_scenario_amended_count(source_records, scenario_records, scenario_name)
    total_incomplete_records = _count_incomplete_records(scenario_records)
    total_duplicate_evaluation_cases = _count_duplicate_cases(source_records, scenario_records)
    detected_nulls = int(metrics.get('nulls', metrics.get('detected_loss', 0)))
    detected_duplicates = int(metrics.get('mapping_issues', metrics.get('detected_duplicates', 0)))
    recovery_attempts = int(metrics.get('recovery_attempts', metrics.get('retry_attempts', 0)))
    successful_recoveries = int(metrics.get('successful_recoveries', metrics.get('checkpoint_recoveries', 0)))
    total_transformation_rules = len(TRANSFORMATION_RULE_CHECKS)
    validated_transformation_rules = (
        _count_validated_transformation_rules(metrics)
        if pipeline_type == 'proposed' else 0
    )

    return {
        'actual_integrity_issues': actual_integrity_issues,
        'valid_cases': max(0, len(scenario_records) - actual_integrity_issues),
        'total_incomplete_records': total_incomplete_records,
        'correctly_detected_incomplete_records': min(total_incomplete_records, max(0, detected_nulls)),
        'total_duplicate_evaluation_cases': total_duplicate_evaluation_cases,
        'correct_duplicate_decisions': min(total_duplicate_evaluation_cases, max(0, detected_duplicates)),
        'total_transformation_rules': total_transformation_rules,
        'validated_transformation_rules': min(total_transformation_rules, max(0, validated_transformation_rules)),
        'recovery_attempts': max(0, recovery_attempts),
        'successful_recoveries': min(max(0, recovery_attempts), max(0, successful_recoveries)) if recovery_attempts > 0 else 0,
        'baseline_latency_ms': float(baseline_latency_ms or 0.0),
    }


def _compute_exact_evaluation_metrics(
    prop_metrics: dict,
    row_count: int,
    latency_ms: float,
    evaluation_context: dict | None = None,
) -> dict:
    context = dict(evaluation_context or {})
    detected_issues = max(0, int(prop_metrics.get('proposed_detected_issues', 0)))
    false_positives = max(0, int(prop_metrics.get('false_positives', 0)))
    actual_integrity_issues = max(
        0,
        int(context.get('actual_integrity_issues', max(detected_issues + int(prop_metrics.get('false_negatives', 0)), int(prop_metrics.get('scenario_amended_count', 0))))),
    )
    detected_integrity_issues = min(actual_integrity_issues, detected_issues) if actual_integrity_issues > 0 else 0
    missed_integrity_issues = max(
        0,
        int(context.get('missed_integrity_issues', max(0, actual_integrity_issues - detected_integrity_issues))),
    )
    valid_cases = max(0, int(context.get('valid_cases', max(0, row_count - actual_integrity_issues))))

    total_incomplete_records = max(0, int(context.get('total_incomplete_records', prop_metrics.get('nulls', 0))))
    correctly_detected_incomplete_records = max(
        0,
        min(total_incomplete_records, int(context.get('correctly_detected_incomplete_records', prop_metrics.get('nulls', 0)))),
    )

    detected_duplicates = max(0, int(prop_metrics.get('mapping_issues', prop_metrics.get('detected_duplicates', 0))))
    total_duplicate_evaluation_cases = max(
        0,
        int(context.get('total_duplicate_evaluation_cases', detected_duplicates)),
    )
    correct_duplicate_decisions = max(
        0,
        min(total_duplicate_evaluation_cases, int(context.get('correct_duplicate_decisions', detected_duplicates))),
    )

    total_transformation_rules = max(1, int(context.get('total_transformation_rules', len(TRANSFORMATION_RULE_CHECKS))))
    validated_transformation_rules = max(
        0,
        min(total_transformation_rules, int(context.get('validated_transformation_rules', _count_validated_transformation_rules(prop_metrics)))),
    )

    recovery_attempts = max(0, int(context.get('recovery_attempts', prop_metrics.get('recovery_attempts', 0))))
    successful_recoveries = max(
        0,
        min(recovery_attempts, int(context.get('successful_recoveries', prop_metrics.get('successful_recoveries', 0)))) if recovery_attempts > 0 else 0,
    )
    baseline_latency_ms = float(context.get('baseline_latency_ms', 0.0) or 0.0)
    latency_overhead_percent = round(((float(latency_ms) - baseline_latency_ms) / baseline_latency_ms) * 100.0, 2) if baseline_latency_ms > 0 else 0.0

    return {
        'defect_detection_rate': _percentage(detected_integrity_issues, actual_integrity_issues, default=100.0),
        'false_positive_rate': _percentage(false_positives, valid_cases, default=0.0),
        'false_negative_rate': _percentage(missed_integrity_issues, actual_integrity_issues, default=0.0),
        'transformation_rule_coverage': _percentage(validated_transformation_rules, total_transformation_rules, default=100.0),
        'completeness_check_effectiveness': _percentage(correctly_detected_incomplete_records, total_incomplete_records, default=100.0),
        'deduplication_accuracy': _percentage(correct_duplicate_decisions, total_duplicate_evaluation_cases, default=100.0),
        'recovery_success_rate': _percentage(successful_recoveries, recovery_attempts, default=100.0),
        'latency_overhead_percent': latency_overhead_percent,
        'actual_integrity_issues': actual_integrity_issues,
        'detected_integrity_issues': detected_integrity_issues,
        'valid_cases': valid_cases,
        'missed_integrity_issues': missed_integrity_issues,
        'total_incomplete_records': total_incomplete_records,
        'correctly_detected_incomplete_records': correctly_detected_incomplete_records,
        'total_duplicate_evaluation_cases': total_duplicate_evaluation_cases,
        'correct_duplicate_decisions': correct_duplicate_decisions,
        'total_transformation_rules': total_transformation_rules,
        'validated_transformation_rules': validated_transformation_rules,
        'recovery_attempts': recovery_attempts,
        'successful_recoveries': successful_recoveries,
    }


def _scenario_detection_label(scenario_name: str) -> str:
    return SCENARIO_DETECTION_LABELS.get(scenario_name, f'{scenario_name.replace("_", " ")} detected')


def _apply_scenario(records, scenario_name: str):
    scenario_map = {
        'real_world': lambda rows: rows,
        'clean': lambda rows: rows,
        'duplicated': lambda rows: inject_duplicates(rows, 0.2),
        'dropped': lambda rows: inject_missing(rows, 0.2),
        'corrupted': lambda rows: inject_corruption(rows, 0.2),
        'schema_drift': lambda rows: inject_schema_drift(rows, 0.2),
        'out_of_order': lambda rows: inject_out_of_order(rows, 0.2),
        'mixed': lambda rows: inject_out_of_order(inject_corruption(inject_duplicates(inject_missing(rows, 0.1), 0.1), 0.1), 0.1),
    }
    return scenario_map.get(scenario_name, lambda rows: rows)(records)


def _compute_scenario_amended_count(source_records, scenario_records, scenario_name: str) -> int:
    if scenario_name in {'real_world', 'clean'}:
        return 0

    source_ids = Counter(str(r.get('event_id')) for r in source_records)
    scenario_ids = Counter(str(r.get('event_id')) for r in scenario_records)

    if scenario_name == 'duplicated':
        return int(sum(max(0, scenario_ids[key] - source_ids.get(key, 0)) for key in scenario_ids))
    if scenario_name == 'out_of_order':
        limit = min(len(source_records), len(scenario_records))
        return int(sum(1 for idx in range(limit) if source_records[idx].get('event_id') != scenario_records[idx].get('event_id')))

    tracked_fields = ['event_time', 'customer_id', 'source_system', 'amount', 'status', 'version', 'checksum']
    source_by_id = {str(r.get('event_id')): r for r in source_records}
    changed = 0
    for row in scenario_records:
        event_id = str(row.get('event_id'))
        original = source_by_id.get(event_id)
        if original is None:
            changed += 1
            continue
        if any(original.get(field) != row.get(field) for field in tracked_fields):
            changed += 1

    if scenario_name == 'dropped':
        removed = int(sum(max(0, source_ids[key] - scenario_ids.get(key, 0)) for key in source_ids))
        return max(changed + removed, changed, removed)

    if scenario_name == 'mixed':
        added = int(sum(max(0, scenario_ids[key] - source_ids.get(key, 0)) for key in scenario_ids))
        removed = int(sum(max(0, source_ids[key] - scenario_ids.get(key, 0)) for key in source_ids))
        return max(changed + added + removed, changed)

    return changed


def _derive_proposed_result_metrics(prop_metrics: dict, row_count: int, latency_ms: float, evaluation_context: dict | None = None):
    detected_issues = float(prop_metrics.get('proposed_detected_issues', 0))
    stored_rows = int(prop_metrics.get('stored_rows', row_count))
    false_positives = max(0, int(prop_metrics.get('false_positives', 0)))
    dimension_findings = prop_metrics.get('dimension_findings', {}) or {}
    evaluation_metrics = _compute_exact_evaluation_metrics(prop_metrics, row_count, latency_ms, evaluation_context=evaluation_context)
    false_negatives = max(0, int(evaluation_metrics.get('missed_integrity_issues', max(0, row_count - stored_rows))))

    detected_duplicates = max(0, int(prop_metrics.get('mapping_issues', dimension_findings.get('uniqueness', 0))))
    detected_loss = max(
        0,
        int(prop_metrics.get('nulls', 0)),
        int(dimension_findings.get('completeness', 0)),
        false_negatives,
    )
    detected_corruption = max(
        0,
        int(prop_metrics.get('malformed', 0)),
        int(prop_metrics.get('checksum_mismatch', 0)),
        int(prop_metrics.get('transformation_failures', 0)),
        int(dimension_findings.get('validity', 0)),
    )
    detected_inconsistency = max(
        0,
        int(prop_metrics.get('row_count_mismatch', 0) + prop_metrics.get('invalid_schema', 0) + prop_metrics.get('type_mismatches', 0)),
    )

    true_detected_issues = float(evaluation_metrics.get('detected_integrity_issues', detected_issues))
    precision = true_detected_issues / max(1.0, true_detected_issues + false_positives)
    recall = max(0.0, min(1.0, evaluation_metrics.get('defect_detection_rate', 0.0) / 100.0))
    detection_accuracy = recall if evaluation_metrics.get('actual_integrity_issues', 0) >= 0 else (float(prop_metrics.get('dimension_average_score', 0.0)) or (detected_issues / max(1.0, float(row_count))))

    summary_json = {
        **prop_metrics,
        **evaluation_metrics,
        'evaluation_metrics': evaluation_metrics,
    }

    return {
        'detection_accuracy': detection_accuracy,
        'precision': precision,
        'recall': recall,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'detected_loss': detected_loss,
        'detected_duplicates': detected_duplicates,
        'detected_corruption': detected_corruption,
        'detected_inconsistency': detected_inconsistency,
        'latency_ms': latency_ms,
        'summary_json': summary_json,
        'evaluation_metrics': evaluation_metrics,
    }


def _build_pipeline_export_rows(
    exp: ExperimentRun,
    dataset: Dataset,
    pipeline_type: str,
    pipeline_result: PipelineResult | None,
    stage_checks: list[StageCheckResult],
):
    detection_label = _scenario_detection_label(exp.scenario_name)
    summary = pipeline_result.summary_json if (pipeline_result and isinstance(pipeline_result.summary_json, dict)) else {}
    engine_name = summary.get('engine', 'python' if pipeline_type == 'proposed' else 'baseline')

    base_row = {
        'experiment_id': exp.id,
        'dataset_id': dataset.id if dataset else None,
        'dataset_name': dataset.name if dataset else 'unknown',
        'dataset_type': dataset.type if dataset else 'unknown',
        'scenario': exp.scenario_name,
        'detection': detection_label,
        'source_record_count': int(summary.get('source_record_count', 0)),
        'scenario_record_count': int(summary.get('scenario_record_count', 0)),
        'actual_amended_count': int(summary.get('scenario_amended_count', 0)),
        'pipeline_type': pipeline_type,
        'engine': engine_name,
        'accuracy': pipeline_result.detection_accuracy if pipeline_result else 0,
        'precision': pipeline_result.precision if pipeline_result else 0,
        'recall': pipeline_result.recall if pipeline_result else 0,
        'false_positives': pipeline_result.false_positives if pipeline_result else 0,
        'false_negatives': pipeline_result.false_negatives if pipeline_result else 0,
        'detected_loss': pipeline_result.detected_loss if pipeline_result else 0,
        'detected_duplicates': pipeline_result.detected_duplicates if pipeline_result else 0,
        'detected_corruption': pipeline_result.detected_corruption if pipeline_result else 0,
        'detected_inconsistency': pipeline_result.detected_inconsistency if pipeline_result else 0,
        'latency_ms': pipeline_result.latency_ms if pipeline_result else 0,
        'defect_detection_rate': float(summary.get('defect_detection_rate', 0)),
        'false_positive_rate': float(summary.get('false_positive_rate', 0)),
        'false_negative_rate': float(summary.get('false_negative_rate', 0)),
        'transformation_rule_coverage': float(summary.get('transformation_rule_coverage', 0)),
        'completeness_check_effectiveness': float(summary.get('completeness_check_effectiveness', 0)),
        'deduplication_accuracy': float(summary.get('deduplication_accuracy', 0)),
        'recovery_success_rate': float(summary.get('recovery_success_rate', 0)),
        'latency_overhead_percent': float(summary.get('latency_overhead_percent', 0)),
        'record_type': 'summary',
        'stage': 'overall_summary',
        'check_name': 'pipeline_summary',
        'issue_type': detection_label,
        'passed': True if pipeline_result else False,
        'findings': int(
            (pipeline_result.detected_loss if pipeline_result else 0)
            + (pipeline_result.detected_duplicates if pipeline_result else 0)
            + (pipeline_result.detected_corruption if pipeline_result else 0)
            + (pipeline_result.detected_inconsistency if pipeline_result else 0)
        ),
        'notes': summary.get('composite_formula', '') if pipeline_type == 'proposed' else '',
    }

    rows = [base_row]
    for check in stage_checks:
        rows.append({
            **base_row,
            'record_type': 'stage_check',
            'stage': check.stage_name,
            'check_name': check.check_name,
            'issue_type': check.issue_type,
            'passed': check.passed,
            'findings': check.findings_count,
            'notes': check.notes or '',
        })
    return rows


def get_pipeline_flow_definitions():
    baseline_nodes = [
        {'id': 'b1', 'label': 'Ingestion', 'stage': 'Ingestion', 'checks': ['basic_schema_read'], 'issue_types': [], 'x': 0, 'y': 0},
        {'id': 'b2', 'label': 'Preprocessing', 'stage': 'Preprocessing', 'checks': ['optional_type_conversion'], 'issue_types': [], 'x': 300, 'y': 0},
        {'id': 'b3', 'label': 'Transformation', 'stage': 'Transformation', 'checks': ['basic_math'], 'issue_types': [], 'x': 600, 'y': 0},
        {'id': 'b4', 'label': 'Storage', 'stage': 'Storage', 'checks': ['file_write'], 'issue_types': [], 'x': 900, 'y': 0},
        {'id': 'b5', 'label': 'Output', 'stage': 'Output', 'checks': ['manual_review'], 'issue_types': [], 'x': 1200, 'y': 0},
    ]

    baseline_edges = [
        {'source': 'b1', 'target': 'b2'}, {'source': 'b2', 'target': 'b3'},
        {'source': 'b3', 'target': 'b4'}, {'source': 'b4', 'target': 'b5'},
    ]

    proposed_nodes = [
        {'id': 'p1', 'label': 'Ingestion', 'stage': 'Ingestion', 'checks': ['schema_validation', 'null_check'], 'issue_types': ['schema_drift', 'null_values'], 'x': 0, 'y': 300},
        {'id': 'p2', 'label': 'Preprocessing', 'stage': 'Preprocessing', 'checks': ['duplicate_detection', 'checksum_validate'], 'issue_types': ['duplication', 'schema_drift'], 'x': 300, 'y': 300},
        {'id': 'p3', 'label': 'Transformation', 'stage': 'Transformation', 'checks': ['assertion_check', 'type_validation'], 'issue_types': ['incorrect_transformation'], 'x': 600, 'y': 300},
        {'id': 'p4', 'label': 'Storage', 'stage': 'Storage', 'checks': ['row_count_check', 'checksum_reconcile'], 'issue_types': ['data_loss', 'inconsistency'], 'x': 900, 'y': 300},
        {'id': 'p5', 'label': 'Output', 'stage': 'Output', 'checks': ['downstream_validation', 'consistency_check'], 'issue_types': ['inconsistency', 'corruption'], 'x': 1200, 'y': 300},
    ]

    proposed_edges = [
        {'source': 'p1', 'target': 'p2'}, {'source': 'p2', 'target': 'p3'},
        {'source': 'p3', 'target': 'p4'}, {'source': 'p4', 'target': 'p5'},
    ]

    return {
        'baseline': {'nodes': baseline_nodes, 'edges': baseline_edges},
        'proposed': {'nodes': proposed_nodes, 'edges': proposed_edges},
    }


def build_experiment_response(exp: ExperimentRun, dataset: Dataset | None, baseline: PipelineResult | None, proposed: PipelineResult | None):
    proposed_summary = proposed.summary_json if (proposed and isinstance(proposed.summary_json, dict)) else {}
    baseline_summary = baseline.summary_json if (baseline and isinstance(baseline.summary_json, dict)) else {}

    return {
        'id': exp.id,
        'dataset_id': exp.dataset_id,
        'dataset_name': dataset.name if dataset else None,
        'scenario': exp.scenario_name,
        'detection_label': _scenario_detection_label(exp.scenario_name),
        'actual_amended_count': proposed_summary.get('scenario_amended_count', baseline_summary.get('scenario_amended_count', 0)),
        'mode': exp.mode,
        'engine': proposed_summary.get('engine', 'python'),
        'status': exp.status,
        'baseline': {
            'accuracy': baseline.detection_accuracy if baseline else 0,
            'precision': baseline.precision if baseline else 0,
            'recall': baseline.recall if baseline else 0,
            'false_positives': baseline.false_positives if baseline else 0,
            'false_negatives': baseline.false_negatives if baseline else 0,
            'latency': baseline.latency_ms if baseline else 0,
            'detected_duplicates': baseline.detected_duplicates if baseline else 0,
            'detected_loss': baseline.detected_loss if baseline else 0,
            'detected_corruption': baseline.detected_corruption if baseline else 0,
            'detected_inconsistency': baseline.detected_inconsistency if baseline else 0,
            'defect_detection_rate': baseline_summary.get('defect_detection_rate', 0),
            'false_positive_rate': baseline_summary.get('false_positive_rate', 0),
            'false_negative_rate': baseline_summary.get('false_negative_rate', 0),
            'transformation_rule_coverage': baseline_summary.get('transformation_rule_coverage', 0),
            'completeness_check_effectiveness': baseline_summary.get('completeness_check_effectiveness', 0),
            'deduplication_accuracy': baseline_summary.get('deduplication_accuracy', 0),
            'recovery_success_rate': baseline_summary.get('recovery_success_rate', 0),
            'latency_overhead_percent': baseline_summary.get('latency_overhead_percent', 0),
        } if baseline else None,
        'proposed': {
            'accuracy': proposed.detection_accuracy if proposed else 0,
            'precision': proposed.precision if proposed else 0,
            'recall': proposed.recall if proposed else 0,
            'false_positives': proposed.false_positives if proposed else 0,
            'false_negatives': proposed.false_negatives if proposed else 0,
            'latency': proposed.latency_ms if proposed else 0,
            'overhead': proposed.overhead_ms if proposed else 0,
            'detected_duplicates': proposed.detected_duplicates if proposed else 0,
            'detected_loss': proposed.detected_loss if proposed else 0,
            'detected_corruption': proposed.detected_corruption if proposed else 0,
            'detected_inconsistency': proposed.detected_inconsistency if proposed else 0,
            'defect_detection_rate': proposed_summary.get('defect_detection_rate', 0),
            'false_positive_rate': proposed_summary.get('false_positive_rate', 0),
            'false_negative_rate': proposed_summary.get('false_negative_rate', 0),
            'transformation_rule_coverage': proposed_summary.get('transformation_rule_coverage', 0),
            'completeness_check_effectiveness': proposed_summary.get('completeness_check_effectiveness', 0),
            'deduplication_accuracy': proposed_summary.get('deduplication_accuracy', 0),
            'recovery_success_rate': proposed_summary.get('recovery_success_rate', 0),
            'latency_overhead_percent': proposed_summary.get('latency_overhead_percent', 0),
            'dimension_average_score': proposed_summary.get('dimension_average_score', 0),
            'sector': proposed_summary.get('sector', 'cross_industry'),
            'sector_compliance_score': proposed_summary.get('sector_compliance_score', 0),
            'sector_pass_rate': proposed_summary.get('sector_pass_rate', 0),
            'composite_score': proposed_summary.get('composite_score', 0),
            'composite_formula': proposed_summary.get('composite_formula', ''),
            'engine': proposed_summary.get('engine', 'python'),
            'retry_attempts': proposed_summary.get('retry_attempts', 0),
            'recovery_attempts': proposed_summary.get('recovery_attempts', 0),
            'successful_recoveries': proposed_summary.get('successful_recoveries', 0),
            'quarantine_count': proposed_summary.get('quarantine_count', 0),
            'checkpoint_recoveries': proposed_summary.get('checkpoint_recoveries', 0),
        } if proposed else None,
    }


def build_experiment_list_item(exp: ExperimentRun, dataset: Dataset | None, baseline: PipelineResult | None, proposed: PipelineResult | None):
    proposed_summary = proposed.summary_json if (proposed and isinstance(proposed.summary_json, dict)) else {}
    baseline_summary = baseline.summary_json if (baseline and isinstance(baseline.summary_json, dict)) else {}

    return {
        'id': exp.id,
        'dataset_id': exp.dataset_id,
        'dataset_name': dataset.name if dataset else None,
        'scenario': exp.scenario_name,
        'detection_label': _scenario_detection_label(exp.scenario_name),
        'scenario_amended_count': proposed_summary.get('scenario_amended_count', baseline_summary.get('scenario_amended_count', 0)),
        'baseline_accuracy': baseline.detection_accuracy if baseline else 0,
        'proposed_accuracy': proposed.detection_accuracy if proposed else 0,
        'proposed_composite_score': proposed_summary.get('composite_score', 0),
        'proposed_sector_compliance': proposed_summary.get('sector_compliance_score', 0),
        'engine': proposed_summary.get('engine', 'python') if proposed else 'python',
        'timestamp': exp.started_at,
    }
