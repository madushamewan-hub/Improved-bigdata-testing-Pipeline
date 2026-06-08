# Data Quality Pipeline: Integrity Testing Dashboard

A thesis-grade prototype to implement and validate stage-aware data integrity testing for batch data pipelines. This system compares a baseline pipeline (minimal checks) with a proposed pipeline (comprehensive stage-level validations) across multiple data quality scenarios.

## 🎯 Research Objective

Validate the hypothesis:
> **Adding systematic stage-level data quality validations improves overall data integrity detection while maintaining acceptable performance overhead.**


### Prerequisites
- Python 3.8+
- Node.js 16+
- Ports 3000 & 8000 available

### Step 1: Start Backend (Terminal 1)
```bash
cd backend
pip install -r requirements.txt
python main.py
# Runs on http://localhost:8000
```

### Step 2: Start Frontend (Terminal 2)
```bash
cd ui
npm install
npm run dev
# Runs on http://localhost:3000
```

### Step 3: Access Dashboard
Open browser: **http://localhost:3000/dashboard**


## 🔄 Pipeline Comparison

### Baseline Pipeline (Minimal Approach)
```
Ingestion → Preprocessing → Transformation → Storage → Output
   ✓              ✓               ✓            ✓        ✓ manual review
Checks: basic_schema_read, optional_type_conversion, basic_math, file_write
```

### Proposed Pipeline (Comprehensive Approach)
```
Ingestion → Preprocessing → Transformation → Storage → Output
  ✓✓✓          ✓✓✓             ✓✓✓          ✓✓✓      ✓✓✓
- Schema validation + null checking
- Duplicate detection + checksum validation
- Assertion checking + type validation
- Row count checking + checksum reconciliation
- Downstream validation + consistency checking
```

## 📈 Key Metrics Tracked

- **Detection Accuracy**: % of quality issues found
- **Precision**: % of detections that were correct
- **Recall**: % of actual issues caught
- **False Positives/Negatives**: Error analysis
- **Latency**: Execution time in milliseconds
- **Overhead**: Additional time for proposed pipeline
- **Issue Categories**: Loss, duplicates, corruption, inconsistency

## API Endpoints

### Dataset Management
- `POST /api/upload` - Upload CSV dataset
- `GET /api/datasets` - List all datasets

### Experiment Execution
- `POST /api/experiments/run` - Run experiment (baseline/proposed/compare)
- `GET /api/experiments` - List all experiments
- `GET /api/experiments/{exp_id}` - Get experiment details

### Analytics
- `GET /api/dashboard/stats` - Aggregated statistics
- `GET /api/stage-checks/{exp_id}` - Stage-level check results

### Visualization
- `GET /api/flows` - Pipeline architecture diagrams



## 🛠️ Development

Set-Location "c:\Users\ASUS\Downloads\Project"
py -3.11 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

### Backend Development
```bash
cd backend
python -m pip install -r requirements.txt
python main.py

# With auto-reload
uvicorn main:app --reload
```

Set-Location "c:\Users\ASUS\Downloads\Project\ui"
npm run dev
### Frontend Development
```bash
cd ui
npm install
npm run dev

# Build for production
npm run build
npm start
```

### Database Reset
```bash
# Delete database to reset
rm *.db

# Backend will auto-create on startup
```

## 📝 Example Workflow

1. **Upload Data**
   ```
   Dashboard → Upload Data → Select CSV → Click Upload
   ```

2. **Run Experiment**
   ```
   Dashboard → Run Experiments → Select Dataset → Choose "duplicated"
   → Mode "compare" → Click Run
   ```

3. **View Results**
   ```
   Dashboard → Results Comparison → Click experiment
   → See metrics comparison
   ```

4. **Export Report**
   ```
   Dashboard → Reports → Click "Download as CSV/JSON"
   ```

## 🙏 Acknowledgments

- FastAPI & SQLAlchemy for robust backend framework
- Next.js & React for dynamic UI
- Recharts for data visualization
- Research supervisors and committee

---