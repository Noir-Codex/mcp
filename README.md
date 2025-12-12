# MCP Warehouse Management System

AI-агент для управления складом и запасами с полной интеграцией в CRM Битрикс24.

## 🚀 Возможности

- 📦 **Управление запасами**: Отслеживание остатков, приход/расход товаров
- 🏪 **Многоскладской учет**: Поддержка нескольких складов
- 🔄 **Интеграция с Битрикс24**: Автоматическая синхронизация с CRM
- 🤖 **AI-агент**: Управление через естественный язык
- 📊 **Отчетность и аналитика**: История движений, прогнозирование

## 🛠 Технологии

- **Python 3.11+**
- **FastAPI** — REST API сервер
- **LangChain** — AI агент
- **Evolution Foundation Models** — LLM от Cloud.ru
- **SQLite** — База данных
- **Docker** — Контейнеризация
- **Bitrix24 REST API** — Интеграция с CRM

## 📦 Установка

### Локальная установка

1. Клонируйте репозиторий:

```bash
git clone https://github.com/Noir-Codex/mcp.git
cd mcp
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

3. Настройте переменные окружения:

```bash
cp .env.example .env
# Отредактируйте .env файл
```

4. Запустите MCP сервер:

```bash
python -m mcp_server.http_server
```

5. Запустите AI агент (в отдельном терминале):

```bash
python -m agent.agent
```

---

### Запуск в Docker

```bash
# Сборка и запуск

docker-compose up --build

# Только MCP сервер

docker run -p 8000:8000 mcp-warehouse
```

---

## 🔧 Конфигурация

**Основные переменные окружения**

```env
# Evolution Foundation Models API
EVOLUTION_API_KEY=ваш_api_ключ
EVOLUTION_API_URL=https://foundation-models.api.cloud.ru/v1
EVOLUTION_MODEL=Qwen/Qwen3-235B-A22B-Instruct-2507

# MCP Server
MCP_SERVER_PORT=8000
MCP_SERVER_HOST=0.0.0.0

# Bitrix24 Integration
BITRIX24_WEBHOOK_URL=ваш_webhook_url
BITRIX24_ENABLED=true
```

---

## 🚀 Быстрый старт

1. Проверьте подключение к Битрикс24:
   > проверь подключение к битрикс24
2. Посмотрите список складов:
   > покажи все склады
3. Создайте новый товар:
   > добавь товар МОЛОКО с артикулом MILK-001
4. Проверьте остатки:
   > сколько товара МОЛОКО
5. Создайте заявку на пополнение:
   > создай заявку на пополнение товара МОЛОКО 100 единиц

---

## 📚 API Документация

MCP сервер предоставляет REST API:

```
GET /health                 # Проверка состояния сервера
POST /mcp/tools/{tool_name} # Вызов MCP инструмента
```

Доступные инструменты:

### Управление запасами:
- `get_inventory_status` — Статус запасов товара
- `update_inventory` — Обновление остатков
- `create_reorder_request` — Заявка на пополнение

### Работа с товарами:
- `search_products` — Поиск товаров
- `create_product` — Создание товара
- `list_products` — Список товаров

### Интеграция с Битрикс24:
- `get_bitrix_warehouses` — Список складов
- `get_bitrix_product_stock` — Остатки товара
- `sync_all_stock_to_bitrix` — Полная синхронизация

---

## 🌐 Деплой на cloud.ru

**Требования:**  
- Аккаунт на cloud.ru  
- Docker registry в cloud.ru  
- Настроенный Kubernetes кластер

**Шаги деплоя:**

1. Настройте переменные окружения:

```bash
export EVOLUTION_API_KEY="ваш_ключ"
export HOSTNAME="ваш-домен.cloud.ru"
```

2. Соберите и запушьте Docker-образ:

```bash
./deploy.sh
```

3. Проверьте деплой:

```bash
kubectl get pods -l app=mcp-warehouse
```

---

## 🔗 Полезные ссылки

- [Документация Evolution Foundation Models](https://cloud.ru/ru/products/foundation-models)
- [Модуль Склад Битрикс24](https://bitrix24.ru/apps/app/bitrix24/warehouse/)
- [LangChain Documentation](https://langchain.readthedocs.io/)
- [Docker Documentation](https://docs.docker.com/)

---

## 📄 Лицензия

MIT License

---

## 👥 Авторы

- **Кривичев Алексей**  
  Email: Krivichev2000@gmail.com  
  Telegram: [@Noir_Codex](https://t.me/Noir_Codex)
- **Пугач Илья**  
  Email: ya.20022012@yandex.ru


