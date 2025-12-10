"""MCP инструменты для управления складом (FastMCP протокол)."""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from difflib import SequenceMatcher
from fastmcp import FastMCP
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv

from .models import (
    InventoryStatus, InventoryUpdate, ReorderRequest, ProductSearchResult, 
    ReorderStatus, ReorderListResult, ProductCreate, ProductDelete
)

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Инициализация FastMCP
mcp = FastMCP("Warehouse Inventory MCP Server")

# Конфигурация внешнего API
WAREHOUSE_API_URL = os.getenv("WAREHOUSE_API_URL", "http://localhost:8001")
WAREHOUSE_API_KEY = os.getenv("WAREHOUSE_API_KEY", "")

# Временное хранилище для демонстрации (пустое при старте)
_inventory_storage = {}

# Индекс для быстрого поиска по названию
_product_name_index = {item["product_name"].lower(): sku for sku, item in _inventory_storage.items()}

# Импорт модуля базы данных для хранения заявок и товаров
from .database import (
    create_reorder_request as db_create_reorder_request,
    get_reorder_request as db_get_reorder_request,
    update_reorder_request_status as db_update_reorder_request_status,
    list_reorder_requests as db_list_reorder_requests,
    create_product as db_create_product,
    get_product as db_get_product,
    update_product_quantity as db_update_product_quantity,
    delete_product as db_delete_product,
    search_products_db as db_search_products,
    list_all_products as db_list_all_products,
    update_product as db_update_product
)

# Все заявки теперь хранятся в базе данных


# Модели параметров
class GetInventoryStatusParams(BaseModel):
    """Параметры для получения статуса запасов."""
    product_sku: str = Field(..., description="Артикул товара (SKU) или название товара")
    warehouse_id: Optional[str] = Field(None, description="ID склада (опционально)")


class UpdateInventoryParams(BaseModel):
    """Параметры для обновления запасов."""
    product_sku: str = Field(..., description="Артикул товара (SKU)")
    quantity_change: int = Field(..., description="Изменение количества")
    operation_type: str = Field(..., description="Тип операции: 'incoming' или 'outgoing'")
    warehouse_id: Optional[str] = Field(None, description="ID склада (опционально)")
    notes: Optional[str] = Field(None, description="Примечания к операции")


class CreateReorderRequestParams(BaseModel):
    """Параметры для создания заявки на пополнение."""
    product_sku: str = Field(..., description="Артикул товара (SKU)")
    requested_quantity: int = Field(..., description="Запрашиваемое количество товара")
    priority: Optional[str] = Field("medium", description="Приоритет заявки: 'low', 'medium', 'high'")
    warehouse_id: Optional[str] = Field(None, description="ID склада (опционально)")


class SearchProductsParams(BaseModel):
    """Параметры для поиска товаров по названию."""
    product_name: str = Field(..., description="Название товара для поиска (можно частичное)")
    warehouse_id: Optional[str] = Field(None, description="ID склада (опционально)")


class GetReorderStatusParams(BaseModel):
    """Параметры для получения статуса заявки на пополнение."""
    request_id: str = Field(..., description="ID заявки на пополнение")


class UpdateReorderStatusParams(BaseModel):
    """Параметры для обновления статуса заявки."""
    request_id: str = Field(..., description="ID заявки")
    status: str = Field(..., description="Новый статус: 'pending', 'approved', 'rejected', 'completed'")
    notes: Optional[str] = Field(None, description="Примечания к изменению статуса")


class ListReorderRequestsParams(BaseModel):
    """Параметры для получения списка заявок."""
    status: Optional[str] = Field(None, description="Фильтр по статусу")
    product_sku: Optional[str] = Field(None, description="Фильтр по артикулу товара")
    limit: Optional[int] = Field(100, description="Максимальное количество заявок")


