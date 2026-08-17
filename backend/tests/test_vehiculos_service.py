"""Tests de `app.features.vehiculos.service` (Block 2 de spec-FEAT-001a, y
Block 1 de spec-FEAT-001e para la validación de reservas activas).

Cada test referencia el AC del PRD que cubre (docs/daw/prd/prd-FEAT-001a.md,
docs/daw/prd/prd-FEAT-001e.md). Corren contra la base de datos de test real
(fixture `db_session` de `conftest.py`), no contra mocks: la capa que se
ejercita incluye `repository.py`, así que también sirve como evidencia de la
mitigación TM-03 (traducción de `IntegrityError` a `PatenteYaExisteError`).
"""
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.features.reservas import service as reservas_service
from app.features.reservas.exceptions import VehiculoNoActivoError
from app.features.reservas.schemas import ReservaCreate
from app.features.vehiculos import repository, service
from app.features.vehiculos.exceptions import (
    PatenteYaExisteError,
    TipoInvalidoError,
    TransicionEstadoInvalidaError,
    VehiculoConReservasActivasError,
    VehiculoNoEncontradoError,
)
from app.features.vehiculos.models import EstadoVehiculo, TipoVehiculo
from app.features.vehiculos.schemas import VehiculoCreate, VehiculoUpdate

IP_TEST = "10.0.0.1"


def _dt(offset_hours: int = 0) -> datetime:
    """Datetime timezone-aware, offset en horas desde un punto fijo futuro."""
    base = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    return base + timedelta(hours=offset_hours)


def _reserva_data(vehiculo_id, inicio, fin, **overrides) -> ReservaCreate:
    base = {
        "nombre_empleado": "Juan Perez",
        "legajo": "1234",
        "licencia": "B1",
        "vehiculo_id": vehiculo_id,
        "fecha_inicio": inicio,
        "fecha_fin": fin,
        "destino": "Rosario",
    }
    base.update(overrides)
    return ReservaCreate(**base)


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


def test_baja_temporal_rechazada_con_reserva_activa(db_session):
    """AC-01 (FEAT-001e): vehículo activo con 1 reserva activa rechaza la
    baja temporal y el vehículo permanece activo (sin persistir el cambio de
    estado)."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    reservas_service.crear_reserva(
        db_session, _reserva_data(creado.id, _dt(0), _dt(2)), ip_origen=IP_TEST
    )

    with pytest.raises(VehiculoConReservasActivasError):
        service.dar_de_baja_temporal(db_session, creado.id)

    vehiculo_recargado = repository.obtener_por_id(db_session, creado.id)
    assert vehiculo_recargado.estado == EstadoVehiculo.activo


def test_baja_definitiva_rechazada_con_reserva_activa(db_session):
    """AC-02 (FEAT-001e): ídem para baja definitiva."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    reservas_service.crear_reserva(
        db_session, _reserva_data(creado.id, _dt(0), _dt(2)), ip_origen=IP_TEST
    )

    with pytest.raises(VehiculoConReservasActivasError):
        service.dar_de_baja_definitiva(db_session, creado.id)

    vehiculo_recargado = repository.obtener_por_id(db_session, creado.id)
    assert vehiculo_recargado.estado == EstadoVehiculo.activo


def test_baja_temporal_permitida_sin_reservas_activas(db_session):
    """No regresión sobre FEAT-001a: un vehículo activo sin reservas, o con
    reservas solo en estado 'cancelada', se sigue dando de baja
    normalmente."""
    sin_reservas = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    resultado = service.dar_de_baja_temporal(db_session, sin_reservas.id)
    assert resultado.estado == EstadoVehiculo.baja_temporal

    con_cancelada = service.crear_vehiculo(
        db_session, VehiculoCreate(patente="CC456DD", tipo="camioneta")
    )
    reserva = reservas_service.crear_reserva(
        db_session,
        _reserva_data(con_cancelada.id, _dt(0), _dt(2), legajo="5678"),
        ip_origen=IP_TEST,
    )
    reservas_service.cancelar_reserva(db_session, reserva.id, legajo="5678", ip_origen=IP_TEST)

    resultado2 = service.dar_de_baja_temporal(db_session, con_cancelada.id)
    assert resultado2.estado == EstadoVehiculo.baja_temporal


