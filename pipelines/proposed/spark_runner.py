import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        from pipelines.proposed.pipeline import _run_spark_batch_internal

        result = _run_spark_batch_internal(
            orders=payload.get('orders', []),
            db_path=payload.get('db_path', ':memory:'),
            sector=payload.get('sector', 'cross_industry'),
            policy=payload.get('resilience_policy', {}),
        )
        sys.stdout.write('__SPARK_RESULT__' + json.dumps(result))
        return 0
    except Exception as exc:
        sys.stderr.write(str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())