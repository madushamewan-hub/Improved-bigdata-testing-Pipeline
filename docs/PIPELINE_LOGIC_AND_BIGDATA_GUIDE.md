# Pipeline Logic and Big-Data Guide

This document explains the architecture, core functions, and operational choices in this repository, with a focus on large-scale / big-data concerns. Read this end-to-end to understand how uploads, parsing, synthetic scenario injection, experiment execution, and result evaluation are implemented — and how to scale them safely.

## 1. High-level architecture

- Frontend (Next.js): user interface for uploads, experiment configuration, progress visualization, and results.
- Backend (FastAPI): REST API that accepts uploads, parses files, stores metadata, and runs experiments.
- Data & Pipeline components: parsers (`backend/file_parser.py`), dataset services (`backend/services/dataset_service.py`), experiment logic (`backend/api/experiments.py`, `backend/services/experiment_service.py`), and pipelines (`pipelines/*`) that emulate baseline and proposed processing.
- Helper and utilities: `backend/utils.py` (sanitizers), `data_generator/order_events.py` (simulated data + injection tools).

For large files we use chunked parsing, sampling, and parallel chunk processing to keep memory bounded and wall-clock latency low.

## 2. Data ingestion and file parsing

Key file: `backend/file_parser.py`.

Responsibilities:
- Detect file format (`get_file_format`).
- Validate size and existence (`validate_file`).
- Parse various formats: CSV/TSV, JSON array, NDJSON (newline-delimited JSON), Parquet, Excel.
- Provide a sanitized preview via `get_preview` that converts numpy and NaN/Inf to JSON-friendly values.

Important details and big-data choices:
- Chunked CSV reading: large CSVs are read with `pandas.read_csv(..., chunksize=...)`. This prevents loading entire files into memory.
- Parallel chunk processing: the parser uses a thread pool to process chunks concurrently, extracting per-chunk samples and inferring per-chunk schema. The system then merges per-chunk schemas and accumulates a bounded sample (controlled by `max_rows`) rather than materializing the entire dataset.
- Sampling: the API accepts `max_rows` (or the UI `sample_rate`) to limit how many rows are materialized and processed end-to-end, enabling fast approximate runs.
- NDJSON handling: stream parse newline JSON, skip malformed lines, and limit records to `max_records` to bound memory.
- Parquet & Arrow: Parquet reading uses `pandas.read_parquet` (and benefits greatly from `pyarrow` and columnar access). For true big-data workloads we recommend running DuckDB or a PyArrow-based scan to enable predicate pushdown and minimize I/O.

Configuration knobs (env / args):
- `FILE_PARSER_CHUNK_SIZE`: chunk size for CSV readers.
- `FILE_PARSER_MAX_ROWS`: maximum rows to materialize for sampling/preview.
- `LARGE_FILE_THRESHOLD_MB`: threshold for switching to chunked/parallel mode.
- `max_workers` (argument): number of threads used for parallel chunk processing.

Usage: `parse_file(path, format, chunksize=..., max_rows=..., max_workers=...)` returns `(df_sample, schema, processing_info)`.

## 3. Upload flow and sanitization

Key file: `backend/api/datasets.py`.

When a user uploads a file:
- The endpoint validates the filename and file format.
- The file is streamed to disk with `shutil.copyfileobj` using a configurable buffer to avoid reading the entire body into memory.
- `FileParser.validate_file` enforces file-size limits.
- `FileParser.parse_file` is invoked; for large files this yields a sampled `DataFrame` and metadata rather than a full materialized dataset.
- The preview is passed through `_sanitize_for_json` (now in `backend/utils.py`) which converts numpy ints/floats and non-finite floats to JSON-safe types/None.

Why the sanitizer matters for big data: sensor or analytic datasets often contain NaN/Inf; attempting to JSON-serialize raw numpy scalars or NaN will cause server errors. Centralized sanitization prevents upload failures.

## 4. Synthetic scenarios & injection (data_generator)

Key file: `data_generator/order_events.py`.

This module provides a base generator (`generate_base_orders`) and injectors:
- `inject_missing` (introduce nulls),
- `inject_duplicates`,
- `inject_corruption` (mutates numeric fields),
- `inject_schema_drift` (change column types), and
- `inject_out_of_order` (shuffle rows randomly).

Design note: the `mixed` scenario composes injectors to emulate realistic multi-issue conditions. When composing injectors, ensure nulls are handled defensively (e.g., `inject_corruption` checks for None before arithmetic), otherwise composed injectors can raise TypeErrors. This repo includes that defensive fix.

