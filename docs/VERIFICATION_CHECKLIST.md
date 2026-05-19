# Verification Checklist: Data Quality Pipeline Dashboard

## Prerequisites Check
- [ ] Python 3.8+ installed
- [ ] Node.js 16+ installed
- [ ] Git accessible
- [ ] Ports 3000 and 8000 available

## Backend Verification

### 1. Check Dependencies
```bash
cd backend
python -c "import fastapi, sqlalchemy, pandas; print('✓ Core dependencies installed')"
```
✅ Expected: No errors

### 2. Start Backend Server
```bash
cd backend
python main.py
```
✅ Expected output:
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3. Verify API Health
```bash
curl http://localhost:8000/health
```
✅ Expected: `{"status":"ok"}`

### 4. Verify All Endpoints
```bash
# Check flows endpoint
curl http://localhost:8000/api/flows | jq '.baseline.nodes | length'

# Check datasets
curl http://localhost:8000/api/datasets

# Check stats
curl http://localhost:8000/api/dashboard/stats
```
✅ Expected: Valid JSON responses from all endpoints

## Frontend Verification

### 1. Check Dependencies
```bash
cd ui
npm list next react react-dom recharts
```
✅ Expected: No unmet peer dependencies

### 2. Build Frontend
```bash
cd ui
npm run build
```
✅ Expected: 
- No build errors
- Successful compilation of all pages
- Output in `.next/` directory

### 3. Start Frontend Server
```bash
cd ui
npm run dev
```
✅ Expected output:
```
- ready started server on 0.0.0.0:3000, url: http://localhost:3000
- event compiled client and server successfully
```

### 4. Test Frontend Routes
Access these URLs in browser:
- [ ] http://localhost:3000/dashboard - Main dashboard
- [ ] http://localhost:3000/dashboard/flows - Pipeline flows
- [ ] http://localhost:3000/dashboard/upload - Upload page
- [ ] http://localhost:3000/dashboard/experiments - Experiments
- [ ] http://localhost:3000/dashboard/results - Results comparison
- [ ] http://localhost:3000/dashboard/stage-checks - Stage checks
- [ ] http://localhost:3000/dashboard/history - History
- [ ] http://localhost:3000/dashboard/reports - Reports

✅ Expected: All pages load without errors

## Integration Tests

### 1. Test Frontend-Backend Connection
In browser console on Dashboard page:
```javascript
fetch('http://localhost:8000/api/dashboard/stats')
  .then(r => r.json())
  .then(d => console.log('✓ Connection OK', d))
  .catch(e => console.error('✗ Connection failed', e))
```
✅ Expected: Dashboard stats printed to console

### 2. Test Data Upload
1. Navigate to http://localhost:3000/dashboard/upload
2. Create sample CSV:
```csv
order_id,customer_id,amount,date
1,100,50.00,2024-01-01
2,101,75.50,2024-01-02
3,102,100.00,2024-01-03
```
3. Upload file
4. Check console for "Upload successful"
✅ Expected: File appears in `/uploads` directory

### 3. Test Experiment Execution
1. Go to http://localhost:3000/dashboard/experiments
2. Select uploaded dataset
3. Select "clean" scenario
4. Choose "compare" mode
5. Click "Run Experiment"
6. Wait for completion
✅ Expected: 
- No errors in browser console
- Results displayed in results section
- Database entry created

### 4. Test Results Display
1. Navigate to http://localhost:3000/dashboard/results
2. Click on experiment
✅ Expected: Detailed metrics shown

### 5. Test Exports
1. Go to http://localhost:3000/dashboard/reports
2. Click "Download as CSV"
✅ Expected: CSV file downloaded with experiment data

3. Click "Download as JSON"
✅ Expected: JSON file downloaded with full experiment info

## Database Verification

### 1. Check Database File
```bash
ls -la *.db  # SQLite database file should exist
```

### 2. Query Database
```bash
sqlite3 *.db ".tables"
```
✅ Expected: Tables listed: dataset, experiment_run, pipeline_result, stage_check_result

### 3. Check Data Population
```bash
sqlite3 *.db "SELECT COUNT(*) FROM experiment_run;"
```
✅ Expected: Number ≥ number of experiments run

## Performance Tests

### 1. Dashboard Load Time
- Open DevTools → Network tab
- Refresh dashboard page
✅ Expected: Page loads in < 2 seconds

### 2. API Response Time
```bash
# Time the stats API
time curl http://localhost:8000/api/dashboard/stats > /dev/null
```
✅ Expected: < 500ms response time

### 3. Experiment Execution Time
- Run single experiment
- Note completion time
✅ Expected: < 5 seconds for 100 rows

## Component-Specific Checks

### Navigation
- [ ] All sidebar links clickable
- [ ] Active page highlighted
- [ ] Back navigation works

### Dashboard KPIs
- [ ] Shows total experiments count
- [ ] Shows detection rates
- [ ] Shows improvement percentage
- [ ] Shows overhead in ms

### Pipeline Flow
- [ ] Baseline nodes visible (5 stages)
- [ ] Proposed nodes visible (5 stages)
- [ ] Edges connecting nodes
- [ ] Check labels visible

### Experiments
- [ ] Dataset dropdown populated
- [ ] Scenario options available
- [ ] Mode selection works
- [ ] Run button functional

### Results
- [ ] Metrics displayed accurately
- [ ] Comparison shows differences
- [ ] Charts render without errors

### Reports
- [ ] Summary stats correct
- [ ] CSV export contains data
- [ ] JSON export valid
- [ ] Thesis summary displayed

## Error Handling Tests

### 1. Missing Backend
- Stop backend server
- Refresh frontend page
✅ Expected: Graceful error message (not blank page)

### 2. Invalid Dataset
- Try uploading non-CSV file
✅ Expected: Error message about file format

### 3. Missing Dataset Selection
- Click Run without selecting dataset
✅ Expected: Error: "Please select a dataset"

## Cleanup & Reset

### Clear All Data
```bash
rm *.db              # Remove database
rm -rf uploads/*     # Clear uploaded files
rm -rf reports/*     # Clear generated reports
```

### Restart Fresh
1. Backend: `python main.py`
2. Frontend: `npm run dev`
3. Upload sample data
4. Run test experiment

## Success Criteria

All checks passed if:
- ✅ Backend runs on port 8000 with no errors
- ✅ Frontend runs on port 3000 with no errors
- ✅ All 8 dashboard pages load
- ✅ API endpoints respond with valid JSON
- ✅ Frontend connects to backend
- ✅ Experiments can be uploaded and run
- ✅ Results display correctly
- ✅ Reports can be exported
- ✅ Database stores all data properly
- ✅ Navigation works across all pages

## Troubleshooting

### Backend Won't Start
```bash
# Check port availability
netstat -tln | grep 8000

# Check Python dependencies
pip list | grep fastapi

# Try explicit port
python main.py --port 8001
```

### Frontend Won't Start
```bash
# Clear node_modules
rm -rf node_modules
npm install

# Check Node version
node --version  # Should be 16+

# Try explicit port
npm run dev -- -p 3001
```

### Connection Issues
```bash
# Check CORS is enabled (in main.py)
# Check firewall allows 3000 and 8000
# Test with curl:
curl -X GET http://localhost:8000/health
```

### Database Corruption
- Delete *.db file
- Restart backend (auto-creates)

## Performance Benchmarks

Expected metrics:
- Page load: < 2s
- API response: < 500ms
- Experiment run: < 5s
- Export generation: < 1s

---

**TEST STATUS**: Ready for validation
**ENVIRONMENT**: Development
**NEXT STEP**: Begin research experiments
