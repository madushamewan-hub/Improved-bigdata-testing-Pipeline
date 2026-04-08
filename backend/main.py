import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.append('..')

from backend.api.analytics import router as analytics_router
from backend.api.datasets import router as datasets_router
from backend.api.experiments import router as experiments_router
from backend.api.health import router as health_router
from backend.database import Base, engine
from backend.services.dataset_service import (
    _infer_record_semantics,
    _load_dataset_records,
    _normalize_dataset_records,
    _normalize_record_for_pipeline,
    _pick_first_value,
    _resolve_dataset_file_format,
)
from backend.services.experiment_service import (
    SCENARIO_DETECTION_LABELS,
    _apply_scenario,
    _build_evaluation_context,
    _build_pipeline_export_rows,
    _compute_exact_evaluation_metrics,
    _compute_scenario_amended_count,
    _derive_proposed_result_metrics,
    _scenario_detection_label,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title='Integrity Testing Dashboard API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

for router in (health_router, datasets_router, analytics_router, experiments_router):
    app.include_router(router)

__all__ = [
    'app',
    'SCENARIO_DETECTION_LABELS',
    '_apply_scenario',
    '_build_evaluation_context',
    '_build_pipeline_export_rows',
    '_compute_exact_evaluation_metrics',
    '_compute_scenario_amended_count',
    '_derive_proposed_result_metrics',
    '_infer_record_semantics',
    '_load_dataset_records',
    '_normalize_dataset_records',
    '_normalize_record_for_pipeline',
    '_pick_first_value',
    '_resolve_dataset_file_format',
    '_scenario_detection_label',
]
