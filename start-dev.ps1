# Start backend and frontend (PowerShell)
# Usage: Run this from project root in PowerShell

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
& .\.venv\Scripts\Activate.ps1

Start-Process powershell -ArgumentList '-NoExit','-Command','& .\.venv\Scripts\Activate.ps1; uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000' -WindowStyle Normal
Start-Process powershell -ArgumentList '-NoExit','-Command','cd ui; npm run dev' -WindowStyle Normal

Write-Host "Started backend (uvicorn) and frontend (Next.js)." -ForegroundColor Green