Big-data impact: injecting at scale must avoid full materialization. For very large datasets, apply injectors as streaming transforms (process row-by-row, or operate on chunk windows) rather than materializing a full list.

## 5. Experiment execution and evaluation

Key files:
- Request & routing: `backend/api/experiments.py`
- Scenario logic & metrics: `backend/services/experiment_service.py`
- Dataset loading & normalization for pipelines: `backend/services/dataset_service.py`
- Baseline/proposed emulators: `pipelines/*` (simulate checks and run_batch functions)

Flow:
1. API receives `ExperimentRunRequest` with fields: `dataset_id`, `scenario_name`, `mode` (`baseline|proposed|compare`), optional `force_full_scan`, `engine`, `sample_rate`, `max_workers`.
2. Backend resolves dataset metadata and (unless `force_full_scan`) uses `_load_dataset_records` to obtain a normalized set of records. `_load_dataset_records` now accepts `sample_rate` and `max_workers` and passes these to `FileParser.parse_file` to enable fast sampled runs.
3. `_apply_scenario` creates the synthetic scenario view from the source records (using injectors). For large data, we prefer chunked streaming injectors.
4. Baseline simulation runs a lightweight simulator (`simulate_baseline_execution`) to produce quick metrics and stage-level checks.
5. Proposed pipeline executes `pipelines.proposed.run_batch(...)`, returning detailed `prop_metrics` and `check_evidence` that are mapped into stage-check results.
6. Evaluation functions (`_build_evaluation_context`, `_compute_exact_evaluation_metrics`, `_derive_proposed_result_metrics`) combine pipeline metrics, detection counts, and derived evaluation metrics (precision, recall, detection accuracy) and persist `ExperimentRun` and `PipelineResult` rows.

Scale considerations:
- Use `sample_rate` to get approximate results quickly. The UI exposes this as a percent — e.g., 10% sampling gives fast feedback while conserving CPU.
- `max_workers` allows the parser to parallelize per-chunk processing; increase for more CPU cores.
- `force_full_scan` runs a complete analysis, which may be slow and memory-intensive for very large files. Prefer background jobs for full scans.

## 6. Performance strategies and recommendations

1. Offload long runs to a background worker
- Use Celery, RQ, or FastAPI `BackgroundTasks` + a worker process. Return job id immediately and push progress via SSE or WebSocket.

2. Prefer columnar access and SQL-style scanning
- Use DuckDB (Python API) or direct PyArrow/Parquet scanning for large CSV/Parquet files: `duckdb.read_csv_auto()` or `duckdb.query('SELECT ...')` can scan FAST with vectorized operators and minimal Python crossing.

3. Chunked + parallel processing
- Keep chunk size tuned (`FILE_PARSER_CHUNK_SIZE`). Use a `ThreadPoolExecutor` for I/O-bound parsing and `ProcessPoolExecutor` if per-chunk CPU checks are heavy (pickling overhead is a tradeoff).

4. Sampling & progressive refinement
- Provide a `sample_rate` for fast approximate runs. Optionally implement progressive runs where an initial sample is shown, and a background worker refines the results over time by scanning more chunks.

5. Avoid full materialization
- Compute summaries, sketches (HyperLogLog for distinct, quantiles, histograms), and small samples rather than returning full datasets.

6. Parallelize independent checks
- Run schema checks, null checks, dedup checks, and checksum validations in parallel and combine results.

7. Use approximate algorithms where acceptable
- Bloom filters for membership, HyperLogLog for distinct counts, t-digest for quantiles — these dramatically reduce time and memory.

8. Partitioning and predicate pushdown
- For repeated runs, store datasets as Parquet partitioned by a natural key so runs can read only relevant partitions.

9. Caching
- Cache parsed schema, checksums, and aggregated stats in a lightweight key-value store (Redis) to accelerate repeated analyses.

10. Monitoring & profiling
- Add timing around each check (per-stage timing), use `pyinstrument` or `cProfile` in dev to find hotspots, then optimize I/O (DuckDB) or CPU (parallel processing) accordingly.

## 7. API and UI knobs (how to use)

Run a sampled experiment (example):

```bash
curl -X POST http://localhost:8000/api/experiments/run \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":1,"scenario_name":"mixed","mode":"compare","sample_rate":0.1,"max_workers":4}'
```

UI controls:
- `Sample Rate (%)`: lower means faster approximate result.
- `Parser Workers`: number of threads used during chunked parse.
- `Force Full Scan`: requests a full reparse of the dataset on disk (expensive).

## 8. Troubleshooting common issues

