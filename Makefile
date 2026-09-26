.DEFAULT_GOAL := help
# Sem isto, o alvo `data` colide com o diretório data/ e o make não faz nada.
.PHONY: help setup data run test test-llm lint switch-project stage-data deploy teardown smoke event eval eval-report traffic-split load-bq agent-engine model-armor stage-evento
UV := uv
ACLI := uvx google-agents-cli

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

setup: ## cria o venv 3.12, instala deps e o .env
	cd agent && $(UV) venv --python 3.12 --clear && $(UV) sync --all-groups
	@test -f agent/.env || cp agent/.env.example agent/.env

test: ## testes determinísticos, sem credencial
	cd agent && $(UV) run pytest tests -m "not llm" -q

lint: ## ruff
	cd agent && $(UV) run ruff check app ../data ../infra && $(UV) run ruff format --check app ../data ../infra

data: ## gera os dados sintéticos
	cd agent && PYTHONPATH=.. $(UV) run python -m data.generator.generate --out ../data/synthetic

PLAYGROUND_PORT ?= 8501

run: ## abre o playground local: make run [PLAYGROUND_PORT=8501]
	@echo "playground em http://localhost:$(PLAYGROUND_PORT)/dev-ui/"
	cd agent && $(ACLI) playground --port $(PLAYGROUND_PORT)

test-llm: ## inclui os testes que precisam de credencial
	cd agent && $(UV) run pytest tests -q

REGION ?= southamerica-east1
APIS := aiplatform.googleapis.com run.googleapis.com artifactregistry.googleapis.com \
        cloudbuild.googleapis.com bigquery.googleapis.com pubsub.googleapis.com \
        secretmanager.googleapis.com logging.googleapis.com monitoring.googleapis.com \
        modelarmor.googleapis.com

MODE ?= vertex

switch-project: ## troca projeto GCP e modo: make switch-project PROJECT_ID=x [REGION=y] [MODE=vertex|local]
	@test -n "$(PROJECT_ID)" || (echo "PROJECT_ID é obrigatório"; exit 1)
	python3 infra/scripts/switch_project.py "$(PROJECT_ID)" "$(REGION)" "$(MODE)"
	gcloud config set project $(PROJECT_ID)
	@echo "Para habilitar as APIs, rode:"
	@echo "  gcloud services enable $(APIS)"

stage-data: ## copia data/ para dentro do contexto de build (agent/data/)
	rm -rf agent/data
	mkdir -p agent/data
	cp -R data/knowledge agent/data/knowledge
	cp -R data/synthetic agent/data/synthetic
	@test -d data/evento && cp -R data/evento agent/data/evento || true
	@echo "agent/data/ pronto para o build"

deploy: stage-data ## deploy: make deploy PROJECT_ID=x AGENT_ENGINE_ID=y [PUBLIC=1] [DRY_RUN=1]
	@test -n "$(PROJECT_ID)" || (echo "PROJECT_ID é obrigatório"; exit 1)
	PROJECT_ID=$(PROJECT_ID) REGION=$(REGION) AGENT_ENGINE_ID=$(AGENT_ENGINE_ID) \
	  MEMORY_LOCATION=$(MEMORY_LOCATION) PUBLIC=$(PUBLIC) MANAGED_IAM=$(MANAGED_IAM) RUNTIME_SA=$(RUNTIME_SA) \
	  AR_REPO=$(AR_REPO) BUILD=$(BUILD) MODEL_KEY_SECRET=$(MODEL_KEY_SECRET) MAX_INSTANCES=$(MAX_INSTANCES) DATA_SOURCE=$(DATA_SOURCE) \
	  USE_MODEL_ARMOR=$(USE_MODEL_ARMOR) MEMORY_BACKEND=$(MEMORY_BACKEND) DEMO_CUSTOMER_ID=$(DEMO_CUSTOMER_ID) \
	  bash infra/scripts/deploy.sh $(if $(DRY_RUN),--dry-run,)

MEMORY_LOCATION ?= southamerica-east1

agent-engine: ## cria o Agent Engine de sessão/memória: make agent-engine PROJECT_ID=x [MEMORY_LOCATION=...]
	@test -n "$(PROJECT_ID)" || (echo "PROJECT_ID é obrigatório"; exit 1)
	cd agent && $(UV) run python ../infra/scripts/agent_engine_setup.py \
	  --project "$(PROJECT_ID)" --location "$(MEMORY_LOCATION)"

