def transform_data(data):
    """Transform data with a simple a + b total computation."""
    transformed = []
    for item in data:
        transformed.append({**item, 'total': item['a'] + item['b']})
    return transformed

def run_pipeline(data):
    """Run the baseline pipeline without integrity checks."""
    transformed = transform_data(data)
    return transformed