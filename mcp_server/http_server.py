"""HTTP сервер для MCP инструментов (FastAPI)."""

import os
import logging
from fastapi import FastAPI, HTTPException, Request
from dotenv import load_dotenv
import uvicorn

from .mcp_tools import (
    GetInventoryStatusParams,
    UpdateInventoryParams,
    CreateReorderRequestParams,
    SearchProductsParams,
    GetReorderStatusParams,
    UpdateReorderStatusParams,
    ListReorderRequestsParams,
    CreateProductParams,
    DeleteProductParams,
    ListProductsParams,
    _get_inventory_status_impl,
    _update_inventory_impl,
    _create_reorder_request_impl,
    _search_products_impl,
    _get_reorder_status_impl,
    _update_reorder_status_impl,
    _list_reorder_requests_impl,
    _create_product_impl,
    _delete_product_impl,
    _list_products_impl
)

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(title="Warehouse Inventory MCP Server")

# Добавление кастомных HTTP эндпоинтов для вызова инструментов
@app.post("/mcp/tools/{tool_name}")
async def call_mcp_tool(tool_name: str, request: Request):
    """HTTP эндпоинт для вызова MCP инструментов."""
    try:
        params = await request.json()
        logger.info(f"Вызов инструмента {tool_name} с параметрами: {params}")
        
        # Вызов соответствующего инструмента напрямую
        if tool_name == "get_inventory_status":
            tool_params = GetInventoryStatusParams(**params)
            result = await _get_inventory_status_impl(tool_params)
            return result.model_dump()
        
        elif tool_name == "update_inventory":
            tool_params = UpdateInventoryParams(**params)
            result = await _update_inventory_impl(tool_params)
            return result.model_dump()
        
        elif tool_name == "create_reorder_request":
            tool_params = CreateReorderRequestParams(**params)
            result = await _create_reorder_request_impl(tool_params)
            return result.model_dump()
        
        elif tool_name == "search_products":
            tool_params = SearchProductsParams(**params)
            result = await _search_products_impl(tool_params)
            return result.model_dump()
        
        elif tool_name == "get_reorder_status":
            tool_params = GetReorderStatusParams(**params)
            result = await _get_reorder_status_impl(tool_params)
            return result.model_dump()
        
        elif tool_name == "update_reorder_status":
            tool_params = UpdateReorderStatusParams(**params)
            result = await _update_reorder_status_impl(tool_params)
            return result.model_dump()
        
        elif tool_name == "list_reorder_requests":
            tool_params = ListReorderRequestsParams(**params)
            result = await _list_reorder_requests_impl(tool_params)
            return result.model_dump()
        
        elif tool_name == "create_product":
            tool_params = CreateProductParams(**params)
            result = await _create_product_impl(tool_params)
            return result.model_dump()
        
        elif tool_name == "delete_product":
            tool_params = DeleteProductParams(**params)
            result = await _delete_product_impl(tool_params)
            return result.model_dump()
        
        elif tool_name == "list_products":
            tool_params = ListProductsParams(**params)
            result = await _list_products_impl(tool_params)
            return result.model_dump()
        
        else:
            raise HTTPException(status_code=404, detail=f"Инструмент {tool_name} не найден")
    
    except ValueError as e:
        logger.error(f"Ошибка валидации: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка при вызове инструмента: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check эндпоинт."""
    return {"status": "ok", "service": "Warehouse Inventory MCP Server"}


def run_server():
    """Запуск HTTP сервера."""
    port = int(os.getenv("MCP_SERVER_PORT", 8000))
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    
    logger.info(f"Запуск HTTP сервера на {host}:{port}")
    logger.info("Доступные инструменты:")
    logger.info("  - get_inventory_status")
    logger.info("  - update_inventory")
    logger.info("  - create_reorder_request")
    logger.info("  - search_products")
    logger.info("  - get_reorder_status")
    logger.info("  - update_reorder_status")
    logger.info("  - list_reorder_requests")
    logger.info("  - create_product")
    logger.info("  - delete_product")
    logger.info("  - list_products")
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()