- Unexpected JSON errors: ensure sanitization (`backend/utils.py._sanitize_for_json`) is used when returning previews/result payloads.
- Mixed-scenario crashes: check injector order and null-safety in `data_generator/order_events.py` (the repo includes a defensive fix for `inject_corruption`).
- Memory pressure: use `sample_rate` or increase chunking; prefer DuckDB for large CSVs.
- Slow disk I/O: try converting CSVs to Parquet to exploit columnar reads and predicate pushdown.

## 9. Next enhancements (roadmap)

1. Add a background job queue + progress streaming (SSE) for full scans.
2. Integrate DuckDB for fast in-process SQL scans and replace heavy Python loops.
3. Implement approximate-check variants using sketches and Bloom filters.
4. Add per-check instrumentation exported to Prometheus.
5. Expand parser parallelism to NDJSON and Parquet (worker pools) and implement streaming injectors for the `mixed` composition.

## 10. Appendix — Key functions (summary)

- `FileParser.parse_file(path, format, chunksize, max_rows, max_workers)` — parse various formats, use chunked+parallel CSV processing and return `(df_sample, schema, processing_info)`.
- `FileParser.get_preview(df, rows)` — returns sanitized JSON preview for UI.
- `backend/utils._sanitize_for_json(value)` — recursively convert numpy scalars and non-finite floats to JSON-friendly types.
- `backend/api/datasets.upload_dataset` — handles file streaming, parse, persist `Dataset` metadata, and return preview.
- `backend/api/experiments.run_experiment` — master endpoint to run baseline/proposed/comparison, accepts `sample_rate` and `max_workers`.
- `backend/services/dataset_service._load_dataset_records(dataset, sample_rate, max_workers)` — normalizes and returns pipeline-ready records; uses sampling and parser knobs.
- `backend/services/experiment_service._apply_scenario(records, scenario_name)` — apply synthetic injectors.

---

If you'd like, I can:

- Commit this doc to the repo (done) and open a short README entry linking to it.
- Add diagrams (Mermaid) visualizing the pipeline stages and parallel execution.
- Implement one of the roadmap items (background queue, DuckDB integration) next.

File: `docs/PIPELINE_LOGIC_AND_BIGDATA_GUIDE.md`

## 11. Thesis Context — Research Goals and Contributions

This project doubles as an engineering deliverable and a thesis-grade study on stage-aware integrity testing for large-scale data pipelines. The thesis framing clarifies experimental design, hypotheses, and evaluation criteria.

- Research objectives: quantify the trade-offs between detection accuracy and latency when adding integrity checks; demonstrate stage-aware testing reduces downstream failure cost; show sampling + parallel parsing yields accurate approximations with large time savings.
- Hypotheses:
  - H1: Stage-aware checks (performed close to ingestion and preprocessing) reduce end-to-end remediation cost compared to monolithic post-hoc checks.
  - H2: Sampling (10–20%) with validated statistical summaries provides comparable detection metrics for many anomaly types (duplication, schema drift), reducing compute by an order of magnitude.
  - H3: Integrating columnar scan engines (DuckDB/PyArrow) further reduces scan overhead by 5–20× vs pure Python/pandas for large CSVs.

- Contributions:
  - A practical framework for multi-format upload, sampled and parallel parsing, stage-aware checks, and comparative evaluation (baseline vs proposed).
  - Reproducible experiment harness and metrics collection suitable for academic reporting and industrial benchmarking.

## 12. Stage-Aware Testing: Approach and Best Practices

Stage-aware testing means applying targeted checks at each pipeline stage rather than relying solely on end-to-end assertions. This reduces time-to-detection and isolates faults to a particular processing stage.

Pipeline stages (used in the system): Ingestion → Preprocessing → Transformation → Storage → Output

Recommended per-stage checks:

- Ingestion: malformed payloads, schema validity, null spikes, freshness (lateness) checks.
- Preprocessing: type enforcement, normalization failures, unit conversions, checksum verification.
- Transformation: duplicate mapping checks, transformation validation, mapping/lookup failures.
- Storage: row count reconciliation, checksum integrity, partition completeness.
- Output: event ordering, downstream reconciliation, end-to-end latency regressions.

Implementation notes:
- Stage mapping: `pipelines.proposed` produces `check_evidence` with `check_id` which is mapped to stage names in `backend/api/experiments.py`. Keep mapping deterministic to enable stage-level metrics aggregation.
- Lightweight gating: Fail-fast at stages that can block downstream work (e.g., schema mismatch). For batch experiments mark the stage as 'warning' rather than aborting to collect full metrics.
- Isolation and instrumentation: time and count each check separately and store as `StageCheckResult` rows. This enables fine-grained analysis of which stage consumes the most time and produces the most signals.

