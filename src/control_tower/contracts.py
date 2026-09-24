from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Supplier(Record):
    supplier_id: str
    supplier_name: str
    region: str
    target_lead_days: int = Field(ge=1)


class Product(Record):
    sku: str
    supplier_id: str
    category: str
    unit_cost_cents: int = Field(gt=0)


class Warehouse(Record):
    warehouse_id: str
    region: str


class OrderLine(Record):
    line_id: str
    order_id: str
    sku: str
    warehouse_id: str
    order_date: date
    promised_date: date
    ordered_qty: int = Field(gt=0)
    status: Literal["open", "cancelled"]


class Shipment(Record):
    shipment_id: str
    line_id: str
    shipped_date: date
    delivered_date: date | None
    shipped_qty: int = Field(gt=0)
    transport_cost_cents: int = Field(ge=0)
    carrier: str


class Inventory(Record):
    sku: str
    warehouse_id: str
    snapshot_date: date
    opening_qty: int = Field(ge=0)
    received_qty: int = Field(ge=0)
    shipped_qty: int = Field(ge=0)
    on_hand_qty: int = Field(ge=0)
    reserved_qty: int = Field(ge=0)
    safety_stock: int = Field(ge=0)


class PurchaseOrder(Record):
    po_id: str
    sku: str
    warehouse_id: str
    supplier_id: str
    placed_date: date
    expected_date: date
    received_date: date | None
    ordered_qty: int = Field(gt=0)
    received_qty: int = Field(ge=0)


CONTRACTS = {
    "suppliers": Supplier,
    "products": Product,
    "warehouses": Warehouse,
    "order_lines": OrderLine,
    "shipments": Shipment,
    "inventory": Inventory,
    "purchase_orders": PurchaseOrder,
}
KEYS = {
    "suppliers": ["supplier_id"],
    "products": ["sku"],
    "warehouses": ["warehouse_id"],
    "order_lines": ["line_id"],
    "shipments": ["shipment_id"],
    "inventory": ["sku", "warehouse_id", "snapshot_date"],
    "purchase_orders": ["po_id"],
}
