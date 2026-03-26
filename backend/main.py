from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
import pandas as pd
import os
import sys
import math
import numpy as np
sys.path.append('..')

from backend.database import SessionLocal, engine, Base, Dataset, ExperimentRun, PipelineResult, StageCheckResult
from backend.schemas import ExperimentRunRequest
from backend.pipeline_sim import simulate_baseline_execution, simulate_proposed_execution
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
    """Upload a CSV dataset"""
    try:
        if file is None or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files supported")

        file_path = os.path.join("uploads", os.path.basename(file.filename))
        os.makedirs("uploads", exist_ok=True)

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Parse CSV to infer schema
        try:
            df = pd.read_csv(file_path)
        except Exception as parse_err:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"CSV parse failed: {parse_err}")

        row_count = len(df)
        schema = {col: str(df[col].dtype) for col in df.columns}

        # Store in DB
        db = SessionLocal()
        try:
            dataset = Dataset(
                name=file.filename.replace('.csv', ''),
                type="custom",
                row_count=row_count,
                schema_json=schema,
                file_path=file_path
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)
            dataset_id = dataset.id
        finally:
            db.close()

        # Make preview JSON-safe by replacing NaN/inf with None and converting numpy scalars
        preview_records = df.head(5).to_dict(orient="records")
        preview_records = _sanitize_for_json(preview_records)

        return {
            "id": dataset_id,
            "name": dataset.name,
            "row_count": row_count,
            "schema": schema,
            "preview": preview_records
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        app.logger if hasattr(app, 'logger') else None
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {e}")

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
        
        # Simulate pipeline execution
        row_count = dataset.row_count
        
        if req.mode in ["baseline", "compare"]:
            bl_metrics, bl_stages, bl_latency = simulate_baseline_execution(row_count, req.scenario_name)
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
            prop_metrics, prop_stages, prop_latency = simulate_proposed_execution(row_count, req.scenario_name)
            prop_result = PipelineResult(
                experiment_run_id=exp_run_id,
                pipeline_type="proposed",
                detection_accuracy=prop_metrics["detection_accuracy"],
                precision=prop_metrics["precision"],
                recall=prop_metrics["recall"],
                false_positives=prop_metrics["false_positives"],
                false_negatives=prop_metrics["false_negatives"],
                detected_loss=prop_metrics["detected_loss"],
                detected_duplicates=prop_metrics["detected_duplicates"],
                detected_corruption=prop_metrics["detected_corruption"],
                detected_inconsistency=prop_metrics["detected_inconsistency"],
                latency_ms=prop_latency,
                overhead_ms=prop_latency,
                summary_json=prop_metrics
            )
            db.add(prop_result)
            
            # Store stage results
            for stage in prop_stages:
                for check in stage["checks"]:
                    sr = StageCheckResult(
                        experiment_run_id=exp_run_id,
                        pipeline_type="proposed",
                        stage_name=stage["stage"],
                        check_name=check,
                        issue_type=",".join(stage.get("issue_types", [])),
                        passed=stage["passed"],
                        findings_count=stage["findings"]
                    )
                    db.add(sr)
        
        # Mark as completed
        exp_run.status = "completed"
        db.commit()
        
        db.close()
        return {"experiment_id": exp_run_id, "status": "completed"}
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
    
    return {
        "id": exp.id,
        "dataset_id": exp.dataset_id,
        "scenario": exp.scenario_name,
        "mode": exp.mode,
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
            "overhead": proposed.overhead_ms if proposed else 0
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