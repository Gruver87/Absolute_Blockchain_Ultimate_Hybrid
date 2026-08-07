# Absolute Blockchain Ultimate Hybrid — Linux/macOS operator entrypoints
#
# Thin wrappers over existing bash/Python scripts. PowerShell remains the
# Windows operator path (scripts/*.ps1). Honesty: make green ≠ public mainnet.
#
#   make help
#   make build
#   make test-quick
#   make test-gate
#   make verify
#   make verify-industrial
#   make mesh-up

.PHONY: help build test-quick test-gate verify verify-industrial mesh-up

help:
	@echo "Absolute Blockchain — make targets (Linux/macOS)"
	@echo ""
	@echo "  make build               Build+install abs_native (scripts/build_native.sh)"
	@echo "  make test-quick          Industrial waves verify (scripts/verify_industrial_waves.py)"
	@echo "  make test-gate           Industrial gate only (scripts/industrial_gate.py)"
	@echo "  make verify              Unified project check (quick)"
	@echo "  make verify-industrial   Unified check + tip-v2 48h soak evidence"
	@echo "  make mesh-up             3-node prod Docker mesh (scripts/docker_prod_3node.sh)"
	@echo ""
	@echo "Windows: .\\scripts\\verify_project.ps1  (Quick / Standard / Industrial / Max)"
	@echo "CI:      .github/workflows/test.yml (already runs Ubuntu + native + pytest)"

build:
	bash scripts/build_native.sh

test-quick:
	python scripts/verify_industrial_waves.py

test-gate:
	python scripts/industrial_gate.py

verify:
	python scripts/verify_project.py --mode quick

verify-industrial:
	python scripts/verify_project.py --mode industrial --min-soak-hours 48

mesh-up:
	bash scripts/docker_prod_3node.sh
