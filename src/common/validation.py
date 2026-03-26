from typing import List, Dict, Any
import hashlib

def check_duplicates(data: List[Dict[str, Any]], key: str) -> int:
    """Check for duplicate records based on a key field."""
    seen = set()
    count = 0
    for item in data:
        id_val = item.get(key)
        if id_val in seen:
            count += 1
        else:
            seen.add(id_val)
    return count

def validate_data_types(data: List[Dict[str, Any]], schema: Dict[str, type]) -> int:
    """Validate data types against a schema."""
    count = 0
    for item in data:
        for field, expected_type in schema.items():
            if field in item and not isinstance(item[field], expected_type):
                count += 1
    return count

def compute_checksum(data: Dict[str, Any]) -> str:
    """Compute MD5 checksum for data integrity."""
    data_str = str(sorted(data.items()))
    return hashlib.md5(data_str.encode()).hexdigest()

def check_transformation_correctness(original: List[Dict[str, Any]], transformed: List[Dict[str, Any]], transform_func) -> int:
    """Check if transformation is applied correctly."""
    count = 0
    for orig, trans in zip(original, transformed):
        expected = transform_func(orig)
        if trans != expected:
            count += 1
    return count

def detect_inconsistencies(data: List[Dict[str, Any]], rules: List[callable]) -> int:
    """Detect inconsistencies using custom rules."""
    count = 0
    for rule in rules:
        count += len(rule(data))
    return count

def check_integrity(data: List[Dict[str, Any]]) -> int:
    """Check integrity of transformed data."""
    count = 0
    for item in data:
        if item.get('a', 0) + item.get('b', 0) != item.get('total', 0):
            count += 1
    return count

def check_data_loss(data: List[Dict[str, Any]], expected_n: int) -> int:
    """Check for data loss by missing ids."""
    ids = set(item['id'] for item in data if 'id' in item)
    expected_ids = set(range(expected_n))
    missing = expected_ids - ids
    return len(missing)

def check_inconsistency(data: List[Dict[str, Any]]) -> int:
    """Check for inconsistencies like negative ids."""
    return len([item for item in data if item.get('id', 0) < 0])