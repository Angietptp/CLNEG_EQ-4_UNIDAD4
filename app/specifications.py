"""Specification Pattern: reglas booleanas combinables con & (AND), | (OR) y ~ (NOT).

Las Specifications solo LEEN el pedido; nunca modifican estado, artículos ni eventos.
El cálculo monetario del descuento vive en app/pricing.py.
"""
from decimal import Decimal


class Specification:
    def is_satisfied_by(self, order) -> bool:
        raise NotImplementedError

    def __and__(self, other: "Specification") -> "Specification":
        return AndSpec(self, other)

    def __or__(self, other: "Specification") -> "Specification":
        return OrSpec(self, other)

    def __invert__(self) -> "Specification":
        return NotSpec(self)


class AndSpec(Specification):
    def __init__(self, left, right):
        self.left, self.right = left, right

    def is_satisfied_by(self, order) -> bool:
        return self.left.is_satisfied_by(order) and self.right.is_satisfied_by(order)


class OrSpec(Specification):
    def __init__(self, left, right):
        self.left, self.right = left, right

    def is_satisfied_by(self, order) -> bool:
        return self.left.is_satisfied_by(order) or self.right.is_satisfied_by(order)


class NotSpec(Specification):
    def __init__(self, spec):
        self.spec = spec

    def is_satisfied_by(self, order) -> bool:
        return not self.spec.is_satisfied_by(order)


class MinimumAmountSpec(Specification):
    """Total ESTRICTAMENTE mayor que el umbral (>), nunca >=."""

    def __init__(self, threshold: Decimal):
        self.threshold = Decimal(threshold)

    def is_satisfied_by(self, order) -> bool:
        return order.total.amount > self.threshold


class VIPCustomerSpec(Specification):
    def is_satisfied_by(self, order) -> bool:
        return order.customer.is_vip


class MinimumUnitsSpec(Specification):
    """Al menos N unidades (>=)."""

    def __init__(self, minimum: int):
        self.minimum = minimum

    def is_satisfied_by(self, order) -> bool:
        return order.units >= self.minimum


class ActivePromotionSpec(Specification):
    def is_satisfied_by(self, order) -> bool:
        return order.has_promotion


# Reglas de descuento (README.txt del paquete y guía, secciones 8 y 14)
TEN_PERCENT_RULE = (
    MinimumAmountSpec(Decimal("500"))
    & VIPCustomerSpec()
    & MinimumUnitsSpec(4)
    & ~ActivePromotionSpec()
)
FIVE_PERCENT_RULE = MinimumAmountSpec(Decimal("5000")) & ~ActivePromotionSpec()
ANY_DISCOUNT_RULE = TEN_PERCENT_RULE | FIVE_PERCENT_RULE
