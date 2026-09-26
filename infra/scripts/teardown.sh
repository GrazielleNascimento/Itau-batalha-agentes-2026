#!/usr/bin/env bash
# Apaga o que o deploy criou. Rode depois de testar, para não deixar cobrança viva.
set -euo pipefail

SERVICE="${SERVICE:-batalha-agentes}"
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-southamerica-east1}"
SA_NAME="${SA_NAME:-${SERVICE}-sa}"
DRY_RUN=0

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

if [[ -z "$PROJECT_ID" ]]; then
  echo "erro: PROJECT_ID é obrigatório." >&2
  exit 1
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

run() {
  if [[ $DRY_RUN -eq 1 ]]; then printf '%s\n' "$*"; else "$@"; fi
}

run gcloud run services delete "$SERVICE" --project="$PROJECT_ID" --region="$REGION" --quiet
run gcloud iam service-accounts delete "$SA_EMAIL" --project="$PROJECT_ID" --quiet
echo "# A imagem no Artifact Registry continua ocupando espaço. Para apagá-la:"
echo "#   gcloud artifacts docker images list ${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy"
