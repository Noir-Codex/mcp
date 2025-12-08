#!/bin/bash

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Файл для хранения PID процессов
PID_FILE=".pids"

# Функция для вывода сообщений
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Функция для проверки доступности порта
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 1  # Порт занят
    else
        return 0  # Порт свободен
    fi
}

# Функция для проверки health endpoint
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=0
    
    info "Ожидание готовности $name..."
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            success "$name готов к работе"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    
    error "$name не отвечает после $max_attempts попыток"
    return 1
}

# Функция для остановки всех процессов
cleanup() {
    echo ""
    warning "Получен сигнал остановки..."
    info "Остановка всех процессов..."
    
    if [ -f "$PID_FILE" ]; then
        while read pid; do
            if [ ! -z "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null
                info "Остановлен процесс $pid"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    
    # Дополнительная очистка по PID переменным
    [ ! -z "$MOCK_API_PID" ] && kill "$MOCK_API_PID" 2>/dev/null
    [ ! -z "$MCP_SERVER_PID" ] && kill "$MCP_SERVER_PID" 2>/dev/null
    
    success "Все процессы остановлены"
    exit 0
}

# Установка обработчика сигналов
trap cleanup SIGINT SIGTERM EXIT

# Очистка старых PID файлов
rm -f "$PID_FILE"

echo "========================================"
echo "  Запуск всех компонентов системы"
echo "========================================"
echo ""

# Проверка Python
info "Проверка Python..."
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    error "Python не найден! Установите Python 3.11+"
    exit 1
fi

PYTHON_CMD=$(command -v python3 2>/dev/null || command -v python)
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1)
success "Найден: $PYTHON_VERSION"

# Проверка зависимостей
info "Проверка зависимостей..."
if ! $PYTHON_CMD -c "import fastapi, langchain" 2>/dev/null; then
    warning "Некоторые зависимости не установлены"
    info "Установка зависимостей из requirements.txt..."
    if [ -f "requirements.txt" ]; then
        $PYTHON_CMD -m pip install -q -r requirements.txt
        if [ $? -ne 0 ]; then
            error "Не удалось установить зависимости"
            exit 1
        fi
        success "Зависимости установлены"
    else
        error "Файл requirements.txt не найден"
        exit 1
    fi
else
    success "Все зависимости установлены"
fi

# Проверка .env файла
if [ ! -f ".env" ]; then
    warning "Файл .env не найден"
    if [ -f "env.example" ]; then
        info "Создайте .env на основе env.example"
    fi
fi

# Проверка портов
info "Проверка портов..."
if ! check_port 8000; then
    error "Порт 8000 уже занят (MCP-сервер)"
    exit 1
fi

if ! check_port 8001; then
    warning "Порт 8001 уже занят (Mock API может быть уже запущен)"
else
    success "Порты 8000 и 8001 свободны"
fi

echo ""
info "Запуск компонентов..."
echo ""

# [1/3] Запуск Mock Warehouse API
info "[1/3] Запуск Mock Warehouse API на порту 8001..."
if [ -f "mock_warehouse_api.py" ]; then
    $PYTHON_CMD mock_warehouse_api.py > /tmp/mock_api.log 2>&1 &
    MOCK_API_PID=$!
    echo "$MOCK_API_PID" >> "$PID_FILE"
    
    if wait_for_service "http://localhost:8001/health" "Mock Warehouse API"; then
        success "Mock Warehouse API запущен (PID: $MOCK_API_PID)"
    else
        error "Не удалось запустить Mock Warehouse API"
        exit 1
    fi
else
    warning "Файл mock_warehouse_api.py не найден, пропускаем..."
    MOCK_API_PID=""
fi

# [2/3] Запуск MCP-сервера
info "[2/3] Запуск MCP-сервера на порту 8000..."
if [ -d "mcp_server" ]; then
    $PYTHON_CMD -m mcp_server.http_server > /tmp/mcp_server.log 2>&1 &
    MCP_SERVER_PID=$!
    echo "$MCP_SERVER_PID" >> "$PID_FILE"
    
    if wait_for_service "http://localhost:8000/health" "MCP-сервер"; then
        success "MCP-сервер запущен (PID: $MCP_SERVER_PID)"
    else
        error "Не удалось запустить MCP-сервер"
        error "Проверьте логи: /tmp/mcp_server.log"
        exit 1
    fi
else
    error "Директория mcp_server не найдена"
    exit 1
fi

# [3/3] Запуск AI-агента
echo ""
info "[3/3] Запуск AI-агента..."
echo ""
echo "========================================"
success "Все компоненты успешно запущены!"
echo "========================================"
echo ""
echo "  Mock Warehouse API: http://localhost:8001"
echo "  MCP-сервер:         http://localhost:8000"
echo ""
echo "  Для остановки нажмите Ctrl+C"
echo ""

# Запуск агента в foreground режиме
if [ -d "agent" ]; then
    $PYTHON_CMD -m agent.agent
else
    error "Директория agent не найдена"
    exit 1
fi
