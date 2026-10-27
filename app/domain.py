"""Núcleo de dominio TechStore U4: Value Objects, entidades, Aggregate Root y eventos."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

MAX_UNITS_PER_ORDER = 20
DEFAULT_CURRENCY = "MXN"


# ---------------------------------------------------------------- excepciones
class DomainException(Exception):
    """Base de todas las violaciones de reglas de negocio."""


class InvalidOrderData(DomainException):
    """Datos inválidos (monto, artículo, cliente inactivo, guía vacía...)."""


class InvalidOrderTransition(DomainException):
    """Operación no permitida desde el estado actual del pedido."""


class OrderItemLimitExceeded(DomainException):
    """Se superarían las 20 unidades acumuladas del pedido."""


# ---------------------------------------------------------------- Value Objects
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = DEFAULT_CURRENCY

    def __post_init__(self):
        amount = self.amount
        if isinstance(amount, (bool, float)):
            raise InvalidOrderData("Monto inválido: no se admite float")
        if isinstance(amount, int):
            object.__setattr__(self, "amount", Decimal(amount))
            amount = self.amount
        if not isinstance(amount, Decimal):
            raise InvalidOrderData("Monto inválido: debe ser Decimal")
        if not amount.is_finite() or amount < 0:
            raise InvalidOrderData("Monto inválido")
        if not isinstance(self.currency, str) or not self.currency.strip():
            raise InvalidOrderData("Moneda inválida")

    def add(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            raise InvalidOrderData("Solo se puede sumar Money")
        if self.currency != other.currency:
            raise InvalidOrderData("Monedas distintas")
        return Money(self.amount + other.amount, self.currency)


@dataclass(frozen=True)
class Customer:
    id: str
    is_vip: bool = False
    active: bool = True

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidOrderData("Cliente sin identificador")


@dataclass(frozen=True)
class OrderItem:
    sku: str
    quantity: int
    unit_price: Money

    def __post_init__(self):
        if not isinstance(self.sku, str) or not self.sku.strip():
            raise InvalidOrderData("Artículo inválido: SKU vacío")
        if (
            isinstance(self.quantity, bool)
            or not isinstance(self.quantity, int)
            or self.quantity <= 0
        ):
            raise InvalidOrderData("Artículo inválido: cantidad debe ser un entero positivo")
        if not isinstance(self.unit_price, Money):
            raise InvalidOrderData("Artículo inválido: el precio debe ser Money")

    @property
    def subtotal(self) -> Money:
        return Money(self.unit_price.amount * self.quantity, self.unit_price.currency)


# ---------------------------------------------------------------- eventos
@dataclass(frozen=True)
class DomainEvent:
    name: str
    order_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class OrderConfirmed(DomainEvent):
    name: str = field(default="OrderConfirmed", init=False)


@dataclass(frozen=True)
class OrderShipped(DomainEvent):
    name: str = field(default="OrderShipped", init=False)
    tracking_number: str = ""


@dataclass(frozen=True)
class OrderCancelled(DomainEvent):
    name: str = field(default="OrderCancelled", init=False)
    reason: str = ""


@dataclass(frozen=True)
class OrderDelivered(DomainEvent):
    name: str = field(default="OrderDelivered", init=False)


@dataclass(frozen=True)
class OrderReturned(DomainEvent):
    name: str = field(default="OrderReturned", init=False)


# ---------------------------------------------------------------- Aggregate Root
class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


@dataclass(eq=False)
class Order:
    customer: Customer
    id: str
    has_promotion: bool = False
    status: OrderStatus = OrderStatus.DRAFT
    items: list[OrderItem] = field(default_factory=list)
    events: list[DomainEvent] = field(default_factory=list)
    tracking_number: str | None = None
    cancel_reason: str | None = None

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidOrderData("Pedido sin identificador")
        if not isinstance(self.customer, Customer):
            raise InvalidOrderData("Pedido sin cliente válido")

    # -- consultas
    @property
    def units(self) -> int:
        return sum(item.quantity for item in self.items)

    @property
    def total(self) -> Money:
        amount = sum((x.subtotal.amount for x in self.items), Decimal("0.00"))
        return Money(amount)

    # -- artículos
    def add_item(self, item: OrderItem) -> None:
        if not isinstance(item, OrderItem):
            raise InvalidOrderData("Solo se admiten OrderItem")
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo DRAFT admite artículos")
        if item.unit_price.currency != DEFAULT_CURRENCY:
            raise InvalidOrderData("Solo MXN")
        if self.units + item.quantity > MAX_UNITS_PER_ORDER:
            raise OrderItemLimitExceeded("Máximo 20 unidades")
        self.items.append(item)

    # -- transiciones: validar -> cambiar estado -> registrar evento
    def confirm(self) -> None:
        if self.status != OrderStatus.DRAFT:
            raise InvalidOrderTransition("Solo se confirma un pedido en DRAFT")
        if not self.items:
            raise InvalidOrderData("No se puede confirmar un pedido vacío")
        if not self.customer.active:
            raise InvalidOrderData("No se puede confirmar: cliente inactivo")
        self.status = OrderStatus.CONFIRMED
        self.events.append(OrderConfirmed(order_id=self.id))

    def ship(self, tracking_number: str) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition("Solo se envía un pedido CONFIRMED")
        if not isinstance(tracking_number, str) or not tracking_number.strip():
            raise InvalidOrderData("La guía de envío no puede estar vacía")
        tracking = tracking_number.strip()
        self.status = OrderStatus.SHIPPED
        self.tracking_number = tracking
        self.events.append(OrderShipped(order_id=self.id, tracking_number=tracking))

    def cancel(self, reason: str) -> None:
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderTransition("Solo se cancela un pedido CONFIRMED")
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidOrderData("El motivo de cancelación no puede estar vacío")
        reason = reason.strip()
        self.status = OrderStatus.CANCELLED
        self.cancel_reason = reason
        self.events.append(OrderCancelled(order_id=self.id, reason=reason))

    def deliver(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition("Solo se entrega un pedido SHIPPED")
        self.status = OrderStatus.DELIVERED
        self.events.append(OrderDelivered(order_id=self.id))

    def return_order(self) -> None:
        if self.status != OrderStatus.SHIPPED:
            raise InvalidOrderTransition("Solo se devuelve un pedido SHIPPED")
        self.status = OrderStatus.RETURNED
        self.events.append(OrderReturned(order_id=self.id))
