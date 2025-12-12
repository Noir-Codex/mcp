"""Модели данных для MCP-сервера управления складом."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class InventoryStatus(BaseModel):
    """Модель статуса запасов товара."""
    product_sku: str = Field(..., description="Артикул товара")
    product_name: str = Field(..., description="Название товара")
    current_quantity: int = Field(..., description="Текущее количество на складе")
    min_quantity: int = Field(..., description="Минимальный уровень запасов")
    max_quantity: int = Field(..., description="Максимальный уровень запасов")
    status: str = Field(..., description="Статус: 'in_stock', 'low_stock', 'out_of_stock'")
    last_updated: str = Field(..., description="Дата и время последнего обновления в ISO формате")
    warehouse_id: Optional[str] = Field(None, description="ID склада")
    unit: Optional[str] = Field("шт", description="Единица измерения (кг, шт и т.д.)")


class InventoryUpdate(BaseModel):
    """Модель обновления запасов."""
    success: bool = Field(..., description="Успешность операции")
    product_sku: str = Field(..., description="Артикул товара")
    previous_quantity: int = Field(..., description="Предыдущее количество")
    new_quantity: int = Field(..., description="Новое количество")
    operation_type: str = Field(..., description="Тип операции: 'incoming' или 'outgoing'")
    timestamp: str = Field(..., description="Время операции в ISO формате")
    warehouse_id: Optional[str] = Field(None, description="ID склада")


class ReorderRequest(BaseModel):
    """Модель заявки на пополнение запасов."""
    success: bool = Field(..., description="Успешность создания заявки")
    request_id: str = Field(..., description="Уникальный ID заявки")
    product_sku: str = Field(..., description="Артикул товара")
    requested_quantity: int = Field(..., description="Запрашиваемое количество")
    status: str = Field(..., description="Статус заявки: 'pending', 'approved', 'rejected'")
    created_at: str = Field(..., description="Дата создания в ISO формате")
    priority: Optional[str] = Field(None, description="Приоритет: 'low', 'medium', 'high'")
    warehouse_id: Optional[str] = Field(None, description="ID склада")


class ProductSearchResult(BaseModel):
    """Результат поиска товаров по названию."""
    found: bool = Field(..., description="Найден ли товар")
    products: list = Field(..., description="Список найденных товаров с их SKU и информацией")
    count: int = Field(..., description="Количество найденных товаров")


class ReorderStatus(BaseModel):
    """Модель статуса заявки на пополнение."""
    request_id: str = Field(..., description="ID заявки")
    product_sku: str = Field(..., description="Артикул товара")
    product_name: Optional[str] = Field(None, description="Название товара")
    requested_quantity: int = Field(..., description="Запрашиваемое количество")
    status: str = Field(..., description="Статус заявки: 'pending', 'approved', 'rejected', 'completed'")
    priority: Optional[str] = Field(None, description="Приоритет: 'low', 'medium', 'high'")
    created_at: str = Field(..., description="Дата создания в ISO формате")
    updated_at: Optional[str] = Field(None, description="Дата последнего обновления в ISO формате")
    warehouse_id: Optional[str] = Field(None, description="ID склада")
    notes: Optional[str] = Field(None, description="Примечания")


class ReorderListResult(BaseModel):
    """Результат списка заявок."""
    requests: list = Field(..., description="Список заявок")
    count: int = Field(..., description="Количество заявок")


class ProductCreate(BaseModel):
    """Модель создания товара."""
    success: bool = Field(..., description="Успешность создания")
    product_sku: str = Field(..., description="Артикул товара")
    product_name: str = Field(..., description="Название товара")
    message: str = Field(..., description="Сообщение о результате")


class ProductDelete(BaseModel):
    """Модель удаления товара."""
    success: bool = Field(..., description="Успешность удаления")
    product_sku: str = Field(..., description="Артикул удаленного товара")
    message: str = Field(..., description="Сообщение о результате")