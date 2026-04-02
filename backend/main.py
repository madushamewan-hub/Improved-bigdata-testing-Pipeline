from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd
import os
import sys
import math
import time
import numpy as np
sys.path.append('..')

from backend.database import SessionLocal, engine, Base, Dataset, ExperimentRun, PipelineResult, StageCheckResult
from backend.schemas import ExperimentRunRequest
from backend.pipeline_sim import simulate_baseline_execution, simulate_proposed_execution
from backend.file_parser import FileParser
from pipelines.proposed.pipeline import run_batch as proposed_run_batch, get_engine_capabilities
from data_generator.order_events import compute_checksum
from data_generator.order_events import inject_duplicates, inject_missing, inject_corruption, inject_schema_drift, inject_out_of_order
import shutil

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Integrity Testing Dashboard API")


def _sanitize_for_json(value):
    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(v) for v in value]

    if isinstance(value, (np.integer, np.int_)):
        return int(value)
    if isinstance(value, (np.floating, np.float_)):
        if math.isfinite(value):
            return float(value)
        return None
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return None

    if value is None:
        return None

    return value

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== HEALTH & INFO ==========

@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/runtime/engines")
async def get_runtime_engines():
    return get_engine_capabilities()


def _resolve_dataset_file_format(dataset: Dataset) -> str:
    schema_json = dataset.schema_json if isinstance(dataset.schema_json, dict) else {}
    candidates = [
        schema_json.get('source_format'),
        schema_json.get('format'),
        dataset.type,
        FileParser.get_file_format(dataset.file_path or ''),
        FileParser.get_file_format(dataset.name or ''),
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.lower() in FileParser.SUPPORTED_FORMATS:
            return candidate.lower()

    supported = ', '.join(FileParser.SUPPORTED_FORMATS)
    raise ValueError(
        f"Could not resolve a supported file format for dataset '{dataset.name}'. "
        f"Stored type was '{dataset.type}'. Supported: {supported}"
    )


def _pick_first_value(row: dict, aliases) -> object:
    lowered = {str(key).lower(): key for key in row.keys()}
    for alias in aliases:
        actual_key = lowered.get(alias.lower())
        if actual_key is None:
            continue
        value = row.get(actual_key)
        if value is not None and value != '':
            return value
    return None


def _normalize_record_for_pipeline(row: dict, row_index: int, dataset: Dataset) -> dict:
    event_id = _pick_first_value(row, ['event_id', 'order_id', 'id'])
    event_time = _pick_first_value(row, ['event_time', 'created_at', 'timestamp', 'date', 'birthdate'])
    customer_id = _pick_first_value(row, ['customer_id', 'user_id', 'patient_id', 'website_session_id', 'first', 'customer'])
    amount = _pick_first_value(row, ['amount', 'price_usd', 'price', 'total', 'cogs_usd'])
    status = _pick_first_value(row, ['status', 'state', 'marital'])
    version = _pick_first_value(row, ['version'])
    source_system = _pick_first_value(row, ['source_system', 'source', 'channel'])

    normalized = {
        'event_id': str(event_id) if event_id is not None else f"{dataset.name or 'dataset'}-{row_index}",
        'event_time': str(event_time) if event_time is not None else datetime.utcnow().isoformat(),
        'customer_id': str(customer_id) if customer_id is not None else str(event_id if event_id is not None else f"entity-{row_index}"),
        'source_system': str(source_system) if source_system is not None else (_resolve_dataset_file_format(dataset) or 'uploaded_file'),
        'amount': amount if amount is not None else 0.0,
        'status': str(status) if status is not None else 'observed',
        'version': version if version is not None else 1,
    }
    normalized['checksum'] = compute_checksum(normalized)
    return normalized


def _normalize_dataset_records(records, dataset: Dataset):
    return [
        _normalize_record_for_pipeline(row, row_index=index, dataset=dataset)
        for index, row in enumerate(records)
    ]


def _load_dataset_records(dataset: Dataset):
    file_format = _resolve_dataset_file_format(dataset)
    df, _, _ = FileParser.parse_file(dataset.file_path, file_format)
    raw_records = df.to_dict(orient='records')
    return _normalize_dataset_records(raw_records, dataset)


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


def _derive_proposed_result_metrics(prop_metrics: dict, row_count: int, latency_ms: float):
    detected_issues = float(prop_metrics.get('proposed_detected_issues', 0))
    false_negatives = max(0, int(row_count - prop_metrics.get('stored_rows', 0)))
    false_positives = max(0, int(prop_metrics.get('mapping_issues', 0)))
    precision = detected_issues / max(1.0, detected_issues + false_positives)
    recall = detected_issues / max(1.0, detected_issues + false_negatives) if (detected_issues + false_negatives) > 0 else 1.0
    detection_accuracy = float(prop_metrics.get('dimension_average_score', 0.0)) or (detected_issues / max(1.0, float(row_count)))

    return {
        'detection_accuracy': detection_accuracy,
        'precision': precision,
        'recall': recall,
        'false_positives': false_positives,
        'false_negatives': false_negatives,
        'detected_loss': max(0, int(prop_metrics.get('nulls', 0))),
        'detected_duplicates': max(0, int(prop_metrics.get('mapping_issues', 0))),
        'detected_corruption': max(0, int(prop_metrics.get('checksum_mismatch', 0))),
        'detected_inconsistency': max(0, int(prop_metrics.get('row_count_mismatch', 0) + prop_metrics.get('invalid_schema', 0))),
        'latency_ms': latency_ms,
        'summary_json': prop_metrics,
    }

@app.get("/api/flows")
async def get_pipeline_flows():
    """Get pipeline flow definitions for visualization"""
    baseline_nodes = [
        {"id": "b1", "label": "Ingestion", "stage": "Ingestion", "checks": ["basic_schema_read"], "issue_types": [], "x": 0, "y": 0},
        {"id": "b2", "label": "Preprocessing", "stage": "Preprocessing", "checks": ["optional_type_conversion"], "issue_types": [], "x": 300, "y": 0},
        {"id": "b3", "label": "Transformation", "stage": "Transformation", "checks": ["basic_math"], "issue_types": [], "x": 600, "y": 0},
        {"id": "b4", "label": "Storage", "stage": "Storage", "checks": ["file_write"], "issue_types": [], "x": 900, "y": 0},
        {"id": "b5", "label": "Output", "stage": "Output", "checks": ["manual_review"], "issue_types": [], "x": 1200, "y": 0},
    ]
    
    baseline_edges = [
        {"source": "b1", "target": "b2"}, {"source": "b2", "target": "b3"},
        {"source": "b3", "target": "b4"}, {"source": "b4", "target": "b5"}
    ]
    
    proposed_nodes = [
        {"id": "p1", "label": "Ingestion", "stage": "Ingestion", "checks": ["schema_validation", "null_check"], "issue_types": ["schema_drift", "null_values"], "x": 0, "y": 300},
        {"id": "p2", "label": "Preprocessing", "stage": "Preprocessing", "checks": ["duplicate_detection", "checksum_validate"], "issue_types": ["duplication", "schema_drift"], "x": 300, "y": 300},
        {"id": "p3", "label": "Transformation", "stage": "Transformation", "checks": ["assertion_check", "type_validation"], "issue_types": ["incorrect_transformation"], "x": 600, "y": 300},
        {"id": "p4", "label": "Storage", "stage": "Storage", "checks": ["row_count_check", "checksum_reconcile"], "issue_types": ["data_loss", "inconsistency"], "x": 900, "y": 300},
        {"id": "p5", "label": "Output", "stage": "Output", "checks": ["downstream_validation", "consistency_check"], "issue_types": ["inconsistency", "corruption"], "x": 1200, "y": 300},
    ]
    
    proposed_edges = [
        {"source": "p1", "target": "p2"}, {"source": "p2", "target": "p3"},
        {"source": "p3", "target": "p4"}, {"source": "p4", "target": "p5"}
    ]
    
    return {
        "baseline": {"nodes": baseline_nodes, "edges": baseline_edges},
        "proposed": {"nodes": proposed_nodes, "edges": proposed_edges}
    }

# ========== DATASET MANAGEMENT ==========

@app.post("/api/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload dataset in multiple formats: CSV, JSON, NDJSON, Parquet, Excel, TSV"""
    try:
        if file is None or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # Detect file format
        file_format = FileParser.get_file_format(file.filename)
        if not file_format:
            supported = ', '.join(FileParser.SUPPORTED_FORMATS)
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Supported formats: {supported}"
            )

        # Save uploaded file
        file_path = os.path.join("uploads", os.path.basename(file.filename))
        os.makedirs("uploads", exist_ok=True)

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Validate file size
        file_size = os.path.getsize(file_path)
        is_valid, error_msg = FileParser.validate_file(file_path, file_size)
        if not is_valid:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=error_msg)

        # Parse file
        try:
            df, schema, processing_info = FileParser.parse_file(file_path, file_format)
        except ValueError as parse_err:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=str(parse_err))
        except Exception as parse_err:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"File parsing failed: {parse_err}")

        row_count = len(df)
        total_rows = processing_info.get('total_rows', row_count)
        
        # Store in DB
        db = SessionLocal()
        try:
            # Store processing info in schema
            schema_with_processing = dict(schema)
            schema_with_processing['processing_info'] = processing_info
            
            dataset = Dataset(
                name=file.filename.rsplit('.', 1)[0],  # Remove extension
                type=file_format,
                row_count=row_count,
                schema_json=schema_with_processing,
                file_path=file_path
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)
            dataset_id = dataset.id
        finally:
            db.close()

        # Get preview and sanitize
        preview_records = FileParser.get_preview(df, rows=5)

        return {
            "id": dataset_id,
            "name": dataset.name,
            "format": file_format,
            "size_mb": file_size / 1024 / 1024,
            "row_count": row_count,
            "total_rows": total_rows,
            "schema": schema,
            "preview": preview_records,
            "processing_mode": processing_info.get('processing_mode', 'full'),
            "truncated": processing_info.get('truncated', False),
            "rows_processed": processing_info.get('rows_processed', row_count)
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {e}")

@app.get("/api/upload/formats")
async def get_supported_formats():
    """Get list of supported file formats and their info"""
    return FileParser.get_format_info()


@app.get("/api/datasets")
async def list_datasets():
    """List all uploaded datasets"""
    db = SessionLocal()
    datasets = db.query(Dataset).all()
    db.close()
    return [{"id": d.id, "name": d.name, "type": d.type, "row_count": d.row_count, "uploaded_at": d.uploaded_at} for d in datasets]

@app.get("/api/db-summary")
async def db_summary():
    """Get summary / raw records for all tables"""
    db = SessionLocal()
    try:
        datasets = db.query(Dataset).all()
        experiments = db.query(ExperimentRun).all()
        pipelines = db.query(PipelineResult).all()
        checks = db.query(StageCheckResult).all()

        return {
            "datasets": [{"id": d.id, "name": d.name, "type": d.type, "row_count": d.row_count, "uploaded_at": d.uploaded_at} for d in datasets],
            "experiment_runs": [{"id": e.id, "dataset_id": e.dataset_id, "scenario_name": e.scenario_name, "mode": e.mode, "status": e.status, "started_at": e.started_at, "finished_at": e.finished_at, "error_message": e.error_message} for e in experiments],
            "pipeline_results": [{"id": p.id, "experiment_run_id": p.experiment_run_id, "pipeline_type": p.pipeline_type, "detection_accuracy": p.detection_accuracy, "precision": p.precision, "recall": p.recall, "false_positives": p.false_positives, "false_negatives": p.false_negatives, "latency_ms": p.latency_ms, "overhead_ms": p.overhead_ms} for p in pipelines],
            "stage_checks": [{"id": s.id, "experiment_run_id": s.experiment_run_id, "pipeline_type": s.pipeline_type, "stage_name": s.stage_name, "check_name": s.check_name, "issue_type": s.issue_type, "passed": s.passed, "findings_count": s.findings_count} for s in checks],
        }
    finally:
        db.close()

# ========== EXPERIMENT EXECUTION ==========

@app.post("/api/experiments/run")
async def run_experiment(req: ExperimentRunRequest):
    """Execute an experiment (baseline, proposed, or both)"""
    try:
        db = SessionLocal()
        
        # Get dataset
        dataset = db.query(Dataset).filter(Dataset.id == req.dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        engine_name = getattr(req, 'engine', 'python') or 'python'
        engine_capabilities = get_engine_capabilities()
        if engine_name not in engine_capabilities:
            raise HTTPException(status_code=400, detail=f"Unsupported engine: {engine_name}")
        if not engine_capabilities[engine_name].get('available', False):
            raise HTTPException(status_code=400, detail=engine_capabilities[engine_name].get('reason', 'Selected engine is unavailable'))

        # Check if force full scan is requested
        force_full_scan = getattr(req, 'force_full_scan', False)
        
        # If force full scan, re-parse the entire file
        if force_full_scan:
            file_path = dataset.file_path
            if os.path.exists(file_path):
                file_format = _resolve_dataset_file_format(dataset)
                try:
                    df, schema, processing_info = FileParser.parse_file(file_path, file_format)
                    # Update dataset with full processing info
                    schema_with_processing = dict(schema)
                    schema_with_processing['processing_info'] = processing_info
                    dataset.schema_json = schema_with_processing
                    dataset.row_count = len(df)
                    db.commit()
                    # Refresh snapshot after commit
                    db.refresh(dataset)
                    dataset_schema_json = dataset.schema_json if isinstance(dataset.schema_json, dict) else {}
                    row_count = len(df)
                    print(f"Force full scan: processed {processing_info.get('rows_processed', 0)}/{processing_info.get('total_rows', 0)} rows")
                except Exception as e:
                    print(f"Force full scan failed: {e}")
                    row_count = dataset.row_count
            else:
                row_count = dataset.row_count
        else:
            row_count = dataset.row_count
        
        # Snapshot values we need later before any commit that could expire the object
        dataset_name = dataset.name
        dataset_type = dataset.type
        dataset_schema_json = dataset.schema_json if isinstance(dataset.schema_json, dict) else {}
        
        # Create experiment run
        exp_run = ExperimentRun(
            dataset_id=req.dataset_id,
            scenario_name=req.scenario_name,
            mode=req.mode,
            status="running"
        )
        db.add(exp_run)
        db.commit()
        exp_run_id = exp_run.id
        
        # Get processing info (already snapshotted above; use updated version if force full scan ran)
        processing_info = dataset_schema_json.get('processing_info', {})
        source_records = _load_dataset_records(dataset)
        scenario_records = _apply_scenario(source_records, req.scenario_name)
        scenario_row_count = len(scenario_records)
        
        if req.mode in ["baseline", "compare"]:
            bl_metrics, bl_stages, bl_latency = simulate_baseline_execution(scenario_row_count, req.scenario_name)
            bl_result = PipelineResult(
                experiment_run_id=exp_run_id,
                pipeline_type="baseline",
                detection_accuracy=bl_metrics["detection_accuracy"],
                precision=bl_metrics["precision"],
                recall=bl_metrics["recall"],
                false_positives=bl_metrics["false_positives"],
                false_negatives=bl_metrics["false_negatives"],
                detected_loss=bl_metrics["detected_loss"],
                detected_duplicates=bl_metrics["detected_duplicates"],
                detected_corruption=bl_metrics["detected_corruption"],
                detected_inconsistency=bl_metrics["detected_inconsistency"],
                latency_ms=bl_latency,
                overhead_ms=0,
                summary_json=bl_metrics
            )
            db.add(bl_result)
            
            # Store stage results
            for stage in bl_stages:
                for check in stage["checks"]:
                    sr = StageCheckResult(
                        experiment_run_id=exp_run_id,
                        pipeline_type="baseline",
                        stage_name=stage["stage"],
                        check_name=check,
                        issue_type=",".join(stage.get("issue_types", [])),
                        passed=stage["passed"],
                        findings_count=stage["findings"]
                    )
                    db.add(sr)
        
        if req.mode in ["proposed", "compare"]:
            prop_start = time.perf_counter()
            prop_metrics = proposed_run_batch(scenario_records, sector='cross_industry', engine=engine_name)
            prop_latency = (time.perf_counter() - prop_start) * 1000.0
            derived_metrics = _derive_proposed_result_metrics(prop_metrics, scenario_row_count, prop_latency)
            prop_result = PipelineResult(
                experiment_run_id=exp_run_id,
                pipeline_type="proposed",
                detection_accuracy=derived_metrics["detection_accuracy"],
                precision=derived_metrics["precision"],
                recall=derived_metrics["recall"],
                false_positives=derived_metrics["false_positives"],
                false_negatives=derived_metrics["false_negatives"],
                detected_loss=derived_metrics["detected_loss"],
                detected_duplicates=derived_metrics["detected_duplicates"],
                detected_corruption=derived_metrics["detected_corruption"],
                detected_inconsistency=derived_metrics["detected_inconsistency"],
                latency_ms=derived_metrics["latency_ms"],
                overhead_ms=derived_metrics["latency_ms"],
                summary_json={**derived_metrics["summary_json"], "engine": engine_name}
            )
            db.add(prop_result)
            
            stage_mapping = {
                'schema_validation': 'Ingestion',
                'null_check': 'Ingestion',
                'freshness_check': 'Ingestion',
                'type_enforcement': 'Preprocessing',
                'transformation_validation': 'Transformation',
                'duplicate_mapping_check': 'Transformation',
                'row_count_reconciliation': 'Storage',
                'checksum_integrity': 'Storage',
                'event_ordering_monitor': 'Output',
                'downstream_reconciliation': 'Output',
            }
            for evidence in prop_metrics.get("check_evidence", []):
                sr = StageCheckResult(
                    experiment_run_id=exp_run_id,
                    pipeline_type="proposed",
                    stage_name=stage_mapping.get(evidence.get("check_id"), "Output"),
                    check_name=evidence.get("check_id", "unknown_check"),
                    issue_type=evidence.get("dimension", "integrity"),
                    passed=evidence.get("status") == "pass",
                    findings_count=int(evidence.get("findings", 0)),
                    notes=str(evidence.get("evidence", {}).get("detail", "")),
                )
                db.add(sr)
        
        # Mark as completed
        exp_run.status = "completed"
        db.commit()
        
        db.close()
        
        # Add processing mode info to response — use pre-snapshotted plain Python dicts (session is closed)
        processing_info = dataset_schema_json.get('processing_info', {})
        
        # Log processing info
        print(f"Experiment {exp_run_id}: Dataset {dataset_name} ({dataset_type}) - "
              f"Total rows: {processing_info.get('total_rows', row_count)}, "
              f"Processed: {processing_info.get('rows_processed', row_count)}, "
              f"Mode: {processing_info.get('processing_mode', 'unknown')}, "
              f"Truncated: {processing_info.get('truncated', False)}, "
              f"Force full scan: {force_full_scan}, "
              f"Engine: {engine_name}")
        
        response = {
            "experiment_id": exp_run_id, 
            "status": "completed",
            "dataset_info": {
                "total_rows": processing_info.get('total_rows', row_count),
                "rows_processed": processing_info.get('rows_processed', row_count),
                "processing_mode": processing_info.get('processing_mode', 'full'),
                "truncated": processing_info.get('truncated', False)
            },
            "engine": engine_name,
        }
        
        return response
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ========== RESULTS & METRICS ==========

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get summary statistics for dashboard"""
    db = SessionLocal()
    
    total_exps = db.query(ExperimentRun).count()
    
    baseline_results = db.query(func.avg(PipelineResult.detection_accuracy)).filter(
        PipelineResult.pipeline_type == "baseline"
    ).scalar() or 0
    
    proposed_results = db.query(func.avg(PipelineResult.detection_accuracy)).filter(
        PipelineResult.pipeline_type == "proposed"
    ).scalar() or 0
    
    baseline_fn = db.query(func.avg(PipelineResult.false_negatives)).filter(
        PipelineResult.pipeline_type == "baseline"
    ).scalar() or 0
    
    proposed_fn = db.query(func.avg(PipelineResult.false_negatives)).filter(
        PipelineResult.pipeline_type == "proposed"
    ).scalar() or 0
    
    avg_overhead = db.query(func.avg(PipelineResult.overhead_ms)).filter(
        PipelineResult.pipeline_type == "proposed"
    ).scalar() or 0
    
    db.close()
    
    return {
        "total_experiments": total_exps,
        "baseline_detection_rate": float(baseline_results),
        "proposed_detection_rate": float(proposed_results),
        "baseline_false_negatives": int(baseline_fn),
        "proposed_false_negatives": int(proposed_fn),
        "average_overhead_ms": float(avg_overhead)
    }

@app.get("/api/experiments/{exp_id}")
async def get_experiment(exp_id: int):
    """Get experiment details and results"""
    db = SessionLocal()
    
    exp = db.query(ExperimentRun).filter(ExperimentRun.id == exp_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    baseline = db.query(PipelineResult).filter(
        PipelineResult.experiment_run_id == exp_id,
        PipelineResult.pipeline_type == "baseline"
    ).first()
    
    proposed = db.query(PipelineResult).filter(
        PipelineResult.experiment_run_id == exp_id,
        PipelineResult.pipeline_type == "proposed"
    ).first()
    
    db.close()

    proposed_summary = proposed.summary_json if (proposed and isinstance(proposed.summary_json, dict)) else {}
    
    return {
        "id": exp.id,
        "dataset_id": exp.dataset_id,
        "scenario": exp.scenario_name,
        "mode": exp.mode,
        "engine": proposed_summary.get("engine", "python"),
        "status": exp.status,
        "baseline": {
            "accuracy": baseline.detection_accuracy if baseline else 0,
            "precision": baseline.precision if baseline else 0,
            "recall": baseline.recall if baseline else 0,
            "false_positives": baseline.false_positives if baseline else 0,
            "false_negatives": baseline.false_negatives if baseline else 0,
            "latency": baseline.latency_ms if baseline else 0
        } if baseline else None,
        "proposed": {
            "accuracy": proposed.detection_accuracy if proposed else 0,
            "precision": proposed.precision if proposed else 0,
            "recall": proposed.recall if proposed else 0,
            "false_positives": proposed.false_positives if proposed else 0,
            "false_negatives": proposed.false_negatives if proposed else 0,
            "latency": proposed.latency_ms if proposed else 0,
            "overhead": proposed.overhead_ms if proposed else 0,
            "dimension_average_score": proposed_summary.get("dimension_average_score", 0),
            "sector": proposed_summary.get("sector", "cross_industry"),
            "sector_compliance_score": proposed_summary.get("sector_compliance_score", 0),
            "sector_pass_rate": proposed_summary.get("sector_pass_rate", 0),
            "composite_score": proposed_summary.get("composite_score", 0),
            "composite_formula": proposed_summary.get("composite_formula", ""),
            "engine": proposed_summary.get("engine", "python"),
            "retry_attempts": proposed_summary.get("retry_attempts", 0),
            "quarantine_count": proposed_summary.get("quarantine_count", 0),
            "checkpoint_recoveries": proposed_summary.get("checkpoint_recoveries", 0)
        } if proposed else None
    }

@app.get("/api/experiments")
async def list_experiments():
    """List all experiments"""
    db = SessionLocal()
    exps = db.query(ExperimentRun).order_by(ExperimentRun.id.desc()).all()
    db.close()
    
    results = []
    for exp in exps:
        db = SessionLocal()
        baseline = db.query(PipelineResult).filter(
            PipelineResult.experiment_run_id == exp.id,
            PipelineResult.pipeline_type == "baseline"
        ).first()
        proposed = db.query(PipelineResult).filter(
            PipelineResult.experiment_run_id == exp.id,
            PipelineResult.pipeline_type == "proposed"
        ).first()
        db.close()
        
        results.append({
            "id": exp.id,
            "dataset_id": exp.dataset_id,
            "scenario": exp.scenario_name,
            "baseline_accuracy": baseline.detection_accuracy if baseline else 0,
            "proposed_accuracy": proposed.detection_accuracy if proposed else 0,
            "proposed_composite_score": (proposed.summary_json or {}).get("composite_score", 0) if proposed else 0,
            "proposed_sector_compliance": (proposed.summary_json or {}).get("sector_compliance_score", 0) if proposed else 0,
            "engine": (proposed.summary_json or {}).get("engine", "python") if proposed else "python",
            "timestamp": exp.started_at
        })
    
    return results

@app.get("/api/stage-checks/{exp_id}")
async def get_stage_checks(exp_id: int):
    """Get stage-level checks for an experiment"""
    db = SessionLocal()
    
    baseline_checks = db.query(StageCheckResult).filter(
        StageCheckResult.experiment_run_id == exp_id,
        StageCheckResult.pipeline_type == "baseline"
    ).all()
    
    proposed_checks = db.query(StageCheckResult).filter(
        StageCheckResult.experiment_run_id == exp_id,
        StageCheckResult.pipeline_type == "proposed"
    ).all()
    
    db.close()
    
    return {
        "baseline": [
            {
                "stage": c.stage_name,
                "check": c.check_name,
                "issue_type": c.issue_type,
                "passed": c.passed,
                "findings": c.findings_count
            } for c in baseline_checks
        ],
        "proposed": [
            {
                "stage": c.stage_name,
                "check": c.check_name,
                "issue_type": c.issue_type,
                "passed": c.passed,
                "findings": c.findings_count
            } for c in proposed_checks
        ]
    }

@app.delete("/api/experiments/{exp_id}")
async def delete_experiment(exp_id: int):
    """Delete an experiment"""
    db = SessionLocal()
    db.query(ExperimentRun).filter(ExperimentRun.id == exp_id).delete()
    db.query(PipelineResult).filter(PipelineResult.experiment_run_id == exp_id).delete()
    db.query(StageCheckResult).filter(StageCheckResult.experiment_run_id == exp_id).delete()
    db.commit()
    db.close()
    return {"deleted": True}