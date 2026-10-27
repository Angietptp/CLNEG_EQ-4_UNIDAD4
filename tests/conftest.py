"""Fixtures compartidas por las pruebas (pytest las inyecta por nombre)."""
import pytest

from cargar_csv import load_fixture


@pytest.fixture
def orders():
    """Carga NUEVA de los 16 pedidos para cada prueba (aislamiento entre pruebas)."""
    return load_fixture()
