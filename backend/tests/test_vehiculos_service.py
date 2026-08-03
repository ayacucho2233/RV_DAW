"""Tests de `app.features.vehiculos.service` (Block 2 de spec-FEAT-001a).

Cada test referencia el AC del PRD que cubre (docs/daw/prd/prd-FEAT-001a.md).
Corren contra la base de datos de test real (fixture `db_session` de
`conftest.py`), no contra mocks: la capa que se ejercita incluye
`repository.py`, así que también sirve como evidencia de la mitigación TM-03
(traducción de `IntegrityError` a `PatenteYaExisteError`).
"""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.features.vehiculos import repository, service
from app.features.vehiculos.exceptions import (
    PatenteYaExisteError,
    TipoInvalidoError,
    TransicionEstadoInvalidaError,
    VehiculoNoEncontradoError,
)
from app.features.vehiculos.models import EstadoVehiculo, TipoVehiculo
from app.features.vehiculos.schemas import VehiculoCreate, VehiculoUpdate


def test_crear_vehiculo_ok(db_session):
    """AC-01: alta con patente y tipo válidos deja el vehículo disponible."""
    data = VehiculoCreate(patente="AA123BB", tipo="auto")

    vehiculo = service.crear_vehiculo(db_session, data)

    assert vehiculo.id is not None
    assert vehiculo.patente == "AA123BB"
    assert vehiculo.tipo == TipoVehiculo.auto
    assert vehiculo.estado == EstadoVehiculo.activo


def test_crear_vehiculo_patente_duplicada(db_session):
    """AC-08: alta con patente ya existente se rechaza (chequeo previo)."""
    service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    with pytest.raises(PatenteYaExisteError):
        service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="camioneta"))


def test_crear_vehiculo_patente_duplicada_integrity_error_traducido(db_session):
    """TM-03: si dos altas concurrentes evitan el chequeo previo de
    `service.py` (p. ej. llamando `repository.crear` directamente dos veces
    con la misma patente, simulando la carrera TOCTOU), `repository.py`
    debe traducir el `IntegrityError` del UNIQUE constraint a
    `PatenteYaExisteError` — nunca dejarlo pasar crudo."""
    payload = VehiculoCreate(patente="ZZ999ZZ", tipo="auto")
    repository.crear(db_session, payload)

    with pytest.raises(PatenteYaExisteError):
        repository.crear(db_session, payload)


@pytest.mark.parametrize("patente", ["ABC 123", "AB-123", "AB_123", "AB.123", "AB123 "])
def test_crear_vehiculo_patente_formato_invalido(patente):
    """Aclaración de negocio (no escrita en la spec original): la patente
    debe ser alfanumérica, sin espacios ni caracteres especiales. Se valida
    a nivel de esquema (Pydantic), antes de llegar a `service.py`."""
    with pytest.raises(ValidationError):
        VehiculoCreate(patente=patente, tipo="auto")

    with pytest.raises(ValidationError):
        VehiculoUpdate(patente=patente, tipo="auto")


@pytest.mark.parametrize("patente", ["ABC123", "AB123CD", "1", "A1", "1234567890"])
def test_crear_vehiculo_patente_formato_valido(patente):
    """Patentes alfanuméricas sin separadores siguen siendo aceptadas,
    incluyendo el formato Mercosur (AB123CD)."""
    data = VehiculoCreate(patente=patente, tipo="auto")
    assert data.patente == patente


def test_crear_vehiculo_tipo_invalido(db_session):
    """AC-10: tipo distinto de auto/camioneta se rechaza.

    Nivel de esquema: Pydantic ya lo bloquea vía `Literal`. Nivel de
    servicio (defensivo, por si un caller interno pasa un objeto crudo que
    no pasó por el schema): `service.py` debe lanzar `TipoInvalidoError`.
    """
    with pytest.raises(ValidationError):
        VehiculoCreate(patente="AA123BB", tipo="moto")

    payload_crudo = SimpleNamespace(patente="AA123BB", tipo="moto")
    with pytest.raises(TipoInvalidoError):
        service.crear_vehiculo(db_session, payload_crudo)


