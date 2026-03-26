# Thesis Mapping

| Integrity Issue | Stage | Mechanism | Metric |
|---|---|---|---|
| Data loss | Ingestion / storage | missing record injection, row count reconciliation | missing count, false negatives |
| Duplication | Ingestion / transformation | duplicate injection, dedupe checks | duplicate count, false positives |
| Corruption | Preprocessing / transformation | corrupted payload injection, checksum validation | checksum mismatch count |
| Incorrect transformation | Transformation | wrong mapping injection, transformation assertions | transformation failures |
| Inconsistency | Downstream | out-of-order injection, reconciliation checks | out_of_order_rate, reconciliation flag |

## Pipeline stages and testing
- Ingestion: `pipelines/proposed/pipeline.py` ingestion() handles schema and null checks.
- Preprocessing: enforce_types() and null handling.
- Transformation: transformation_check() and duplicate_check().
- Storage: row count and checksum via DuckDB storage().
- Downstream: reconciliation_check() and out_of_order_check().

## Evaluation metrics
- Detection accuracy: derived from detected issue counts vs ground truth scenario
- Precision/Recall: computed in `experiments/run_experiment.py`
- False positives/negatives: derived from mismatch/quantity
- Latency: baseline vs proposed runtime in each scenario
- Overhead: proposed - baseline

## Scenario coverage
1. clean data
2. duplicated events
3. dropped events
4. corrupted records
5. schema drift
6. out-of-order events
7. mixed failures
