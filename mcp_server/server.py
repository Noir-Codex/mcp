"""MCP-сервер для управления складом и запасами (для обратной совместимости)."""

# Импорт из разделенных модулей
from .mcp_tools import mcp
from .http_server import app, run_server

# Экспорт для обратной совместимости
__all__ = ["mcp", "app"]

if __name__ == "__main__":
    # Запуск HTTP сервера
    run_server()