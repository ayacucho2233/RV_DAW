"""Tests de `app.features.reservas.router` + wiring de `app.main` (Block 3 de
spec-FEAT-001c).

Cada test referencia el AC del PRD o la mitigación del threat model que
cubre (docs/daw/prd/prd-FEAT-001c.md, docs/daw/security/threat-FEAT-001c.md).

`app.features.reservas.router` define su propio `Limiter` a nivel de módulo
(mismo patrón que `app.core.security`): para que el contador de rate limit
arranque en cero en cada test, la fixture `app_client` recarga ese módulo (y
`app.main`, que lo importa) antes de cada test — mismo criterio de recarga
que usa `test_vehiculos_router.py`. `app.core.database` NUNCA se recarga:
`get_db` debe conservar su identidad de objeto para que
`dependency_overrides` lo pueda reemplazar por la sesión de test
(`db_session`, la misma fixture de Block 1/2).

Este feature no tiene autenticación (a diferencia de `vehiculos`), así que
no hace falta la gimnasia de credenciales de `test_vehiculos_router.py`.
"""
import importlib
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.features.vehiculos import repository as vehiculos_repository
from app.features.vehiculos import service as vehiculos_service
from app.features.vehiculos.models import EstadoVehiculo
from app.features.vehiculos.schemas import VehiculoCreate

_MODULES_A_RECARGAR = (
    "app.features.reservas.router",
    "app.main",
)


@pytest.fixture
def app_client(db_session):
    """`TestClient` con `get_db` apuntando a la sesión de test (`db_session`)
    y el `Limiter` de `reservas.router` reiniciado en cero para cada test."""
    for module_name in _MODULES_A_RECARGAR:
        sys.modules.pop(module_name, None)
    for module_name in _MODULES_A_RECARGAR:
        importlib.import_module(module_name)

    from app.core.database import get_db
    from app.main import app as fastapi_app

    def _override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db

    with TestClient(fastapi_app, raise_server_exceptions=False) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


def _crear_vehiculo(db_session, patente="AA123BB", tipo="auto"):
    return vehiculos_service.crear_vehiculo(db_session, VehiculoCreate(patente=patente, tipo=tipo))


def _dt_iso(offset_hours: int) -> str:
    """ISO 8601 timezone-aware, offset en horas desde un punto fijo futuro."""
    base = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    return (base + timedelta(hours=offset_hours)).isoformat()


def _reserva_payload(vehiculo_id, inicio_h=0, fin_h=2, **overrides):
    payload = {
        "nombre_empleado": "Juan Perez",
        "legajo": "1234",
        "licencia": "B1",
        "vehiculo_id": vehiculo_id,
        "fecha_inicio": _dt_iso(inicio_h),
        "fecha_fin": _dt_iso(fin_h),
        "destino": "Rosario",
    }
    payload.update(overrides)
    return payload


def _dt_real_iso(offset_hours: float) -> str:
    """ISO 8601 timezone-aware, offset en horas desde el momento real de
    ejecución del test (a diferencia de `_dt_iso`, fijo en 2026-09-01) —
    necesario para los tests de filtro por período (Block 2), que comparan
    contra `datetime.now(timezone.utc)`."""
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).isoformat()


def _reserva_payload_real(vehiculo_id, inicio_h, fin_h, **overrides):
    """Igual que `_reserva_payload`, pero con fechas relativas al momento
    real de ejecución (`_dt_real_iso`) en vez de la base fija 2026-09-01."""
    payload = {
        "nombre_empleado": "Juan Perez",
        "legajo": "1234",
        "licencia": "B1",
        "vehiculo_id": vehiculo_id,
        "fecha_inicio": _dt_real_iso(inicio_h),
        "fecha_fin": _dt_real_iso(fin_h),
        "destino": "Rosario",
    }
    payload.update(overrides)
    return payload


def test_get_vehiculos_pool_200(app_client, db_session):
    """AC-01: listado público del pool, solo patente/tipo."""
    _crear_vehiculo(db_session, patente="AA111AA", tipo="auto")
    _crear_vehiculo(db_session, patente="BB222BB", tipo="camioneta")

    resp = app_client.get("/reservas/vehiculos")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {v["patente"] for v in body} == {"AA111AA", "BB222BB"}
    assert "estado" not in body[0]


