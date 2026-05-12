import math
import os
import shutil

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.database import Dataset, ExperimentRun, PipelineResult, SessionLocal, StageCheckResult
from backend.file_parser import FileParser

router = APIRouter()


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

    return value


@router.post('/api/upload')
async def upload_dataset(file: UploadFile = File(...)):
    """Upload dataset in multiple formats: CSV, JSON, NDJSON, Parquet, Excel, TSV."""
    try:
        if file is None or not file.filename:
            raise HTTPException(status_code=400, detail='No file provided')

        file_format = FileParser.get_file_format(file.filename)
        if not file_format:
            supported = ', '.join(FileParser.SUPPORTED_FORMATS)
            raise HTTPException(
                status_code=400,
                detail=f'Unsupported file format. Supported formats: {supported}',
            )

        file_path = os.path.join('uploads', os.path.basename(file.filename))
        os.makedirs('uploads', exist_ok=True)

        copy_buffer_mb = max(1, int(os.environ.get('UPLOAD_COPY_BUFFER_MB', '16')))
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f, length=copy_buffer_mb * 1024 * 1024)

        file_size = os.path.getsize(file_path)
        is_valid, error_msg = FileParser.validate_file(file_path, file_size)
        if not is_valid:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=error_msg)

        try:
            df, schema, processing_info = FileParser.parse_file(file_path, file_format)
        except ValueError as parse_err:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=str(parse_err))
        except Exception as parse_err:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f'File parsing failed: {parse_err}')

        row_count = len(df)
        total_rows = processing_info.get('total_rows', row_count)

        db = SessionLocal()
        try:
            schema_with_processing = dict(schema)
            schema_with_processing['processing_info'] = processing_info

            dataset = Dataset(
                name=file.filename.rsplit('.', 1)[0],
                type=file_format,
                row_count=row_count,
                schema_json=schema_with_processing,
                file_path=file_path,
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)
            dataset_id = dataset.id
        finally:
            db.close()

        preview_records = FileParser.get_preview(df, rows=5)

        return {
            'id': dataset_id,
            'name': dataset.name,
            'format': file_format,
            'size_mb': file_size / 1024 / 1024,
            'row_count': row_count,
            'total_rows': total_rows,
            'schema': schema,
            'preview': preview_records,
            'processing_mode': processing_info.get('processing_mode', 'full'),
            'truncated': processing_info.get('truncated', False),
            'rows_processed': processing_info.get('rows_processed', row_count),
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f'Upload error: {e}')
        raise HTTPException(status_code=500, detail=f'Unexpected server error: {e}')


@router.get('/api/upload/formats')
async def get_supported_formats():
    """Get list of supported file formats and their info."""
    return FileParser.get_format_info()


@router.get('/api/datasets')
async def list_datasets():
    """List all uploaded datasets."""
    db = SessionLocal()
    try:
        datasets = db.query(Dataset).all()
        return [
            {
                'id': d.id,
                'name': d.name,
                'type': d.type,
                'row_count': d.row_count,
                'uploaded_at': d.uploaded_at,
            }
            for d in datasets
        ]
    finally:
        db.close()


@router.get('/api/db-summary')
async def db_summary():
    """Get summary / raw records for all tables."""
    db = SessionLocal()
    try:
        datasets = db.query(Dataset).all()
        experiments = db.query(ExperimentRun).all()
        pipelines = db.query(PipelineResult).all()
        checks = db.query(StageCheckResult).all()

        return {
            'datasets': [
                {'id': d.id, 'name': d.name, 'type': d.type, 'row_count': d.row_count, 'uploaded_at': d.uploaded_at}
                for d in datasets
            ],
            'experiment_runs': [
                {
                    'id': e.id,
                    'dataset_id': e.dataset_id,
                    'scenario_name': e.scenario_name,
                    'mode': e.mode,
                    'status': e.status,
                    'started_at': e.started_at,
                    'finished_at': e.finished_at,
                    'error_message': e.error_message,
                }
                for e in experiments
            ],
            'pipeline_results': [
                {
                    'id': p.id,
                    'experiment_run_id': p.experiment_run_id,
                    'pipeline_type': p.pipeline_type,
                    'detection_accuracy': p.detection_accuracy,
                    'precision': p.precision,
                    'recall': p.recall,
                    'false_positives': p.false_positives,
                    'false_negatives': p.false_negatives,
                    'latency_ms': p.latency_ms,
                    'overhead_ms': p.overhead_ms,
                }
                for p in pipelines
            ],
            'stage_checks': [
                {
                    'id': s.id,
                    'experiment_run_id': s.experiment_run_id,
                    'pipeline_type': s.pipeline_type,
                    'stage_name': s.stage_name,
                    'check_name': s.check_name,
                    'issue_type': s.issue_type,
                    'passed': s.passed,
                    'findings_count': s.findings_count,
                }
                for s in checks
            ],
        }
    finally:
        db.close()
