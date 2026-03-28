"""
Pipeline simulation engine - generates realistic experiment results
This simulates baseline and proposed pipeline execution.
Can be replaced with real pipeline execution later.
"""
import random
import time
from typing import Dict, List, Any, Tuple

BASELINE_STAGE_CHECKS = {
    "Ingestion": ["basic_schema_read"],
    "Preprocessing": ["optional_type_conversion"],
    "Transformation": ["basic_math"],
    "Storage": ["file_write"],
    "Output": ["manual_review"]
}

PROPOSED_STAGE_CHECKS = {
    "Ingestion": ["schema_validation", "null_check"],
    "Preprocessing": ["duplicate_detection", "checksum_validate"],
    "Transformation": ["assertion_check", "type_validation"],
    "Storage": ["row_count_check", "checksum_reconcile"],
    "Output": ["downstream_validation", "consistency_check"]
}

def simulate_baseline_execution(row_count: int, scenario: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], float]:
    """
    Simulate baseline pipeline execution.
    Returns: (metrics, stage_results, latency_ms)
    """
    if scenario == "clean":
        # Nothing injected, nothing flagged — precision is 1.0 by convention (no false alarms)
        detected_issues = 0
        false_positives = 0
    elif scenario == "duplicated":
        detected_issues = max(0, int(row_count * 0.05))  # detects 5% of injected dupes
        false_positives = 2
    elif scenario == "dropped":
        # Baseline partially spots drops but also raises false alarms on valid rows
        detected_issues = max(0, int(row_count * 0.02))
        false_positives = max(1, int(row_count * 0.02))  # ~equal noise → precision ~0.5
    elif scenario == "corrupted":
        detected_issues = max(0, int(row_count * 0.03))
        false_positives = 3
    elif scenario == "schema_drift":
        detected_issues = max(0, int(row_count * 0.04))
        false_positives = random.randint(2, 5)
    elif scenario == "out_of_order":
        detected_issues = max(0, int(row_count * 0.03))
        false_positives = random.randint(1, 4)
    else:  # mixed, real_world, etc.
        detected_issues = max(0, int(row_count * 0.06))
        false_positives = random.randint(2, 6)
    
    total_injected = int(row_count * 0.2) if scenario not in ["clean", "real_world"] else 0
    stored_rows = row_count - max(0, total_injected * 0.5)
    false_negatives = max(0, total_injected - detected_issues)
    
    # When nothing is flagged at all (detected=0 and FP=0), precision is 1.0 by convention
    total_flagged = detected_issues + false_positives
    precision = (detected_issues / total_flagged) if total_flagged > 0 else 1.0
    
    metrics = {
        "detection_accuracy": detected_issues / max(1, total_injected) if total_injected > 0 else 1.0,
        "precision": precision,
        "recall": detected_issues / max(1, detected_issues + false_negatives) if (detected_issues + false_negatives) > 0 else 1.0,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "detected_loss": max(0, int(false_negatives * 0.3)) if scenario == "dropped" else 0,
        "detected_duplicates": max(0, int(detected_issues * 0.4)) if scenario == "duplicated" else 0,
        "detected_corruption": max(0, int(detected_issues * 0.3)) if scenario == "corrupted" else 0,
        "detected_inconsistency": max(0, int(detected_issues * 0.3)),
        "record_count": int(stored_rows),
        "source_count": row_count
    }
    
    stage_results = [
        {
            "stage": "Ingestion",
            "checks": BASELINE_STAGE_CHECKS["Ingestion"],
            "issue_types": [],
            "passed": True,
            "findings": 0
        },
        {
            "stage": "Preprocessing",
            "checks": BASELINE_STAGE_CHECKS["Preprocessing"],
            "issue_types": [],
            "passed": True,
            "findings": 0
        },
        {
            "stage": "Transformation",
            "checks": BASELINE_STAGE_CHECKS["Transformation"],
            "issue_types": [],
            "passed": True,
            "findings": 0 if scenario == "clean" else random.randint(1, 3)
        },
        {
            "stage": "Storage",
            "checks": BASELINE_STAGE_CHECKS["Storage"],
            "issue_types": [],
            "passed": True,
            "findings": 0
        },
        {
            "stage": "Output",
            "checks": BASELINE_STAGE_CHECKS["Output"],
            "issue_types": [],
            "passed": True,
            "findings": 0
        }
    ]
    
    latency_ms = random.uniform(200, 500)
    return metrics, stage_results, latency_ms

