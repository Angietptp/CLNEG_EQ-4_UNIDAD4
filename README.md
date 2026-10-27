# TechStore U4 — Núcleo de negocio (DDD, Specifications, máquina de estados y API)

**Actividad Práctica 4 · Componentes de Lógica de Negocio · Unidad 4 · FIME–UANL**

Lee clientes, productos y pedidos de CSV, los convierte en objetos de dominio, aplica reglas de descuento con Specifications,
controla el estado de los pedidos, emite Domain Events y expone operaciones por API REST (FastAPI). Todo en memoria; sin base de datos.

## Datos académicos

| Dato | Información |
|---|---|
| **Materia** | Componentes de lógica de negocios |
| **Actividad** | Actividad Práctica 4: Implementación del núcleo de negocio TechStore |
| **Profesor** | Miguel Ángel Gómez Marroquín |
| **Equipo / Grupo** | Equipo 4 (ITS) / 004 |

| Alumno(a) | Matrícula |
|---|---:|
| García Cerda Randal Guillermo | 2112493 |
| Sarmiento Hernández Cesar Martín | 2119427 |
| Torres Pasillas Angela Susana | 2101844 |

## Estado de validación

Lo que se comprobó y cómo:

- **Carga de datos:** `python cargar_csv.py` carga 16 pedidos, todos en `DRAFT`; O001 con 4 unidades y `2100.00` MXN (salida en `evidencias/salida_cargar_csv.txt`).
- **Escenarios del profesor:** `python ejecutar_escenarios.py` → E01–E15 cumplen su objetivo (`TODOS PASAN`, salida en `evidencias/salida_escenarios.txt`).
- **Pruebas con pytest real (ejecución del equipo, antes de agregar tres archivos de pruebas):** `103 passed` (81 en `test_domain.py` y 22 en `test_api.py`), con 1 advertencia de deprecación de `httpx`.
- **Pruebas agregadas después:** `test_specifications.py` (39), `test_datos.py` (22) y `test_escenarios.py` (17). Se verificaron con un ejecutor local equivalente a pytest (159 casos sin API, 0 fallos), no con pytest real. **Pendiente:** correr `python -m pytest -q` en tu equipo; el total esperado es 181 casos.
- **API (Swagger):** se probó manualmente `POST /orders/O013/confirm` (200) y un ID inexistente (404). El 409 y el 422 están cubiertos por pruebas automáticas; **falta tomar las capturas** de Swagger para ambos (ver «Evidencias»).

Los datos de `datos/` y `cargar_csv.py` son el material original del profesor y se conservan sin modificar (`tests/test_datos.py` compara la huella SHA-256 de cada CSV).

## Requisitos
Python 3.11 o superior. Dependencias: `fastapi`, `uvicorn`, `pytest`, `httpx` (`requirements.txt`).

## Estructura
```
TechStore_U4/
  datos/                       CSV originales del profesor (sin modificar)
  app/
    domain.py                  Money, Customer, OrderItem, Order, estados, eventos y excepciones
    specifications.py          Specification, AndSpec/OrSpec/NotSpec y reglas de descuento
    pricing.py                 Cálculo del monto del descuento (usa las Specifications)
    api.py                     API REST con FastAPI
  tests/
    conftest.py, helpers.py    Fixture `orders` y constructores de pedidos de prueba
    test_domain.py             Dominio, límites, transiciones y eventos
    test_specifications.py     Operadores &, |, ~, fronteras y descuentos
    test_datos.py              CSV originales y cargador
    test_escenarios.py         E01–E15
    test_api.py                Endpoints y códigos 404, 409 y 422
  ejecutar_escenarios.py       Ejecuta E01–E15 y genera la bitácora
  docs/
    bitacora/                  Bitácora E01–E15 (docx, pdf, csv, md, xlsx)
    diagramas/                 Diagrama de estados (png, pdf, drawio, mmd)
    domain events/             Domain Events y diagrama (docx, pdf)
    reporte/                   Reporte de la Actividad 4 (docx, pdf)
  evidencias/                  Capturas y salidas de texto
  cargar_csv.py                Cargador original del profesor
  README.md, README.txt        README propio y README original del paquete
  requirements.txt, pytest.ini, .gitignore, .gitattributes
```

