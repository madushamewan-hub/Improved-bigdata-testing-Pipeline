import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

SPARK_ALT_PYTHON_ENV = 'SPARK_PYTHON_EXECUTABLE'
SPARK_EXTERNAL_RUNNER_ACTIVE_ENV = 'SPARK_EXTERNAL_RUNNER_ACTIVE'
SPARK_FORCE_IN_PROCESS_ENV = 'SPARK_FORCE_IN_PROCESS'


def _configure_spark_python_runtime() -> str:
    python_executable = sys.executable
    os.environ['PYSPARK_PYTHON'] = python_executable
    os.environ['PYSPARK_DRIVER_PYTHON'] = python_executable
    return python_executable


def _resolve_external_spark_python() -> str | None:
    alt_python = os.environ.get(SPARK_ALT_PYTHON_ENV)
    if alt_python and Path(alt_python).exists():
        return alt_python
    if sys.version_info < (3, 14) and Path(sys.executable).exists():
        return sys.executable
    return None


def _should_use_external_spark_runner() -> bool:
    if os.environ.get(SPARK_EXTERNAL_RUNNER_ACTIVE_ENV) == '1':
        return False
    if os.environ.get(SPARK_FORCE_IN_PROCESS_ENV) == '1':
        return False
    return True


def get_engine_capabilities() -> Dict[str, Dict[str, Any]]:
    alt_python = _resolve_external_spark_python()
    alt_python_exists = bool(alt_python) and Path(alt_python).exists()
    configured_alt_python = os.environ.get(SPARK_ALT_PYTHON_ENV)
    prefer_external_runner = _should_use_external_spark_runner()
    current_python_version = f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
    recommended_python = '3.11/3.12'
    pyspark_installed = importlib.util.find_spec('pyspark') is not None

    python_supported = sys.version_info < (3, 14)
    spark_available = (python_supported and pyspark_installed) or alt_python_exists

    if spark_available and alt_python_exists and prefer_external_runner:
        if configured_alt_python is not None:
            spark_reason = f'Using alternate Spark Python runtime from {alt_python}.'
        else:
            spark_reason = f'Using external Spark execution with Python runtime {alt_python}.'
        spark_mode = 'external_python'
    elif spark_available and python_supported and pyspark_installed:
        spark_reason = f'PySpark is available in the current Python {current_python_version} runtime.'
        spark_mode = 'in_process'
    elif not python_supported:
        spark_reason = (
            f'Current backend Python runtime is {current_python_version}; '
            f'Spark adapter requires Python {recommended_python} or SPARK_PYTHON_EXECUTABLE '
            f'to point to a compatible interpreter.'
        )
        spark_mode = 'unavailable'
    else:
        spark_reason = (
            f'PySpark is not installed in the current Python {current_python_version} runtime. '
            f'Use Python {recommended_python} for the Spark adapter.'
        )
        spark_mode = 'unavailable'

    return {
        'python': {
            'available': True,
            'mode': 'in_process',
            'reason': 'Default reference execution engine.',
            'current_python': current_python_version,
        },
        'spark': {
            'available': spark_available,
            'mode': spark_mode,
            'reason': spark_reason,
            'alternate_python': alt_python if spark_mode == 'external_python' else None,
            'current_python': current_python_version,
            'recommended_python': recommended_python,
        },
    }


def _run_spark_via_external_python(orders: List[Dict], db_path: str, sector: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    alt_python = _resolve_external_spark_python()
    if not alt_python or not Path(alt_python).exists():
        raise RuntimeError('Spark engine requires SPARK_PYTHON_EXECUTABLE to point to a Python 3.11/3.12 interpreter.')

    runner_path = Path(__file__).with_name('spark_runner.py')
    payload = {
        'orders': orders,
        'db_path': db_path,
        'sector': sector,
        'resilience_policy': policy,
    }
    runner_env = dict(os.environ)
    runner_env[SPARK_EXTERNAL_RUNNER_ACTIVE_ENV] = '1'
    runner_env['PYSPARK_PYTHON'] = alt_python
    runner_env['PYSPARK_DRIVER_PYTHON'] = alt_python
    completed = subprocess.run(
        [alt_python, str(runner_path)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env=runner_env,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or 'Unknown Spark runner error'
        raise RuntimeError(f'External Spark runner failed: {stderr}')

    stdout_text = completed.stdout.strip()
    result_marker = '__SPARK_RESULT__'
    if result_marker in stdout_text:
        marker_payload = stdout_text.rsplit(result_marker, 1)[-1].strip()
        try:
            decoded_result, _ = json.JSONDecoder().raw_decode(marker_payload)
            return decoded_result
        except Exception as exc:
            raise RuntimeError(f'External Spark runner produced invalid marked JSON: {exc}')

    candidate_lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
    for candidate in reversed(candidate_lines):
        try:
            return json.loads(candidate)
        except Exception:
            continue

    try:
        return json.loads(stdout_text)
    except Exception as exc:
        raise RuntimeError(f'External Spark runner produced invalid JSON: {exc}')
