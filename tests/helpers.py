"""Funciones auxiliares para construir pedidos de prueba."""
from decimal import Decimal

from app.domain import Customer, Money, Order, OrderItem


def make_order(*, vip=False, active=True, promo=False, lines=None, order_id="T001") -> Order:
    """Construye un pedido de prueba. lines = [(sku, cantidad, "precio"), ...]."""
    order = Order(customer=Customer("CX", vip, active), id=order_id, has_promotion=promo)
    for sku, quantity, price in lines or []:
        order.add_item(OrderItem(sku, quantity, Money(Decimal(price))))
    return order


def order_in_state(state: str) -> Order:
    """Lleva un pedido válido al estado indicado usando solo transiciones válidas."""
    order = make_order(lines=[("SKU001", 1, "600.00")])
    if state in {"CONFIRMED", "SHIPPED", "DELIVERED", "RETURNED", "CANCELLED"}:
        order.confirm()
    if state == "CANCELLED":
        order.cancel("Motivo de prueba")
    if state in {"SHIPPED", "DELIVERED", "RETURNED"}:
        order.ship("GUIA-1")
    if state == "DELIVERED":
        order.deliver()
    if state == "RETURNED":
        order.return_order()
    return order


def snapshot(order: Order):
    """Fotografía del pedido: sirve para comprobar que una operación fallida no cambió nada."""
    return (order.status, tuple(order.items), tuple(order.events), order.units, order.total,
            order.tracking_number, order.cancel_reason)
