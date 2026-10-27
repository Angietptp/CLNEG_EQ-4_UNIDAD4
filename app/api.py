"""API REST TechStore U4 (FastAPI). Los pedidos viven en memoria (se pierden al reiniciar).

Los controladores solo buscan el pedido, llaman al método de Order y devuelven JSON.
Las reglas de negocio viven en app/domain.py; el mapeo excepción -> HTTP está en
los exception handlers de abajo.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cargar_csv import load_fixture
from app.domain import (
    DomainException,
    InvalidOrderTransition,
    Order,
)
from app.pricing import calculate_discount

app = FastAPI(title="TechStore U4", version="1.0.0")

# Repositorio en memoria. Se muta en sitio para que reset_orders() sea visible a los handlers.
orders: dict[str, Order] = load_fixture()


def reset_orders() -> None:
    """Recarga los fixtures originales (útil para pruebas y demostraciones)."""
    orders.clear()
    orders.update(load_fixture())


class ShipRequest(BaseModel):
    tracking_number: str


class CancelRequest(BaseModel):
    reason: str


# ------------------------------------------------------------ manejo de errores
class OrderNotFound(Exception):
    def __init__(self, order_id: str):
        self.order_id = order_id


@app.exception_handler(OrderNotFound)
async def _not_found(_: Request, exc: OrderNotFound):
    return JSONResponse(status_code=404, content={"detail": f"No existe el pedido {exc.order_id}"})


@app.exception_handler(InvalidOrderTransition)
async def _conflict(_: Request, exc: InvalidOrderTransition):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DomainException)
async def _unprocessable(_: Request, exc: DomainException):
    # InvalidOrderData, OrderItemLimitExceeded y otras reglas de datos -> 422
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def _internal(_: Request, exc: Exception):
    # No se filtra el detalle del error interno al cliente.
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


# ------------------------------------------------------------ utilidades
def _get(order_id: str) -> Order:
    order = orders.get(order_id)
    if order is None:
        raise OrderNotFound(order_id)
    return order


def _view(order: Order) -> dict:
    return {
        "id": order.id,
        "customer_id": order.customer.id,
        "status": order.status.value,
        "units": order.units,
        "total": str(order.total.amount),
        "currency": order.total.currency,
        "has_promotion": order.has_promotion,
        "tracking_number": order.tracking_number,
        "cancel_reason": order.cancel_reason,
        "items": [
            {
                "sku": i.sku,
                "quantity": i.quantity,
                "unit_price": str(i.unit_price.amount),
                "subtotal": str(i.subtotal.amount),
            }
            for i in order.items
        ],
        "events": [e.name for e in order.events],
    }


def _short(order: Order) -> dict:
    return {"id": order.id, "status": order.status.value}


# ------------------------------------------------------------ endpoints
@app.get("/orders")
def list_orders():
    return [_short(o) for o in orders.values()]


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    return _view(_get(order_id))


@app.get("/orders/{order_id}/discount")
def get_discount(order_id: str):
    result = calculate_discount(_get(order_id))
    return {
        "id": order_id,
        "rate": str(result.rate),
        "subtotal": str(result.subtotal.amount),
        "discount": str(result.discount.amount),
        "total": str(result.total.amount),
        "currency": result.total.currency,
    }


@app.post("/orders/{order_id}/confirm")
def confirm_order(order_id: str):
    order = _get(order_id)
    order.confirm()
    return _short(order)


@app.post("/orders/{order_id}/ship")
def ship_order(order_id: str, body: ShipRequest):
    order = _get(order_id)
    order.ship(body.tracking_number)
    return {**_short(order), "tracking_number": order.tracking_number}


@app.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, body: CancelRequest):
    order = _get(order_id)
    order.cancel(body.reason)
    return {**_short(order), "cancel_reason": order.cancel_reason}


@app.post("/orders/{order_id}/deliver")
def deliver_order(order_id: str):
    order = _get(order_id)
    order.deliver()
    return _short(order)


@app.post("/orders/{order_id}/return")
def return_order(order_id: str):
    order = _get(order_id)
    order.return_order()
    return _short(order)