teardown: ## apaga o que o deploy criou: make teardown PROJECT_ID=x [DRY_RUN=1]
	@test -n "$(PROJECT_ID)" || (echo "PROJECT_ID é obrigatório"; exit 1)
	PROJECT_ID=$(PROJECT_ID) REGION=$(REGION) bash infra/scripts/teardown.sh $(if $(DRY_RUN),--dry-run,)

smoke: ## smoke de arquitetura contra um agente vivo: make smoke BASE_URL=... [TOKEN=...]
	@test -n "$(BASE_URL)" || (echo "BASE_URL é obrigatório"; exit 1)
	python3 infra/scripts/smoke.py --base-url "$(BASE_URL)" $(if $(TOKEN),--token "$(TOKEN)",)

EVENT ?= salary_received

event: ## simula um evento proativo: make event [BASE_URL=...] [EVENT=...] [TOKEN=...]
	python3 data/generator/simulate_event.py \
	  --base-url "$(or $(BASE_URL),http://localhost:$(PLAYGROUND_PORT))" \
	  --event "$(EVENT)" $(if $(TOKEN),--token "$(TOKEN)",)

eval: ## avaliação offline sobre o dataset de eval (precisa de credencial)
	cd agent && $(ACLI) eval run --config tests/eval/eval_config.yaml

eval-report: ## abre o relatório HTML da última avaliação
	@f=$$(ls -t agent/artifacts/grade_results/*.html 2>/dev/null | head -1); \
	  test -n "$$f" || { echo "nenhum relatório. Rode: make eval"; exit 1; }; \
	  echo "$$f"; open "$$f"

traffic-split: ## experimento 90/10: make traffic-split PROJECT_ID=x [DRY_RUN=1] [ROLLBACK=1]
	@test -n "$(PROJECT_ID)" || (echo "PROJECT_ID é obrigatório"; exit 1)
	PROJECT_ID=$(PROJECT_ID) REGION=$(REGION) bash infra/scripts/traffic_split.sh \
	  $(if $(DRY_RUN),--dry-run,) $(if $(ROLLBACK),--rollback,)

load-bq: ## carrega os CSVs no BigQuery: make load-bq PROJECT_ID=x [DRY_RUN=1]
	@test -n "$(PROJECT_ID)" || (echo "PROJECT_ID é obrigatório"; exit 1)
	PROJECT_ID=$(PROJECT_ID) bash infra/scripts/load_bigquery.sh $(if $(DRY_RUN),--dry-run,)

model-armor: ## cria/atualiza o template do Model Armor: make model-armor PROJECT_ID=x
	@test -n "$(PROJECT_ID)" || (echo "PROJECT_ID é obrigatório"; exit 1)
	cd agent && $(UV) run python ../infra/scripts/model_armor_setup.py --project "$(PROJECT_ID)"

EVENTO_USUARIOS ?= 200

stage-evento: ## exporta um recorte de hackathon_dados.extrato_sintetico para data/evento/: make stage-evento PROJECT_ID=x
	@test -n "$(PROJECT_ID)" || (echo "PROJECT_ID é obrigatório"; exit 1)
	@mkdir -p data/evento
	bq --project_id=$(PROJECT_ID) query --nouse_legacy_sql --format=csv --max_rows=1000000 \
	  "SELECT id_usuario, FORMAT_TIMESTAMP('%Y-%m-%d', anomesdia) AS data, tipo, descr, vlr, nom_cate_macro, nom_cate_micro, saldo_apos, parcela_atual, parcela_total \
	   FROM \`$(PROJECT_ID).hackathon_dados.extrato_sintetico\` \
	   WHERE id_usuario IN (SELECT id_usuario FROM (SELECT DISTINCT id_usuario FROM \`$(PROJECT_ID).hackathon_dados.extrato_sintetico\` ORDER BY id_usuario LIMIT $(EVENTO_USUARIOS))) \
	   ORDER BY id_usuario, anomesdia" > data/evento/extrato.csv
	@echo "linhas: $$(($$(wc -l < data/evento/extrato.csv) - 1)) em data/evento/extrato.csv"
