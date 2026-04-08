from typing import Dict, Any


ADVANCED_METRIC_KEYS = [
    'defect_detection_rate',
    'test_coverage_improvement',
    'data_quality_issue_reduction',
    'regression_testing_automation',
    'test_case_maintenance_effort',
    'etl_testing_efficiency',
    'transformation_rule_coverage',
    'deduplication_accuracy',
    'completeness_check_effectiveness',
    'accuracy_verification',
    'schema_governance_effectiveness',
    'event_time_ordering_accuracy',
    'distributed_integrity_verification',
    'fault_tolerance_checkpoint_recovery',
    'latency_optimization_factor',
]


BASE_TARGETS = {
    'defect_detection_rate': 0.84,
    'test_coverage_improvement': 0.90,
    'data_quality_issue_reduction': 0.95,
    'regression_testing_automation': 0.80,
    'test_case_maintenance_effort': 0.80,
    'etl_testing_efficiency': 0.70,
    'transformation_rule_coverage': 0.95,
    'deduplication_accuracy': 0.95,
    'completeness_check_effectiveness': 0.99,
    'accuracy_verification': 0.95,
    'schema_governance_effectiveness': 1.00,
    'event_time_ordering_accuracy': 0.999,
    'distributed_integrity_verification': 1.00,
    'fault_tolerance_checkpoint_recovery': 0.99,
    'latency_optimization_factor': 0.90,
}