def test_post_reserva_ok_201(app_client, db_session):
    """AC-02: alta con vehículo disponible y campos completos."""
    vehiculo = _crear_vehiculo(db_session)

    resp = app_client.post("/reservas", json=_reserva_payload(vehiculo.id))

    assert resp.status_code == 201
    body = resp.json()
    assert body["vehiculo_id"] == vehiculo.id
    assert body["estado"] == "activa"
    assert "id" in body


def test_post_reserva_campo_faltante_422(app_client, db_session):
    """AC-03: falta un campo obligatorio (destino)."""
    vehiculo = _crear_vehiculo(db_session)
    payload = _reserva_payload(vehiculo.id)
    del payload["destino"]

    resp = app_client.post("/reservas", json=payload)

    assert resp.status_code == 422


def test_post_reserva_fecha_fin_menor_o_igual_422(app_client, db_session):
    """AC-04: `fecha_fin <= fecha_inicio` se rechaza con 422."""
    vehiculo = _crear_vehiculo(db_session)

    resp = app_client.post(
        "/reservas", json=_reserva_payload(vehiculo.id, inicio_h=4, fin_h=2)
    )

    assert resp.status_code == 422


def test_post_reserva_vehiculo_inexistente_404(app_client, db_session):
    resp = app_client.post("/reservas", json=_reserva_payload(9999))

    assert resp.status_code == 404


def test_post_reserva_vehiculo_no_activo_409(app_client, db_session):
    """AC-08: vehículo en `baja_temporal` es rechazado."""
    vehiculo = _crear_vehiculo(db_session)
    vehiculo_baja = vehiculos_service.dar_de_baja_temporal(db_session, vehiculo.id)
    assert vehiculo_baja.estado == EstadoVehiculo.baja_temporal

    resp = app_client.post("/reservas", json=_reserva_payload(vehiculo.id))

    assert resp.status_code == 409


def test_post_reserva_solapada_409(app_client, db_session):
    """AC-05: una segunda reserva sobre el mismo vehículo con período que se
    cruza con una reserva activa existente se rechaza."""
    vehiculo = _crear_vehiculo(db_session)
    resp1 = app_client.post(
        "/reservas", json=_reserva_payload(vehiculo.id, inicio_h=0, fin_h=4)
    )
    assert resp1.status_code == 201

    resp2 = app_client.post(
        "/reservas", json=_reserva_payload(vehiculo.id, inicio_h=2, fin_h=6)
    )

    assert resp2.status_code == 409


def test_get_disponibilidad_200(app_client, db_session):
    """AC-07: un vehículo con reserva solapando el rango consultado aparece
    `disponible=False`; uno sin solapamiento, `disponible=True`."""
    ocupado = _crear_vehiculo(db_session, patente="AA111AA", tipo="auto")
    libre = _crear_vehiculo(db_session, patente="BB222BB", tipo="camioneta")

    resp_alta = app_client.post(
        "/reservas", json=_reserva_payload(ocupado.id, inicio_h=0, fin_h=4)
    )
    assert resp_alta.status_code == 201

    resp = app_client.get(
        "/reservas/disponibilidad",
        params={"desde": _dt_iso(1), "hasta": _dt_iso(3)},
    )

    assert resp.status_code == 200
    body = resp.json()
    por_id = {v["vehiculo_id"]: v for v in body}
    assert por_id[ocupado.id]["disponible"] is False
    assert por_id[libre.id]["disponible"] is True


def test_get_disponibilidad_query_invalido_422(app_client, db_session):
    """Falta el query param `hasta`."""
    resp = app_client.get("/reservas/disponibilidad", params={"desde": _dt_iso(0)})

    assert resp.status_code == 422


def test_post_reserva_rate_limit_429(app_client, db_session):
    """TM-C-02: máx. 10 altas por IP por hora; la 11ª responde 429."""
    vehiculo = _crear_vehiculo(db_session)

    for i in range(10):
        resp = app_client.post(
            "/reservas",
            json=_reserva_payload(vehiculo.id, inicio_h=i * 3, fin_h=i * 3 + 2),
        )
        assert resp.status_code == 201, resp.text

    resp_bloqueado = app_client.post(
        "/reservas",
        json=_reserva_payload(vehiculo.id, inicio_h=100, fin_h=102),
    )

    assert resp_bloqueado.status_code == 429


