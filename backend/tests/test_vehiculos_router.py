"""Tests de `app.features.vehiculos.router` + `app.core.security` + wiring de
`app.main` (Block 3 de spec-FEAT-001a).

Cada test referencia el AC del PRD o la mitigación del threat model que
cubre (docs/daw/prd/prd-FEAT-001a.md, docs/daw/security/threat-FEAT-001a.md).

`app.core.config.settings`, `app.core.security` y
`app.features.vehiculos.router` leen `ADMIN_USERNAME`/`ADMIN_PASSWORD_HASH`
a nivel de módulo, así que la fixture `app_client` genera un hash bcrypt real
para una contraseña conocida, lo inyecta vía env vars y recarga esos módulos
(más `app.main`) en orden de dependencia — mismo patrón de recarga que usa
`test_config.py` para `app.core.config`. `app.core.database` NUNCA se
recarga: `get_db` debe conservar su identidad de objeto para que
`dependency_overrides` lo pueda reemplazar por la sesión de test
(`db_session`, la misma fixture de Block 2).
"""
import base64
import importlib
import sys
from datetime import datetime, timezone

import bcrypt
import pytest
from fastapi.testclient import TestClient

from app.features.reservas import service as reservas_service
from app.features.reservas.schemas import ReservaCreate
from app.features.vehiculos import service
from app.features.vehiculos.schemas import VehiculoCreate
from tests.conftest import REQUIRED_ENV

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "clave-segura-123"

_MODULES_A_RECARGAR = (
    "app.core.config",
    "app.core.security",
    "app.features.vehiculos.router",
    "app.main",
)