def simulate_proposed_execution(row_count: int, scenario: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], float]:
    """
    Simulate proposed integrity-focused pipeline execution.
    Returns: (metrics, stage_results, latency_ms)
    """
    # Proposed detects most issues
    if scenario == "clean":
        detected_issues = 0
        false_positives = 0
    elif scenario == "duplicated":
        detected_issues = max(0, int(row_count * 0.19))  # detects 95% of injected dupes
        false_positives = 1
    elif scenario == "dropped":
        detected_issues = max(0, int(row_count * 0.19))  # detects 95% of drops
        false_positives = 0
    elif scenario == "corrupted":
        detected_issues = max(0, int(row_count * 0.19))  # detects 95% of corruption
        false_positives = 1
    elif scenario == "schema_drift":
        detected_issues = max(0, int(row_count * 0.2))
        false_positives = 0
    else:
        detected_issues = max(0, int(row_count * 0.19))
        false_positives = 1
    
    total_injected = int(row_count * 0.2) if scenario not in ["clean", "real_world"] else 0
    stored_rows = row_count - max(0, (total_injected - detected_issues) * 0.5)
    false_negatives = max(0, total_injected - detected_issues)
    
    # When nothing is flagged at all (detected=0 and FP=0), precision is 1.0 by convention
    total_flagged = detected_issues + false_positives
    precision = (detected_issues / total_flagged) if total_flagged > 0 else 1.0
    
    metrics = {
        "detection_accuracy": detected_issues / max(1, total_injected) if total_injected > 0 else 1.0,
        "precision": precision,
        "recall": detected_issues / max(1, detected_issues + false_negatives) if (detected_issues + false_negatives) > 0 else 1.0,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "detected_loss": max(0, int(total_injected * 0.95)) if scenario == "dropped" else 0,
        "detected_duplicates": max(0, int(total_injected * 0.95)) if scenario == "duplicated" else 0,
        "detected_corruption": max(0, int(total_injected * 0.95)) if scenario == "corrupted" else 0,
        "detected_inconsistency": max(0, int(detected_issues * 0.8)),
        "record_count": int(stored_rows),
        "source_count": row_count
    }
    
    stage_results = [
        {
            "stage": "Ingestion",
            "checks": PROPOSED_STAGE_CHECKS["Ingestion"],
            "issue_types": ["schema_drift", "null_values"],
            "passed": detected_issues == 0,
            "findings": 0 if scenario == "clean" else random.randint(0, 2)
        },
        {
            "stage": "Preprocessing",
            "checks": PROPOSED_STAGE_CHECKS["Preprocessing"],
            "issue_types": ["duplication", "schema_drift"],
            "passed": scenario not in ["duplicated", "schema_drift"],
            "findings": detected_issues if scenario in ["duplicated", "schema_drift"] else 0
        },
        {
            "stage": "Transformation",
            "checks": PROPOSED_STAGE_CHECKS["Transformation"],
            "issue_types": ["incorrect_transformation"],
            "passed": True,
            "findings": 0
        },
        {
            "stage": "Storage",
            "checks": PROPOSED_STAGE_CHECKS["Storage"],
            "issue_types": ["data_loss", "inconsistency"],
            "passed": scenario in ["clean", "schema_drift"],
            "findings": detected_issues if scenario in ["dropped", "corrupted"] else 0
        },
        {
            "stage": "Output",
            "checks": PROPOSED_STAGE_CHECKS["Output"],
            "issue_types": ["inconsistency", "corruption"],
            "passed": detected_issues == 0,
            "findings": 0
        }
    ]
    
    latency_ms = random.uniform(400, 900)  # Slightly slower due to more checks
    return metrics, stage_results, latency_ms