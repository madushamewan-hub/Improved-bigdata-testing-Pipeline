import os
import time
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.database import Dataset, ExperimentRun, PipelineResult, SessionLocal, StageCheckResult
from backend.file_parser import FileParser
from backend.pipeline_sim import simulate_baseline_execution
from backend.schemas import ExperimentRunRequest
from backend.services.dataset_service import _load_dataset_records, _resolve_dataset_file_format
from backend.services.experiment_service import (
    _apply_scenario,
    _build_evaluation_context,
    _build_pipeline_export_rows,
    _compute_exact_evaluation_metrics,
    _compute_scenario_amended_count,
    _derive_proposed_result_metrics,
    _scenario_detection_label,
    build_experiment_list_item,
    build_experiment_response,
)
from pipelines.proposed.pipeline import get_engine_capabilities, run_batch as proposed_run_batch

router = APIRouter()


@router.post('/api/experiments/run')
async def run_experiment(req: ExperimentRunRequest):
    """Execute an experiment (baseline, proposed, or both)."""
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.id == req.dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail='Dataset not found')

        engine_name = getattr(req, 'engine', 'python') or 'python'
        engine_capabilities = get_engine_capabilities()
        if engine_name not in engine_capabilities:
            raise HTTPException(status_code=400, detail=f'Unsupported engine: {engine_name}')
        if not engine_capabilities[engine_name].get('available', False):
            raise HTTPException(
                status_code=400,
                detail=engine_capabilities[engine_name].get('reason', 'Selected engine is unavailable'),
            )

        force_full_scan = getattr(req, 'force_full_scan', False)
        if force_full_scan:
            file_path = dataset.file_path
            if os.path.exists(file_path):
                file_format = _resolve_dataset_file_format(dataset)
                try:
                    df, schema, processing_info = FileParser.parse_file(file_path, file_format)
                    schema_with_processing = dict(schema)
                    schema_with_processing['processing_info'] = processing_info
                    dataset.schema_json = schema_with_processing
                    dataset.row_count = len(df)
                    db.commit()
                    db.refresh(dataset)
                    dataset_schema_json = dataset.schema_json if isinstance(dataset.schema_json, dict) else {}
                    row_count = len(df)
                    print(f"Force full scan: processed {processing_info.get('rows_processed', 0)}/{processing_info.get('total_rows', 0)} rows")
                except Exception as e:
                    print(f'Force full scan failed: {e}')
                    row_count = dataset.row_count
            else:
                row_count = dataset.row_count
        else:
            row_count = dataset.row_count

        dataset_name = dataset.name
        dataset_type = dataset.type
        dataset_schema_json = dataset.schema_json if isinstance(dataset.schema_json, dict) else {}

        exp_run = ExperimentRun(
            dataset_id=req.dataset_id,
            scenario_name=req.scenario_name,
            mode=req.mode,
            status='running',
        )
        db.add(exp_run)
        db.commit()
        exp_run_id = exp_run.id

        processing_info = dataset_schema_json.get('processing_info', {})
        source_records = _load_dataset_records(dataset, sample_rate=getattr(req, 'sample_rate', None), max_workers=getattr(req, 'max_workers', None))
        scenario_records = _apply_scenario(source_records, req.scenario_name)
        scenario_row_count = len(scenario_records)
        scenario_amended_count = _compute_scenario_amended_count(source_records, scenario_records, req.scenario_name)
        detection_label = _scenario_detection_label(req.scenario_name)

        baseline_latency_ms = 0.0

        if req.mode in ['baseline', 'compare']:
            bl_metrics, bl_stages, bl_latency = simulate_baseline_execution(scenario_row_count, req.scenario_name)
            baseline_latency_ms = bl_latency
            baseline_eval_context = _build_evaluation_context(
                source_records,
                scenario_records,
                req.scenario_name,
                bl_metrics,
                baseline_latency_ms=bl_latency,
                pipeline_type='baseline',
            )
            baseline_exact_metrics = _compute_exact_evaluation_metrics(
                bl_metrics,
                scenario_row_count,
                bl_latency,
                evaluation_context=baseline_eval_context,
            )
            baseline_summary = {
                **bl_metrics,
                **baseline_exact_metrics,
                'evaluation_metrics': baseline_exact_metrics,
                'scenario_amended_count': scenario_amended_count,
                'source_record_count': len(source_records),
                'scenario_record_count': scenario_row_count,
                'detection_label': detection_label,
                'engine': 'baseline',
            }
            bl_result = PipelineResult(
                experiment_run_id=exp_run_id,
                pipeline_type='baseline',
                detection_accuracy=bl_metrics['detection_accuracy'],
                precision=bl_metrics['precision'],
                recall=bl_metrics['recall'],
                false_positives=bl_metrics['false_positives'],
                false_negatives=bl_metrics['false_negatives'],
                detected_loss=bl_metrics['detected_loss'],
                detected_duplicates=bl_metrics['detected_duplicates'],
                detected_corruption=bl_metrics['detected_corruption'],
                detected_inconsistency=bl_metrics['detected_inconsistency'],
                latency_ms=bl_latency,
                overhead_ms=0,
                summary_json=baseline_summary,
            )
            db.add(bl_result)

            for stage in bl_stages:
                for check in stage['checks']:
                    sr = StageCheckResult(
                        experiment_run_id=exp_run_id,
                        pipeline_type='baseline',
                        stage_name=stage['stage'],
                        check_name=check,
                        issue_type=','.join(stage.get('issue_types', [])),
                        passed=stage['passed'],
                        findings_count=stage['findings'],
                    )
                    db.add(sr)

        if req.mode in ['proposed', 'compare']:
            prop_start = time.perf_counter()
            prop_metrics = proposed_run_batch(scenario_records, sector='cross_industry', engine=engine_name)
            prop_latency = (time.perf_counter() - prop_start) * 1000.0
            proposed_eval_context = _build_evaluation_context(
                source_records,
                scenario_records,
                req.scenario_name,
                prop_metrics,
                baseline_latency_ms=baseline_latency_ms,
                pipeline_type='proposed',
            )
            derived_metrics = _derive_proposed_result_metrics(
                prop_metrics,
                scenario_row_count,
                prop_latency,
                evaluation_context=proposed_eval_context,
            )
            prop_result = PipelineResult(
                experiment_run_id=exp_run_id,
                pipeline_type='proposed',
                detection_accuracy=derived_metrics['detection_accuracy'],
                precision=derived_metrics['precision'],
                recall=derived_metrics['recall'],
                false_positives=derived_metrics['false_positives'],
                false_negatives=derived_metrics['false_negatives'],
                detected_loss=derived_metrics['detected_loss'],
                detected_duplicates=derived_metrics['detected_duplicates'],
                detected_corruption=derived_metrics['detected_corruption'],
                detected_inconsistency=derived_metrics['detected_inconsistency'],
                latency_ms=derived_metrics['latency_ms'],
                overhead_ms=(prop_latency - baseline_latency_ms) if baseline_latency_ms > 0 else 0,
                summary_json={
                    **derived_metrics['summary_json'],
                    'engine': engine_name,
                    'scenario_amended_count': scenario_amended_count,
                    'source_record_count': len(source_records),
                    'scenario_record_count': scenario_row_count,
                    'detection_label': detection_label,
                },
            )
            db.add(prop_result)

            stage_mapping = {
                'schema_validation': 'Ingestion',
                'null_check': 'Ingestion',
                'freshness_check': 'Ingestion',
                'malformed_payload_check': 'Ingestion',
                'type_enforcement': 'Preprocessing',
                'transformation_validation': 'Transformation',
                'duplicate_mapping_check': 'Transformation',
                'row_count_reconciliation': 'Storage',
                'checksum_integrity': 'Storage',
                'event_ordering_monitor': 'Output',
                'downstream_reconciliation': 'Output',
            }
            for evidence in prop_metrics.get('check_evidence', []):
                sr = StageCheckResult(
                    experiment_run_id=exp_run_id,
                    pipeline_type='proposed',
                    stage_name=stage_mapping.get(evidence.get('check_id'), 'Output'),
                    check_name=evidence.get('check_id', 'unknown_check'),
                    issue_type=evidence.get('dimension', 'integrity'),
                    passed=evidence.get('status') == 'pass',
                    findings_count=int(evidence.get('findings', 0)),
                    notes=str(evidence.get('evidence', {}).get('detail', '')),
                )
                db.add(sr)

        exp_run.status = 'completed'
        db.commit()
    finally:
        db.close()

    processing_info = dataset_schema_json.get('processing_info', {})
    print(
        f'Experiment {exp_run_id}: Dataset {dataset_name} ({dataset_type}) - '
        f"Total rows: {processing_info.get('total_rows', row_count)}, "
        f"Processed: {processing_info.get('rows_processed', row_count)}, "
        f"Mode: {processing_info.get('processing_mode', 'unknown')}, "
        f"Truncated: {processing_info.get('truncated', False)}, "
        f'Force full scan: {force_full_scan}, '
        f'Engine: {engine_name}'
    )

    return {
        'experiment_id': exp_run_id,
        'status': 'completed',
        'detection_label': detection_label,
        'scenario_amended_count': scenario_amended_count,
        'dataset_info': {
            'total_rows': processing_info.get('total_rows', row_count),
            'rows_processed': processing_info.get('rows_processed', row_count),
            'processing_mode': processing_info.get('processing_mode', 'full'),
            'truncated': processing_info.get('truncated', False),
        },
        'engine': engine_name,
    }