class CreateProductParams(BaseModel):
    """Параметры для создания товара."""
    product_sku: str = Field(..., description="Артикул товара (SKU)")
    product_name: str = Field(..., description="Название товара")
    current_quantity: Optional[int] = Field(0, description="Начальное количество")
    min_quantity: Optional[int] = Field(0, description="Минимальный уровень запасов")
    max_quantity: Optional[int] = Field(0, description="Максимальный уровень запасов")
    unit: Optional[str] = Field("шт", description="Единица измерения")
    category: Optional[str] = Field(None, description="Категория товара")
    warehouse_id: Optional[str] = Field("WH001", description="ID склада")
    description: Optional[str] = Field(None, description="Описание товара")


class DeleteProductParams(BaseModel):
    """Параметры для удаления товара."""
    product_sku: str = Field(..., description="Артикул товара для удаления")


class ListProductsParams(BaseModel):
    """Параметры для получения списка товаров."""
    category: Optional[str] = Field(None, description="Фильтр по категории")
    warehouse_id: Optional[str] = Field(None, description="Фильтр по складу")
    limit: Optional[int] = Field(100, description="Максимальное количество товаров")


# Вспомогательные функции
def _normalize_product_name(search_name: str) -> str:
    """Нормализация названия товара."""
    return search_name.lower().strip()


def _fuzzy_find_products(
    search_term: str,
    warehouse_id: Optional[str] = None,
    limit: int = 5,
    threshold: float = 0.55,
) -> List[Dict[str, Any]]:
    """
    Нечеткий поиск товаров по названию или SKU.
    Возвращает отсортированный список товаров с совпадением выше порога.
    """
    query = search_term.lower().strip()
    if not query:
        return []

    products = db_list_all_products(limit=1000)
    if warehouse_id:
        products = [p for p in products if p.get("warehouse_id") == warehouse_id]

    scored: List[tuple[float, Dict[str, Any]]] = []
    for product in products:
        candidates = [
            product.get("product_name", ""),
            product.get("product_sku", ""),
        ]
        best_ratio = 0.0
        for candidate in candidates:
            cand = candidate.lower().strip()
            if not cand:
                continue
            ratio = SequenceMatcher(None, query, cand).ratio()
            best_ratio = max(best_ratio, ratio)
        if best_ratio >= threshold:
            scored.append((best_ratio, product))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [p for _, p in scored[:limit]]


