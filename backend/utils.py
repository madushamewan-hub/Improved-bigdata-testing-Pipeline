import math
import numpy as np


def _sanitize_for_json(value):
    """Recursively sanitize values to be JSON serializable.

    Converts numpy types to native Python types and replaces non-finite
    floats with None so JSON encoding doesn't fail.
    """
    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(v) for v in value]

    if isinstance(value, (np.integer, np.int_)):
        return int(value)
    if isinstance(value, (np.floating, np.float_)):
        if math.isfinite(value):
            return float(value)
        return None
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return None

    return value