def test_get_disponibilidad_rate_limit_429(app_client, db_session):
    """TM-C-02: máx. 60 consultas por IP por minuto; la 61ª responde 429."""
    for _ in range(60):
        resp = app_client.get(
            "/reservas/disponibilidad",
            params={"desde": _dt_iso(0), "hasta": _dt_iso(2)},
        )
        assert resp.status_code == 200, resp.text

    resp_bloqueado = app_client.get(
        "/reservas/disponibilidad",
        params={"desde": _dt_iso(0), "hasta": _dt_iso(2)},
    )

    assert resp_bloqueado.status_code == 429


# --- Block 2: GET /reservas (listado + filtro por período) --------------


def test_get_reservas_sin_filtro_200(app_client, db_session):
    """AC-01: el listado devuelve todas las reservas existentes,
    enriquecidas con patente/tipo, sin exponer legajo/licencia."""
    vehiculo = _crear_vehiculo(db_session)
    resp_post = app_client.post("/reservas", json=_reserva_payload(vehiculo.id))
    assert resp_post.status_code == 201

    resp = app_client.get("/reservas")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    item = body[0]
    assert item["patente"] == vehiculo.patente
    assert item["destino"] == "Rosario"
    assert item["estado"] == "activa"
    assert "legajo" not in item
    assert "licencia" not in item


def test_get_reservas_filtro_futuras_200(app_client, db_session):
    """AC-02: `periodo=futuras` devuelve solo reservas cuya `fecha_inicio`
    es posterior a ahora."""
    vehiculo = _crear_vehiculo(db_session)
    resp_futura = app_client.post(
        "/reservas", json=_reserva_payload_real(vehiculo.id, 10, 12)
    )
    assert resp_futura.status_code == 201
    resp_pasada = app_client.post(
        "/reservas", json=_reserva_payload_real(vehiculo.id, -10, -8)
    )
    assert resp_pasada.status_code == 201

    resp = app_client.get("/reservas", params={"periodo": "futuras"})

    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert ids == {resp_futura.json()["id"]}


def test_get_reservas_filtro_en_curso_200(app_client, db_session):
    """AC-03: `periodo=en_curso` devuelve solo reservas donde
    `fecha_inicio <= ahora <= fecha_fin`."""
    vehiculo = _crear_vehiculo(db_session)
    resp_en_curso = app_client.post(
        "/reservas", json=_reserva_payload_real(vehiculo.id, -1, 1)
    )
    assert resp_en_curso.status_code == 201
    resp_futura = app_client.post(
        "/reservas", json=_reserva_payload_real(vehiculo.id, 10, 12)
    )
    assert resp_futura.status_code == 201

    resp = app_client.get("/reservas", params={"periodo": "en_curso"})

    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert ids == {resp_en_curso.json()["id"]}


def test_get_reservas_filtro_pasadas_200(app_client, db_session):
    """AC-04: `periodo=pasadas` devuelve solo reservas cuya `fecha_fin` es
    anterior a ahora."""
    vehiculo = _crear_vehiculo(db_session)
    resp_pasada = app_client.post(
        "/reservas", json=_reserva_payload_real(vehiculo.id, -10, -8)
    )
    assert resp_pasada.status_code == 201
    resp_futura = app_client.post(
        "/reservas", json=_reserva_payload_real(vehiculo.id, 10, 12)
    )
    assert resp_futura.status_code == 201

    resp = app_client.get("/reservas", params={"periodo": "pasadas"})

    assert resp.status_code == 200
    ids = {item["id"] for item in resp.json()}
    assert ids == {resp_pasada.json()["id"]}


def test_get_reservas_periodo_invalido_422(app_client, db_session):
    """`periodo` fuera del enum `FiltroPeriodoReserva` se rechaza con 422."""
    resp = app_client.get("/reservas", params={"periodo": "invalido"})

    assert resp.status_code == 422


# --- Block 2 de spec-FEAT-001e: reservas pasadas de vehículos dados de baja


