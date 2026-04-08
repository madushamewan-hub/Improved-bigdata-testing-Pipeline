from typing import Dict, List

from .stages import downstream_validation, ingestion, preprocessing, storage, transform


def _run_batch_internal(orders: List[Dict], db_path: str = ':memory:') -> Dict:
    data = ingestion(orders, mode='batch')
    data = preprocessing(data)
    data = transform(data)
    storage(data, db_path=db_path)
    return downstream_validation(data)


def run_batch(orders: List[Dict], db_path: str = ':memory:') -> Dict:
    return _run_batch_internal(orders, db_path=db_path)


def run_streaming(orders: List[Dict], db_path: str = ':memory:') -> Dict:
    """Reuse the same logic with staged input for the baseline flow."""
    return _run_batch_internal(orders, db_path=db_path)


__all__ = [
    '_run_batch_internal',
    'run_batch',
    'run_streaming',
]