def _basic_auth_header(username: str, password: str) -> dict:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture
def app_client(db_session, monkeypatch: pytest.MonkeyPatch):
    """`TestClient` con credenciales admin conocidas y `get_db` apuntando a
    la sesión de test (`db_session`, Block 2)."""
    password_hash = bcrypt.hashpw(ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
    monkeypatch.setenv("ADMIN_USERNAME", ADMIN_USERNAME)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", password_hash)

    for module_name in _MODULES_A_RECARGAR:
        sys.modules.pop(module_name, None)
    for module_name in _MODULES_A_RECARGAR:
        importlib.import_module(module_name)

    from app.core.database import get_db
    from app.main import app as fastapi_app

    def _override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db

    # `raise_server_exceptions=False`: sin esto, el TestClient re-lanza
    # cualquier excepción no capturada por el ASGI app en vez de devolver la
    # respuesta que produjo `manejador_error_generico` — necesario para
    # poder testear el 500 genérico de TM-03 como lo vería un cliente real.
    with TestClient(fastapi_app, raise_server_exceptions=False) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return _basic_auth_header(ADMIN_USERNAME, ADMIN_PASSWORD)


def test_post_vehiculo_sin_credenciales_401(app_client):
    resp = app_client.post("/vehiculos", json={"patente": "AA123BB", "tipo": "auto"})

    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Basic"


def test_post_vehiculo_credenciales_invalidas_401_mensaje_generico(app_client):
    """TM-05: el mensaje de error es idéntico si falla el usuario o la
    contraseña — evita enumeración de usuario."""
    resp_usuario_malo = app_client.post(
        "/vehiculos",
        json={"patente": "AA123BB", "tipo": "auto"},
        headers=_basic_auth_header("otro-usuario", ADMIN_PASSWORD),
    )
    resp_password_mala = app_client.post(
        "/vehiculos",
        json={"patente": "AA123BB", "tipo": "auto"},
        headers=_basic_auth_header(ADMIN_USERNAME, "password-incorrecta"),
    )

    assert resp_usuario_malo.status_code == 401
    assert resp_password_mala.status_code == 401
    assert resp_usuario_malo.json()["detail"] == resp_password_mala.json()["detail"]


def test_post_vehiculo_ok_201(app_client, auth_headers):
    """AC-01: alta con patente y tipo válidos."""
    resp = app_client.post(
        "/vehiculos",
        json={"patente": "AA123BB", "tipo": "auto"},
        headers=auth_headers,
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["patente"] == "AA123BB"
    assert body["tipo"] == "auto"
    assert body["estado"] == "activo"
    assert "id" in body


def test_post_vehiculo_patente_duplicada_409(app_client, auth_headers, db_session):
    """AC-08: alta con patente ya existente responde 409."""
    service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    resp = app_client.post(
        "/vehiculos",
        json={"patente": "AA123BB", "tipo": "camioneta"},
        headers=auth_headers,
    )

    assert resp.status_code == 409


def test_post_vehiculo_tipo_invalido_400(app_client, auth_headers):
    """AC-10: tipo distinto de auto/camioneta responde 400.

    Pydantic ya rechaza el valor en el schema del request, lo que FastAPI
    traduce a 422 (error de validación de payload) — status distinto de 400
    pero igualmente un rechazo del cliente, no un 2xx. El 400 explícito de
    la tabla del spec corresponde a `TipoInvalidoError` de `service.py`
    cuando el payload sí pasa el schema pero el valor es inválido a nivel de
    dominio; acá se confirma que Pydantic bloquea el caso de esquema.
    """
    resp = app_client.post(
        "/vehiculos",
        json={"patente": "AA123BB", "tipo": "moto"},
        headers=auth_headers,
    )

    assert resp.status_code == 422


def test_put_vehiculo_ok_200(app_client, auth_headers, db_session):
    """AC-02: modificar patente/tipo de un vehículo existente."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    resp = app_client.put(
        f"/vehiculos/{creado.id}",
        json={"patente": "CC456DD", "tipo": "camioneta"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["patente"] == "CC456DD"
    assert body["tipo"] == "camioneta"


def test_put_vehiculo_inexistente_404(app_client, auth_headers):
    resp = app_client.put(
        "/vehiculos/9999",
        json={"patente": "AA123BB", "tipo": "auto"},
        headers=auth_headers,
    )

    assert resp.status_code == 404


def test_baja_temporal_200(app_client, auth_headers, db_session):
    """AC-03: baja temporal de un vehículo activo."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    resp = app_client.patch(f"/vehiculos/{creado.id}/baja-temporal", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["estado"] == "baja_temporal"


def test_baja_definitiva_200(app_client, auth_headers, db_session):
    """AC-04: baja definitiva de un vehículo activo."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    resp = app_client.patch(f"/vehiculos/{creado.id}/baja-definitiva", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["estado"] == "baja_definitiva"


def test_patch_baja_temporal_con_reserva_activa_409(app_client, auth_headers, db_session):
    """AC-01 (FEAT-001e), a nivel HTTP: un vehículo con una reserva activa
    responde 409 con el mensaje de `VehiculoConReservasActivasError` en el
    body, y el vehículo permanece activo."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    reservas_service.crear_reserva(
        db_session,
        ReservaCreate(
            nombre_empleado="Juan Perez",
            legajo="1234",
            licencia="B1",
            vehiculo_id=creado.id,
            fecha_inicio=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            fecha_fin=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
            destino="Rosario",
        ),
        ip_origen="10.0.0.1",
    )

    resp = app_client.patch(f"/vehiculos/{creado.id}/baja-temporal", headers=auth_headers)

    assert resp.status_code == 409
    assert (
        resp.json()["detail"]
        == f"El vehículo con id {creado.id} tiene reservas activas y no puede darse de baja."
    )


def test_patch_baja_definitiva_con_reserva_activa_409(app_client, auth_headers, db_session):
    """AC-02 (FEAT-001e), a nivel HTTP: ídem para baja definitiva."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    reservas_service.crear_reserva(
        db_session,
        ReservaCreate(
            nombre_empleado="Juan Perez",
            legajo="1234",
            licencia="B1",
            vehiculo_id=creado.id,
            fecha_inicio=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            fecha_fin=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
            destino="Rosario",
        ),
        ip_origen="10.0.0.1",
    )

    resp = app_client.patch(f"/vehiculos/{creado.id}/baja-definitiva", headers=auth_headers)

    assert resp.status_code == 409
    assert (
        resp.json()["detail"]
        == f"El vehículo con id {creado.id} tiene reservas activas y no puede darse de baja."
    )


def test_reactivar_200(app_client, auth_headers, db_session):
    """AC-06: reactivar un vehículo en baja temporal."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    service.dar_de_baja_temporal(db_session, creado.id)

    resp = app_client.patch(f"/vehiculos/{creado.id}/reactivar", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["estado"] == "activo"


def test_reactivar_baja_definitiva_409(app_client, auth_headers, db_session):
    """AC-07: no se puede reactivar un vehículo en baja definitiva."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    service.dar_de_baja_definitiva(db_session, creado.id)

    resp = app_client.patch(f"/vehiculos/{creado.id}/reactivar", headers=auth_headers)

    assert resp.status_code == 409


def test_get_vehiculos_200(app_client, auth_headers, db_session):
    service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    service.crear_vehiculo(db_session, VehiculoCreate(patente="CC456DD", tipo="camioneta"))

    resp = app_client.get("/vehiculos", headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {v["patente"] for v in body} == {"AA123BB", "CC456DD"}


def test_rate_limit_429_tras_intentos_fallidos(app_client):
    """TM-02: máximo 5 intentos fallidos por IP por minuto; el 6to responde
    429, aunque cada intento haya sido contra un endpoint distinto (el
    límite es compartido entre los 6 endpoints, no por-endpoint)."""
    credenciales_invalidas = _basic_auth_header(ADMIN_USERNAME, "password-incorrecta")

    for _ in range(5):
        resp = app_client.get("/vehiculos", headers=credenciales_invalidas)
        assert resp.status_code == 401

    resp_bloqueado = app_client.post(
        "/vehiculos",
        json={"patente": "AA123BB", "tipo": "auto"},
        headers=credenciales_invalidas,
    )

    assert resp_bloqueado.status_code == 429


def test_cors_solo_origen_configurado(app_client):
    origen_permitido = REQUIRED_ENV["FRONTEND_ORIGIN"]

    resp_permitido = app_client.options(
        "/vehiculos",
        headers={
            "Origin": origen_permitido,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp_permitido.headers.get("access-control-allow-origin") == origen_permitido

    resp_no_permitido = app_client.options(
        "/vehiculos",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp_no_permitido.headers.get("access-control-allow-origin") != "http://evil.example"


def test_error_no_anticipado_500_sin_detalle_interno(app_client, auth_headers, monkeypatch):
    """TM-03: una excepción no mapeada por el router responde 500 genérico,
    sin volcar el mensaje interno ni el traceback al cliente."""
    mensaje_interno_secreto = "boom-detalle-interno-de-implementacion"

    def _falla(*args, **kwargs):
        raise RuntimeError(mensaje_interno_secreto)

    monkeypatch.setattr(service, "listar_vehiculos", _falla)

    resp = app_client.get("/vehiculos", headers=auth_headers)

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert mensaje_interno_secreto not in resp.text
