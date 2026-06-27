# run_coverage.ps1
Write-Host "Running tests with coverage..." -ForegroundColor Yellow

pip install pytest pytest-cov

pytest --cov=. --cov-report=term --cov-report=html --cov-report=xml test_*.py -v

Write-Host ""
Write-Host "Coverage report generated in htmlcov/index.html" -ForegroundColor Green
