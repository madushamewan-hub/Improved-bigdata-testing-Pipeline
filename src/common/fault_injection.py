import random
from typing import List, Dict, Any
from copy import deepcopy

def inject_data_loss(data: List[Dict[str, Any]], loss_rate: float = 0.1) -> tuple[List[Dict[str, Any]], int]:
    """Randomly drop records to simulate data loss."""
    number_removed = int(len(data) * loss_rate)
    injected = data[:-number_removed] if number_removed > 0 else data
    return injected, number_removed

def inject_duplication(data: List[Dict[str, Any]], dup_rate: float = 0.1) -> tuple[List[Dict[str, Any]], int]:
    """Randomly duplicate records."""
    number_added = int(len(data) * dup_rate)
    injected = deepcopy(data)
    for _ in range(number_added):
        item = random.choice(data)
        injected.append(deepcopy(item))
    return injected, number_added

def inject_corruption(data: List[Dict[str, Any]], corrupt_rate: float = 0.1, fields: List[str] = None) -> tuple[List[Dict[str, Any]], int]:
    """Randomly corrupt fields."""
    number_corrupted = int(len(data) * corrupt_rate)
    injected = deepcopy(data)
    for i in random.sample(range(len(data)), number_corrupted):
        field = random.choice(fields or list(injected[i].keys()))
        if isinstance(injected[i][field], int):
            injected[i][field] = injected[i][field] * 2
        elif isinstance(injected[i][field], str):
            injected[i][field] += "_corrupt"
    return injected, number_corrupted

def inject_inconsistency(data: List[Dict[str, Any]], inconsistency_rate: float = 0.1) -> tuple[List[Dict[str, Any]], int]:
    """Introduce inconsistencies."""
    number_inconsistent = int(len(data) * inconsistency_rate)
    injected = deepcopy(data)
    for i in random.sample(range(len(data)), number_inconsistent):
        injected[i]['id'] = -1
    return injected, number_inconsistent