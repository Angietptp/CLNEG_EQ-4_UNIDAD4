"""Ejecuta los 15 escenarios de datos/escenarios.csv y comprueba su resultado."""
import pytest

from cargar_csv import rows
from ejecutar_escenarios import ejecutar_escenario

ESCENARIOS = rows("escenarios.csv")

# Detalle adicional que se comprueba contra el estado real del pedido (no solo la etiqueta del CSV).
DETALLE_ESPERADO = {
    "E03": {"estado_final": "DRAFT", "eventos": []},
    "E06": {"estado_final": "DRAFT", "eventos": []},
    "E07": {"estado_final": "CONFIRMED", "unidades_final": 20, "eventos": ["OrderConfirmed"]},
    "E08": {"estado_final": "DRAFT", "unidades_final": 19, "eventos": []},
    "E11": {"estado_final": "CONFIRMED", "eventos": ["OrderConfirmed"]},
    "E12": {"estado_final": "CONFIRMED", "eventos": ["OrderConfirmed"]},
    "E13": {"estado_final": "SHIPPED", "eventos": ["OrderConfirmed", "OrderShipped"]},
    "E14": {"estado_final": "RETURNED", "eventos": ["OrderConfirmed", "OrderShipped", "OrderReturned"]},
    "E15": {"estado_final": "DELIVERED", "eventos": ["OrderConfirmed", "OrderShipped", "OrderDelivered"]},
}


def test_hay_15_escenarios_e01_a_e15():
    assert [e["caso_id"] for e in ESCENARIOS] == [f"E{n:02}" for n in range(1, 16)]


@pytest.mark.parametrize("fila", ESCENARIOS, ids=[e["caso_id"] for e in ESCENARIOS])
def test_escenario(fila):
    r = ejecutar_escenario(fila)
    assert r.estado_inicial == "DRAFT"
    assert r.resultado == fila["objetivo"], r.pasos
    assert r.invariantes_ok, "una operación rechazada modificó el pedido"
    assert r.cumple, r.pasos
    for campo, valor in DETALLE_ESPERADO.get(fila["caso_id"], {}).items():
        assert getattr(r, campo) == valor, campo
    if fila["accion"] == "evaluar_descuento":
        assert r.estado_final == "DRAFT" and r.eventos == []


def test_escenarios_no_se_contaminan_entre_si():
    primero = ejecutar_escenario(ESCENARIOS[11])  # E12 confirma O013
    segundo = ejecutar_escenario(ESCENARIOS[11])
    assert primero.estado_inicial == segundo.estado_inicial == "DRAFT"
    assert primero.eventos == segundo.eventos == ["OrderConfirmed"]
