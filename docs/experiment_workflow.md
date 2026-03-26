# Experiment Workflow

1. Generate deterministic base data with seed.
2. Apply scenario-specific faults.
3. Run baseline pipeline (batch mode).
4. Run proposed pipeline (batch mode).
5. Collect stage metrics, detected issues, and latency.
6. Output to `reports/experiment_results.csv` and `reports/experiment_results.md`.

## Mermaid Flow

```mermaid
graph LR
    A[Generate clean data] --> B[Scenario fault injection]
    B --> C[Baseline pipeline run]
    B --> D[Proposed pipeline run]
    C --> E[Collect baseline metrics]
    D --> F[Collect proposed metrics]
    E --> G[Comparison & evaluation]
    F --> G
    G --> H[CSV/Markdown output]
```
