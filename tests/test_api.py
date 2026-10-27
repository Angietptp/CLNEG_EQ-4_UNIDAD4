import pytest
from fastapi.testclient import TestClient

from app import api


@pytest.fixture(autouse=True)
def fresh_orders():
    api.reset_orders()
    yield
    api.reset_orders()


@pytest.fixture
def client():
    return TestClient(api.app)


# -------------------------------------------------------------- GET
def test_get_order_o001(client):
    r = client.get("/orders/O001")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "O001" and body["status"] == "DRAFT"
    assert body["units"] == 4 and body["total"] == "2100.00" and body["events"] == []


def test_get_order_inexistente_404(client):
    assert client.get("/orders/NOPE").status_code == 404


def test_list_orders_16(client):
    assert len(client.get("/orders").json()) == 16


def test_discount_endpoint(client):
    assert client.get("/orders/O001/discount").json()["rate"] == "0.10"
    assert client.get("/orders/O006/discount").json()["rate"] == "0.05"
    assert client.get("/orders/O010/discount").json()["rate"] == "0"


# -------------------------------------------------------------- confirm
def test_confirm_ok(client):
    r = client.post("/orders/O013/confirm")
    assert r.status_code == 200 and r.json() == {"id": "O013", "status": "CONFIRMED"}
    assert client.get("/orders/O013").json()["events"] == ["OrderConfirmed"]


def test_confirm_inexistente_404(client):
    assert client.post("/orders/NOPE/confirm").status_code == 404


def test_confirm_doble_409_sin_evento_extra(client):
    assert client.post("/orders/O013/confirm").status_code == 200
    r = client.post("/orders/O013/confirm")
    assert r.status_code == 409 and "detail" in r.json()
    assert client.get("/orders/O013").json()["events"] == ["OrderConfirmed"]


def test_confirm_pedido_vacio_422(client):
    r = client.post("/orders/O007/confirm")
    assert r.status_code == 422
    assert client.get("/orders/O007").json()["status"] == "DRAFT"


def test_confirm_cliente_inactivo_422(client):
    assert client.post("/orders/O003/confirm").status_code == 422


def test_get_no_cambia_estado_y_confirm_es_post(client):
    assert client.get("/orders/O013/confirm").status_code == 405


# -------------------------------------------------------------- ship
def test_ship_ok(client):
    client.post("/orders/O014/confirm")
    r = client.post("/orders/O014/ship", json={"tracking_number": "G-1"})
    assert r.status_code == 200 and r.json()["status"] == "SHIPPED"
    assert r.json()["tracking_number"] == "G-1"


def test_ship_sin_guia_422(client):
    client.post("/orders/O012/confirm")
    r = client.post("/orders/O012/ship", json={"tracking_number": ""})
    assert r.status_code == 422
    assert client.get("/orders/O012").json()["status"] == "CONFIRMED"


def test_ship_sin_cuerpo_422(client):
    client.post("/orders/O012/confirm")
    assert client.post("/orders/O012/ship").status_code == 422


def test_ship_desde_draft_409(client):
    assert client.post("/orders/O012/ship", json={"tracking_number": "G"}).status_code == 409


def test_ship_inexistente_404(client):
    assert client.post("/orders/NOPE/ship", json={"tracking_number": "G"}).status_code == 404


# -------------------------------------------------------------- cancel
def test_cancel_ok(client):
    client.post("/orders/O014/confirm")
    r = client.post("/orders/O014/cancel", json={"reason": "Cliente lo pidió"})
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"


def test_cancel_desde_shipped_409(client):
    client.post("/orders/O014/confirm")
    client.post("/orders/O014/ship", json={"tracking_number": "G"})
    r = client.post("/orders/O014/cancel", json={"reason": "x"})
    assert r.status_code == 409
    assert client.get("/orders/O014").json()["status"] == "SHIPPED"


def test_cancel_motivo_vacio_422(client):
    client.post("/orders/O014/confirm")
    assert client.post("/orders/O014/cancel", json={"reason": " "}).status_code == 422
    assert client.get("/orders/O014").json()["status"] == "CONFIRMED"


def test_cancel_inexistente_404(client):
    assert client.post("/orders/NOPE/cancel", json={"reason": "x"}).status_code == 404


# -------------------------------------------------------------- deliver / return
def test_deliver_y_return(client):
    for oid, op, final in (("O016", "deliver", "DELIVERED"), ("O015", "return", "RETURNED")):
        client.post(f"/orders/{oid}/confirm")
        client.post(f"/orders/{oid}/ship", json={"tracking_number": "G"})
        r = client.post(f"/orders/{oid}/{op}")
        assert r.status_code == 200 and r.json()["status"] == final


def test_deliver_desde_draft_409(client):
    assert client.post("/orders/O016/deliver").status_code == 409


# -------------------------------------------------------------- docs
def test_docs_y_openapi(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    for path in ("/orders/{order_id}", "/orders/{order_id}/confirm",
                 "/orders/{order_id}/ship", "/orders/{order_id}/cancel"):
        assert path in spec["paths"]
    assert "post" in spec["paths"]["/orders/{order_id}/confirm"]
