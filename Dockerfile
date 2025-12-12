# Базовый образ Python
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание директорий для логов
RUN mkdir -p /var/log/mcp

# Создание не-root пользователя для безопасности
RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app /var/log/mcp

# Переключение на не-root пользователя
USER mcpuser

# Экспорт порта MCP сервера
EXPOSE 8000

# Переменные окружения по умолчанию
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV MCP_SERVER_PORT=8000
ENV MCP_SERVER_HOST=0.0.0.0

# Команда запуска
CMD ["sh", "-c", "python -m mcp_server.http_server"]