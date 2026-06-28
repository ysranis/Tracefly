# TraceFly MVP — Makefile
# Usage: make <target>
# Run 'make help' to see all commands

.PHONY: help setup db-start db-stop db-reset demo run run-cli clean

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  TraceFly MVP"
	@echo "  ─────────────────────────────────────────────"
	@echo "  First time setup:"
	@echo "    make setup       Install dependencies + start DB + load schema"
	@echo ""
	@echo "  Demo (for recruiters / quick showcase):"
	@echo "    make demo        Load real Bitext dataset + run full pipeline"
	@echo ""
	@echo "  Daily use:"
	@echo "    make run         Start the TraceFly agent (web UI)"
	@echo "    make run-cli     Start the TraceFly agent (CLI mode)"
	@echo "    make db-start    Start the database (Docker)"
	@echo "    make db-stop     Stop the database"
	@echo "    make db-reset    Clear all data and reload demo dataset"
	@echo "  ─────────────────────────────────────────────"
	@echo ""

# ── First-time setup ──────────────────────────────────────────────────────────
setup:
	@echo "Setting up TraceFly..."
	@echo ""
	@echo "[1/4] Checking .env file..."
	@test -f .env || (cp .env.example .env && echo "      Created .env from .env.example — please add your ANTHROPIC_API_KEY")
	@echo "[2/4] Starting database..."
	docker-compose up -d
	@echo "      Waiting for Postgres to be ready..."
	@sleep 5
	@echo "[3/4] Running database schema..."
	docker exec -i tracefly_db psql -U tracefly -d tracefly < database/schema.sql
	@echo "[4/4] Installing Python dependencies..."
	uv pip install -r requirements.txt
	@echo ""
	@echo "Setup complete!"
	@echo ""
	@echo "   Next steps:"
	@echo "   1. Add your ANTHROPIC_API_KEY to .env"
	@echo "   2. Run: make demo"
	@echo ""

# ── Database controls ─────────────────────────────────────────────────────────
db-start:
	@echo "Starting database..."
	docker-compose up -d
	@echo "Database running at localhost:5432"

db-stop:
	@echo "Stopping database..."
	docker-compose down
	@echo "Database stopped (data is saved)"

db-reset:
	@echo "Resetting database and reloading demo data..."
	python demo/load_demo_data.py --reset --limit 1000
	@echo "Database reset with fresh demo data"

# ── Demo ──────────────────────────────────────────────────────────────────────
demo:
	@echo ""
	@echo "TraceFly Demo"
	@echo "============================================"
	@echo ""
	@echo "Step 1: Loading real customer support data from Hugging Face..."
	python demo/load_demo_data.py --limit 1000
	@echo ""
	@echo "Step 2: Starting TraceFly agent..."
	@echo ""
	@echo "============================================"
	@echo "  In the chat that opens, type:"
	@echo "  -> 'Run the full analysis pipeline'"
	@echo "============================================"
	@echo ""
	adk web .

# ── Run ───────────────────────────────────────────────────────────────────────
run:
	@echo "Starting TraceFly agent (web UI)..."
	@echo "   Open: http://localhost:8000"
	@echo "   Type: 'Run the full analysis pipeline'"
	@echo ""
	adk web .

run-cli:
	@echo "Starting TraceFly agent (CLI mode)..."
	adk run tracefly_agent

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned"
