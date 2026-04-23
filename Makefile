# ═══════════════════════════════════════════════════════════════════
#  AI DevOps Copilot — Developer Makefile
#  Single source of truth for all development commands
#
#  Usage: make <target>
#  Run 'make help' to see all available targets
# ═══════════════════════════════════════════════════════════════════

.PHONY: help setup dev test lint build deploy tf-init tf-plan tf-apply tf-destroy clean logs health

# ── Colors ────────────────────────────────────────────────────────
CYAN  := \033[0;36m
GREEN := \033[0;32m
AMBER := \033[0;33m
RED   := \033[0;31m
RESET := \033[0m

# ── Config ────────────────────────────────────────────────────────
BACKEND_DIR  := backend
FRONTEND_DIR := frontend
TF_DIR       := infra/terraform
TF_VARS      := infra/terraform/prod.tfvars

# Load .env if it exists
-include backend/.env
export

# ══════════════════════════════════════════════════════════════════
# HELP
# ══════════════════════════════════════════════════════════════════

help:  ## Show this help message
	@echo ""
	@echo "$(CYAN)AI DevOps Copilot — Make Targets$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ══════════════════════════════════════════════════════════════════
# SETUP
# ══════════════════════════════════════════════════════════════════

setup: setup-backend setup-frontend setup-env  ## Full local setup (backend + frontend + .env)
	@echo "$(GREEN)✅ Setup complete! Run 'make dev' to start.$(RESET)"

setup-backend:  ## Install Python dependencies
	@echo "$(CYAN)▶ Setting up backend...$(RESET)"
	cd $(BACKEND_DIR) && \
		python3 -m venv venv && \
		. venv/bin/activate && \
		pip install -r requirements.txt && \
		pip install pytest pytest-asyncio httpx ruff
	@echo "$(GREEN)  ✅ Backend ready$(RESET)"

setup-frontend:  ## Install Node.js dependencies
	@echo "$(CYAN)▶ Setting up frontend...$(RESET)"
	cd $(FRONTEND_DIR) && npm install
	@echo "$(GREEN)  ✅ Frontend ready$(RESET)"

setup-env:  ## Create .env from example if not exists
	@if [ ! -f $(BACKEND_DIR)/.env ]; then \
		cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env; \
		echo "$(AMBER)  ⚠️  Created backend/.env — add your GROQ_API_KEY$(RESET)"; \
	else \
		echo "  ℹ️  backend/.env already exists"; \
	fi
	@if [ ! -f $(FRONTEND_DIR)/.env ]; then \
		cp $(FRONTEND_DIR)/.env.example $(FRONTEND_DIR)/.env 2>/dev/null || true; \
	fi

# ══════════════════════════════════════════════════════════════════
# DEVELOPMENT
# ══════════════════════════════════════════════════════════════════

dev:  ## Start both backend and frontend in development mode
	@echo "$(CYAN)▶ Starting dev servers...$(RESET)"
	@echo "  Backend: http://localhost:8000"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Press Ctrl+C to stop"
	@trap 'kill %1 %2 2>/dev/null; exit' INT; \
		(cd $(BACKEND_DIR) && uvicorn main:app --host 0.0.0.0 --port 8000 --reload 2>&1 | sed 's/^/[backend] /') & \
		(cd $(FRONTEND_DIR) && npm run dev 2>&1 | sed 's/^/[frontend] /') & \
		wait

dev-backend:  ## Start backend only (port 8000)
	cd $(BACKEND_DIR) && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:  ## Start frontend only (port 5173)
	cd $(FRONTEND_DIR) && npm run dev

# ══════════════════════════════════════════════════════════════════
# TESTING
# ══════════════════════════════════════════════════════════════════

test:  ## Run all backend tests
	@echo "$(CYAN)▶ Running tests...$(RESET)"
	cd $(BACKEND_DIR) && python3 -m pytest tests/ -v --tb=short
	@echo "$(GREEN)  ✅ Tests complete$(RESET)"

test-watch:  ## Run tests in watch mode (auto-rerun on change)
	cd $(BACKEND_DIR) && python3 -m pytest tests/ -v --tb=short -f

test-cov:  ## Run tests with coverage report
	cd $(BACKEND_DIR) && python3 -m pytest tests/ -v \
		--cov=. \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-omit="tests/*,venv/*"
	@echo "$(GREEN)  Coverage report: backend/htmlcov/index.html$(RESET)"

lint:  ## Run Ruff linter
	@echo "$(CYAN)▶ Linting...$(RESET)"
	cd $(BACKEND_DIR) && ruff check . --select=E,F,W,I --ignore=E501
	@echo "$(GREEN)  ✅ Lint clean$(RESET)"

lint-fix:  ## Auto-fix lint issues
	cd $(BACKEND_DIR) && ruff check . --fix --select=E,F,W,I --ignore=E501

# ══════════════════════════════════════════════════════════════════
# DOCKER
# ══════════════════════════════════════════════════════════════════

build:  ## Build Docker images locally
	@echo "$(CYAN)▶ Building Docker images...$(RESET)"
	docker build -t ai-copilot-backend:local ./$(BACKEND_DIR)
	docker build -t ai-copilot-frontend:local \
		--build-arg VITE_API_URL=http://localhost:8000/api \
		./$(FRONTEND_DIR)
	@echo "$(GREEN)  ✅ Images built$(RESET)"

build-backend:  ## Build backend Docker image only
	docker build -t ai-copilot-backend:local ./$(BACKEND_DIR)

run-docker:  ## Run both services in Docker
	docker compose up --build

run-docker-bg:  ## Run Docker services in background
	docker compose up --build -d
	@echo "$(GREEN)  Frontend: http://localhost:3000$(RESET)"
	@echo "$(GREEN)  Backend:  http://localhost:8000$(RESET)"

stop-docker:  ## Stop Docker services
	docker compose down

# ══════════════════════════════════════════════════════════════════
# GCP SETUP
# ══════════════════════════════════════════════════════════════════

gcp-setup:  ## Run GCP prerequisites setup (APIs, SA, state bucket)
	@if [ -z "$(GCP_PROJECT_ID)" ]; then \
		echo "$(RED)❌ Set GCP_PROJECT_ID in backend/.env first$(RESET)"; exit 1; \
	fi
	bash infra/gcp-setup.sh

gcp-auth:  ## Authenticate with GCP
	gcloud auth login
	gcloud auth application-default login
	gcloud config set project $(GCP_PROJECT_ID)

# ══════════════════════════════════════════════════════════════════
# TERRAFORM
# ══════════════════════════════════════════════════════════════════

tf-init:  ## Initialize Terraform (run after gcp-setup)
	@echo "$(CYAN)▶ Initializing Terraform...$(RESET)"
	cd $(TF_DIR) && terraform init
	@echo "$(GREEN)  ✅ Terraform initialized$(RESET)"

tf-plan:  ## Preview infrastructure changes
	@echo "$(CYAN)▶ Planning infrastructure...$(RESET)"
	cd $(TF_DIR) && terraform plan -var-file=prod.tfvars

tf-apply:  ## Apply infrastructure changes
	@echo "$(CYAN)▶ Applying infrastructure...$(RESET)"
	cd $(TF_DIR) && terraform apply -var-file=prod.tfvars
	@echo "$(GREEN)  ✅ Infrastructure updated$(RESET)"
	@echo ""
	@echo "$(CYAN)  Outputs:$(RESET)"
	cd $(TF_DIR) && terraform output

tf-destroy:  ## Destroy all infrastructure (⚠️ irreversible)
	@echo "$(RED)⚠️  This will DESTROY all GCP resources!$(RESET)"
	@read -p "Type 'destroy' to confirm: " CONFIRM; \
	if [ "$$CONFIRM" = "destroy" ]; then \
		cd $(TF_DIR) && terraform destroy -var-file=prod.tfvars; \
	else \
		echo "Cancelled."; \
	fi

tf-output:  ## Show Terraform outputs
	cd $(TF_DIR) && terraform output

tf-fmt:  ## Format all Terraform files
	cd $(TF_DIR) && terraform fmt -recursive

tf-validate:  ## Validate Terraform configuration
	cd $(TF_DIR) && terraform init -backend=false && terraform validate

get-sa-key:  ## Extract CI/CD service account key (add to GitHub Secrets)
	@echo "$(CYAN)▶ Extracting CI/CD service account key...$(RESET)"
	@cd $(TF_DIR) && terraform output -raw cicd_sa_key_json
	@echo ""
	@echo "$(AMBER)👆 Copy the JSON above → GitHub repo → Settings → Secrets → GCP_SA_KEY$(RESET)"

# ══════════════════════════════════════════════════════════════════
# DEPLOYMENT
# ══════════════════════════════════════════════════════════════════

deploy:  ## Deploy via GitHub Actions (push to main)
	@echo "$(CYAN)▶ Triggering deployment via git push...$(RESET)"
	git add -A
	git commit -m "deploy: $(shell date '+%Y-%m-%d %H:%M')" || true
	git push origin main
	@echo "$(GREEN)  ✅ Pushed — check GitHub Actions for deployment status$(RESET)"

deploy-force:  ## Force redeploy (empty commit push)
	git commit --allow-empty -m "ci: force redeploy $(shell date '+%Y-%m-%d %H:%M')"
	git push origin main

rollback:  ## Roll back backend to previous revision
	@echo "$(CYAN)▶ Rolling back backend...$(RESET)"
	PREV=$$(gcloud run revisions list \
		--service=ai-copilot-backend \
		--region=$(GCP_REGION) \
		--format="value(name)" \
		--sort-by="~createTime" \
		--limit=2 | tail -1); \
	echo "  Rolling back to: $$PREV"; \
	gcloud run services update-traffic ai-copilot-backend \
		--to-revisions=$$PREV=100 \
		--region=$(GCP_REGION)

# ══════════════════════════════════════════════════════════════════
# MONITORING
# ══════════════════════════════════════════════════════════════════

health:  ## Check health of deployed services
	@echo "$(CYAN)▶ Checking deployed service health...$(RESET)"
	@BACKEND_URL=$$(cd $(TF_DIR) && terraform output -raw backend_url 2>/dev/null || echo ""); \
	FRONTEND_URL=$$(cd $(TF_DIR) && terraform output -raw frontend_url 2>/dev/null || echo ""); \
	if [ -n "$$BACKEND_URL" ]; then \
		STATUS=$$(curl -s -o /dev/null -w "%{http_code}" $$BACKEND_URL/api/ping); \
		if [ "$$STATUS" = "200" ]; then \
			echo "  $(GREEN)✅ Backend healthy$(RESET): $$BACKEND_URL"; \
		else \
			echo "  $(RED)❌ Backend down$(RESET) (HTTP $$STATUS): $$BACKEND_URL"; \
		fi; \
	else \
		echo "  $(AMBER)⚠️  Backend URL not found — run 'make tf-output'$(RESET)"; \
	fi; \
	if [ -n "$$FRONTEND_URL" ]; then \
		STATUS=$$(curl -s -o /dev/null -w "%{http_code}" $$FRONTEND_URL); \
		if [ "$$STATUS" = "200" ]; then \
			echo "  $(GREEN)✅ Frontend healthy$(RESET): $$FRONTEND_URL"; \
		else \
			echo "  $(RED)❌ Frontend down$(RESET) (HTTP $$STATUS): $$FRONTEND_URL"; \
		fi; \
	fi

logs:  ## Tail Cloud Run backend logs
	@echo "$(CYAN)▶ Streaming Cloud Run logs (Ctrl+C to stop)...$(RESET)"
	gcloud alpha logging tail \
		'resource.type="cloud_run_revision" AND resource.labels.service_name="ai-copilot-backend"' \
		--project=$(GCP_PROJECT_ID) \
		--format='value(timestamp,severity,textPayload)'

logs-errors:  ## Show only ERROR/CRITICAL logs from last hour
	gcloud logging read \
		'resource.type="cloud_run_revision" severity>=ERROR' \
		--limit=50 \
		--freshness=1h \
		--project=$(GCP_PROJECT_ID) \
		--format="table(timestamp,severity,resource.labels.service_name,textPayload)"

# ══════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════

clean:  ## Remove local build artifacts and caches
	@echo "$(CYAN)▶ Cleaning...$(RESET)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf backend/htmlcov backend/test-results.xml
	rm -rf frontend/dist
	@echo "$(GREEN)  ✅ Cleaned$(RESET)"

check-secrets:  ## Verify all required GitHub Secrets are set (needs gh CLI)
	@echo "$(CYAN)▶ Checking GitHub Secrets...$(RESET)"
	@for secret in GCP_PROJECT_ID GCP_REGION GCP_SA_KEY; do \
		if gh secret list | grep -q "$$secret"; then \
			echo "  $(GREEN)✅ $$secret is set$(RESET)"; \
		else \
			echo "  $(RED)❌ $$secret is MISSING$(RESET)"; \
		fi; \
	done

urls:  ## Print all service URLs
	@echo "$(CYAN)Service URLs:$(RESET)"
	@cd $(TF_DIR) && terraform output -json 2>/dev/null | \
		python3 -c "import json,sys; d=json.load(sys.stdin); \
		[print(f'  {k}: {v[\"value\"]}') for k,v in d.items() if 'url' in k.lower()]" \
		|| echo "  Run 'make tf-apply' first"
