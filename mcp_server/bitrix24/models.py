"""Модели данных для Битрикс24."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BitrixDeal(BaseModel):
    """Модель сделки Битрикс24."""
    id: Optional[int] = Field(None, description="ID сделки в Битрикс24")
    title: str = Field(..., description="Название сделки")
    stage_id: str = Field("NEW", description="ID стадии: NEW, PREPARATION, WON, LOST")
    type_id: str = Field("SALE", description="Тип сделки: SALE, COMPLEX")
    category_id: Optional[int] = Field(1, description="ID воронки")
    assigned_by_id: Optional[int] = Field(None, description="ID ответственного")
    opportunity: Optional[float] = Field(0.0, description="Сумма сделки")
    currency_id: str = Field("RUB", description="Валюта: RUB, USD, EUR")
    comments: Optional[str] = Field(None, description="Комментарии")
    created_at: Optional[str] = Field(None, description="Дата создания")
    
    # Пользовательские поля (UF_*)
    product_sku: Optional[str] = Field(None, description="SKU товара")
    request_id: Optional[str] = Field(None, description="ID заявки из MCP")
    warehouse_id: Optional[str] = Field(None, description="ID склада")


class BitrixTask(BaseModel):
    """Модель задачи Битрикс24."""
    id: Optional[int] = Field(None, description="ID задачи")
    title: str = Field(..., description="Название задачи")
    description: Optional[str] = Field(None, description="Описание")
    responsible_id: Optional[int] = Field(None, description="ID ответственного")
    creator_id: Optional[int] = Field(None, description="ID создателя")
    deadline: Optional[str] = Field(None, description="Дедлайн (YYYY-MM-DD HH:MM:SS)")
    priority: int = Field(2, description="Приоритет: 1-низкий, 2-средний, 3-высокий")
    group_id: Optional[int] = Field(0, description="ID группы")
    status: int = Field(2, description="Статус: 2-ожидает, 3-выполняется, 4-ждёт контроля, 5-завершена")
    
    # Связь с другими сущностями
    entity_id: Optional[int] = Field(None, description="ID связанной сущности (сделка)")
    entity_type: Optional[str] = Field(None, description="Тип сущности: deals, leads, contacts")


class BitrixProduct(BaseModel):
    """Модель товара Битрикс24."""
    id: Optional[int] = Field(None, description="ID товара")
    name: str = Field(..., description="Название товара")
    xml_id: str = Field(..., description="Внешний ID (SKU)")
    description: Optional[str] = Field(None, description="Описание")
    price: float = Field(0.0, description="Цена")
    currency_id: str = Field("RUB", description="Валюта")
    measure: Optional[int] = Field(796, description="Единица измерения: 796-шт, 166-кг, 163-л")
    active: str = Field("Y", description="Активность: Y/N")


class BitrixContact(BaseModel):
    """Модель контакта Битрикс24."""
    id: Optional[int] = Field(None, description="ID контакта")
    name: str = Field(..., description="Имя")
    last_name: Optional[str] = Field(None, description="Фамилия")
    second_name: Optional[str] = Field(None, description="Отчество")
    email: Optional[str] = Field(None, description="Email")
    phone: Optional[str] = Field(None, description="Телефон")
    company_id: Optional[int] = Field(None, description="ID компании")


class BitrixDealProductRow(BaseModel):
    """Товарная позиция в сделке."""
    product_id: int = Field(..., description="ID товара в Битрикс24")
    product_name: str = Field(..., description="Название товара")
    quantity: float = Field(1.0, description="Количество")
    price: float = Field(0.0, description="Цена")
    discount_rate: Optional[float] = Field(0.0, description="Скидка %")
    tax_rate: Optional[float] = Field(0.0, description="Налог %")
    measure_code: Optional[int] = Field(796, description="Код единицы измерения")
    measure_name: Optional[str] = Field("шт.", description="Название единицы")