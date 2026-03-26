# Stage-Aware Integrity-Testing Pipeline MVP

This project implements a Minimum Viable Product (MVP) for a stage-aware integrity-testing pipeline designed to detect data integrity issues in data processing workflows. The pipeline uses Docker for containerization, Kafka for messaging, PySpark for data processing, and PostgreSQL for storage.

## Architecture

The pipeline consists of two implementations:
- **Baseline Pipeline**: A standard data processing pipeline without integrity checks.
- **Proposed Pipeline**: An enhanced pipeline with validation rules at ingestion, transformation, storage, and output stages.

### Architecture Diagram

```mermaid
graph TD
    A[Data Generator] --> B[Kafka Producer]
    B --> C[Kafka Topic]
    C --> D[Ingestion]
    D --> E[Transformation (PySpark)]
    E --> F[Storage (PostgreSQL)]
    F --> G[Output]

    D --> H{Validation?}
    E --> I{Validation?}
    F --> J{Validation?}
    G --> K{Validation?}

    H --> L[Baseline: No]
    H --> M[Proposed: Yes]
    I --> L
    I --> M
    J --> L
    J --> M
    K --> L
    K --> M
```

## Features

- **Integrity Issue Detection**: Targets data loss, duplication, corruption, incorrect transformations, and inconsistency.
- **Synthetic Fault Injection**: Injects faults for testing purposes.
- **Validation Rules**: Checks at multiple stages.
- **Automated Testing**: Pytest-based unit tests.
- **Experiment Scripts**: Compare baseline vs. proposed pipelines with metrics like precision, recall, false positives, false negatives, detection counts, and latency overhead.

## Setup

1. **Prerequisites**:
   - Docker and Docker Compose
   - Python 3.8+
   - PySpark

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start Infrastructure**:
   ```bash
   cd docker
   docker-compose up -d
   ```

4. **Run Tests**:
   ```bash
   pytest tests/
   ```

5. **Run Experiments**:
   ```bash
   python experiments/run_experiment.py
   ```

## Project Structure

```
.
├── docker/
│   └── docker-compose.yml
├── src/
│   ├── baseline/
│   │   └── pipeline.py
│   ├── proposed/
│   │   └── pipeline.py
│   └── common/
│       ├── config.py
│       ├── data_generator.py
│       ├── fault_injection.py
│       └── validation.py
├── tests/
│   └── test_validation.py
├── experiments/
│   └── run_experiment.py
├── docs/
│   ├── README.md
│   └── architecture.md
├── requirements.txt
└── .github/
    └── copilot-instructions.md
```

## Experiments

The experiment script generates synthetic data, injects faults, runs both pipelines, and outputs metrics to `experiments/results.csv` and `experiments/results.md`.

### Metrics

- Precision: TP / (TP + FP)
- Recall: TP / (TP + FN)
- False Positives: FP
- False Negatives: FN
- Detection Counts: Number of issues detected
- Latency Overhead: Proposed latency - Baseline latency

## License

MIT