def test_modificar_vehiculo_ok(db_session):
    """AC-02: modificar patente/tipo de un vehículo existente se refleja."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    actualizado = service.modificar_vehiculo(
        db_session, creado.id, VehiculoUpdate(patente="CC456DD", tipo="camioneta")
    )

    assert actualizado.id == creado.id
    assert actualizado.patente == "CC456DD"
    assert actualizado.tipo == TipoVehiculo.camioneta

    # Modificar sin cambiar la patente (contra sí mismo) no debe disparar
    # falso positivo de duplicado (FR-09 excluye el propio id).
    sin_cambios = service.modificar_vehiculo(
        db_session, creado.id, VehiculoUpdate(patente="CC456DD", tipo="camioneta")
    )
    assert sin_cambios.patente == "CC456DD"


def test_modificar_vehiculo_patente_duplicada(db_session):
    """AC-09: modificar asignando la patente de otro vehículo se rechaza."""
    service.crear_vehiculo(db_session, VehiculoCreate(patente="AA111AA", tipo="auto"))
    v2 = service.crear_vehiculo(db_session, VehiculoCreate(patente="BB222BB", tipo="camioneta"))

    with pytest.raises(PatenteYaExisteError):
        service.modificar_vehiculo(
            db_session, v2.id, VehiculoUpdate(patente="AA111AA", tipo="camioneta")
        )


def test_modificar_vehiculo_tipo_invalido(db_session):
    """AC-11: modificar asignando un tipo inválido se rechaza."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    with pytest.raises(ValidationError):
        VehiculoUpdate(patente="AA123BB", tipo="moto")

    payload_crudo = SimpleNamespace(patente="AA123BB", tipo="moto")
    with pytest.raises(TipoInvalidoError):
        service.modificar_vehiculo(db_session, creado.id, payload_crudo)


def test_modificar_vehiculo_inexistente(db_session):
    """404 de dominio: modificar un id que no existe."""
    with pytest.raises(VehiculoNoEncontradoError):
        service.modificar_vehiculo(db_session, 9999, VehiculoUpdate(patente="AA123BB", tipo="auto"))


def test_baja_temporal_ok(db_session):
    """AC-03: baja temporal de un vehículo activo."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    resultado = service.dar_de_baja_temporal(db_session, creado.id)

    assert resultado.estado == EstadoVehiculo.baja_temporal


def test_baja_temporal_vehiculo_inexistente(db_session):
    with pytest.raises(VehiculoNoEncontradoError):
        service.dar_de_baja_temporal(db_session, 9999)


def test_baja_temporal_transicion_invalida(db_session):
    """Un vehículo en baja definitiva no puede pasar a baja temporal."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    service.dar_de_baja_definitiva(db_session, creado.id)

    with pytest.raises(TransicionEstadoInvalidaError):
        service.dar_de_baja_temporal(db_session, creado.id)


def test_baja_definitiva_ok(db_session):
    """AC-04: baja definitiva permitida desde activo o baja temporal."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    resultado = service.dar_de_baja_definitiva(db_session, creado.id)
    assert resultado.estado == EstadoVehiculo.baja_definitiva

    otro = service.crear_vehiculo(db_session, VehiculoCreate(patente="CC456DD", tipo="camioneta"))
    service.dar_de_baja_temporal(db_session, otro.id)
    resultado2 = service.dar_de_baja_definitiva(db_session, otro.id)
    assert resultado2.estado == EstadoVehiculo.baja_definitiva


def test_baja_definitiva_vehiculo_inexistente(db_session):
    with pytest.raises(VehiculoNoEncontradoError):
        service.dar_de_baja_definitiva(db_session, 9999)


def test_baja_definitiva_transicion_invalida(db_session):
    """Un vehículo ya en baja definitiva no puede volver a darse de baja."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    service.dar_de_baja_definitiva(db_session, creado.id)

    with pytest.raises(TransicionEstadoInvalidaError):
        service.dar_de_baja_definitiva(db_session, creado.id)


def test_reactivar_ok(db_session):
    """AC-06: reactivar un vehículo en baja temporal lo vuelve a activo."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    service.dar_de_baja_temporal(db_session, creado.id)

    resultado = service.reactivar(db_session, creado.id)

    assert resultado.estado == EstadoVehiculo.activo


def test_reactivar_baja_definitiva_rechazado(db_session):
    """AC-07: no se puede reactivar un vehículo en baja definitiva."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    service.dar_de_baja_definitiva(db_session, creado.id)

    with pytest.raises(TransicionEstadoInvalidaError):
        service.reactivar(db_session, creado.id)


def test_reactivar_vehiculo_inexistente(db_session):
    with pytest.raises(VehiculoNoEncontradoError):
        service.reactivar(db_session, 9999)


def test_listar_vehiculos(db_session):
    """Soporte de Block 3/4 (GET /vehiculos)."""
    service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    service.crear_vehiculo(db_session, VehiculoCreate(patente="CC456DD", tipo="camioneta"))

    resultado = service.listar_vehiculos(db_session)

    assert len(resultado) == 2
    assert {v.patente for v in resultado} == {"AA123BB", "CC456DD"}


def test_crear_vehiculo_loguea_operacion_sin_credenciales(db_session, caplog):
    """TM-04: cada escritura loguea INFO con la operación, sin filtrar
    credenciales (no aplica auth en este bloque, pero el log no debe
    incluir nunca un header Authorization ni datos sensibles)."""
    import logging

    with caplog.at_level(logging.INFO, logger="app.features.vehiculos.service"):
        vehiculo = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    mensajes = [r.getMessage() for r in caplog.records]
    assert any("crear_vehiculo" in m and str(vehiculo.id) in m for m in mensajes)
    assert not any("Authorization" in m or "authorization" in m.lower() for m in mensajes)
