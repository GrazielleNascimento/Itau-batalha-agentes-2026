#!/usr/bin/env bash
# Deploy do agente no Cloud Run.
#
# Sem acesso público: a Fase 7 do HANDOFF pede isso, e é também o plano B se a
# org policy do evento bloquear invocação pública. Acesso na demo por
# `gcloud run services proxy`.
set -euo pipefail

SERVICE="${SERVICE:-batalha-agentes}"
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-southamerica-east1}"
# Onde o MODELO roda. Separado de REGION de propósito (D5): a disponibilidade
# de Gemini em southamerica-east1 é limitada.
MODEL_LOCATION="${MODEL_LOCATION:-global}"
SA_NAME="${SA_NAME:-${SERVICE}-sa}"
# Sessão e memória gerenciadas pelo Agent Engine. Sem isto, o ADK cai em
# InMemorySessionService — um dict no processo — e com mais de uma instância
# o turno 2 de uma conversa pode chegar onde a sessão não existe.
# SEM valor padrão de propósito: o engine é por projeto. Um padrão apontaria
# o projeto do evento para o engine do preparo e falharia por permissão.
AGENT_ENGINE_ID="${AGENT_ENGINE_ID:-}"
# southamerica-east1: a sessão persiste o texto BRUTO do usuário (o mascaramento
# age no LlmRequest, não no evento gravado). Sessão e memória ficam no Brasil;
# só a inferência do modelo sai (GOOGLE_CLOUD_LOCATION=global).
MEMORY_LOCATION="${MEMORY_LOCATION:-southamerica-east1}"
# PUBLIC=1: reaplica allUsers DEPOIS do deploy. O --no-allow-unauthenticated
# remove um binding concedido antes, em todo deploy — quem escolheu público
# perdia a escolha sem aviso. O padrão continua privado.
PUBLIC="${PUBLIC:-0}"
# MANAGED_IAM=0: projeto sem permissão para criar SA nem alterar IAM (o do
# evento). Pula os passos de identidade e usa a SA existente em RUNTIME_SA.
MANAGED_IAM="${MANAGED_IAM:-1}"
RUNTIME_SA="${RUNTIME_SA:-}"
# AR_REPO: repositório do Artifact Registry já provisionado (writer não cria).
# Com MANAGED_IAM=0 o build vai para ele e o deploy usa --image, não --source.
AR_REPO="${AR_REPO:-agentes}"
# BUILD=cloudbuild (padrão) | local. No projeto do evento não há bucket de
# staging e o usuário não pode criar um: Cloud Build está fora. `local` faz
# docker build --platform linux/amd64 + push, que só exige artifactregistry.writer.
BUILD="${BUILD:-cloudbuild}"
# MODEL_KEY_SECRET: nome de um segredo com chave do AI Studio. A SA não lê o
# Secret Manager; quem lê é QUEM DEPLOYA, e o valor vai para a revisão. Fica
# visível a quem tem run.viewer — aceitável em projeto isolado por time.
MODEL_KEY_SECRET="${MODEL_KEY_SECRET:-}"
MAX_INSTANCES="${MAX_INSTANCES:-3}"
DATA_SOURCE="${DATA_SOURCE:-local}"
DRY_RUN=0

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

if [[ -z "$PROJECT_ID" ]]; then
  echo "erro: PROJECT_ID é obrigatório. Ex.: PROJECT_ID=meu-projeto $0" >&2
  exit 1
fi

# MEMORY_BACKEND=local sem engine: projeto onde a SA de runtime não pode usar
# o Agent Engine e ninguém pode conceder (o do evento). Sessão no processo,
# logo UMA instância — senão o turno 2 cai onde a sessão não existe.
MEMORY_BACKEND="${MEMORY_BACKEND:-agent_engine}"
if [[ -z "$AGENT_ENGINE_ID" && "$MEMORY_BACKEND" == "local" ]]; then
  echo "# AVISO: MEMORY_BACKEND=local sem AGENT_ENGINE_ID — sessão no processo, MAX_INSTANCES=1"
  MAX_INSTANCES=1
  ENGINE_ENV=""
elif [[ -z "$AGENT_ENGINE_ID" ]]; then
  echo "erro: AGENT_ENGINE_ID é obrigatório (sessão e memória gerenciadas)." >&2
  echo "      Crie um para este projeto: make agent-engine PROJECT_ID=$PROJECT_ID" >&2
  exit 1
else
  ENGINE_ENV="GOOGLE_CLOUD_AGENT_ENGINE_ID=${AGENT_ENGINE_ID},GOOGLE_CLOUD_AGENT_ENGINE_LOCATION=${MEMORY_LOCATION},"
fi

if [[ "$MANAGED_IAM" == "0" ]]; then
  if [[ -z "$RUNTIME_SA" ]]; then
    echo "erro: MANAGED_IAM=0 exige RUNTIME_SA (a SA existente que vai executar o agente)." >&2
    exit 1
  fi
  SA_EMAIL="$RUNTIME_SA"
