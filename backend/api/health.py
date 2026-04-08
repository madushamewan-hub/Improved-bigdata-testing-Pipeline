from fastapi import APIRouter

from pipelines.proposed.pipeline import get_engine_capabilities
from backend.services.experiment_service import get_pipeline_flow_definitions

router = APIRouter()


@router.get('/health')
async def health_check():
    return {'status': 'ok'}


@router.get('/api/runtime/engines')
async def get_runtime_engines():
    return get_engine_capabilities()


@router.get('/api/flows')
async def get_pipeline_flows():
    """Get pipeline flow definitions for visualization."""
    return get_pipeline_flow_definitions()
