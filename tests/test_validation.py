import pytest
from src.common.validation import check_duplicates, validate_data_types, compute_checksum, check_transformation_correctness

def test_check_duplicates():
    data = [{'id': 1, 'value': 10}, {'id': 2, 'value': 20}, {'id': 1, 'value': 30}]
    dups = check_duplicates(data, 'id')
    assert dups == 1

def test_validate_data_types():
    data = [{'id': 1, 'name': 'Alice'}, {'id': '2', 'name': 'Bob'}]
    schema = {'id': int, 'name': str}
    errors = validate_data_types(data, schema)
    assert errors == 1

def test_compute_checksum():
    data = {'id': 1, 'name': 'Alice'}
    checksum = compute_checksum(data)
    assert isinstance(checksum, str)
    assert len(checksum) == 32  # MD5

def test_check_transformation_correctness():
    original = [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}]
    transformed = [{'a': 1, 'b': 2, 'total': 3}, {'a': 3, 'b': 4, 'total': 7}]
    def transform_func(item):
        return {**item, 'total': item['a'] + item['b']}
    errors = check_transformation_correctness(original, transformed, transform_func)
    assert errors == 0
    # With error
    wrong_transformed = [{'a': 1, 'b': 2, 'total': 4}]
    errors = check_transformation_correctness(original[:1], wrong_transformed, transform_func)
    assert errors == 1