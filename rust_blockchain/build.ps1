# build.ps1 - Build Rust blockchain component
cd rust_blockchain
cargo build --release
Write-Host "✅ Rust component built successfully!" -ForegroundColor Green
Write-Host "📦 Library: target/release/absolute_blockchain.dll" -ForegroundColor Cyan
