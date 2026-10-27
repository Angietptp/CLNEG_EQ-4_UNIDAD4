"""Política de descuentos: calcula el monto usando las Specifications.

Módulo auxiliar: separa "¿cumple la regla?" (Specification, solo booleano) de
"¿cuánto se descuenta?" (cálculo con Decimal).

Decisiones documentadas (la guía no las especifica):
  * El descuento se redondea a centavos con ROUND_HALF_UP.
  * No hay acumulación: se aplica un solo descuento; el 10 % tiene prioridad.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.domain import Money
from app.specifications import ANY_DISCOUNT_RULE, TEN_PERCENT_RULE

CENT = Decimal("0.01")


@dataclass(frozen=True)
class DiscountResult:
    rate: Decimal
    subtotal: Money
    discount: Money
    total: Money


def calculate_discount(order) -> DiscountResult:
    subtotal = order.total
    rate = Decimal("0")
    if ANY_DISCOUNT_RULE.is_satisfied_by(order):
        rate = Decimal("0.10") if TEN_PERCENT_RULE.is_satisfied_by(order) else Decimal("0.05")
    discount_amount = (subtotal.amount * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    return DiscountResult(
        rate=rate,
        subtotal=subtotal,
        discount=Money(discount_amount, subtotal.currency),
        total=Money(subtotal.amount - discount_amount, subtotal.currency),
    )