async def _call_warehouse_api(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Вызов внешнего Warehouse API."""
    try:
        headers = {"Content-Type": "application/json"}
        if WAREHOUSE_API_KEY and WAREHOUSE_API_KEY != "your_warehouse_api_key_here":
            headers["Authorization"] = f"Bearer {WAREHOUSE_API_KEY}"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{WAREHOUSE_API_URL.rstrip('/')}/{endpoint.lstrip('/')}"
            logger.info(f"Вызов внешнего API: {method} {url}")
            
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=data)
            elif method == "PUT":
                response = await client.put(url, headers=headers, json=data)
            else:
                raise ValueError(f"Неподдерживаемый метод: {method}")
            
            response.raise_for_status()
            result = response.json()
            logger.info(f"Успешный ответ от внешнего API: {endpoint}")
            return result
    except httpx.ConnectError:
        logger.warning(f"Не удалось подключиться к внешнему API {WAREHOUSE_API_URL}, используем локальное хранилище")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP ошибка от внешнего API: {e.response.status_code}, используем локальное хранилище")
        return None
    except Exception as e:
        logger.warning(f"Ошибка при вызове внешнего API: {str(e)}, используем локальное хранилище")
        return None


# Реализации функций (используются и в MCP, и в HTTP)
async def _search_products_impl(params: SearchProductsParams) -> ProductSearchResult:
    """Поиск товаров по названию в базе данных."""
    try:
        logger.info(f"Поиск товаров по названию: {params.product_name}")
        
        search_name = params.product_name.lower().strip()
        normalized_name = _normalize_product_name(search_name)
        
        found_products = []
        seen_skus = set()
        
        # Если название было нормализовано, используем нормализованное для поиска
        # Иначе используем оригинальное название
        search_terms = []
        if normalized_name != search_name:
            logger.info(f"Название нормализовано: '{search_name}' -> '{normalized_name}'")
            search_terms.append(normalized_name)
        search_terms.append(params.product_name)  # Также пробуем оригинальное название
        
        # Убираем дубликаты
        search_terms = list(dict.fromkeys(search_terms))
        
        # Ищем по всем вариантам названия
        for search_term in search_terms:
            logger.debug(f"Поиск товаров с термином: '{search_term}'")
            products = db_search_products(
                product_name=search_term,
                warehouse_id=params.warehouse_id,
                limit=100
            )
            
            # Добавляем найденные товары
            for product in products:
                if product["product_sku"] not in seen_skus:
                    found_products.append({
                        "sku": product["product_sku"],
                        "product_name": product["product_name"],
                        "current_quantity": product["current_quantity"],
                        "status": "in_stock" if product["current_quantity"] > 0 else "out_of_stock",
                        "unit": product.get("unit", "шт")
                    })
                    seen_skus.add(product["product_sku"])
                    logger.debug(f"Найден товар: {product['product_name']} (SKU: {product['product_sku']})")
        
        # Если ничего не нашли, пробуем нечеткий поиск
        if not found_products:
            fuzzy_products = _fuzzy_find_products(
                search_term=params.product_name,
                warehouse_id=params.warehouse_id,
                limit=10,
                threshold=0.5,
            )
            for product in fuzzy_products:
                if product["product_sku"] not in seen_skus:
                    found_products.append({
                        "sku": product["product_sku"],
                        "product_name": product["product_name"],
                        "current_quantity": product["current_quantity"],
                        "status": "in_stock" if product["current_quantity"] > 0 else "out_of_stock",
                        "unit": product.get("unit", "шт")
                    })
                    seen_skus.add(product["product_sku"])
                    logger.debug(f"Нечеткое совпадение: {product['product_name']} (SKU: {product['product_sku']})")

        logger.info(f"Найдено товаров: {len(found_products)}")
        
        return ProductSearchResult(
            found=len(found_products) > 0,
            products=found_products,
            count=len(found_products)
        )
    
    except Exception as e:
        logger.error(f"Ошибка при поиске товаров: {str(e)}")
        raise


async def _get_inventory_status_impl(params: GetInventoryStatusParams) -> InventoryStatus:
    """Получает текущее состояние запасов для указанного товара."""
    try:
        logger.info(f"Запрос статуса запасов для товара: {params.product_sku}")
        
        # Проверяем, является ли параметр названием товара или SKU
        product_sku = params.product_sku
        
        # Сначала пытаемся найти по SKU в БД
        product = db_get_product(product_sku)
        
        # Если не нашли по SKU, ищем по названию в БД
        if not product:
            # Нормализуем название для поиска синонимов
            search_name = product_sku.lower().strip()
            normalized_name = _normalize_product_name(search_name)
            
            # Пробуем поиск с оригинальным названием
            products = db_search_products(product_name=product_sku, limit=1)
            if products:
                product = products[0]
                product_sku = product["product_sku"]
                logger.info(f"Найден товар по названию: {product_sku}")
            # Если не нашли и название было нормализовано, пробуем с нормализованным названием
            elif normalized_name != search_name:
                products = db_search_products(product_name=normalized_name, limit=1)
                if products:
                    product = products[0]
                    product_sku = product["product_sku"]
                    logger.info(f"Найден товар по нормализованному названию: {product_sku}")

        # Если прямой поиск не дал результата, пробуем нечеткое сопоставление
        if not product:
            fuzzy_products = _fuzzy_find_products(
                search_term=params.product_sku,
                warehouse_id=params.warehouse_id,
                limit=1,
                threshold=0.55,
            )
            if fuzzy_products:
                product = fuzzy_products[0]
                product_sku = product["product_sku"]
                logger.info(f"Нечеткое совпадение товара: {product_sku}")
        
        # Попытка получить данные из внешнего API
        use_external_api = (WAREHOUSE_API_URL and 
                           WAREHOUSE_API_URL != "https://api.example.com/warehouse" and
                           WAREHOUSE_API_URL != "https://jsonplaceholder.typicode.com")
        
        if use_external_api:
            search_sku = product_sku
            search_name = product_sku.lower().strip()
            normalized_name = _normalize_product_name(search_name)
            
            if product_sku not in _inventory_storage:
                if normalized_name in _product_name_index:
                    search_sku = _product_name_index[normalized_name]
                elif search_name in _product_name_index:
                    search_sku = _product_name_index[search_name]
            
            api_data = await _call_warehouse_api(f"inventory/{search_sku}")
            if not api_data and product_sku not in _inventory_storage:
                api_data = await _call_warehouse_api(f"inventory/{product_sku}")
            
            if api_data:
                current_qty = api_data.get("current_quantity", 0)
                min_qty = api_data.get("min_quantity", 50)
                max_qty = api_data.get("max_quantity", 500)
                
                if current_qty == 0:
                    status = "out_of_stock"
                elif current_qty <= min_qty:
                    status = "low_stock"
                else:
                    status = "in_stock"
                
                return InventoryStatus(
                    product_sku=api_data.get("product_sku", search_sku),
                    product_name=api_data.get("product_name", f"Товар {search_sku}"),
                    current_quantity=current_qty,
                    min_quantity=min_qty,
                    max_quantity=max_qty,
                    status=status,
                    last_updated=api_data.get("last_updated", datetime.utcnow().isoformat() + "Z"),
                    warehouse_id=params.warehouse_id or api_data.get("warehouse_id"),
                    unit=api_data.get("unit", "шт")
                )
        
        # Получение из базы данных
        if not product:
            # Если товар еще не найден, пробуем поиск по названию с нормализацией
            search_name = params.product_sku.lower().strip()
            normalized_name = _normalize_product_name(search_name)
            
            # Пробуем поиск с оригинальным названием
            products = db_search_products(product_name=params.product_sku, limit=1)
            if products:
                product = products[0]
                product_sku = product["product_sku"]
            # Если не нашли и название было нормализовано, пробуем с нормализованным названием
            elif normalized_name != search_name:
                products = db_search_products(product_name=normalized_name, limit=1)
                if products:
                    product = products[0]
                    product_sku = product["product_sku"]
            
            if not product:
                raise ValueError(f"Товар '{params.product_sku}' не найден. Используйте поиск товаров для получения списка доступных товаров.")
        
        current_qty = product["current_quantity"]
        min_qty = product["min_quantity"]
        
        if current_qty == 0:
            status = "out_of_stock"
        elif current_qty <= min_qty:
            status = "low_stock"
        else:
            status = "in_stock"
        
        return InventoryStatus(
            product_sku=product_sku,
            product_name=product["product_name"],
            current_quantity=current_qty,
            min_quantity=min_qty,
            max_quantity=product["max_quantity"],
            status=status,
            last_updated=product.get("updated_at") or product.get("created_at"),
            warehouse_id=params.warehouse_id or product.get("warehouse_id"),
            unit=product.get("unit", "шт")
        )
    
    except Exception as e:
        logger.error(f"Ошибка при получении статуса запасов: {str(e)}")
        raise


async def _update_inventory_impl(params: UpdateInventoryParams) -> InventoryUpdate:
    """Обновляет количество товара на складе."""
    try:
        logger.info(f"Обновление запасов для товара {params.product_sku}: {params.quantity_change} ({params.operation_type})")
        
        if params.operation_type not in ["incoming", "outgoing"]:
            raise ValueError("operation_type должен быть 'incoming' или 'outgoing'")
        
        # Попытка обновить через внешний API
        use_external_api = (WAREHOUSE_API_URL and 
                           WAREHOUSE_API_URL != "https://api.example.com/warehouse" and
                           WAREHOUSE_API_URL != "https://jsonplaceholder.typicode.com")
        
        if use_external_api:
            api_data = await _call_warehouse_api(
                "inventory/update",
                method="POST",
                data={
                    "product_sku": params.product_sku,
                    "quantity_change": params.quantity_change,
                    "operation_type": params.operation_type,
                    "warehouse_id": params.warehouse_id,
                    "notes": params.notes
                }
            )
            if api_data:
                return InventoryUpdate(
                    success=True,
                    product_sku=api_data.get("product_sku", params.product_sku),
                    previous_quantity=api_data.get("previous_quantity", 0),
                    new_quantity=api_data.get("new_quantity", 0),
                    operation_type=params.operation_type,
                    timestamp=api_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                    warehouse_id=params.warehouse_id or api_data.get("warehouse_id")
                )
        
        # Получение товара из БД
        product = db_get_product(params.product_sku)
        if not product:
            raise ValueError(f"Товар '{params.product_sku}' не найден")
        
        previous_quantity = product["current_quantity"]
        
        if params.operation_type == "incoming":
            new_quantity = previous_quantity + abs(params.quantity_change)
        else:
            new_quantity = max(0, previous_quantity - abs(params.quantity_change))
        
        if new_quantity < 0:
            raise ValueError(f"Недостаточно товара. Текущее количество: {previous_quantity}, запрошено: {params.quantity_change}")
        
        # Обновление в БД
        db_update_product_quantity(params.product_sku, new_quantity)
        
        logger.info(f"Запасы обновлены: {previous_quantity} -> {new_quantity}")
        
        return InventoryUpdate(
            success=True,
            product_sku=params.product_sku,
            previous_quantity=previous_quantity,
            new_quantity=new_quantity,
            operation_type=params.operation_type,
            timestamp=datetime.utcnow().isoformat() + "Z",
            warehouse_id=params.warehouse_id or product.get("warehouse_id"),
            unit=product.get("unit", "шт")
        )
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении запасов: {str(e)}")
        raise


async def _create_reorder_request_impl(params: CreateReorderRequestParams) -> ReorderRequest:
    """Создает заявку на пополнение запасов в базе данных."""
    try:
        logger.info(f"Создание заявки на пополнение для товара {params.product_sku}: {params.requested_quantity}")
        
        if params.priority not in ["low", "medium", "high"]:
            raise ValueError("priority должен быть 'low', 'medium' или 'high'")
        
        # Проверяем, существует ли товар
        product = db_get_product(params.product_sku)
        if not product:
            raise ValueError(f"Товар '{params.product_sku}' не найден. Используйте поиск товаров для получения списка доступных товаров.")
        
        # Генерируем уникальный ID заявки
        date_str = datetime.utcnow().strftime('%Y%m%d')
        existing_requests = db_list_reorder_requests(limit=1000)
        # Находим максимальный номер для сегодняшней даты
        max_num = 0
        for req in existing_requests:
            if req['request_id'].startswith(f"REQ-{date_str}-"):
                try:
                    num = int(req['request_id'].split('-')[-1])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        request_id = f"REQ-{date_str}-{max_num + 1:03d}"
        
        # Создаем заявку в БД
        request_data = db_create_reorder_request(
            request_id=request_id,
            product_sku=params.product_sku,
            requested_quantity=params.requested_quantity,
            priority=params.priority,
            warehouse_id=params.warehouse_id,
            notes=None
        )
        
        logger.info(f"Заявка создана в БД: {request_id}")
        
        return ReorderRequest(
            success=True,
            request_id=request_data["request_id"],
            product_sku=request_data["product_sku"],
            requested_quantity=request_data["requested_quantity"],
            status=request_data["status"],
            created_at=request_data["created_at"],
            priority=request_data["priority"],
            warehouse_id=request_data.get("warehouse_id")
        )
    
    except Exception as e:
        logger.error(f"Ошибка при создании заявки на пополнение: {str(e)}")
        raise


# Регистрация MCP инструментов
@mcp.tool()
async def get_inventory_status(params: GetInventoryStatusParams) -> InventoryStatus:
    """Получает текущее состояние запасов для указанного товара."""
    return await _get_inventory_status_impl(params)


@mcp.tool()
async def update_inventory(params: UpdateInventoryParams) -> InventoryUpdate:
    """Обновляет количество товара на складе (приход или расход)."""
    return await _update_inventory_impl(params)


@mcp.tool()
async def create_reorder_request(params: CreateReorderRequestParams) -> ReorderRequest:
    """Создает заявку на пополнение запасов для товаров с низким остатком."""
    return await _create_reorder_request_impl(params)


@mcp.tool()
async def search_products(params: SearchProductsParams) -> ProductSearchResult:
    """Поиск товаров по названию. Возвращает список товаров с их SKU для дальнейшей работы."""
    return await _search_products_impl(params)


async def _get_reorder_status_impl(params: GetReorderStatusParams) -> ReorderStatus:
    """Получает статус заявки на пополнение запасов из базы данных."""
    try:
        logger.info(f"Запрос статуса заявки: {params.request_id}")
        
        # Получаем из базы данных
        request_data = db_get_reorder_request(params.request_id)
        
        if not request_data:
            raise ValueError(f"Заявка {params.request_id} не найдена в базе данных")
        
        # Получаем название товара из БД
        product = db_get_product(request_data["product_sku"])
        product_name = product["product_name"] if product else None
        
        return ReorderStatus(
            request_id=params.request_id,
            product_sku=request_data["product_sku"],
            product_name=product_name,
            requested_quantity=request_data["requested_quantity"],
            status=request_data["status"],
            priority=request_data.get("priority"),
            created_at=request_data["created_at"],
            warehouse_id=request_data.get("warehouse_id")
        )
    
    except Exception as e:
        logger.error(f"Ошибка при получении статуса заявки: {str(e)}")
        raise


@mcp.tool()
async def get_reorder_status(params: GetReorderStatusParams) -> ReorderStatus:
    """Получает статус заявки на пополнение запасов по ID заявки."""
    return await _get_reorder_status_impl(params)


async def _update_reorder_status_impl(params: UpdateReorderStatusParams) -> ReorderStatus:
    """Обновляет статус заявки на пополнение."""
    try:
        logger.info(f"Обновление статуса заявки {params.request_id} на {params.status}")
        
        if params.status not in ["pending", "approved", "rejected", "completed"]:
            raise ValueError("status должен быть 'pending', 'approved', 'rejected' или 'completed'")
        
        # Обновление в базе данных
        success = db_update_reorder_request_status(
            request_id=params.request_id,
            status=params.status,
            notes=params.notes
        )
        
        if not success:
            raise ValueError(f"Заявка {params.request_id} не найдена")
        
        # Получаем обновленные данные
        request_data = db_get_reorder_request(params.request_id)
        if not request_data:
            raise ValueError(f"Заявка {params.request_id} не найдена после обновления")
        
        # Получаем название товара
        product_name = None
        if request_data["product_sku"] in _inventory_storage:
            product_name = _inventory_storage[request_data["product_sku"]]["product_name"]
        
        return ReorderStatus(
            request_id=params.request_id,
            product_sku=request_data["product_sku"],
            product_name=product_name,
            requested_quantity=request_data["requested_quantity"],
            status=request_data["status"],
            priority=request_data.get("priority"),
            created_at=request_data["created_at"],
            updated_at=request_data.get("updated_at"),
            warehouse_id=request_data.get("warehouse_id"),
            notes=request_data.get("notes")
        )
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса заявки: {str(e)}")
        raise


async def _list_reorder_requests_impl(params: ListReorderRequestsParams) -> ReorderListResult:
    """Получает список заявок на пополнение с фильтрацией."""
    try:
        logger.info(f"Получение списка заявок: status={params.status}, product_sku={params.product_sku}")
        
        requests = db_list_reorder_requests(
            status=params.status,
            product_sku=params.product_sku,
            limit=params.limit or 100
        )
        
        # Добавляем названия товаров из БД
        for req in requests:
            product = db_get_product(req["product_sku"])
            if product:
                req["product_name"] = product["product_name"]
            else:
                req["product_name"] = f"Товар {req['product_sku']}"
        
        logger.info(f"Возвращаем {len(requests)} заявок")
        
        return ReorderListResult(
            requests=requests,
            count=len(requests)
        )
    
    except Exception as e:
        logger.error(f"Ошибка при получении списка заявок: {str(e)}")
        raise


@mcp.tool()
async def update_reorder_status(params: UpdateReorderStatusParams) -> ReorderStatus:
    """Обновляет статус заявки на пополнение (например, одобрить или отклонить)."""
    return await _update_reorder_status_impl(params)


@mcp.tool()
async def list_reorder_requests(params: ListReorderRequestsParams) -> ReorderListResult:
    """Получает список заявок на пополнение с возможностью фильтрации по статусу и товару."""
    return await _list_reorder_requests_impl(params)


async def _create_product_impl(params: CreateProductParams) -> ProductCreate:
    """Создает новый товар в базе данных."""
    try:
        logger.info(f"Создание товара: {params.product_sku} - {params.product_name}")
        
        product = db_create_product(
            product_sku=params.product_sku,
            product_name=params.product_name,
            current_quantity=params.current_quantity or 0,
            min_quantity=params.min_quantity or 0,
            max_quantity=params.max_quantity or 0,
            unit=params.unit or "шт",
            category=params.category,
            warehouse_id=params.warehouse_id or "WH001",
            description=params.description
        )
        
        return ProductCreate(
            success=True,
            product_sku=product["product_sku"],
            product_name=product["product_name"],
            message=f"Товар {params.product_name} (SKU: {params.product_sku}) успешно создан"
        )
    except ValueError as e:
        return ProductCreate(
            success=False,
            product_sku=params.product_sku,
            product_name=params.product_name,
            message=str(e)
        )
    except Exception as e:
        logger.error(f"Ошибка при создании товара: {str(e)}")
        raise


async def _delete_product_impl(params: DeleteProductParams) -> ProductDelete:
    """Удаляет товар из базы данных."""
    try:
        logger.info(f"Удаление товара: {params.product_sku}")
        
        # Получаем информацию о товаре перед удалением
        product = db_get_product(params.product_sku)
        if not product:
            return ProductDelete(
                success=False,
                product_sku=params.product_sku,
                message=f"Товар с SKU {params.product_sku} не найден"
            )
        
        success = db_delete_product(params.product_sku)
        
        if success:
            return ProductDelete(
                success=True,
                product_sku=params.product_sku,
                message=f"Товар {product['product_name']} (SKU: {params.product_sku}) успешно удален"
            )
        else:
            return ProductDelete(
                success=False,
                product_sku=params.product_sku,
                message=f"Не удалось удалить товар {params.product_sku}"
            )
    except Exception as e:
        logger.error(f"Ошибка при удалении товара: {str(e)}")
        raise


async def _list_products_impl(params: ListProductsParams) -> ProductSearchResult:
    """Получает список всех товаров с возможностью фильтрации."""
    try:
        logger.info(f"Получение списка товаров: category={params.category}, warehouse_id={params.warehouse_id}")
        
        products = db_search_products(
            category=params.category,
            warehouse_id=params.warehouse_id,
            limit=params.limit or 100
        )
        
        found_products = []
        for product in products:
            found_products.append({
                "sku": product["product_sku"],
                "product_name": product["product_name"],
                "current_quantity": product["current_quantity"],
                "status": "in_stock" if product["current_quantity"] > 0 else "out_of_stock",
                "unit": product.get("unit", "шт")
            })
        
        return ProductSearchResult(
            found=len(found_products) > 0,
            products=found_products,
            count=len(found_products)
        )
    except Exception as e:
        logger.error(f"Ошибка при получении списка товаров: {str(e)}")
        raise


@mcp.tool()
async def create_product(params: CreateProductParams) -> ProductCreate:
    """Создает новый товар в базе данных."""
    return await _create_product_impl(params)


@mcp.tool()
async def delete_product(params: DeleteProductParams) -> ProductDelete:
    """Удаляет товар из базы данных."""
    return await _delete_product_impl(params)


@mcp.tool()
async def list_products(params: ListProductsParams) -> ProductSearchResult:
    """Получает список всех товаров с возможностью фильтрации по категории и складу."""
    return await _list_products_impl(params)