Benefits in big-data context:
- Early detection reduces compute waste; e.g., detecting schema drift at ingestion avoids heavy transformations on bad data.
- Parallel stage checks allow concurrency and exploitation of multi-core hosts.

## 13. Industrial Evaluation — Metrics, Benchmarks, and SLAs

Core metrics to report (mapped to repo's computed values):

- Latency (ms): per-pipeline and per-stage latency measured end-to-end and per-check.
- Throughput (rows/sec): how many rows the pipeline can analyze per second under given resources.
- Defect Detection Rate (DDR): proportion of real injected issues correctly identified.
- Precision / Recall: classical detection metrics for alarms (false positives reduce trust; false negatives miss defects).
- False Positive Rate (FPR) / False Negative Rate (FNR): critical for operational adoption.
- Resource usage: CPU-hours and peak memory per experiment.
- Cost estimate: map resource usage to cost-per-run for cloud billing models.

Benchmark methodology:

1. Controlled synthetic benchmarks: run experiments with injectors at known rates (duplicated, dropped, corrupted, out_of_order, mixed) across dataset sizes (10k, 100k, 1M, 10M rows) and record metrics.
2. Real-world validation: run on uploaded production-like datasets without injection (measure baseline false positives and unexplained detections).
3. Scaling curve: measure latency and throughput as a function of dataset size and number of `max_workers`.

Failure injection and reliability testing:
- Inject gradual and burst corruption to test recovery semantics and detection latency.
- Test partial failures (e.g., disk I/O slowdown, worker crashes) and observe pipeline degradation.

Operational SLAs & thresholds (example):
- Small runs (≤100k rows): 90% of experiments should finish within 30s.
- Large runs (~1M rows): configure sampling by default; full scans may take minutes — recommend background job scheduling and quota enforcement.
- Precision target: ≥ 0.8 for synthetic injected defects. Recall target: ≥ 0.8 for high-severity defect classes.

Reporting and dashboards:
- Export experiment summaries to CSV/Excel (`/api/experiments/{id}/export.xlsx`) for offline analysis.
- Dashboard should display per-stage timing, detection counts, and a composite score (example implemented in `pipelines.proposed` summary).

## 14. Sector Targets and Industrial Profiles

This project includes sector-target awareness (see `pipelines/sector_targets.py`), enabling evaluation against industry-specific thresholds. For industrial evaluation, define:

- Sector profile (e.g., healthcare, finance, retail) with target thresholds for accuracy, timeliness, completeness, and integrity.
- Compliance gates: per-sector must-pass checks (e.g., patient data must not have null patient_id beyond 0.01%).

Use the `summary_json` in `PipelineResult` to encode sector attainment and produce per-sector compliance reports.

## 15. Experimental Design & Reproducibility

For thesis-grade experiments and auditable industrial benchmarks, follow these practices:

- Fix random seeds for synthetic generators (`generate_base_orders(seed=...)`) and document seed values in experiment metadata.
- Version control dataset snapshots or record exact file checksums used in each experiment run.
- Store experiment parameters: `sample_rate`, `max_workers`, `engine`, `scenario_name`, and `force_full_scan` in the `ExperimentRun` record.
- Repeat experiments multiple times and report mean ± s.d. for stochastic injectors.

Reproducible pipeline run example (script):

```bash
# Run a sampled compare experiment
curl -X POST http://localhost:8000/api/experiments/run \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":1,"scenario_name":"mixed","mode":"compare","sample_rate":0.1,"max_workers":8}'
```

## 16. CI, Benchmarks, and Automation

- Integrate repeatable benchmark jobs into CI using GitHub Actions or a CI runner that can allocate larger machines for the large-run stages.
- Keep small quick tests in PR checks; offload heavy benchmarking to scheduled workflows.
- Store benchmark artifacts (CSV/Excel) in the repo or a secure blob store for later analysis.

## 17. Governance, Security, and Privacy

- Sensitive datasets: avoid storing raw PII in experiment artifacts. Provide anonymization or synthetic generators for reproducible tests.
- RBAC for UI / API: in industrial settings add authentication and authorization for dataset access and experiment runs.
- Quotas and resource limits: enforce per-user or per-project constraints to avoid noisy neighbors consuming all cluster resources.

## 18. Closing notes and next steps

This guide now contains both engineering details and an academic framing suitable for thesis writing or industrial adoption. Next recommended work items (repeat of roadmap): integrate DuckDB, add a background job queue, implement sketches for approximate checks, and add per-stage Prometheus instrumentation.

---

Updated: May 19, 2026

