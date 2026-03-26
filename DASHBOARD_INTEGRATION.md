# Data Quality Pipeline - Dashboard Integration Guide

## Overview
This document describes the complete integration of the Dashboard UI with the Backend API for the Data Quality Pipeline research project.

## System Architecture

### Backend (FastAPI)
- **Location**: `backend/main.py`
- **Port**: 8000
- **CORS**: Enabled for all origins

#### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/flows` | GET | Get pipeline flow definitions for visualization |
| `/api/upload` | POST | Upload CSV dataset |
| `/api/datasets` | GET | List all uploaded datasets |
| `/api/experiments/run` | POST | Execute an experiment |
| `/api/dashboard/stats` | GET | Get aggregated dashboard statistics |
| `/api/experiments/{exp_id}` | GET | Get specific experiment details |
| `/api/experiments` | GET | List all experiments |
| `/api/stage-checks/{exp_id}` | GET | Get stage-level check results |

### Frontend (Next.js)
- **Location**: `ui/`
- **Port**: 3000
- **Framework**: Next.js 13+ with App Router

#### Dashboard Pages
- `/dashboard` - Main overview with KPI cards
- `/dashboard/flows` - Pipeline flow visualization (baseline vs proposed)
- `/dashboard/upload` - Data upload interface
- `/dashboard/experiments` - Run new experiments
- `/dashboard/results` - Side-by-side results comparison
- `/dashboard/stage-checks` - Stage-level validation checks
- `/dashboard/history` - Experiment history log
- `/dashboard/reports` - Generate and export reports

## Key Features

### 1. Dashboard Overview
- KPI cards showing:
  - Total experiments run
  - Baseline detection rate
  - Proposed detection rate
  - Average improvement
  - Average latency overhead
  - False negatives reduction

### 2. Pipeline Flow Visualization
- **Baseline Pipeline** (5 stages):
  - Ingestion (basic_schema_read)
  - Preprocessing (optional_type_conversion)
  - Transformation (basic_math)
  - Storage (file_write)
  - Output (manual_review)

- **Proposed Pipeline** (5 stages with comprehensive checks):
  - Ingestion (schema_validation, null_check)
  - Preprocessing (duplicate_detection, checksum_validate)
  - Transformation (assertion_check, type_validation)
  - Storage (row_count_check, checksum_reconcile)
  - Output (downstream_validation, consistency_check)

### 3. Experiment Execution
- Upload custom datasets (CSV format)
- Select data quality scenarios:
  - clean
  - duplicated
  - dropped (missing data)
  - corrupted
  - schema_drift
  - out_of_order
  - mixed
- Run experiments in three modes:
  - baseline only
  - proposed only
  - compare (both pipelines)

### 4. Results Comparison
- Side-by-side metric comparison:
  - Detection accuracy
  - Precision & recall
  - False positives & negatives
  - Detected issues by type
  - Latency comparison
  - Overhead calculation

### 5. Stage-Level Checks
- Detailed breakdown by pipeline stage
- Check-level results and issue counts
- Issue type categorization
- Pass/fail status per check

### 6. Reports & Export
- View aggregated experiment statistics
- Export data in two formats:
  - **CSV**: Tabular format for spreadsheets
  - **JSON**: Structured data for further analysis
- Thesis summary highlighting key findings

## Data Flow

```
User Upload → Backend API → Database (SQLAlchemy)
           ↓
      Dataset Created
           ↓
  Experiment Triggered → Baseline Pipeline Simulation
                      → Proposed Pipeline Simulation
                      → Results Stored in DB
           ↓
    Frontend Queries API → Dashboard Displays Results
```

## Running the System

### Prerequisites
- Python 3.8+
- Node.js 16+
- FastAPI dependencies (see backend/requirements.txt)
- Next.js dependencies (see ui/package.json)

### Backend Setup
```bash
cd backend
python -m pip install -r requirements.txt
python main.py
# Server runs on http://localhost:8000
```

### Frontend Setup
```bash
cd ui
npm install
npm run dev
# Server runs on http://localhost:3000
```

### Database
- SQLAlchemy ORM with SQLite (default)
- Auto-creates tables on initialization
- Stores datasets, experiments, pipeline results, and stage check results

## Key Data Models

### Dataset
- id, name, type, row_count, schema_json, file_path, uploaded_at

### ExperimentRun
- id, dataset_id, scenario_name, mode, status, created_at, completed_at

### PipelineResult
- experiment_run_id, pipeline_type (baseline/proposed)
- Detection metrics: accuracy, precision, recall, false_pos/neg
- Issue detection: loss, duplicates, corruption, inconsistency
- Performance: latency_ms, overhead_ms

### StageCheckResult
- experiment_run_id, pipeline_type, stage_name, check_name
- issue_type, passed (bool), findings_count

## Testing

Run the test suite to verify system functionality:
```bash
cd Project
python -m pytest tests/ -q
```

## Documentation
- Architecture: `docs/architecture.md`
- Experiment workflow: `docs/experiment_workflow.md`
- Thesis mapping: `docs/thesis_mapping.md`

## Troubleshooting

### API Connection Issues
- Ensure backend is running on port 8000
- Check CORS is enabled
- Verify frontend is on port 3000

### Database Issues
- Delete old database and let SQLAlchemy recreate it
- Check database permissions

### Dataset Upload Fails
- Ensure CSV format
- Check file size limits
- Verify write permissions in `uploads/` directory

## Performance Considerations
- Experiment simulation with 100+ rows takes ~50-100ms
- Dashboard aggregation queries optimize with database indexes
- Frontend implements client-side caching where appropriate

## Future Enhancements
- Real pipeline execution with actual data
- Custom check implementation interface
- Advanced filtering and search in results
- Real-time experiment progress tracking
- Export to additional formats (Parquet, Excel)
- Integration with CI/CD pipelines
