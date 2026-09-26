#!/usr/bin/env bash
# Carrega os CSVs sintéticos no BigQuery, para a BigQueryDataSource consumir.
#
#   PROJECT_ID=x bash infra/scripts/load_bigquery.sh --dry-run
#   PROJECT_ID=x bash infra/scripts/load_bigquery.sh
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-}"
# Dataset na mesma região do serviço: o dado do cliente não sai do Brasil.
# (O modelo roda em `global` — são coisas diferentes, ver D5.)
BQ_LOCATION="${BQ_LOCATION:-southamerica-east1}"
DATASET="${DATASET:-batalha_agentes}"
DATA_DIR="${DATA_DIR:-data/synthetic}"
DRY_RUN=0

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

if [[ -z "$PROJECT_ID" ]]; then
  echo "erro: PROJECT_ID é obrigatório. Ex.: PROJECT_ID=meu-projeto $0 --dry-run" >&2
  exit 1
fi

run() {
  if [[ $DRY_RUN -eq 1 ]]; then printf '%s\n' "$*"; else "$@"; fi
}

echo "# 1. Dataset (|| true: já existir não é erro)"
run bq --location="$BQ_LOCATION" mk --dataset \
  --description="Dados sinteticos da Batalha de Agentes. Nenhum dado real." \
  "${PROJECT_ID}:${DATASET}" || true

echo "# 2. Tabelas, com schema DECLARADO"
# Schema explícito em vez de --autodetect: em customers todas as colunas são
# texto, e nesse caso o autodetect não distingue cabeçalho de dado — gera
# string_field_0..N e quebra toda consulta por nome. Palpite é bug silencioso.
# case em vez de array associativo: `declare -A` exige bash 4, e o macOS
# traz o 3.2. Quebraria na máquina do evento se for Mac.
schema_de() {
  case "$1" in
    customers)    echo "customer_id:STRING,cpf:STRING,full_name:STRING,first_name:STRING,age_band:STRING,income_band:STRING,suitability:STRING,preferred_channel:STRING,accessibility_flags:STRING,archetype:STRING" ;;
    accounts)     echo "customer_id:STRING,balance:FLOAT,overdraft_limit:FLOAT" ;;
    transactions) echo "customer_id:STRING,date:STRING,category:STRING,amount:FLOAT,description:STRING" ;;
    credit_cards) echo "customer_id:STRING,credit_limit:FLOAT,current_invoice:FLOAT,minimum_payment:FLOAT,revolving_balance:FLOAT,installment_count:INTEGER" ;;
    goals)        echo "customer_id:STRING,goal_id:STRING,name:STRING,target_amount:FLOAT,current_amount:FLOAT" ;;
    *)            echo "tabela desconhecida: $1" >&2; exit 1 ;;
  esac
}

# date fica STRING de propósito: a LocalDataSource compara datas como texto ISO,
# e as duas fontes precisam devolver exatamente o mesmo resultado.
for tabela in customers accounts transactions credit_cards goals; do
  # --replace numa tabela existente mantém o schema antigo; apagar garante o novo.
  run bq --location="$BQ_LOCATION" rm -f -t "${PROJECT_ID}:${DATASET}.${tabela}"
  run bq --location="$BQ_LOCATION" load \
    --source_format=CSV \
    --skip_leading_rows=1 \
    --replace \
    --schema="$(schema_de "$tabela")" \
    "${PROJECT_ID}:${DATASET}.${tabela}" \
    "${DATA_DIR}/${tabela}.csv"
done

echo
echo "# Para usar: make switch-project ... e DATA_SOURCE=bigquery no .env"
echo "# Conferir:  bq query --use_legacy_sql=false 'SELECT COUNT(*) FROM \`${PROJECT_ID}.${DATASET}.customers\`'"