@router.get('/api/experiments/{exp_id}')
async def get_experiment(exp_id: int):
    """Get experiment details and results."""
    db = SessionLocal()
    try:
        exp = db.query(ExperimentRun).filter(ExperimentRun.id == exp_id).first()
        if not exp:
            raise HTTPException(status_code=404, detail='Experiment not found')

        baseline = db.query(PipelineResult).filter(
            PipelineResult.experiment_run_id == exp_id,
            PipelineResult.pipeline_type == 'baseline',
        ).first()

        proposed = db.query(PipelineResult).filter(
            PipelineResult.experiment_run_id == exp_id,
            PipelineResult.pipeline_type == 'proposed',
        ).first()
        dataset = db.query(Dataset).filter(Dataset.id == exp.dataset_id).first()

        return build_experiment_response(exp, dataset, baseline, proposed)
    finally:
        db.close()


@router.get('/api/experiments')
async def list_experiments():
    """List all experiments."""
    db = SessionLocal()
    try:
        exps = db.query(ExperimentRun).order_by(ExperimentRun.id.desc()).all()
    finally:
        db.close()

    results = []
    for exp in exps:
        db = SessionLocal()
        try:
            baseline = db.query(PipelineResult).filter(
                PipelineResult.experiment_run_id == exp.id,
                PipelineResult.pipeline_type == 'baseline',
            ).first()
            proposed = db.query(PipelineResult).filter(
                PipelineResult.experiment_run_id == exp.id,
                PipelineResult.pipeline_type == 'proposed',
            ).first()
            dataset = db.query(Dataset).filter(Dataset.id == exp.dataset_id).first()
        finally:
            db.close()

        results.append(build_experiment_list_item(exp, dataset, baseline, proposed))

    return results


