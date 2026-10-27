from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from app.domain import (
    Customer, DomainEvent, DomainException, InvalidOrderData, InvalidOrderTransition,
    Money, Order, OrderItem, OrderItemLimitExceeded, OrderStatus,
)
from app.pricing import calculate_discount
from app.specifications import (
    ActivePromotionSpec, AndSpec, MinimumAmountSpec, MinimumUnitsSpec, NotSpec, OrSpec,
    VIPCustomerSpec, FIVE_PERCENT_RULE, TEN_PERCENT_RULE, ANY_DISCOUNT_RULE,
)
from cargar_csv import load_fixture


# ------------------------------------------------------------------ helpers
def mxn(x):
    return Money(Decimal(x))


def make_order(units=1, price="100.00", vip=False, active=True, promo=False, oid="T1"):
    o = Order(customer=Customer("C", vip, active), id=oid, has_promotion=promo)
    if units:
        o.add_item(OrderItem("SKU", units, mxn(price)))
    return o


def snapshot(o):
    return (o.status, o.units, list(o.items), list(o.events), o.tracking_number, o.cancel_reason)


def confirmed(**kw):
    o = make_order(**kw)
    o.confirm()
    return o


def shipped():
    o = confirmed()
    o.ship("G1")
    return o


# ------------------------------------------------------------------ Money
def test_money_negativo():
    with pytest.raises(InvalidOrderData):
        Money(Decimal("-1"))


