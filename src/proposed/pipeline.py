from ..common.validation import check_transformation_correctness, check_duplicates, check_integrity, check_data_loss, check_inconsistency

SCHEMA = {'id': int, 'a': int, 'b': int}

def transform_func(item):
    """Expected transformation."""
    return {**item, 'total': item['a'] + item['b']}

def transform_data(data):
    """Transform data with validation."""
    transformed = []
    for item in data:
        transformed.append(transform_func(item))

    # Validation at transformation
    transform_errors = check_transformation_correctness(data, transformed, transform_func)
    return transformed, transform_errors

def run_pipeline(data, original_n):
    """Run the proposed pipeline with integrity checks."""
    transformed, transform_errors = transform_data(data)
    integrity_errors = check_integrity(transformed)
    dup_errors = check_duplicates(transformed, 'id')
    data_loss_errors = check_data_loss(transformed, original_n)
    inc_errors = check_inconsistency(transformed)
    detections = transform_errors + integrity_errors + dup_errors + data_loss_errors + inc_errors
    return transformed, detections