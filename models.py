from typing import Optional
from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime

SQLModel.metadata.clear()

class Category(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    __table_args__ = {"extend_existing": True}

class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str
    email: str
    __table_args__ = {"extend_existing": True}

class Cashbox(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    drawer: float
    __table_args__ = {"extend_existing": True}

class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    phone: str
    debt: float
    __table_args__ = {"extend_existing": True}

class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    barcode: str
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    quantity: int
    price: float
    item_per_box: Optional[int] = Field(default=None)
    box_price: Optional[float] = Field(default=None)
    cashbox_id: Optional[int] = Field(default=None, foreign_key="cashbox.id")

    __table_args__ = {"extend_existing": True}

class Sale(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: Optional[int] = Field(default=None, foreign_key="product.id")
    quantity: int
    date: datetime = Field(default_factory=datetime.now)
    total: float
    __table_args__ = {"extend_existing": True}

