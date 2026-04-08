from fastapi import APIRouter
from sqlalchemy import func

from backend.database import ExperimentRun, PipelineResult, SessionLocal

router = APIRouter()


@router.get('/api/dashboard/stats')
async def get_dashboard_stats():
    """Get summary statistics for dashboard."""
    db = SessionLocal()
    try:
        total_exps = db.query(ExperimentRun).count()

        baseline_results = db.query(func.avg(PipelineResult.detection_accuracy)).filter(
            PipelineResult.pipeline_type == 'baseline'
        ).scalar() or 0

        proposed_results = db.query(func.avg(PipelineResult.detection_accuracy)).filter(
            PipelineResult.pipeline_type == 'proposed'
        ).scalar() or 0

        baseline_fn = db.query(func.avg(PipelineResult.false_negatives)).filter(
            PipelineResult.pipeline_type == 'baseline'
        ).scalar() or 0

        proposed_fn = db.query(func.avg(PipelineResult.false_negatives)).filter(
            PipelineResult.pipeline_type == 'proposed'
        ).scalar() or 0

        avg_overhead = db.query(func.avg(PipelineResult.overhead_ms)).filter(
            PipelineResult.pipeline_type == 'proposed'
        ).scalar() or 0

        return {
            'total_experiments': total_exps,
            'baseline_detection_rate': float(baseline_results),
            'proposed_detection_rate': float(proposed_results),
            'baseline_false_negatives': int(baseline_fn),
            'proposed_false_negatives': int(proposed_fn),
            'average_overhead_ms': float(avg_overhead),
        }
    finally:
        db.close()