## Instalación (Windows PowerShell)
```
python --version
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
CMD: `.venv\Scripts\activate.bat`. Linux/macOS: `source .venv/bin/activate`.

## Ejecución
```
python cargar_csv.py                      # 16 pedidos, todos DRAFT; O001 = 4 uds, 2100.00
python ejecutar_escenarios.py             # E01–E15 -> docs/bitacora/
python -m pytest -q                       # pruebas
uvicorn app.api:app --reload              # API
```
Swagger: http://127.0.0.1:8000/docs — OpenAPI: http://127.0.0.1:8000/openapi.json

## Evidencias (`evidencias/`)
| Archivo | Qué es |
|---|---|
| `01_carga_16_pedidos.png` | Render de la salida real de `python cargar_csv.py` (no es captura de pantalla) |
| `02_escenarios_E01_E15.png` | Render de la salida real de `python ejecutar_escenarios.py` (no es captura de pantalla) |
| `02_escenarios_E01_E15_y_03_pytest.png` | Captura del equipo: escenarios y pytest con 103 passed |
| `Evidencia_API_O013_200.png` | Captura del equipo: Swagger, `POST /orders/O013/confirm` → 200 |
| `Evidencia_API_ID200_404.png` | Captura del equipo: Swagger, ID inexistente → 404 |
| `salida_cargar_csv.txt`, `salida_escenarios.txt` | Salidas de texto de los comandos |

**Capturas pendientes** (hay que tomarlas con la API corriendo): 409 (confirmar O013 dos veces) → `Evidencia_API_O013_409.png`; 422 (confirmar O007, sin artículos) → `Evidencia_API_O007_422.png`; y una captura de `python -m pytest -q` con el total actualizado → `03_pytest.png`.

## Modelo de dominio
- **Money** (Value Object inmutable): `Decimal` + moneda (MXN por defecto); rechaza negativos, no finitos y `float`; `add()` rechaza monedas distintas y devuelve un objeto nuevo.
- **Customer** (`id`, `is_vip`, `active`), **OrderItem** (SKU, cantidad, precio; rechaza SKU vacío y cantidad ≤ 0; `subtotal` calculado).
- **Order** (Aggregate Root): `customer`, `id`, `has_promotion`, `status`, `items`, `events`; `units` (suma de cantidades) y `total`.
  `add_item()` valida antes de modificar: solo DRAFT, solo MXN, máximo 20 **unidades** acumuladas (no renglones).
- Excepciones: `DomainException` ← `InvalidOrderData`, `InvalidOrderTransition`, `OrderItemLimitExceeded`.

## Specifications y descuentos
`Specification` con `&` (AND), `|` (OR), `~` (NOT); solo leen el pedido. Concretas: `MinimumAmountSpec` (`>` estricto), `VIPCustomerSpec`, `MinimumUnitsSpec` (`>=`), `ActivePromotionSpec`.
- **10 %**: VIP y total > 500 y ≥ 4 unidades y sin promoción.
- **5 %**: total > 5000 y sin promoción.
- Se combinan con OR; si ambas se cumplen se aplica 10 %. Exactamente 500 (O010) o 5000 no superan el umbral.
- El monto se calcula en `app/pricing.py` (`calculate_discount`). **Decisiones propias** (la guía no las fija): redondeo a centavos `ROUND_HALF_UP`; no se acumulan descuentos.
- Nota: la evaluación de descuento no considera si el cliente está activo (O003 y O009 califican al 10 % aunque O003 no pueda confirmarse); la guía no liga ambas reglas.

## Máquina de estados
DRAFT→CONFIRMED (`confirm`), CONFIRMED→SHIPPED (`ship(tracking)`), CONFIRMED→CANCELLED (`cancel(reason)`), SHIPPED→DELIVERED (`deliver`), SHIPPED→RETURNED (`return_order`). Cualquier otra combinación lanza `InvalidOrderTransition`.
Diagrama: `docs/diagramas/Diagrama_Estados_TechStore.png` / `.pdf` / `.drawio` (editable) / `.mmd`. Validaciones de datos (`InvalidOrderData`): pedido vacío, cliente inactivo, guía vacía, motivo vacío.

## Domain Events
`DomainEvent(name, order_id, occurred_at UTC)` y subclases `OrderConfirmed`, `OrderShipped` (con `tracking_number`), `OrderCancelled` (con `reason`), `OrderDelivered`, `OrderReturned`. Regla: **validar → cambiar estado → registrar evento**; una operación fallida no deja cambios ni evento (p. ej. segunda confirmación de O013).

## API
| Método | Ruta | Cuerpo | Respuestas |
|---|---|---|---|
| GET | `/orders/{id}` | — | 200 detalle; 404 |
| POST | `/orders/{id}/confirm` | — | 200 `{id,status}`; 404; 409 (no DRAFT); 422 (vacío/cliente inactivo) |
| POST | `/orders/{id}/ship` | `{"tracking_number": "..."}` | 200; 404; 409; 422 (guía vacía o cuerpo ausente) |
| POST | `/orders/{id}/cancel` | `{"reason": "..."}` | 200; 404; 409; 422 (motivo vacío) |
| POST | `/orders/{id}/deliver` · `/return` | — | 200; 404; 409 (extra) |
| GET | `/orders`, `/orders/{id}/discount` | — | 200 (extra) |

No implementados (opcionales en la guía): `POST /orders` y `POST /orders/{id}/items`. `OrderItemLimitExceeded` se mapea a 422 (decisión propia). Los errores inesperados devuelven 500 genérico sin detalles internos.

## Resultados de los 15 escenarios (ejecutados con `ejecutar_escenarios.py`)
Los 15 coinciden con el `objetivo` de `escenarios.csv`. Detalle completo (5 columnas) en `docs/bitacora/`.
Notas: el CSV no define guías de envío; se usó `GUIA-DEMO-001`. Los estados finales de E07/E14/E15 se toman de la pista del CSV.

| Caso | Pedido / operación | Resultado real |
|---|---|---|
| E01 | O001 descuento | 10 % (1890.00) ✔ |
| E02 | O002 descuento | 0 % ✔ |
| E03 | O003 confirmar | rechazado, cliente inactivo (422) ✔ |
| E04 | O005 descuento | 0 % (promoción) ✔ |
| E05 | O006 descuento | 5 % (17100.00) ✔ |
| E06 | O007 confirmar | rechazado, vacío (422) ✔ |
| E07 | O008 confirmar | CONFIRMED, 20 uds ✔ |
| E08 | O009 + SKU003×2 | rechazado, 21 > 20; sigue en 19 ✔ |
| E09 | O010 descuento | 0 % (500 exacto) ✔ |
| E10 | O011 descuento | 0 % (3 uds) ✔ |
| E11 | O012 confirmar y enviar sin guía | confirma; envío rechazado; queda CONFIRMED ✔ |
| E12 | O013 confirmar 2 veces | 2.ª rechazada (409); 1 evento ✔ |
| E13 | O014 cancelar desde SHIPPED | rechazado; queda SHIPPED ✔ |
| E14 | O015 enviar y devolver | RETURNED ✔ |
| E15 | O016 enviar y entregar | DELIVERED ✔ |

## Limitaciones
Repositorio en memoria (se pierde al reiniciar; sin base de datos); sin control de inventario (la existencia es solo catálogo); un solo proceso; sin autenticación.