else
  SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
fi

if [[ $DRY_RUN -eq 1 ]]; then
  PROJECT_NUMBER="${PROJECT_NUMBER:-<PROJECT_NUMBER>}"
else
  PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
fi

run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    printf '%s\n' "$*"
  else
    "$@"
  fi
}

if [[ "$MANAGED_IAM" == "1" ]]; then
echo "# 1. Service account dedicada, com o mínimo de permissão"
run gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="Runtime do agente ${SERVICE}" || true

echo "# 2. Único papel necessário: chamar modelos no Vertex"
run gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/aiplatform.user" \
  --condition=None

echo "# 3. Repositório do Artifact Registry, criado explicitamente"
# Criar aqui em vez de deixar o `run deploy` criar: quando duas pessoas rodam o
# deploy ao mesmo tempo, a criação implícita colide e as duas falham.
run gcloud artifacts repositories create cloud-run-source-deploy \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --repository-format=docker \
  --description="Imagens do deploy a partir do fonte" || true

echo "# 4. Permissão de build para a SA padrão do Compute"
# Projeto GCP novo não concede papéis a esta SA, e é ela que o Cloud Build usa
# em `run deploy --source`. Sem isto o build falha com storage.objects.get
# negado no bucket de fontes. Acontece em TODO projeto novo.
run gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder" \
  --condition=None

fi  # MANAGED_IAM

# Modelo: Vertex via identidade da SA (padrão) ou chave do AI Studio lida agora.
if [[ -n "$MODEL_KEY_SECRET" ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    CHAVE="<valor de: gcloud secrets versions access latest --secret=${MODEL_KEY_SECRET}>"
  else
    CHAVE="$(gcloud secrets versions access latest --secret="$MODEL_KEY_SECRET" --project="$PROJECT_ID")"
  fi
  MODEL_ENV="GOOGLE_GENAI_USE_VERTEXAI=false,GEMINI_API_KEY=${CHAVE}"
else
  MODEL_ENV="GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=${MODEL_LOCATION}"
fi

ENV_VARS="${MODEL_ENV},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},REGION=${REGION},DATA_DIR=/code/data,DATA_SOURCE=${DATA_SOURCE},DEMO_MODE=true,DEMO_CUSTOMER_ID=${DEMO_CUSTOMER_ID:-FICT-0001},USE_MODEL_ARMOR=${USE_MODEL_ARMOR:-false},USE_RAG_ENGINE=false,${ENGINE_ENV}MEMORY_BACKEND=${MEMORY_BACKEND},MEMORY_LOCATION=${MEMORY_LOCATION}"

if [[ "$MANAGED_IAM" == "0" ]]; then
  IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE}:$(date +%Y%m%d-%H%M%S)"
  if [[ "$BUILD" == "local" ]]; then
    echo "# 5a. Build LOCAL (linux/amd64) e push para o repositório existente"
    run docker build --platform linux/amd64 -t "$IMAGE" agent
    run docker push "$IMAGE"
  else
    echo "# 5a. Build no Cloud Build para o repositório existente (writer faz push, não cria repo)"
    run gcloud builds submit agent --project="$PROJECT_ID" --tag "$IMAGE"
  fi
  echo "# 5b. Deploy por imagem"
  run gcloud run deploy "$SERVICE" \
    --project="$PROJECT_ID" --region="$REGION" \
    --image="$IMAGE" \
    --service-account="$SA_EMAIL" \
    --no-allow-unauthenticated --port=8080 --memory=2Gi --cpu=1 \
    --min-instances=0 --max-instances="$MAX_INSTANCES" \
    --set-env-vars="$ENV_VARS"
else
echo "# 5. Deploy a partir do fonte (Cloud Build monta a imagem)"
run gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --source=agent \
  --service-account="$SA_EMAIL" \
  --no-allow-unauthenticated \
  --port=8080 \
  --memory=2Gi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances="$MAX_INSTANCES" \
  --set-env-vars="$ENV_VARS"
fi  # MANAGED_IAM

if [[ "$PUBLIC" == "1" ]]; then
  echo "# 6. PUBLIC=1: reabre o acesso público (qualquer pessoa com a URL gasta seu crédito)"
  run gcloud run services add-iam-policy-binding "$SERVICE" \
    --project="$PROJECT_ID" --region="$REGION" \
    --member=allUsers --role=roles/run.invoker
fi

echo
if [[ "$PUBLIC" == "1" ]]; then
  echo "# Serviço público: a URL acima responde sem token."
else
  echo "# Serviço privado. Para conversar com ele:"
  echo "#   gcloud run services proxy ${SERVICE} --project=${PROJECT_ID} --region=${REGION}"
  echo "# Depois abra http://localhost:8080"
fi
