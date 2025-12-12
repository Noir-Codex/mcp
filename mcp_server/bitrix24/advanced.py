"""Расширенные инструменты для работы со складом в Битрикс24."""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from .client import bitrix24_client

logger = logging.getLogger(__name__)


class GetWarehousesParams(BaseModel):
    """Параметры для получения списка складов."""
    filter_title: Optional[str] = Field(None, description="Фильтр по названию склада")
    active_only: Optional[bool] = Field(True, description="Только активные склады")
    limit: Optional[int] = Field(50, description="Максимальное количество складов")


class GetProductStockParams(BaseModel):
    """Параметры для получения остатков товара на складах."""
    product_sku: str = Field(..., description="SKU товара")
    warehouse_id: Optional[int] = Field(None, description="ID конкретного склада")


class SetProductStockParams(BaseModel):
    """Параметры для установки остатков товара на складе."""
    product_sku: str = Field(..., description="SKU товара")
    warehouse_id: int = Field(..., description="ID склада")
    quantity: float = Field(..., description="Количество")


class GetStockMovementsParams(BaseModel):
    """Параметры для получения движений товаров."""
    product_sku: Optional[str] = Field(None, description="Фильтр по SKU товара")
    warehouse_id: Optional[int] = Field(None, description="Фильтр по ID склада")
    limit: Optional[int] = Field(100, description="Максимальное количество записей")


class CreateWarehouseParams(BaseModel):
    """Параметры для создания склада."""
    title: str = Field(..., description="Название склада")
    address: Optional[str] = Field(None, description="Адрес склада")
    description: Optional[str] = Field(None, description="Описание склада")


