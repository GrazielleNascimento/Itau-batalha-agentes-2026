#!/usr/bin/env bash
# Experimento online: duas revisões do mesmo container, 90/10.
#
# A candidata difere do controle apenas por variável de ambiente — PROMPT_VERSION
# por padrão, ou MODEL_NAME. É o que torna o experimento uma variável e não um
# branch, e é o motivo de os prompts serem arquivos versionados.
#
#   PROJECT_ID=x bash infra/scripts/traffic_split.sh --dry-run
#   PROJECT_ID=x VARIANT_ENV=MODEL_NAME=gemini-3.8-flash-lite bash ... traffic_split.sh
#   PROJECT_ID=x bash infra/scripts/traffic_split.sh --rollback
set -euo pipefail

SERVICE="${SERVICE:-batalha-agentes}"
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-southamerica-east1}"
# O que muda entre controle e candidata. Uma variável, nada mais.
VARIANT_ENV="${VARIANT_ENV:-PROMPT_VERSION=v2}"
CANDIDATE_PERCENT="${CANDIDATE_PERCENT:-10}"
CONTROL_PERCENT=$((100 - CANDIDATE_PERCENT))
DRY_RUN=0
ROLLBACK=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --rollback) ROLLBACK=1 ;;
    *) echo "argumento desconhecido: $arg" >&2; exit 2 ;;
  esac
done

if [[ -z "$PROJECT_ID" ]]; then
  echo "erro: PROJECT_ID é obrigatório. Ex.: PROJECT_ID=meu-projeto $0 --dry-run" >&2
  exit 1
fi

run() {
  if [[ $DRY_RUN -eq 1 ]]; then printf '%s\n' "$*"; else "$@"; fi
}

BASE=(--project="$PROJECT_ID" --region="$REGION")

if [[ $ROLLBACK -eq 1 ]]; then
  echo "# Rollback: todo o tráfego volta para o controle."
  echo "# É troca de roteamento, não novo deploy — segundos, não minutos."
  run gcloud run services update-traffic "$SERVICE" "${BASE[@]}" --to-tags=v1=100
  exit 0
fi

if [[ $DRY_RUN -eq 1 ]]; then
  ATUAL="<revisão-servindo-agora>"
else
  ATUAL="$(gcloud run services describe "$SERVICE" "${BASE[@]}" \
    --format='value(status.latestReadyRevisionName)')"
fi

echo "# 1. A revisão que já serve vira o controle, com a tag v1"
run gcloud run services update-traffic "$SERVICE" "${BASE[@]}" \
  --set-tags="v1=${ATUAL}"

echo "# 2. Candidata sobe com a tag v2 e SEM tráfego"
# --no-traffic: ninguém é exposto enquanto a revisão não estiver pronta.
run gcloud run deploy "$SERVICE" "${BASE[@]}" \
  --source=agent \
  --tag v2 \
  --no-traffic \
  --update-env-vars "$VARIANT_ENV"

echo "# 3. Divide o tráfego: ${CONTROL_PERCENT}/${CANDIDATE_PERCENT}"
# 90/10 e não 50/50: o custo de uma resposta ruim numa jornada financeira não é
# simétrico ao ganho de uma boa. Os dois lados são explícitos porque deixar o
# resto implícito depende de onde o tráfego estava antes.
run gcloud run services update-traffic "$SERVICE" "${BASE[@]}" \
  --to-tags="v1=${CONTROL_PERCENT},v2=${CANDIDATE_PERCENT}"

echo
echo "# Acompanhe as métricas por revisão no Cloud Logging, filtrando por prompt_version."
echo "# Para voltar atrás: bash infra/scripts/traffic_split.sh --rollback"
