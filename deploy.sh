#!/bin/bash
# deploy.sh - Скрипт деплоя на cloud.ru

set -e

# Конфигурация
DOCKER_REGISTRY="cr.cloud.ru"
PROJECT_NAME="mcp-warehouse"
VERSION="1.0.0"
IMAGE_NAME="${DOCKER_REGISTRY}/${PROJECT_NAME}:${VERSION}"

echo "🚀 Начинаем деплой MCP Warehouse на cloud.ru"

# 1. Проверка наличия Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi

# 2. Проверка наличия kubectl
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl не установлен"
    exit 1
fi

# 3. Проверка подключения к cloud.ru
echo "🔐 Проверка подключения к cloud.ru..."
if ! kubectl cluster-info; then
    echo "❌ Не удалось подключиться к кластеру cloud.ru"
    exit 1
fi

# 4. Сборка Docker образа
echo "🐳 Сборка Docker образа..."
docker build -t ${IMAGE_NAME} .

# 5. Пуш образа в реестр
echo "📦 Отправка образа в реестр cloud.ru..."
docker push ${IMAGE_NAME}

# 6. Создание secrets
echo "🔑 Создание секретов..."
kubectl create secret generic mcp-secrets \
  --from-literal=evolution-api-url="${EVOLUTION_API_URL}" \
  --from-literal=evolution-api-key="${EVOLUTION_API_KEY}" \
  --from-literal=evolution-model="${EVOLUTION_MODEL}" \
  --from-literal=bitrix24-webhook-url="${BITRIX24_WEBHOOK_URL}" \
  --from-literal=bitrix24-assigned-by-id="${BITRIX24_ASSIGNED_BY_ID}" \
  --from-literal=bitrix24-pipeline-id="${BITRIX24_PIPELINE_ID}" \
  --from-literal=bitrix24-task-group-id="${BITRIX24_TASK_GROUP_ID}" \
  --dry-run=client -o yaml | kubectl apply -f -

# 7. Деплой приложения
echo "🚢 Деплой приложения..."
envsubst < cloud.yaml | kubectl apply -f -

# 8. Ожидание запуска
echo "⏳ Ожидание запуска приложения..."
sleep 10
kubectl wait --for=condition=ready pod -l app=mcp-warehouse --timeout=300s

# 9. Проверка статуса
echo "✅ Деплой завершен!"
echo ""
echo "📊 Информация о деплое:"
kubectl get pods -l app=mcp-warehouse
kubectl get svc mcp-warehouse-service
kubectl get ingress mcp-warehouse-ingress

echo ""
echo "🔗 MCP сервер доступен по адресу: https://${HOSTNAME}"
echo "🔧 Инструменты доступны по пути: /mcp/tools/{tool_name}"
echo "🏥 Health check: https://${HOSTNAME}/health"