class BitrixWarehouseManager:
    """Менеджер для работы со складом Битрикс24."""
    
    def __init__(self):
        self.client = bitrix24_client
        self._catalog_available = None
    
    async def check_catalog_access(self) -> bool:
        """Проверка доступа к модулю каталога."""
        if self._catalog_available is not None:
            return self._catalog_available
        
        try:
            result = await self.client._make_request("catalog.store.list", {})
            
            # Логируем ответ для отладки
            logger.debug(f"Проверка доступа к каталогу. Ответ: {json.dumps(result, ensure_ascii=False)[:500]}...")
            
            if isinstance(result, dict) and "error" in result:
                error = result.get("error", "")
                if "ACCESS_DENIED" in error or "AUTH" in error:
                    logger.warning("Нет доступа к модулю каталога. Проверьте права вебхука.")
                    self._catalog_available = False
                    return False
            
            # Если ответ успешный (не содержит ошибку)
            self._catalog_available = True
            return True
            
        except Exception as e:
            logger.warning(f"Ошибка проверки доступа к каталогу: {str(e)}")
            self._catalog_available = False
            return False
    
    async def get_warehouses(self, params: GetWarehousesParams) -> Dict[str, Any]:
        """Получение списка складов из Битрикс24."""
        if not self.client.enabled:
            return {"status": "disabled", "message": "Интеграция с Битрикс24 отключена"}
        
        # Проверяем доступ к каталогу
        if not await self.check_catalog_access():
            return {
                "success": False, 
                "error": "Нет доступа к модулю 'Торговый каталог'",
                "details": "Добавьте права 'catalog' для вебхука в Битрикс24"
            }
        
        try:
            # Параметры запроса согласно документации
            request_params = {}
            
            # Добавляем фильтр по названию если указан
            if params.filter_title:
                request_params["filter"] = {"TITLE": f"%{params.filter_title}%"}
            
            result = await self.client._make_request("catalog.store.list", request_params)
            
            # Логируем сырой ответ для отладки
            logger.debug(f"Сырой ответ от catalog.store.list: {json.dumps(result, ensure_ascii=False)[:1000]}...")
            
            if isinstance(result, dict) and "error" in result:
                error_msg = result.get("error_description", result.get("error", "Unknown error"))
                return {"success": False, "error": error_msg}
            
            # Обрабатываем ответ - в Битрикс24 ответ может быть просто массивом складов
            warehouses = []
            
            # Вариант 1: ответ - это массив складов
            if isinstance(result, list):
                warehouses = result
            # Вариант 2: ответ - это словарь с ключом "result"
            elif isinstance(result, dict) and "result" in result:
                result_data = result["result"]
                if isinstance(result_data, list):
                    warehouses = result_data
                elif isinstance(result_data, dict):
                    # Иногда может быть словарь с ключами-айдишниками
                    warehouses = list(result_data.values())
            # Вариант 3: ответ - это словарь с другими ключами
            elif isinstance(result, dict):
                # Пробуем найти массивы в значениях словаря
                for value in result.values():
                    if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                        warehouses = value
                        break
            
            # Фильтруем по активности если нужно
            filtered_warehouses = []
            for wh in warehouses:
                if not isinstance(wh, dict):
                    continue
                    
                # Проверяем активность
                if params.active_only:
                    active = wh.get("ACTIVE")
                    if active is not None and str(active).upper() not in ["Y", "YES", "1", "TRUE"]:
                        continue
                
                # Форматируем запись склада
                warehouse = {
                    "ID": wh.get("ID") or wh.get("id"),
                    "TITLE": wh.get("TITLE") or wh.get("title") or wh.get("NAME") or "",
                    "ADDRESS": wh.get("ADDRESS") or wh.get("address") or "",
                    "DESCRIPTION": wh.get("DESCRIPTION") or wh.get("description") or "",
                    "ACTIVE": wh.get("ACTIVE") or wh.get("active") or "Y",
                    "SORT": wh.get("SORT") or wh.get("sort") or 500,
                    "CODE": wh.get("CODE") or wh.get("code") or ""
                }
                
                # Преобразуем ID в число если возможно
                try:
                    if warehouse["ID"]:
                        warehouse["ID"] = int(warehouse["ID"])
                except (ValueError, TypeError):
                    pass
                    
                filtered_warehouses.append(warehouse)
            
            # Сортируем по SORT или TITLE
            filtered_warehouses.sort(key=lambda x: (x.get("SORT", 500), x.get("TITLE", "")))
            
            # Ограничиваем количество
            filtered_warehouses = filtered_warehouses[:params.limit]
            
            logger.info(f"Получено складов: {len(filtered_warehouses)}")
            
            return {
                "success": True,
                "warehouses": filtered_warehouses,
                "count": len(filtered_warehouses)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении складов: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def get_product_stock(self, params: GetProductStockParams) -> Dict[str, Any]:
        """Получение остатков товара на складах."""
        if not self.client.enabled:
            return {"status": "disabled", "message": "Интеграция с Битрикс24 отключена"}
        
        if not await self.check_catalog_access():
            return {"success": False, "error": "Нет доступа к модулю 'Торговый каталог'"}
        
        try:
            # 1. Находим товар по SKU в каталоге
            # Пробуем через catalog.product.list
            catalog_product_result = await self.client._make_request("catalog.product.list", {
                "filter": {"XML_ID": params.product_sku},
                "select": ["ID", "NAME", "XML_ID"]
            })
            
            logger.debug(f"Поиск товара в каталоге: {json.dumps(catalog_product_result, ensure_ascii=False)[:500]}...")
            
            product_id = None
            product_name = params.product_sku
            
            if isinstance(catalog_product_result, dict) and "error" not in catalog_product_result:
                result_data = catalog_product_result.get("result", {})
                
                # Вариант 1: результат - словарь с ключом "products"
                if isinstance(result_data, dict) and "products" in result_data:
                    products = result_data["products"]
                    if isinstance(products, list) and products:
                        for product in products:
                            if product.get("XML_ID") == params.product_sku:
                                product_id = product.get("ID")
                                product_name = product.get("NAME", params.product_sku)
                                break
                # Вариант 2: результат - просто список товаров
                elif isinstance(result_data, list):
                    for product in result_data:
                        if product.get("XML_ID") == params.product_sku:
                            product_id = product.get("ID")
                            product_name = product.get("NAME", params.product_sku)
                            break
                # Вариант 3: результат - словарь с ID как ключами
                elif isinstance(result_data, dict):
                    for product_id_key, product in result_data.items():
                        if isinstance(product, dict) and product.get("XML_ID") == params.product_sku:
                            product_id = product.get("ID")
                            product_name = product.get("NAME", params.product_sku)
                            break
            
            # Если не нашли в каталоге, пробуем через CRM
            if not product_id:
                logger.debug(f"Товар {params.product_sku} не найден в каталоге, пробую CRM...")
                
                crm_product_result = await self.client._make_request("crm.product.list", {
                    "filter": {"XML_ID": params.product_sku},
                    "select": ["ID", "NAME"]
                })
                
                if isinstance(crm_product_result, dict) and "error" not in crm_product_result:
                    crm_products = crm_product_result.get("result", [])
                    if isinstance(crm_products, list) and crm_products:
                        product_id = crm_products[0].get("ID")
                        product_name = crm_products[0].get("NAME", params.product_sku)
            
            if not product_id:
                return {"success": False, "error": f"Товар с SKU {params.product_sku} не найден в системе"}
            
            # 2. Получаем остатки на складах через catalog.storeproduct.list
            # Согласно документации, фильтр должен быть в формате {"field": "value"}
            filter_dict = {"PRODUCT_ID": product_id}
            
            if params.warehouse_id:
                filter_dict["STORE_ID"] = params.warehouse_id
            
            # Выбираем поля согласно документации
            stock_params = {
                "filter": filter_dict,
                "select": ["ID", "PRODUCT_ID", "STORE_ID", "AMOUNT"]
            }
            
            stock_result = await self.client._make_request("catalog.storeproduct.list", stock_params)
            
            logger.debug(f"Результат получения остатков: {json.dumps(stock_result, ensure_ascii=False)[:500]}...")
            
            if isinstance(stock_result, dict) and "error" in stock_result:
                error_msg = stock_result.get("error_description", stock_result.get("error", "Unknown error"))
                return {
                    "success": False,
                    "error": f"Не удалось получить остатки: {error_msg}",
                    "product_info": {
                        "id": product_id,
                        "name": product_name,
                        "sku": params.product_sku
                    }
                }
            
            # Обрабатываем ответ с остатками
            stock_items = []
            
            # Вариант 1: ответ - это массив остатков
            if isinstance(stock_result, list):
                stock_items = stock_result
            # Вариант 2: ответ - это словарь с ключом "result"
            elif isinstance(stock_result, dict) and "result" in stock_result:
                result_data = stock_result["result"]
                if isinstance(result_data, list):
                    stock_items = result_data
                elif isinstance(result_data, dict):
                    # Иногда может быть словарь с ключами-айдишниками
                    stock_items = list(result_data.values())
            
            # 3. Получаем информацию о складах для отображения названий
            warehouses_info = await self.get_warehouses(GetWarehousesParams(limit=100))
            warehouses_map = {}
            
            if warehouses_info.get("success"):
                for wh in warehouses_info.get("warehouses", []):
                    wh_id = wh.get("ID")
                    if wh_id:
                        warehouses_map[str(wh_id)] = wh.get("TITLE", f"Склад {wh_id}")
            
            # Формируем ответ
            stocks = []
            total_quantity = 0
            
            for item in stock_items:
                if not isinstance(item, dict):
                    continue
                    
                store_id = item.get("STORE_ID")
                if store_id is None:
                    continue
                    
                # Преобразуем store_id в строку для поиска в словаре
                store_id_str = str(store_id)
                
                quantity = 0
                try:
                    quantity = float(item.get("AMOUNT", 0))
                except (ValueError, TypeError):
                    quantity = 0
                    
                total_quantity += quantity
                
                stocks.append({
                    "warehouse_id": store_id,
                    "warehouse_title": warehouses_map.get(store_id_str, f"Склад {store_id}"),
                    "quantity": quantity,
                    "product_id": product_id
                })
            
            logger.info(f"Получено остатков для товара {params.product_sku}: {len(stocks)} записей, всего {total_quantity} единиц")
            
            return {
                "success": True,
                "product": {
                    "id": product_id,
                    "name": product_name,
                    "sku": params.product_sku
                },
                "stocks": stocks,
                "total_quantity": total_quantity,
                "count": len(stocks)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении остатков: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def set_product_stock(self, params: SetProductStockParams) -> Dict[str, Any]:
        """Установка остатков товара на складе."""
        if not self.client.enabled:
            return {"status": "disabled", "message": "Интеграция с Битрикс24 отключена"}
        
        if not await self.check_catalog_access():
            return {"success": False, "error": "Нет доступа к модулю 'Торговый каталог'"}
        
        try:
            # 1. Находим товар по SKU
            # Пробуем через catalog.product.list
            catalog_product_result = await self.client._make_request("catalog.product.list", {
                "filter": {"XML_ID": params.product_sku},
                "select": ["ID", "NAME"]
            })
            
            product_id = None
            product_name = params.product_sku
            
            if isinstance(catalog_product_result, dict) and "error" not in catalog_product_result:
                result_data = catalog_product_result.get("result", {})
                
                # Обрабатываем разные форматы ответа
                if isinstance(result_data, dict) and "products" in result_data:
                    products = result_data["products"]
                    if isinstance(products, list) and products:
                        product_id = products[0].get("ID")
                        product_name = products[0].get("NAME", params.product_sku)
                elif isinstance(result_data, list) and result_data:
                    product_id = result_data[0].get("ID")
                    product_name = result_data[0].get("NAME", params.product_sku)
            
            # Если не нашли в каталоге, пробуем через CRM
            if not product_id:
                crm_product_result = await self.client._make_request("crm.product.list", {
                    "filter": {"XML_ID": params.product_sku},
                    "select": ["ID", "NAME"]
                })
                
                if isinstance(crm_product_result, dict) and "error" not in crm_product_result:
                    crm_products = crm_product_result.get("result", [])
                    if isinstance(crm_products, list) and crm_products:
                        product_id = crm_products[0].get("ID")
                        product_name = crm_products[0].get("NAME", params.product_sku)
            
            if not product_id:
                return {"success": False, "error": f"Товар с SKU {params.product_sku} не найден"}
            
            # 2. Проверяем существование склада
            warehouses = await self.get_warehouses(GetWarehousesParams())
            warehouse_exists = False
            warehouse_title = f"Склад {params.warehouse_id}"
            
            if warehouses.get("success"):
                for wh in warehouses.get("warehouses", []):
                    if wh.get("ID") == params.warehouse_id:
                        warehouse_exists = True
                        warehouse_title = wh.get("TITLE", f"Склад {params.warehouse_id}")
                        break
            
            if not warehouse_exists:
                return {"success": False, "error": f"Склад с ID {params.warehouse_id} не найден"}
            
            # 3. Устанавливаем остатки через catalog.storeproduct.set
            stock_result = await self.client._make_request("catalog.storeproduct.set", {
                "productId": product_id,
                "storeId": params.warehouse_id,
                "amount": params.quantity
            })
            
            logger.debug(f"Результат установки остатков: {stock_result}")
            
            if isinstance(stock_result, dict) and "error" in stock_result:
                error_msg = stock_result.get("error_description", stock_result.get("error", "Unknown error"))
                return {"success": False, "error": f"Не удалось установить остатки: {error_msg}"}
            
            logger.info(f"Установлены остатки: товар {params.product_sku} ({product_name}), склад {params.warehouse_id} ({warehouse_title}), количество {params.quantity}")
            
            return {
                "success": True,
                "message": f"Остатки товара '{product_name}' на складе '{warehouse_title}' установлены: {params.quantity}",
                "product_id": product_id,
                "warehouse_id": params.warehouse_id,
                "quantity": params.quantity,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при установке остатков: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def create_warehouse(self, params: CreateWarehouseParams) -> Dict[str, Any]:
        """Создание нового склада в Битрикс24."""
        if not self.client.enabled:
            return {"status": "disabled", "message": "Интеграция с Битрикс24 отключена"}
        
        if not await self.check_catalog_access():
            return {"success": False, "error": "Нет доступа к модулю 'Торговый каталог'"}
        
        try:
            # Поля согласно документации - ВСЕ в нижнем регистре!
            fields = {
                "address": params.address or "Не указан",  # ОБЯЗАТЕЛЬНОЕ поле
                "title": params.title,
                "active": "Y",
                "description": params.description or "",
                "sort": 100,
                "code": f"store_{int(datetime.now().timestamp())}",
                "issuingCenter": "N",
                "shippingCenter": "Y",  # Центр отгрузки
                "xmlId": "",  # Внешний код
                "phone": "",  # Телефон
                "email": "",  # Email
                "schedule": "",  # График работы
                "gpsN": 0.0,  # Широта
                "gpsS": 0.0,  # Долгота
            }
            
            # Добавляем даты создания и изменения
            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            fields["dateCreate"] = current_time
            fields["dateModify"] = current_time
            
            # Получаем ID текущего пользователя (администратора)
            user_result = await self.client.get_current_user()
            if user_result:
                user_id = user_result.get("ID", 1)
                fields["userId"] = user_id
                fields["modifiedBy"] = user_id
            
            result = await self.client._make_request("catalog.store.add", {"fields": fields})
            
            logger.debug(f"Результат создания склада: {json.dumps(result, ensure_ascii=False)}")
            
            if isinstance(result, dict) and "error" in result:
                error_msg = result.get("error_description", result.get("error", "Unknown error"))
                return {"success": False, "error": f"Не удалось создать склад: {error_msg}"}
            
            # Извлекаем ID склада из ответа
            warehouse_id = None
            
            # Формат ответа согласно документации: {"result": {"store": {...}}}
            if isinstance(result, dict) and "result" in result:
                result_data = result["result"]
                if isinstance(result_data, dict) and "store" in result_data:
                    # Получаем ID из объекта store
                    store_data = result_data["store"]
                    warehouse_id = store_data.get("id")
                    logger.info(f"Склад создан, данные store: {store_data}")
                elif isinstance(result_data, dict):
                    # Возможно, result_data уже содержит store
                    warehouse_id = result_data.get("id")
                else:
                    # Возможно, result_data - это просто ID
                    warehouse_id = result_data
            
            if not warehouse_id:
                # Последняя попытка: возможно, весь ответ - это ID
                if isinstance(result, (int, float)):
                    warehouse_id = int(result)
                elif isinstance(result, str) and result.isdigit():
                    warehouse_id = int(result)
                else:
                    logger.error(f"Не удалось извлечь ID склада из ответа: {result}")
                    return {
                        "success": False, 
                        "error": "Склад создан, но не получен ID склада", 
                        "raw_response": result
                    }
            
            logger.info(f"Создан склад: ID={warehouse_id}, название='{params.title}'")
            
            return {
                "success": True,
                "message": f"Склад '{params.title}' успешно создан",
                "warehouse_id": warehouse_id,
                "title": params.title,
                "details": fields
            }
            
        except Exception as e:
            logger.error(f"Ошибка при создании склада: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def sync_all_stock_to_bitrix(self) -> Dict[str, Any]:
        """Полная синхронизация остатков из MCP в Битрикс24."""
        if not self.client.enabled:
            return {"status": "disabled", "message": "Интеграция с Битрикс24 отключена"}
        
        # Проверяем доступ к каталогу
        catalog_access = await self.check_catalog_access()
        if not catalog_access:
            return {
                "success": False, 
                "error": "Нет доступа к модулю 'Торговый каталог' для синхронизации остатков",
                "solution": "Добавьте права 'catalog' для вебхука в настройках Битрикс24"
            }
        
        try:
            from mcp_server.database import list_all_products
            
            products = list_all_products(limit=1000)
            
            # Получаем или создаем склад по умолчанию
            warehouses = await self.get_warehouses(GetWarehousesParams(limit=1))
            
            warehouse_id = None
            warehouse_title = "Основной склад"
            
            if warehouses.get("success") and warehouses.get("warehouses"):
                warehouse_id = warehouses["warehouses"][0].get("ID")
                warehouse_title = warehouses["warehouses"][0].get("TITLE", "Основной склад")
            else:
                # Создаем склад по умолчанию
                create_result = await self.create_warehouse(CreateWarehouseParams(
                    title="Основной склад MCP",
                    address="Автоматически создан для синхронизации",
                    description="Создан системой управления складом MCP"
                ))
                
                if create_result.get("success"):
                    warehouse_id = create_result.get("warehouse_id")
                    warehouse_title = create_result.get("title")
                else:
                    return {"success": False, "error": "Не удалось создать склад для синхронизации"}
            
            if not warehouse_id:
                return {"success": False, "error": "Не удалось определить ID склада для синхронизации"}
            
            synced_count = 0
            errors = []
            
            for product in products:
                try:
                    # 1. Создаем/обновляем товар в Битрикс24
                    from .models import BitrixProduct
                    
                    bitrix_product = BitrixProduct(
                        name=product["product_name"],
                        xml_id=product["product_sku"],
                        description=product.get("description", f"Товар из системы MCP. SKU: {product['product_sku']}"),
                        price=0.0,
                        measure=796  # шт
                    )
                    
                    # Используем метод из client.py для создания/получения товара
                    product_id = await self.client.get_or_create_product(bitrix_product)
                    
                    if not product_id:
                        errors.append(f"Товар {product['product_sku']}: не удалось создать/найти в Битрикс24")
                        continue
                    
                    # 2. Устанавливаем остатки
                    stock_result = await self.set_product_stock(SetProductStockParams(
                        product_sku=product["product_sku"],
                        warehouse_id=warehouse_id,
                        quantity=float(product["current_quantity"])
                    ))
                    
                    if stock_result.get("success"):
                        synced_count += 1
                        logger.debug(f"Синхронизирован товар {product['product_sku']}: {product['current_quantity']} шт.")
                    else:
                        errors.append(f"Товар {product['product_sku']}: {stock_result.get('error')}")
                        
                except Exception as e:
                    errors.append(f"Товар {product['product_sku']}: {str(e)}")
                    continue
            
            result = {
                "success": True,
                "message": f"Синхронизировано {synced_count} из {len(products)} товаров",
                "synced_count": synced_count,
                "total_count": len(products),
                "warehouse_id": warehouse_id,
                "warehouse_title": warehouse_title
            }
            
            if errors:
                result["error_count"] = len(errors)
                result["errors_sample"] = errors[:5]
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка полной синхронизации: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def get_stock_movements(self, params: GetStockMovementsParams) -> Dict[str, Any]:
        """Получение движений товаров через сделки CRM."""
        if not self.client.enabled:
            return {"status": "disabled", "message": "Интеграция с Битрикс24 отключена"}
        
        try:
            filter_dict = {}
            
            if params.product_sku:
                filter_dict["UF_CRM_PRODUCT_SKU"] = params.product_sku
            
            # Получаем сделки, связанные с товарами
            deals_result = await self.client._make_request("crm.deal.list", {
                "select": ["ID", "TITLE", "STAGE_ID", "DATE_CREATE", "ASSIGNED_BY_ID", 
                          "UF_CRM_PRODUCT_SKU", "UF_CRM_REQUEST_ID", "OPPORTUNITY"],
                "filter": filter_dict,
                "order": {"DATE_CREATE": "DESC"},
                "start": 0
            })
            
            if isinstance(deals_result, dict) and "error" in deals_result:
                return {"success": False, "error": deals_result.get("error_description", "Unknown error")}
            
            deals = []
            if isinstance(deals_result, dict):
                result_data = deals_result.get("result", [])
                if isinstance(result_data, list):
                    deals = result_data
            
            movements = []
            
            # Маппинг стадий сделок к типам движений
            stage_to_movement = {
                "NEW": "Заявка на закупку",
                "PREPARATION": "В обработке",
                "WON": "Закупка завершена",
                "LOST": "Отменено"
            }
            
            for deal in deals[:params.limit]:
                if not isinstance(deal, dict):
                    continue
                    
                stage_id = deal.get("STAGE_ID", "")
                movement_type = stage_to_movement.get(stage_id, "Другое")
                
                movements.append({
                    "id": deal.get("ID", 0),
                    "date": deal.get("DATE_CREATE"),
                    "type": movement_type,
                    "title": deal.get("TITLE", ""),
                    "product_sku": deal.get("UF_CRM_PRODUCT_SKU"),
                    "request_id": deal.get("UF_CRM_REQUEST_ID"),
                    "amount": deal.get("OPPORTUNITY", 0),
                    "entity_type": "Сделка CRM",
                    "entity_id": deal.get("ID", 0)
                })
            
            return {
                "success": True,
                "movements": movements,
                "count": len(movements),
                "note": "Движения показываются по сделкам CRM"
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении движений: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}


# Глобальный экземпляр менеджера склада
warehouse_manager = BitrixWarehouseManager()