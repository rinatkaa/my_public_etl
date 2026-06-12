#!/usr/bin/env bash
set -e

# Настраиваемые интервалы (переопределяются через .env или docker-compose)
PG_CHECK_INTERVAL=${PG_CHECK_INTERVAL:-10}
ES_CHECK_INTERVAL=${ES_CHECK_INTERVAL:-10}
ETL_RUN_INTERVAL=${ETL_RUN_INTERVAL:-300}

# Дефолтные хосты/порты
PG_HOST=${PG_HOST:-cinema-db}
PG_PORT=${PG_PORT:-5432}
ES_HOST=${ES_HOST:-elasticsearch}
ES_PORT=${ES_PORT:-9200}

# Чистим кэш dns
if command -v nscd >/dev/null 2>&1; then
  nscd -i hosts
fi

echo "Waiting for PostgreSQL at ${PG_HOST}:${PG_PORT}..."
while ! nc -z "$PG_HOST" "$PG_PORT"; do
  sleep "$PG_CHECK_INTERVAL"
done
echo "PostgreSQL is ready!"

echo "Waiting for Elasticsearch at ${ES_HOST}:${ES_PORT}..."
# Проверяем HTTP readiness
until curl -sf "http://${ES_HOST}:${ES_PORT}/_cluster/health?wait_for_status=yellow&timeout=5s" >/dev/null 2>&1; do
  sleep "$ES_CHECK_INTERVAL"
done
echo "Elasticsearch is ready!"

echo "Starting ETL daemon loop..."
while true; do
  python3 etl.py || echo "ETL finished with exit code $?. Will restart after delay..."
  echo "Sleeping for ${ETL_RUN_INTERVAL}s before next cycle..."
  sleep "$ETL_RUN_INTERVAL"
done