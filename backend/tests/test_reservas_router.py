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
    payload = dict(
        nombre_empleado="Juan Perez",
        legajo="1234",
        licencia="B1",
        vehiculo_id=vehiculo_id,
        fecha_inicio=_dt_iso(inicio_h),
        fecha_fin=_dt_iso(fin_h),
        destino="Rosario",
    )
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
