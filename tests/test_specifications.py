"""Pruebas del Specification Pattern y de la política de descuentos (app/pricing.py)."""
from decimal import Decimal

import pytest

from app.pricing import calculate_discount
from app.specifications import (
    ANY_DISCOUNT_RULE, FIVE_PERCENT_RULE, TEN_PERCENT_RULE, ActivePromotionSpec, AndSpec,
    MinimumAmountSpec, MinimumUnitsSpec, NotSpec, OrSpec, Specification, VIPCustomerSpec,
)
from helpers import make_order, snapshot


class Constante(Specification):
    """Specification de apoyo: siempre devuelve el valor indicado."""

    def __init__(self, valor: bool):
        self.valor = valor

    def is_satisfied_by(self, order) -> bool:
        return self.valor


SI, NO = Constante(True), Constante(False)


# ------------------------------------------------------------ operadores & | ~
@pytest.mark.parametrize("a, b, esperado", [(SI, SI, True), (SI, NO, False), (NO, SI, False), (NO, NO, False)])
def test_and_tabla_de_verdad(a, b, esperado):
    assert (a & b).is_satisfied_by(make_order()) is esperado


@pytest.mark.parametrize("a, b, esperado", [(SI, SI, True), (SI, NO, True), (NO, SI, True), (NO, NO, False)])
def test_or_tabla_de_verdad(a, b, esperado):
    assert (a | b).is_satisfied_by(make_order()) is esperado


@pytest.mark.parametrize("a, esperado", [(SI, False), (NO, True)])
def test_not_tabla_de_verdad(a, esperado):
    assert (~a).is_satisfied_by(make_order()) is esperado


def test_operadores_devuelven_las_clases_esperadas():
    assert isinstance(SI & NO, AndSpec)
    assert isinstance(SI | NO, OrSpec)
    assert isinstance(~SI, NotSpec)


def test_composicion_anidada():
    # NOT (A AND B) OR C
    spec = ~(SI & NO) | NO
    assert spec.is_satisfied_by(make_order()) is True


# ------------------------------------------------------------ Specifications individuales
@pytest.mark.parametrize("precio, esperado", [("499.99", False), ("500.00", False), ("500.01", True)])
def test_monto_minimo_es_estrictamente_mayor(precio, esperado):
    order = make_order(lines=[("SKU", 1, precio)])
    assert MinimumAmountSpec(Decimal("500")).is_satisfied_by(order) is esperado


@pytest.mark.parametrize("vip", [True, False])
def test_vip_spec(vip):
    assert VIPCustomerSpec().is_satisfied_by(make_order(vip=vip)) is vip


@pytest.mark.parametrize("unidades, esperado", [(3, False), (4, True), (5, True)])
def test_unidades_minimas_suma_cantidades(unidades, esperado):
    order = make_order(lines=[("SKU", unidades, "10")])
    assert MinimumUnitsSpec(4).is_satisfied_by(order) is esperado


def test_unidades_minimas_con_varios_renglones():
    order = make_order(lines=[("A", 2, "10"), ("B", 2, "10")])  # 2 renglones, 4 unidades
    assert MinimumUnitsSpec(4).is_satisfied_by(order) is True


@pytest.mark.parametrize("promo", [True, False])
def test_promocion_activa_spec(promo):
    assert ActivePromotionSpec().is_satisfied_by(make_order(promo=promo)) is promo


# ------------------------------------------------------------ las Specifications no modifican el pedido
def test_evaluar_specifications_no_modifica_el_pedido():
    order = make_order(vip=True, lines=[("A", 2, "300"), ("B", 2, "450")])
    antes = snapshot(order)
    for spec in (TEN_PERCENT_RULE, FIVE_PERCENT_RULE, ANY_DISCOUNT_RULE):
        spec.is_satisfied_by(order)
    calculate_discount(order)
    assert snapshot(order) == antes


# ------------------------------------------------------------ reglas de descuento
def test_regla_10_por_ciento_cumple_todo():
    order = make_order(vip=True, lines=[("A", 4, "200")])
    assert TEN_PERCENT_RULE.is_satisfied_by(order) is True


@pytest.mark.parametrize(
    "kwargs, lines",
    [
        (dict(vip=False), [("A", 4, "200")]),             # no VIP
        (dict(vip=True), [("A", 4, "125")]),              # total exactamente 500
        (dict(vip=True), [("A", 3, "300")]),              # solo 3 unidades
        (dict(vip=True, promo=True), [("A", 4, "200")]),  # promoción activa
    ],
)
def test_regla_10_por_ciento_falla_si_falta_una_condicion(kwargs, lines):
    assert TEN_PERCENT_RULE.is_satisfied_by(make_order(lines=lines, **kwargs)) is False


@pytest.mark.parametrize("precio, esperado", [("5000.00", False), ("5000.01", True)])
def test_regla_5_por_ciento_frontera(precio, esperado):
    assert FIVE_PERCENT_RULE.is_satisfied_by(make_order(lines=[("A", 1, precio)])) is esperado


def test_regla_5_por_ciento_bloqueada_por_promocion():
    assert FIVE_PERCENT_RULE.is_satisfied_by(make_order(promo=True, lines=[("A", 1, "6000")])) is False


# ------------------------------------------------------------ monto del descuento
def _tasa(order) -> str:
    return str(calculate_discount(order).rate)


def test_descuento_10_calcula_monto_y_total():
    d = calculate_discount(make_order(vip=True, lines=[("A", 2, "600"), ("B", 2, "450")]))
    assert (d.rate, d.discount.amount, d.total.amount) == (Decimal("0.10"), Decimal("210.00"), Decimal("1890.00"))


def test_descuento_5_calcula_monto_y_total():
    d = calculate_discount(make_order(lines=[("A", 1, "18000.00")]))
    assert (d.rate, d.discount.amount, d.total.amount) == (Decimal("0.05"), Decimal("900.00"), Decimal("17100.00"))


def test_prioridad_del_10_cuando_se_cumplen_ambas_reglas():
    order = make_order(vip=True, lines=[("A", 4, "2000")])  # total 8000: cumple 10 % y 5 %
    assert TEN_PERCENT_RULE.is_satisfied_by(order) and FIVE_PERCENT_RULE.is_satisfied_by(order)
    assert _tasa(order) == "0.10"


def test_sin_descuento_devuelve_total_igual_y_descuento_cero():
    d = calculate_discount(make_order(lines=[("A", 2, "250.00")]))  # 500 exactos, no VIP
    assert d.rate == Decimal("0") and d.discount.amount == Decimal("0.00")
    assert d.total.amount == d.subtotal.amount == Decimal("500.00")


def test_promocion_activa_excluye_ambos_descuentos():
    assert _tasa(make_order(vip=True, promo=True, lines=[("A", 4, "2000")])) == "0"


def test_redondeo_half_up_a_centavos():
    # Total 500.05 (> 500, VIP, 5 unidades): 10 % = 50.005 -> 50.01 con ROUND_HALF_UP
    order = make_order(vip=True, lines=[("A", 5, "100.01")])
    assert calculate_discount(order).discount.amount == Decimal("50.01")


def test_pedido_vacio_no_tiene_descuento():
    assert _tasa(make_order(vip=True)) == "0"
