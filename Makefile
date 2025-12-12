.PHONY: help build run test clean deploy docker-run docker-build docker-push

help:
	@echo "Доступные команды:"
	@echo "  build        - Установка зависимостей"
	@echo "  run          - Запуск MCP сервера"
	@echo "  run-agent    - Запуск AI агента"
	@echo "  test         - Запуск тестов"
	@echo "  clean        - Очистка кэша"
	@echo "  docker-build - Сборка Docker образа"
	@echo "  docker-run   - Запуск в Docker"
	@echo "  deploy       - Деплой на cloud.ru"

build:
	pip install -r requirements.txt

run:
	python -m mcp_server.http_server

run-agent:
	python -m agent.agent

test:
	python -m pytest tests/ -v

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +

docker-build:
	docker build -t mcp-warehouse:latest .

docker-run:
	docker-compose up --build

deploy:
	@echo "Для деплоя на cloud.ru выполните:"
	@echo "1. Экспортируйте переменные окружения:"
	@echo "   export EVOLUTION_API_URL='https://foundation-models.api.cloud.ru/v1'"
	@echo "   export EVOLUTION_API_KEY='ваш_ключ'"
	@echo "   export HOSTNAME='ваш.домен.cloud.ru'"
	@echo "2. Запустите: ./deploy.sh"