def test_get_reservas_incluye_reserva_de_vehiculo_dado_de_baja_200(app_client, db_session):
    """AC-03/AC-04 a nivel HTTP: una reserva pasada de un vehículo en
    `baja_temporal` o `baja_definitiva` sigue apareciendo en `GET /reservas`,
    con `patente`/`tipo` resueltos correctamente. El vehículo se pasa a cada
    estado mutando el modelo directamente (no vía los endpoints PATCH de
    baja) para no acoplar este test a la validación de reservas activas de
    Block 1 — acá solo importa el estado final del vehículo."""
    v_temporal = _crear_vehiculo(db_session, patente="BT111BT", tipo="auto")
    v_definitiva = _crear_vehiculo(db_session, patente="BD222BD", tipo="camioneta")

    resp_temporal = app_client.post(
        "/reservas", json=_reserva_payload_real(v_temporal.id, -10, -8)
    )
    assert resp_temporal.status_code == 201
    resp_definitiva = app_client.post(
        "/reservas", json=_reserva_payload_real(v_definitiva.id, -6, -4)
    )
    assert resp_definitiva.status_code == 201

    vehiculo_temporal = vehiculos_repository.obtener_por_id(db_session, v_temporal.id)
    vehiculo_temporal.estado = EstadoVehiculo.baja_temporal
    vehiculos_repository.guardar(db_session, vehiculo_temporal)

    vehiculo_definitiva = vehiculos_repository.obtener_por_id(db_session, v_definitiva.id)
    vehiculo_definitiva.estado = EstadoVehiculo.baja_definitiva
    vehiculos_repository.guardar(db_session, vehiculo_definitiva)

    resp = app_client.get("/reservas", params={"periodo": "pasadas"})

    assert resp.status_code == 200
    body = resp.json()
    por_vehiculo = {item["vehiculo_id"]: item for item in body}
    assert set(por_vehiculo.keys()) == {v_temporal.id, v_definitiva.id}
    assert por_vehiculo[v_temporal.id]["patente"] == "BT111BT"
    assert por_vehiculo[v_temporal.id]["tipo"] == "auto"
    assert por_vehiculo[v_definitiva.id]["patente"] == "BD222BD"
    assert por_vehiculo[v_definitiva.id]["tipo"] == "camioneta"


# --- Block 2: PATCH /reservas/{id}/cancelar ------------------------------