SECTOR_PROFILES: Dict[str, Dict[str, Any]] = {
    'cross_industry': {
        'strictness': 1.00,
        'dimension_weights': {
            'accuracy': 0.14,
            'completeness': 0.11,
            'consistency': 0.11,
            'validity': 0.10,
            'uniqueness': 0.09,
            'timeliness': 0.12,
            'integrity': 0.12,
            'reliability': 0.11,
            'traceability_governance': 0.10,
        },
    },
    'finance': {
        'strictness': 1.02,
        'dimension_weights': {
            'accuracy': 0.16,
            'completeness': 0.10,
            'consistency': 0.12,
            'validity': 0.10,
            'uniqueness': 0.08,
            'timeliness': 0.10,
            'integrity': 0.15,
            'reliability': 0.10,
            'traceability_governance': 0.09,
        },
    },
    'healthcare': {
        'strictness': 1.02,
        'dimension_weights': {
            'accuracy': 0.15,
            'completeness': 0.12,
            'consistency': 0.11,
            'validity': 0.12,
            'uniqueness': 0.08,
            'timeliness': 0.09,
            'integrity': 0.14,
            'reliability': 0.10,
            'traceability_governance': 0.09,
        },
    },
    'telecommunications': {
        'strictness': 1.00,
        'dimension_weights': {
            'accuracy': 0.12,
            'completeness': 0.10,
            'consistency': 0.10,
            'validity': 0.09,
            'uniqueness': 0.09,
            'timeliness': 0.16,
            'integrity': 0.11,
            'reliability': 0.14,
            'traceability_governance': 0.09,
        },
    },
    'retail': {
        'strictness': 0.98,
        'dimension_weights': {
            'accuracy': 0.13,
            'completeness': 0.11,
            'consistency': 0.12,
            'validity': 0.10,
            'uniqueness': 0.11,
            'timeliness': 0.13,
            'integrity': 0.09,
            'reliability': 0.11,
            'traceability_governance': 0.10,
        },
    },
    'e_commerce': {
        'strictness': 0.97,
        'dimension_weights': {
            'accuracy': 0.12,
            'completeness': 0.10,
            'consistency': 0.11,
            'validity': 0.10,
            'uniqueness': 0.12,
            'timeliness': 0.15,
            'integrity': 0.09,
            'reliability': 0.11,
            'traceability_governance': 0.10,
        },
    },
    'manufacturing': {
        'strictness': 0.98,
        'dimension_weights': {
            'accuracy': 0.13,
            'completeness': 0.11,
            'consistency': 0.12,
            'validity': 0.11,
            'uniqueness': 0.08,
            'timeliness': 0.12,
            'integrity': 0.12,
            'reliability': 0.13,
            'traceability_governance': 0.08,
        },
    },
    'logistics': {
        'strictness': 0.99,
        'dimension_weights': {
            'accuracy': 0.12,
            'completeness': 0.10,
            'consistency': 0.12,
            'validity': 0.10,
            'uniqueness': 0.08,
            'timeliness': 0.16,
            'integrity': 0.12,
            'reliability': 0.12,
            'traceability_governance': 0.08,
        },
    },
    'public_sector': {
        'strictness': 1.01,
        'dimension_weights': {
            'accuracy': 0.14,
            'completeness': 0.12,
            'consistency': 0.11,
            'validity': 0.11,
            'uniqueness': 0.09,
            'timeliness': 0.10,
            'integrity': 0.12,
            'reliability': 0.10,
            'traceability_governance': 0.11,
        },
    },
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator <= 0:
        return default
    return numerator / denominator


def estimate_advanced_metric_scores(stage_metrics: Dict[str, Any]) -> Dict[str, float]:
    source_count = float(max(1, int(stage_metrics.get('source_count', 0))))

    invalid_schema = float(stage_metrics.get('invalid_schema', 0))
    nulls = float(stage_metrics.get('nulls', 0))
    malformed = float(stage_metrics.get('malformed', 0))
    type_mismatches = float(stage_metrics.get('type_mismatches', 0))
    transform_failures = float(stage_metrics.get('transformation_failures', 0))
    row_count_mismatch = float(stage_metrics.get('row_count_mismatch', 0))
    checksum_mismatch = float(stage_metrics.get('checksum_mismatch', 0))
    freshness_issues = float(stage_metrics.get('freshness_issues', 0))
    mapping_issues = float(stage_metrics.get('mapping_issues', 0))

    detected_issues = float(stage_metrics.get(
        'proposed_detected_issues',
        invalid_schema + nulls + malformed + type_mismatches + transform_failures + row_count_mismatch + checksum_mismatch,
    ))

    out_of_order = _clamp01(float(stage_metrics.get('out_of_order', 0.0)))
    reconciled = 1.0 if bool(stage_metrics.get('downstream_reconciliation', False)) else 0.0
    overall_confidence = _clamp01(float(stage_metrics.get('overall_confidence', 0.0)))

    dimension_scores = stage_metrics.get('dimension_scores', {}) if isinstance(stage_metrics.get('dimension_scores', {}), dict) else {}

    accuracy_score = _clamp01(float(dimension_scores.get('accuracy', 1.0 - _safe_ratio(detected_issues, source_count, 0.0))))
    completeness_score = _clamp01(float(dimension_scores.get('completeness', 1.0 - _safe_ratio(nulls, source_count, 0.0))))
    consistency_score = _clamp01(float(dimension_scores.get('consistency', 1.0 - _safe_ratio(row_count_mismatch + out_of_order * source_count, source_count, 0.0))))
    validity_score = _clamp01(float(dimension_scores.get('validity', 1.0 - _safe_ratio(malformed + type_mismatches + transform_failures, source_count, 0.0))))
    uniqueness_score = _clamp01(float(dimension_scores.get('uniqueness', 1.0 - _safe_ratio(mapping_issues, source_count, 0.0))))
    timeliness_score = _clamp01(float(dimension_scores.get('timeliness', 1.0 - _safe_ratio(freshness_issues + out_of_order * source_count, source_count, 0.0))))
    integrity_score = _clamp01(float(dimension_scores.get('integrity', 1.0 - _safe_ratio(checksum_mismatch, source_count, 0.0))))
    reliability_score = _clamp01(float(dimension_scores.get('reliability', 1.0 - _safe_ratio(type_mismatches + transform_failures, source_count, 0.0))))
    governance_score = _clamp01(float(dimension_scores.get('traceability_governance', 1.0 - _safe_ratio(invalid_schema, source_count, 0.0))))

    scores = {
        'defect_detection_rate': accuracy_score,
        'test_coverage_improvement': _clamp01((accuracy_score + consistency_score + governance_score) / 3.0),
        'data_quality_issue_reduction': _clamp01(1.0 - _safe_ratio(detected_issues, source_count, 0.0)),
        'regression_testing_automation': _clamp01((overall_confidence + reliability_score) / 2.0),
        'test_case_maintenance_effort': governance_score,
        'etl_testing_efficiency': reliability_score,
        'transformation_rule_coverage': _clamp01((accuracy_score + consistency_score + validity_score) / 3.0),
        'deduplication_accuracy': uniqueness_score,
        'completeness_check_effectiveness': completeness_score,
        'accuracy_verification': accuracy_score,
        'schema_governance_effectiveness': governance_score,
        'event_time_ordering_accuracy': _clamp01(1.0 - out_of_order),
        'distributed_integrity_verification': _clamp01((integrity_score + reconciled) / 2.0),
        'fault_tolerance_checkpoint_recovery': reliability_score,
        'latency_optimization_factor': timeliness_score,
    }

    return {k: _clamp01(scores.get(k, 0.0)) for k in ADVANCED_METRIC_KEYS}


def evaluate_sector_targets(stage_metrics: Dict[str, Any], sector: str = 'cross_industry') -> Dict[str, Any]:
    profile = SECTOR_PROFILES.get(sector, SECTOR_PROFILES['cross_industry'])
    strictness = float(profile.get('strictness', 1.0))
    dimension_weights = profile.get('dimension_weights', {})

    advanced_scores = estimate_advanced_metric_scores(stage_metrics)

    metric_results: Dict[str, Dict[str, Any]] = {}
    passed = 0
    attainment_sum = 0.0

    for metric_key in ADVANCED_METRIC_KEYS:
        actual = _clamp01(advanced_scores.get(metric_key, 0.0))
        target = _clamp01(BASE_TARGETS.get(metric_key, 0.0) * strictness)
        is_pass = actual >= target
        gap = actual - target
        attainment = _clamp01(_safe_ratio(actual, target, default=1.0 if target == 0 else 0.0))

        metric_results[metric_key] = {
            'actual': actual,
            'target': target,
            'passed': is_pass,
            'gap': gap,
            'attainment': attainment,
        }
        if is_pass:
            passed += 1
        attainment_sum += attainment

    pass_rate = _safe_ratio(float(passed), float(len(ADVANCED_METRIC_KEYS)), 0.0)
    target_attainment = _safe_ratio(attainment_sum, float(len(ADVANCED_METRIC_KEYS)), 0.0)

    dim_scores = stage_metrics.get('dimension_scores', {}) if isinstance(stage_metrics.get('dimension_scores', {}), dict) else {}
    weighted_dim_sum = 0.0
    weighted_dim_total = 0.0
    for dim, weight in dimension_weights.items():
        weighted_dim_sum += _clamp01(float(dim_scores.get(dim, 0.0))) * float(weight)
        weighted_dim_total += float(weight)
    dimension_alignment = _safe_ratio(weighted_dim_sum, weighted_dim_total, 0.0)

    compliance_score = _clamp01((target_attainment * 0.7) + (dimension_alignment * 0.3))

    return {
        'sector': sector,
        'strictness': strictness,
        'advanced_metric_scores': advanced_scores,
        'metric_results': metric_results,
        'pass_rate': pass_rate,
        'target_attainment': target_attainment,
        'dimension_alignment': dimension_alignment,
        'compliance_score': compliance_score,
        'passed_metrics': passed,
        'total_metrics': len(ADVANCED_METRIC_KEYS),
    }
