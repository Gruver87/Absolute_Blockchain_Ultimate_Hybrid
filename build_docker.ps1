# build_docker.ps1
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t absolute-blockchain:latest .

Write-Host ""
Write-Host "Running single node:" -ForegroundColor Green
docker run -p 8545:8545 -p 8000:8000 absolute-blockchain:latest

Write-Host ""
Write-Host "Or run 3-node cluster:" -ForegroundColor Green
Write-Host "docker-compose up"
