from typing import Any, Dict, List

from .execution import _dispatch_batch, _run_python_batch_internal, _run_spark_batch_internal, run_streaming
from .resilience import DEFAULT_RESILIENCE_POLICY
from .runtime import get_engine_capabilities
from .stages import downstream_validation, ingestion, preprocessing, storage, transform


def run_batch(
    orders: List[Dict],
    db_path: str = ':memory:',
    sector: str = 'cross_industry',
    resilience_policy: Dict[str, Any] = None,
    engine: str = 'python',
) -> Dict:
    return _dispatch_batch(
        orders,
        db_path=db_path,
        sector=sector,
        resilience_policy=resilience_policy,
        engine=engine,
    )


__all__ = [
    'DEFAULT_RESILIENCE_POLICY',
    'downstream_validation',
    'get_engine_capabilities',
    'ingestion',
    'preprocessing',
    'run_batch',
    'run_streaming',
    'storage',
    'transform',
    '_run_python_batch_internal',
    '_run_spark_batch_internal',
]