@router.get('/api/stage-checks/{exp_id}')
async def get_stage_checks(exp_id: int):
    """Get stage-level checks for an experiment."""
    db = SessionLocal()
    try:
        baseline_checks = db.query(StageCheckResult).filter(
            StageCheckResult.experiment_run_id == exp_id,
            StageCheckResult.pipeline_type == 'baseline',
        ).all()

        proposed_checks = db.query(StageCheckResult).filter(
            StageCheckResult.experiment_run_id == exp_id,
            StageCheckResult.pipeline_type == 'proposed',
        ).all()

        return {
            'baseline': [
                {
                    'stage': c.stage_name,
                    'check': c.check_name,
                    'issue_type': c.issue_type,
                    'passed': c.passed,
                    'findings': c.findings_count,
                }
                for c in baseline_checks
            ],
            'proposed': [
                {
                    'stage': c.stage_name,
                    'check': c.check_name,
                    'issue_type': c.issue_type,
                    'passed': c.passed,
                    'findings': c.findings_count,
                }
                for c in proposed_checks
            ],
        }
    finally:
        db.close()


@router.get('/api/experiments/{exp_id}/export.xlsx')
async def export_experiment_excel(exp_id: int):
    """Download an experiment workbook with separate baseline and proposed sheets."""
    db = SessionLocal()
    try:
        exp = db.query(ExperimentRun).filter(ExperimentRun.id == exp_id).first()
        if not exp:
            raise HTTPException(status_code=404, detail='Experiment not found')

        dataset = db.query(Dataset).filter(Dataset.id == exp.dataset_id).first()
        baseline = db.query(PipelineResult).filter(
            PipelineResult.experiment_run_id == exp_id,
            PipelineResult.pipeline_type == 'baseline',
        ).first()
        proposed = db.query(PipelineResult).filter(
            PipelineResult.experiment_run_id == exp_id,
            PipelineResult.pipeline_type == 'proposed',
        ).first()
        baseline_checks = db.query(StageCheckResult).filter(
            StageCheckResult.experiment_run_id == exp_id,
            StageCheckResult.pipeline_type == 'baseline',
        ).all()
        proposed_checks = db.query(StageCheckResult).filter(
            StageCheckResult.experiment_run_id == exp_id,
            StageCheckResult.pipeline_type == 'proposed',
        ).all()
    finally:
        db.close()

    baseline_rows = _build_pipeline_export_rows(exp, dataset, 'baseline', baseline, baseline_checks)
    proposed_rows = _build_pipeline_export_rows(exp, dataset, 'proposed', proposed, proposed_checks)

    workbook = BytesIO()
    with pd.ExcelWriter(workbook, engine='openpyxl') as writer:
        pd.DataFrame(baseline_rows).to_excel(writer, sheet_name='baseline', index=False)
        pd.DataFrame(proposed_rows).to_excel(writer, sheet_name='proposed', index=False)

    workbook.seek(0)
    filename = f'experiment_{exp_id}_report.xlsx'
    return StreamingResponse(
        workbook,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.delete('/api/experiments/{exp_id}')
async def delete_experiment(exp_id: int):
    """Delete an experiment."""
    db = SessionLocal()
    try:
        db.query(ExperimentRun).filter(ExperimentRun.id == exp_id).delete()
        db.query(PipelineResult).filter(PipelineResult.experiment_run_id == exp_id).delete()
        db.query(StageCheckResult).filter(StageCheckResult.experiment_run_id == exp_id).delete()
        db.commit()
        return {'deleted': True}
    finally:
        db.close()
