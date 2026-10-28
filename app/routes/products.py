"""Product catalogue endpoints."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.database import get_connection

router = APIRouter(prefix="/products", tags=["products"])


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    price: float = Field(gt=0, le=100_000)
    stock: int = Field(default=0, ge=0, le=100_000)


class Product(ProductIn):
    id: int


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=list[Product])
def list_products():
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name, description, price, stock FROM products ORDER BY id").fetchall()
    return [dict(row) for row in rows]


@router.get("/search", response_model=list[Product])
def search_products(q: str = Query(min_length=1, max_length=100)):
    pattern = f"%{_escape_like(q)}%"
    query = (
        "SELECT id, name, description, price, stock FROM products "
        "WHERE name LIKE ? OR description LIKE ? "
        "ORDER BY id"
    )
    with get_connection() as conn:
        rows = conn.execute(query, (pattern, pattern)).fetchall()
    return [dict(row) for row in rows]


@router.get("/{product_id}", response_model=Product)
def get_product(product_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, description, price, stock FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return dict(row)


@router.post("", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductIn):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO products (name, description, price, stock) VALUES (?, ?, ?, ?)",
            (product.name, product.description, product.price, product.stock),
        )
        product_id = cursor.lastrowid
    return {"id": product_id, **product.model_dump()}