def test_baja_definitiva_permitida_con_reserva_cancelada(db_session):
    """Confirma que el filtro es por `estado == 'activa'`, no por existencia
    de cualquier reserva: una reserva cancelada no bloquea la baja
    definitiva."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    reserva = reservas_service.crear_reserva(
        db_session, _reserva_data(creado.id, _dt(0), _dt(2)), ip_origen=IP_TEST
    )
    reservas_service.cancelar_reserva(db_session, reserva.id, legajo="1234", ip_origen=IP_TEST)

    resultado = service.dar_de_baja_definitiva(db_session, creado.id)
    assert resultado.estado == EstadoVehiculo.baja_definitiva


def test_baja_vs_crear_reserva_concurrencia(test_database_url, monkeypatch):
    """AC-01/AC-02/R-01: una baja (temporal) y una creación de reserva
    concurrentes sobre el MISMO `vehiculo_id` comparten el mismo lock
    (`vehiculos_repository.obtener_por_id_con_lock`, `SELECT ... FOR UPDATE`
    sobre la fila del vehículo) — nunca terminan ambas operaciones en éxito.

    Mismo patrón que `test_crear_reserva_concurrencia_solo_una_confirmada`
    de `test_reservas_service.py`: dos conexiones reales (sin mocks del
    acceso a datos), un `threading.Barrier` para alinear el arranque de
    ambos hilos, y un monkeypatch de `obtener_por_id_con_lock` que retiene
    la transacción del PRIMER hilo en llegar 0.5s ADICIONALES sin comitear
    (tiempo de sobra para que el segundo hilo, si el lock real no lo
    bloqueó a nivel de Postgres, alcance a leer el mismo estado "sin
    reservas activas"/"vehículo activo" y también complete su operación). Si
    el lock funciona, el segundo hilo queda genuinamente bloqueado en
    Postgres en su propio `SELECT ... FOR UPDATE` hasta que el primero
    comitea, y entonces ve el estado ya actualizado por el primero."""
    import app.features.reservas.models
    import app.features.vehiculos.models  # noqa: F401
    from app.core.database import Base
    from app.features.vehiculos import repository as vehiculos_repository

    engine = create_engine(test_database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    setup_session = session_factory()
    vehiculo = service.crear_vehiculo(setup_session, VehiculoCreate(patente="AA123BB", tipo="auto"))
    vehiculo_id = vehiculo.id
    setup_session.close()

    inicio, fin = _dt(0), _dt(2)
    resultados = {}
    barrier = threading.Barrier(2)

    original_obtener_con_lock = vehiculos_repository.obtener_por_id_con_lock
    primer_llegada = threading.Event()
    primer_llegada_lock = threading.Lock()

    def _obtener_con_lock_con_retraso_al_primero(db, vehiculo_id_arg):
        resultado = original_obtener_con_lock(db, vehiculo_id_arg)
        with primer_llegada_lock:
            soy_el_primero = not primer_llegada.is_set()
            primer_llegada.set()
        if soy_el_primero:
            time.sleep(0.5)
        return resultado

    monkeypatch.setattr(
        vehiculos_repository,
        "obtener_por_id_con_lock",
        _obtener_con_lock_con_retraso_al_primero,
    )

    def intentar_baja():
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            service.dar_de_baja_temporal(session, vehiculo_id)
            resultados["baja"] = "ok"
        except VehiculoConReservasActivasError:
            resultados["baja"] = "rechazada"
        finally:
            session.close()

    def intentar_reservar():
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            data = _reserva_data(vehiculo_id, inicio, fin, legajo="C001", nombre_empleado="Concurrente")
            reservas_service.crear_reserva(session, data, ip_origen=IP_TEST)
            resultados["reserva"] = "ok"
        except VehiculoNoActivoError:
            resultados["reserva"] = "rechazada"
        finally:
            session.close()

    hilo_baja = threading.Thread(target=intentar_baja)
    hilo_reserva = threading.Thread(target=intentar_reservar)
    hilo_baja.start()
    hilo_reserva.start()
    hilo_baja.join(timeout=10)
    hilo_reserva.join(timeout=10)

    try:
        assert set(resultados.values()) == {"ok", "rechazada"}, resultados
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


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


def test_obtener_por_patente_normalizada_encuentra_por_cualquier_casing(db_session):
    """Block 1/FR-05: `obtener_por_patente_normalizada` es case-insensitive
    — busca con un casing distinto al guardado y encuentra el mismo
    vehículo."""
    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="AbC123", tipo="auto"))

    encontrado = repository.obtener_por_patente_normalizada(db_session, "ABC123")
    assert encontrado is not None
    assert encontrado.id == creado.id

    encontrado_minusculas = repository.obtener_por_patente_normalizada(db_session, "abc123")
    assert encontrado_minusculas is not None
    assert encontrado_minusculas.id == creado.id


def test_crear_vehiculo_rechaza_patente_duplicada_otro_casing(db_session):
    """AC-05: alta con patente que ya existe en el pool en otro casing se
    rechaza."""
    service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    with pytest.raises(PatenteYaExisteError):
        service.crear_vehiculo(db_session, VehiculoCreate(patente="aa123bb", tipo="camioneta"))


def test_modificar_vehiculo_rechaza_patente_duplicada_otro_casing(db_session):
    """AC-06: modificar asignando una patente que ya existe en otro vehículo
    en otro casing se rechaza."""
    service.crear_vehiculo(db_session, VehiculoCreate(patente="AA111AA", tipo="auto"))
    v2 = service.crear_vehiculo(db_session, VehiculoCreate(patente="BB222BB", tipo="camioneta"))

    with pytest.raises(PatenteYaExisteError):
        service.modificar_vehiculo(
            db_session, v2.id, VehiculoUpdate(patente="aa111aa", tipo="camioneta")
        )


def test_crear_vehiculo_patente_distinta_sigue_funcionando(db_session):
    """Regresión: una patente nueva, sin relación de casing con ninguna
    existente, sigue creando el vehículo normalmente."""
    service.crear_vehiculo(db_session, VehiculoCreate(patente="AA123BB", tipo="auto"))

    creado = service.crear_vehiculo(db_session, VehiculoCreate(patente="ZZ999ZZ", tipo="camioneta"))

    assert creado.id is not None
    assert creado.patente == "ZZ999ZZ"


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
