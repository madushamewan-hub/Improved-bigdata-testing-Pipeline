import sys
from typing import Any, Dict, List

from .metrics import CORE_DIMENSIONS, _compute_composite_score, _count_duplicate_event_ids, _finalize_proposed_metrics
from .resilience import (
    DEFAULT_RESILIENCE_POLICY,
    _preprocessing_resilient,
    _snapshot_checkpoint,
    _transform_resilient,
)
from .runtime import (
    _configure_spark_python_runtime,
    _run_spark_via_external_python,
    _should_use_external_spark_runner,
)
from .sector_targets import evaluate_sector_targets
from .stages import downstream_validation, ingestion, preprocessing, storage, transform
from .validation import REQUIRED_FIELDS


def _run_python_batch_internal(orders: List[Dict], db_path: str, sector: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    resilience_metrics = {
        'retry_attempts': 0,
        'recovery_attempts': 0,
        'successful_recoveries': 0,
        'quarantined_records': 0,
        'checkpoint_recoveries': 0,
    }
    quarantine_records: List[Dict[str, Any]] = []
    checkpoint_flow: List[Dict[str, Any]] = []

    ingested, ingestion_metrics = ingestion(orders, mode='batch')
    checkpoint_flow.append(_snapshot_checkpoint('ingestion', ingested))

    if policy.get('enabled', True):
        preprocessed, preprocess_metrics = _preprocessing_resilient(ingested, policy, resilience_metrics, quarantine_records)
    else:
        preprocessed, preprocess_metrics = preprocessing(ingested)
    checkpoint_flow.append(_snapshot_checkpoint('preprocessing', preprocessed))

    if policy.get('enabled', True):
        transformed, transform_metrics = _transform_resilient(preprocessed, policy, resilience_metrics, quarantine_records)
    else:
        transformed, transform_metrics = transform(preprocessed)
    checkpoint_flow.append(_snapshot_checkpoint('transformation', transformed))

    storage_attempts = 0
    max_storage_retries = int(policy.get('max_retries', 2)) if policy.get('enabled', True) else 0
    while True:
        storage_attempts += 1
        try:
            storage_metrics, storage_info = storage(transformed, db_path=db_path)
            break
        except Exception:
            if storage_attempts > max_storage_retries + 1:
                raise
            resilience_metrics['checkpoint_recoveries'] += 1
    resilience_metrics['retry_attempts'] += max(0, storage_attempts - 1)
    if storage_attempts > 1:
        resilience_metrics['recovery_attempts'] += 1
        resilience_metrics['successful_recoveries'] += 1
    checkpoint_flow.append(_snapshot_checkpoint('storage', transformed))

    downstream_metrics = downstream_validation(transformed, orders)

    return _finalize_proposed_metrics(
        orders=orders,
        transformed=transformed,
        ingestion_metrics=ingestion_metrics,
        preprocess_metrics=preprocess_metrics,
        transform_metrics=transform_metrics,
        storage_metrics=storage_metrics,
        storage_info=storage_info,
        downstream_metrics=downstream_metrics,
        sector=sector,
        engine='python',
        resilience_metrics=resilience_metrics,
        checkpoint_flow=checkpoint_flow,
        quarantine_records=quarantine_records,
        resilience_policy=policy,
    )


def _run_spark_batch_internal(orders: List[Dict], db_path: str, sector: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    if sys.version_info >= (3, 14):
        return _run_spark_via_external_python(orders, db_path=db_path, sector=sector, policy=policy)
    if _should_use_external_spark_runner():
        return _run_spark_via_external_python(orders, db_path=db_path, sector=sector, policy=policy)

    try:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F
    except Exception as exc:
        raise RuntimeError(f'Spark engine requested but pyspark is unavailable: {exc}')

    resilience_metrics = {
        'retry_attempts': 0,
        'recovery_attempts': 0,
        'successful_recoveries': 0,
        'quarantined_records': 0,
        'checkpoint_recoveries': 0,
    }
    quarantine_records: List[Dict[str, Any]] = []
    checkpoint_flow: List[Dict[str, Any]] = []

    spark_python = _configure_spark_python_runtime()
    spark = (
        SparkSession.builder
        .master('local[1]')
        .appName('integrity-testing-proposed')
        .config('spark.pyspark.python', spark_python)
        .config('spark.pyspark.driver.python', spark_python)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel('ERROR')

    try:
        ingested, ingestion_metrics = ingestion(orders, mode='batch')
        checkpoint_flow.append(_snapshot_checkpoint('ingestion', ingested))

        if not ingested:
            preprocessed = []
            preprocess_metrics = {'type_mismatches': 0, 'malformed': 0}
            transformed = []
            transform_metrics = {'transformation_failures': 0, 'mapping_issues': 0}
            storage_metrics, storage_info = storage([], db_path=db_path)
            checkpoint_flow.append(_snapshot_checkpoint('preprocessing', preprocessed))
            checkpoint_flow.append(_snapshot_checkpoint('transformation', transformed))
            checkpoint_flow.append(_snapshot_checkpoint('storage', transformed))
            downstream_metrics = downstream_validation(transformed, orders)
        else:
            df = spark.createDataFrame(ingested)

            typed_df = df.select(
                *[F.col(field) for field in REQUIRED_FIELDS],
                F.col('amount').cast('double').alias('amount_cast'),
                F.col('version').cast('int').alias('version_cast'),
            )

            bad_type_df = typed_df.filter(
                (F.col('amount').isNotNull() & F.col('amount_cast').isNull())
                | (F.col('version').isNotNull() & F.col('version_cast').isNull())
            )
            preprocess_metrics = {
                'type_mismatches': int(bad_type_df.count()),
                'malformed': 0,
            }

            good_type_df = typed_df.filter(
                F.col('amount_cast').isNotNull() & F.col('version_cast').isNotNull()
            ).drop('amount', 'version').withColumnRenamed('amount_cast', 'amount').withColumnRenamed('version_cast', 'version')

            preprocessed = [row.asDict() for row in good_type_df.collect()]
            checkpoint_flow.append(_snapshot_checkpoint('preprocessing', preprocessed))

            transformed_df = good_type_df.withColumn('total_tax', F.round(F.col('amount') * F.lit(0.1), 2))
            transformed = [row.asDict() for row in transformed_df.collect()]
            transform_metrics = {
                'transformation_failures': 0,
                'mapping_issues': _count_duplicate_event_ids(transformed),
            }
            checkpoint_flow.append(_snapshot_checkpoint('transformation', transformed))

            storage_metrics, storage_info = storage(transformed, db_path=db_path)
            checkpoint_flow.append(_snapshot_checkpoint('storage', transformed))
            downstream_metrics = downstream_validation(transformed, orders)

        return _finalize_proposed_metrics(
            orders=orders,
            transformed=transformed,
            ingestion_metrics=ingestion_metrics,
            preprocess_metrics=preprocess_metrics,
            transform_metrics=transform_metrics,
            storage_metrics=storage_metrics,
            storage_info=storage_info,
            downstream_metrics=downstream_metrics,
            sector=sector,
            engine='spark',
            resilience_metrics=resilience_metrics,
            checkpoint_flow=checkpoint_flow,
            quarantine_records=quarantine_records,
            resilience_policy=policy,
        )
    finally:
        try:
            spark.stop()
        except Exception:
            pass


def _dispatch_batch(orders: List[Dict], db_path: str, sector: str, resilience_policy: Dict[str, Any] | None, engine: str) -> Dict[str, Any]:
    policy = dict(DEFAULT_RESILIENCE_POLICY)
    if resilience_policy:
        policy.update(resilience_policy)

    if engine == 'python':
        return _run_python_batch_internal(orders, db_path=db_path, sector=sector, policy=policy)
    if engine == 'spark':
        return _run_spark_batch_internal(orders, db_path=db_path, sector=sector, policy=policy)
    raise ValueError(f'Unsupported engine: {engine}')


def run_streaming(orders: List[Dict], db_path: str = ':memory:', sector: str = 'cross_industry', resilience_policy: Dict[str, Any] = None, engine: str = 'python') -> Dict:
    batch_size = 20
    final_metrics = {}
    findings_accumulator = {dim: 0 for dim in CORE_DIMENSIONS}
    score_accumulator = {dim: 0.0 for dim in CORE_DIMENSIONS}
    check_confidence_accumulator: Dict[str, float] = {}
    check_confidence_counts: Dict[str, int] = {}
    dimension_confidence_accumulator = {dim: 0.0 for dim in CORE_DIMENSIONS}
    evidence_batches: List[Dict[str, Any]] = []
    advanced_metric_accumulator: Dict[str, float] = {}
    total_retry_attempts = 0
    total_quarantine_count = 0
    total_checkpoint_recoveries = 0
    checkpoint_batches: List[Dict[str, Any]] = []
    quarantine_batches: List[Dict[str, Any]] = []
    batches = 0

    for i in range(0, len(orders), batch_size):
        batch = orders[i:i + batch_size]
        metrics = _dispatch_batch(batch, db_path=db_path, sector=sector, resilience_policy=resilience_policy, engine=engine)
        batches += 1
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                final_metrics[k] = final_metrics.get(k, 0) + v
        for dim, findings in metrics.get('dimension_findings', {}).items():
            findings_accumulator[dim] = findings_accumulator.get(dim, 0) + int(findings)
        for dim, score in metrics.get('dimension_scores', {}).items():
            score_accumulator[dim] = score_accumulator.get(dim, 0.0) + float(score)
        for check_id, conf in metrics.get('check_confidence', {}).items():
            check_confidence_accumulator[check_id] = check_confidence_accumulator.get(check_id, 0.0) + float(conf)
            check_confidence_counts[check_id] = check_confidence_counts.get(check_id, 0) + 1
        for dim, conf in metrics.get('dimension_confidence', {}).items():
            dimension_confidence_accumulator[dim] = dimension_confidence_accumulator.get(dim, 0.0) + float(conf)
        evidence_batches.append({'batch_index': batches, 'check_evidence': metrics.get('check_evidence', [])})
        for metric_key, metric_score in metrics.get('advanced_metric_scores', {}).items():
            advanced_metric_accumulator[metric_key] = advanced_metric_accumulator.get(metric_key, 0.0) + float(metric_score)
        total_retry_attempts += int(metrics.get('retry_attempts', 0))
        total_quarantine_count += int(metrics.get('quarantine_count', 0))
        total_checkpoint_recoveries += int(metrics.get('checkpoint_recoveries', 0))
        checkpoint_batches.append({'batch_index': batches, 'checkpoint_flow': metrics.get('checkpoint_flow', [])})
        quarantine_batches.append({'batch_index': batches, 'quarantine_records': metrics.get('quarantine_records', [])})

    if batches > 0:
        final_metrics['dimension_findings'] = findings_accumulator
        final_metrics['dimension_scores'] = {dim: score_accumulator[dim] / batches for dim in score_accumulator}
        final_metrics['check_confidence'] = {
            check_id: check_confidence_accumulator[check_id] / max(1, check_confidence_counts.get(check_id, 1))
            for check_id in check_confidence_accumulator
        }
        final_metrics['dimension_confidence'] = {
            dim: dimension_confidence_accumulator.get(dim, 0.0) / batches
            for dim in dimension_confidence_accumulator
        }
        final_metrics['overall_confidence'] = (
            sum(final_metrics['dimension_confidence'].values()) / len(final_metrics['dimension_confidence'])
            if final_metrics['dimension_confidence'] else 0.0
        )
        final_metrics['check_evidence'] = evidence_batches
        final_metrics['advanced_metric_scores'] = {
            metric_key: advanced_metric_accumulator[metric_key] / batches
            for metric_key in advanced_metric_accumulator
        }
        final_metrics['retry_attempts'] = total_retry_attempts
        final_metrics['quarantine_count'] = total_quarantine_count
        final_metrics['checkpoint_recoveries'] = total_checkpoint_recoveries
        final_metrics['checkpoint_flow'] = checkpoint_batches
        final_metrics['quarantine_records'] = quarantine_batches
        final_metrics['resilience_policy'] = dict(DEFAULT_RESILIENCE_POLICY) if resilience_policy is None else {**DEFAULT_RESILIENCE_POLICY, **resilience_policy}
        final_metrics['sector'] = sector
        final_metrics['engine'] = engine

        sector_eval = evaluate_sector_targets(final_metrics, sector=sector)
        final_metrics['sector_target_evaluation'] = sector_eval
        final_metrics['sector_compliance_score'] = sector_eval['compliance_score']
        final_metrics['sector_pass_rate'] = sector_eval['pass_rate']

        composite_summary = _compute_composite_score(
            final_metrics.get('dimension_scores', {}),
            final_metrics.get('sector_compliance_score', 0.0),
        )
        final_metrics['dimension_average_score'] = composite_summary['dimension_average_score']
        final_metrics['composite_score'] = composite_summary['composite_score']
        final_metrics['composite_formula'] = composite_summary['composite_formula']
        final_metrics['rule_pack_version'] = 'v1.0.0'
        final_metrics['core_dimensions'] = CORE_DIMENSIONS

    return final_metrics