def test_patch_cancelar_reserva_ok_200(app_client, db_session):
    """AC-05: cancelar con el legajo correcto pasa `estado` a `cancelada`."""
    vehiculo = _crear_vehiculo(db_session)
    resp_post = app_client.post("/reservas", json=_reserva_payload(vehiculo.id))
    assert resp_post.status_code == 201
    reserva_id = resp_post.json()["id"]

    resp = app_client.patch(
        f"/reservas/{reserva_id}/cancelar", json={"legajo": "1234"}
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "cancelada"


def test_patch_cancelar_reserva_inexistente_404(app_client, db_session):
    resp = app_client.patch("/reservas/9999/cancelar", json={"legajo": "1234"})

    assert resp.status_code == 404


def test_patch_cancelar_reserva_ya_cancelada_409(app_client, db_session):
    """Decisión de diseño confirmada en PLAN: cancelar dos veces devuelve
    409 en la segunda, no 200 idempotente."""
    vehiculo = _crear_vehiculo(db_session)
    resp_post = app_client.post("/reservas", json=_reserva_payload(vehiculo.id))
    reserva_id = resp_post.json()["id"]
    resp1 = app_client.patch(
        f"/reservas/{reserva_id}/cancelar", json={"legajo": "1234"}
    )
    assert resp1.status_code == 200

    resp2 = app_client.patch(
        f"/reservas/{reserva_id}/cancelar", json={"legajo": "1234"}
    )

    assert resp2.status_code == 409


def test_patch_cancelar_reserva_legajo_no_coincide_403(app_client, db_session):
    """AC-06: legajo distinto al de la reserva se rechaza con 403 y el
    mensaje no revela el legajo real."""
    vehiculo = _crear_vehiculo(db_session)
    resp_post = app_client.post("/reservas", json=_reserva_payload(vehiculo.id))
    reserva_id = resp_post.json()["id"]

    resp = app_client.patch(
        f"/reservas/{reserva_id}/cancelar", json={"legajo": "9999"}
    )

    assert resp.status_code == 403
    assert "1234" not in resp.json()["detail"]


def test_patch_cancelar_reserva_legajo_faltante_422(app_client, db_session):
    vehiculo = _crear_vehiculo(db_session)
    resp_post = app_client.post("/reservas", json=_reserva_payload(vehiculo.id))
    reserva_id = resp_post.json()["id"]

    resp = app_client.patch(f"/reservas/{reserva_id}/cancelar", json={})

    assert resp.status_code == 422


def test_get_reservas_rate_limit_429(app_client, db_session):
    """TM-C-02: máx. 60 consultas por IP por minuto sobre la clave
    `"reservas-listado"`, independiente de `"reservas-vehiculos"`."""
    for _ in range(60):
        resp = app_client.get("/reservas")
        assert resp.status_code == 200, resp.text

    resp_bloqueado = app_client.get("/reservas")
    assert resp_bloqueado.status_code == 429

    resp_vehiculos = app_client.get("/reservas/vehiculos")
    assert resp_vehiculos.status_code == 200


def test_patch_cancelar_rate_limit_429(app_client, db_session):
    """TM-C-02: máx. 10 mutaciones por IP por hora sobre la clave
    `"reservas-cancelar"`, independiente de `"reservas-post"` (agotar el
    cupo de cancelación no descuenta el de alta, y viceversa)."""
    for _ in range(10):
        resp = app_client.patch("/reservas/9999/cancelar", json={"legajo": "1234"})
        assert resp.status_code == 404, resp.text

    resp_bloqueado = app_client.patch(
        "/reservas/9999/cancelar", json={"legajo": "1234"}
    )
    assert resp_bloqueado.status_code == 429

    vehiculo = _crear_vehiculo(db_session)
    resp_post = app_client.post("/reservas", json=_reserva_payload(vehiculo.id))
    assert resp_post.status_code == 201


# --- Block 2 de spec-FEAT-004: GET /reservas/vehiculo/{patente} ----------


def test_router_get_reservas_vehiculo_200(app_client, db_session):
    """AC-01: patente existente con reservas activas devuelve 200 con el
    shape de `ReservaListItem`."""
    vehiculo = _crear_vehiculo(db_session, patente="GV111GV", tipo="auto")
    resp_post = app_client.post(
        "/reservas", json=_reserva_payload_real(vehiculo.id, 2, 4)
    )
    assert resp_post.status_code == 201

    resp = app_client.get("/reservas/vehiculo/GV111GV")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    item = body[0]
    assert item["patente"] == "GV111GV"
    assert item["vehiculo_id"] == vehiculo.id
    assert item["destino"] == "Rosario"
    assert "legajo" not in item
    assert "licencia" not in item


def test_router_get_reservas_vehiculo_404(app_client, db_session):
    """AC-03: patente inexistente responde 404 con detail descriptivo,
    mencionando la patente consultada (distingue de un 404 genérico de
    ruta inexistente)."""
    resp = app_client.get("/reservas/vehiculo/ZZ999ZZ")

    assert resp.status_code == 404
    assert "ZZ999ZZ" in resp.json()["detail"]


def test_router_get_reservas_vehiculo_rate_limit(app_client, db_session):
    """TM-C-02: máx. 60 consultas por IP por minuto sobre la clave
    `"reservas-por-patente"`."""
    vehiculo = _crear_vehiculo(db_session, patente="RL222RL", tipo="auto")

    for _ in range(60):
        resp = app_client.get(f"/reservas/vehiculo/{vehiculo.patente}")
        assert resp.status_code == 200, resp.text

    resp_bloqueado = app_client.get(f"/reservas/vehiculo/{vehiculo.patente}")

    assert resp_bloqueado.status_code == 429


def test_router_get_reservas_vehiculo_patente_invalida_422(app_client, db_session):
    """`patente` con caracteres no alfanuméricos o de más de 10 caracteres
    se rechaza con 422 antes de llegar a `service.py`."""
    resp_no_alfanumerica = app_client.get("/reservas/vehiculo/AB-123!")
    assert resp_no_alfanumerica.status_code == 422

    resp_muy_larga = app_client.get("/reservas/vehiculo/ABCDEFGHIJK")
    assert resp_muy_larga.status_code == 422
