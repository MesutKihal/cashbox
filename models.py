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
    address: str
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

class Bill(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    file_name:  str
    type: str
    date: datetime = Field(default_factory=datetime.now)
    __table_args__ = {"extend_existing": True}

class Settings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    store_name: str = Field(default="متجر CashboxPro")
    store_phone: str = Field(default="05 55 55 55 55")
    store_address: str = Field(default="شارع البلدية، وسط المدينة")
    rc: str = Field(default="00 000 0000 0000000")
    nif: str = Field(default="000000000000000")
    nis: str = Field(default="000000000000000")
    art_imp: str = Field(default="00")
    receipt_header: str = Field(default="شكراً لتسوقكم معنا")
    receipt_footer: str = Field(default="هذه الفاتورة صادرة آلياً")
    currency_symbol: str = Field(default="د.ج")
    low_stock_threshold: int = Field(default=10)
    default_customer: str = Field(default="زبون عادي")
    dark_mode: bool = Field(default=False)
    __table_args__ = {"extend_existing": True}