@pytest.mark.parametrize("v", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_money_no_finito(v):
    with pytest.raises(InvalidOrderData):
        Money(v)


def test_money_rechaza_float():
    with pytest.raises(InvalidOrderData):
        Money(1.5)


def test_money_moneda_default_mxn_y_decimal():
    m = Money(Decimal("600.00"))
    assert m.currency == "MXN" and isinstance(m.amount, Decimal)


def test_money_inmutable():
    m = mxn("1")
    with pytest.raises(FrozenInstanceError):
        m.amount = Decimal("2")


def test_money_add_devuelve_objeto_nuevo():
    a, b = mxn("10.10"), mxn("0.20")
    c = a.add(b)
    assert c.amount == Decimal("10.30") and c is not a and c is not b
    assert a.amount == Decimal("10.10")


def test_money_add_monedas_diferentes():
    with pytest.raises(InvalidOrderData):
        mxn("1").add(Money(Decimal("1"), "USD"))


def test_money_sin_errores_de_float():
    assert mxn("0.10").add(mxn("0.20")).amount == Decimal("0.30")


# ------------------------------------------------------------------ OrderItem
@pytest.mark.parametrize("sku", ["", "   "])
def test_item_sku_vacio(sku):
    with pytest.raises(InvalidOrderData):
        OrderItem(sku, 1, mxn("1"))


@pytest.mark.parametrize("qty", [0, -1])
def test_item_cantidad_no_positiva(qty):
    with pytest.raises(InvalidOrderData):
        OrderItem("S", qty, mxn("1"))


def test_item_subtotal_automatico():
    assert OrderItem("SKU001", 2, mxn("600.00")).subtotal.amount == Decimal("1200.00")


# ------------------------------------------------------------------ Order: artículos
def test_total_y_unidades_suman_renglones():
    o = make_order(units=0)
    o.add_item(OrderItem("A", 2, mxn("600.00")))
    o.add_item(OrderItem("B", 2, mxn("450.00")))
    assert o.units == 4 and o.total.amount == Decimal("2100.00")


def test_pedido_o001_inicia_draft():
    o = load_fixture()["O001"]
    assert o.status.value == "DRAFT" and o.units == 4 and o.total.amount == Decimal("2100.00")


def test_fixture_carga_16_pedidos_todos_draft():
    orders = load_fixture()
    assert len(orders) == 16
    assert all(o.status is OrderStatus.DRAFT and o.events == [] for o in orders.values())


def test_limite_20_unidades_exactas_permitido():
    assert load_fixture()["O008"].units == 20


def test_limite_se_aplica_a_unidades_no_a_renglones():
    o = make_order(units=0)
    for i in range(20):  # 20 renglones de 1 unidad = 20 unidades: permitido
        o.add_item(OrderItem(f"S{i}", 1, mxn("1")))
    assert o.units == 20 and len(o.items) == 20
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(OrderItem("X", 1, mxn("1")))


def test_superar_limite_no_modifica_pedido():
    o = load_fixture()["O009"]  # 19 unidades
    before = snapshot(o)
    with pytest.raises(OrderItemLimitExceeded):
        o.add_item(OrderItem("SKU003", 2, mxn("120.00")))
    assert snapshot(o) == before and o.units == 19


def test_un_solo_renglon_de_21_rechazado():
    with pytest.raises(OrderItemLimitExceeded):
        make_order(units=21)


def test_add_item_solo_en_draft():
    o = confirmed()
    before = snapshot(o)
    with pytest.raises(InvalidOrderTransition):
        o.add_item(OrderItem("X", 1, mxn("1")))
    assert snapshot(o) == before


def test_add_item_rechaza_moneda_no_mxn():
    o = make_order(units=0)
    with pytest.raises(InvalidOrderData):
        o.add_item(OrderItem("X", 1, Money(Decimal("1"), "USD")))
    assert o.items == []


def test_excepciones_heredan_de_domain_exception():
    for exc in (InvalidOrderData, InvalidOrderTransition, OrderItemLimitExceeded):
        assert issubclass(exc, DomainException)


# ------------------------------------------------------------------ confirm
def test_cliente_inactivo_no_confirma():
    o = load_fixture()["O003"]
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status is OrderStatus.DRAFT and o.events == []


def test_pedido_vacio_no_confirma():
    o = load_fixture()["O007"]
    with pytest.raises(InvalidOrderData):
        o.confirm()
    assert o.status is OrderStatus.DRAFT and o.events == []


def test_confirmar_registra_evento():
    o = make_order()
    o.confirm()
    assert o.status is OrderStatus.CONFIRMED
    assert [e.name for e in o.events] == ["OrderConfirmed"]
    assert o.events[0].order_id == o.id and isinstance(o.events[0], DomainEvent)
    assert o.events[0].occurred_at.tzinfo is not None


def test_confirmacion_doble_o013_no_duplica_evento():
    o = load_fixture()["O013"]
    o.confirm()
    assert o.status is OrderStatus.CONFIRMED and len(o.events) == 1
    with pytest.raises(InvalidOrderTransition):
        o.confirm()
    assert o.status is OrderStatus.CONFIRMED and len(o.events) == 1


# ------------------------------------------------------------------ transiciones válidas
def test_transicion_confirmed_a_shipped():
    o = confirmed()
    o.ship("G1")
    assert o.status is OrderStatus.SHIPPED and o.tracking_number == "G1"
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped"]
    assert o.events[-1].order_id == o.id


def test_transicion_confirmed_a_cancelled():
    o = confirmed()
    o.cancel("Cliente lo pidió")
    assert o.status is OrderStatus.CANCELLED and o.cancel_reason == "Cliente lo pidió"
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderCancelled"]


def test_transicion_shipped_a_delivered():
    o = shipped()
    o.deliver()
    assert o.status is OrderStatus.DELIVERED
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped", "OrderDelivered"]


def test_transicion_shipped_a_returned():
    o = shipped()
    o.return_order()
    assert o.status is OrderStatus.RETURNED
    assert [e.name for e in o.events] == ["OrderConfirmed", "OrderShipped", "OrderReturned"]


# ------------------------------------------------------------------ transiciones inválidas
OPS = {
    "confirm": lambda o: o.confirm(),
    "ship": lambda o: o.ship("G1"),
    "cancel": lambda o: o.cancel("motivo"),
    "deliver": lambda o: o.deliver(),
    "return_order": lambda o: o.return_order(),
}
BUILDERS = {
    OrderStatus.DRAFT: lambda: make_order(),
    OrderStatus.CONFIRMED: lambda: confirmed(),
    OrderStatus.SHIPPED: lambda: shipped(),
    OrderStatus.DELIVERED: lambda: _to_delivered(),
    OrderStatus.CANCELLED: lambda: _to_cancelled(),
    OrderStatus.RETURNED: lambda: _to_returned(),
}
VALID = {
    (OrderStatus.DRAFT, "confirm"), (OrderStatus.CONFIRMED, "ship"), (OrderStatus.CONFIRMED, "cancel"),
    (OrderStatus.SHIPPED, "deliver"), (OrderStatus.SHIPPED, "return_order"),
}


def _to_delivered():
    o = shipped(); o.deliver(); return o


def _to_cancelled():
    o = confirmed(); o.cancel("x"); return o


def _to_returned():
    o = shipped(); o.return_order(); return o


INVALID_CASES = [(s, op) for s in OrderStatus for op in OPS if (s, op) not in VALID]


def test_matriz_cubre_todas_las_combinaciones():
    assert len(INVALID_CASES) == 6 * 5 - 5


@pytest.mark.parametrize("status,op", INVALID_CASES)
def test_transicion_invalida_lanza_error_sin_cambios(status, op):
    o = BUILDERS[status]()
    before = snapshot(o)
    with pytest.raises(InvalidOrderTransition):
        OPS[op](o)
    assert snapshot(o) == before


# ------------------------------------------------------------------ validaciones de datos en transiciones
@pytest.mark.parametrize("guia", ["", "   "])
def test_ship_con_guia_vacia(guia):
    o = confirmed()
    before = snapshot(o)
    with pytest.raises(InvalidOrderData):
        o.ship(guia)
    assert snapshot(o) == before and o.status is OrderStatus.CONFIRMED


def test_ship_guia_none():
    o = confirmed()
    with pytest.raises(InvalidOrderData):
        o.ship(None)
    assert o.status is OrderStatus.CONFIRMED


@pytest.mark.parametrize("motivo", ["", "  "])
def test_cancel_con_motivo_vacio(motivo):
    o = confirmed()
    before = snapshot(o)
    with pytest.raises(InvalidOrderData):
        o.cancel(motivo)
    assert snapshot(o) == before and o.status is OrderStatus.CONFIRMED


def test_o012_confirma_pero_no_envia_sin_guia():
    o = load_fixture()["O012"]
    o.confirm()
    with pytest.raises(InvalidOrderData):
        o.ship("")
    assert o.status is OrderStatus.CONFIRMED and [e.name for e in o.events] == ["OrderConfirmed"]


def test_o014_no_cancela_desde_shipped():
    o = load_fixture()["O014"]
    o.confirm(); o.ship("G"); 
    with pytest.raises(InvalidOrderTransition):
        o.cancel("x")
    assert o.status is OrderStatus.SHIPPED and len(o.events) == 2


# ------------------------------------------------------------------ Specifications
def test_composicion_and_or_not():
    o = make_order(vip=True)
    t, f = VIPCustomerSpec(), ActivePromotionSpec()
    assert isinstance(t & f, AndSpec) and isinstance(t | f, OrSpec) and isinstance(~f, NotSpec)
    assert (t & f).is_satisfied_by(o) is False
    assert (t | f).is_satisfied_by(o) is True
    assert (~f).is_satisfied_by(o) is True
    assert (~t).is_satisfied_by(o) is False


def test_specifications_no_modifican_pedido():
    o = load_fixture()["O001"]
    before = snapshot(o)
    ANY_DISCOUNT_RULE.is_satisfied_by(o)
    calculate_discount(o)
    assert snapshot(o) == before


def test_minimum_amount_es_estricto():
    spec = MinimumAmountSpec(Decimal("500"))
    assert spec.is_satisfied_by(make_order(units=1, price="500.00")) is False
    assert spec.is_satisfied_by(make_order(units=1, price="500.01")) is True


def test_minimum_units_es_mayor_o_igual():
    spec = MinimumUnitsSpec(4)
    assert spec.is_satisfied_by(make_order(units=3)) is False
    assert spec.is_satisfied_by(make_order(units=4)) is True


def test_descuento_vip_10_por_ciento_o001():
    o = load_fixture()["O001"]
    assert TEN_PERCENT_RULE.is_satisfied_by(o)
    r = calculate_discount(o)
    assert r.rate == Decimal("0.10") and r.discount.amount == Decimal("210.00")
    assert r.total.amount == Decimal("1890.00")


def test_descuento_alternativo_5_por_ciento_o006():
    o = load_fixture()["O006"]
    assert FIVE_PERCENT_RULE.is_satisfied_by(o) and not TEN_PERCENT_RULE.is_satisfied_by(o)
    r = calculate_discount(o)
    assert r.rate == Decimal("0.05") and r.total.amount == Decimal("17100.00")


def test_promocion_activa_excluye_descuentos_o005():
    o = load_fixture()["O005"]
    assert not ANY_DISCOUNT_RULE.is_satisfied_by(o)
    assert calculate_discount(o).rate == 0


def test_promocion_excluye_tambien_el_5_por_ciento():
    o = make_order(units=1, price="6000.00", promo=True)
    assert calculate_discount(o).rate == 0


def test_frontera_500_exacto_o010_sin_descuento():
    o = load_fixture()["O010"]
    assert o.total.amount == Decimal("500.00")
    assert calculate_discount(o).rate == 0


def test_frontera_500_01_vip_4_unidades_10_por_ciento():
    o = make_order(units=4, price="125.0025", vip=True)  # 500.01
    assert o.total.amount == Decimal("500.0100")
    assert calculate_discount(o).rate == Decimal("0.10")


def test_frontera_5000_exacto_sin_descuento_y_5000_01_con_5():
    assert calculate_discount(make_order(units=1, price="5000.00")).rate == 0
    assert calculate_discount(make_order(units=1, price="5000.01")).rate == Decimal("0.05")


def test_vip_con_3_unidades_sin_descuento_o011():
    assert calculate_discount(load_fixture()["O011"]).rate == 0


def test_no_vip_bajo_5000_sin_descuento_o002():
    assert calculate_discount(load_fixture()["O002"]).rate == 0


def test_ambas_reglas_aplica_10_primero():
    o = make_order(units=5, price="2000.00", vip=True)  # 10000, VIP, 5 uds
    assert TEN_PERCENT_RULE.is_satisfied_by(o) and FIVE_PERCENT_RULE.is_satisfied_by(o)
    r = calculate_discount(o)
    assert r.rate == Decimal("0.10") and r.discount.amount == Decimal("1000.00")


def test_descuento_redondea_a_centavos():
    o = make_order(units=1, price="5000.05")  # 5% = 250.0025
    assert calculate_discount(o).discount.amount == Decimal("250.00")
