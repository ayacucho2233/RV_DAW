"""Tests de `app.features.reservas.service` (Block 2 de spec-FEAT-001c).

Cada test referencia el AC del PRD que cubre (docs/daw/prd/prd-FEAT-001c.md) o
la mitigación del threat model (docs/daw/security/threat-FEAT-001c.md) que
cubre. Corren contra la base de datos de test real (fixture `db_session` de
`conftest.py`), no contra mocks: la capa que se ejercita incluye
`repository.py`, así que también sirve como evidencia del `SELECT FOR UPDATE`
(mitigación NFR-03/AC-06).
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.features.reservas import repository
from app.features.reservas.exceptions import (
    ReservaSolapadaError,
    VehiculoNoActivoError,
    VehiculoNoEncontradoError,
)
from app.features.reservas.schemas import ReservaCreate
from app.features.reservas.service import (
    consultar_disponibilidad,
    crear_reserva,
    listar_vehiculos_pool,
)
from app.features.vehiculos import repository as vehiculos_repository
from app.features.vehiculos.models import EstadoVehiculo
from app.features.vehiculos.schemas import VehiculoCreate

IP_TEST = "10.0.0.1"


def _crear_vehiculo(db, patente="AA123BB", tipo="auto"):
    return vehiculos_repository.crear(db, VehiculoCreate(patente=patente, tipo=tipo))


def _reserva_data(vehiculo_id, inicio, fin, **overrides):
    base = dict(
        nombre_empleado="Juan Perez",
        legajo="1234",
        licencia="B1",
        vehiculo_id=vehiculo_id,
        fecha_inicio=inicio,
        fecha_fin=fin,
        destino="Rosario",
    )
    base.update(overrides)
    return ReservaCreate(**base)


def _dt(offset_hours=0):
    """Datetime timezone-aware, offset en horas desde un punto fijo futuro."""
    base = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    return base + timedelta(hours=offset_hours)


def test_listar_vehiculos_pool(db_session):
    """AC-01: el listado público expone solo patente/tipo (no `estado`)."""
    _crear_vehiculo(db_session, patente="AA111AA", tipo="auto")
    _crear_vehiculo(db_session, patente="BB222BB", tipo="camioneta")

    resultado = listar_vehiculos_pool(db_session)

    assert len(resultado) == 2
    for vehiculo in resultado:
        assert hasattr(vehiculo, "patente")
        assert hasattr(vehiculo, "tipo")
        assert not hasattr(vehiculo, "estado")
    assert {v.patente for v in resultado} == {"AA111AA", "BB222BB"}


def test_crear_reserva_ok(db_session):
    """AC-02: alta con vehículo disponible y campos completos se confirma."""
    vehiculo = _crear_vehiculo(db_session)
    data = _reserva_data(vehiculo.id, _dt(0), _dt(2))

    reserva = crear_reserva(db_session, data, ip_origen=IP_TEST)

    assert reserva.id is not None
    assert reserva.vehiculo_id == vehiculo.id
    assert reserva.estado.value == "activa"


def test_crear_reserva_vehiculo_inexistente(db_session):
    """404 de dominio: vehiculo_id que no existe en el pool."""
    data = _reserva_data(9999, _dt(0), _dt(2))

    with pytest.raises(VehiculoNoEncontradoError):
        crear_reserva(db_session, data, ip_origen=IP_TEST)


def test_crear_reserva_vehiculo_no_activo(db_session):
    """AC-08: un vehículo en baja_temporal no puede reservarse."""
    vehiculo = _crear_vehiculo(db_session)
    vehiculo.estado = EstadoVehiculo.baja_temporal
    vehiculos_repository.guardar(db_session, vehiculo)

    data = _reserva_data(vehiculo.id, _dt(0), _dt(2))

    with pytest.raises(VehiculoNoActivoError):
        crear_reserva(db_session, data, ip_origen=IP_TEST)


def test_reserva_create_rechaza_fecha_fin_menor_o_igual():
    """AC-04: `fecha_fin <= fecha_inicio` se rechaza a nivel de schema."""
    inicio = _dt(2)
    with pytest.raises(ValidationError):
        ReservaCreate(
            nombre_empleado="Juan Perez",
            legajo="1234",
            licencia="B1",
            vehiculo_id=1,
            fecha_inicio=inicio,
            fecha_fin=inicio,
            destino="Rosario",
        )

    with pytest.raises(ValidationError):
        ReservaCreate(
            nombre_empleado="Juan Perez",
            legajo="1234",
            licencia="B1",
            vehiculo_id=1,
            fecha_inicio=inicio,
            fecha_fin=inicio - timedelta(hours=1),
            destino="Rosario",
        )


def test_reserva_create_rechaza_fecha_naive():
    """TM-C-03: datetimes sin timezone se rechazan explícitamente."""
    naive_inicio = datetime(2026, 9, 1, 10, 0)
    naive_fin = datetime(2026, 9, 1, 12, 0)

    with pytest.raises(ValidationError):
        ReservaCreate(
            nombre_empleado="Juan Perez",
            legajo="1234",
            licencia="B1",
            vehiculo_id=1,
            fecha_inicio=naive_inicio,
            fecha_fin=_dt(2),
            destino="Rosario",
        )

    with pytest.raises(ValidationError):
        ReservaCreate(
            nombre_empleado="Juan Perez",
            legajo="1234",
            licencia="B1",
            vehiculo_id=1,
            fecha_inicio=_dt(0),
            fecha_fin=naive_fin,
            destino="Rosario",
        )


def test_crear_reserva_solapada_rechazada(db_session):
    """AC-05: una segunda reserva sobre el mismo vehículo con período que se
    cruza con una reserva activa existente se rechaza."""
    vehiculo = _crear_vehiculo(db_session)
    crear_reserva(db_session, _reserva_data(vehiculo.id, _dt(0), _dt(4)), ip_origen=IP_TEST)

    solapada = _reserva_data(vehiculo.id, _dt(2), _dt(6))
    with pytest.raises(ReservaSolapadaError):
        crear_reserva(db_session, solapada, ip_origen=IP_TEST)


def test_crear_reserva_periodos_no_solapados_ok(db_session):
    """Dos reservas disjuntas del mismo vehículo se crean ambas (evita falso
    positivo del chequeo de solapamiento)."""
    vehiculo = _crear_vehiculo(db_session)
    r1 = crear_reserva(db_session, _reserva_data(vehiculo.id, _dt(0), _dt(2)), ip_origen=IP_TEST)
    r2 = crear_reserva(db_session, _reserva_data(vehiculo.id, _dt(2), _dt(4)), ip_origen=IP_TEST)

    assert r1.id != r2.id


def test_crear_reserva_concurrencia_solo_una_confirmada(test_database_url, monkeypatch):
    """AC-06/NFR-03: dos altas concurrentes para el mismo vehículo y período
    solapado; el lock (`vehiculos_repository.obtener_por_id_con_lock`,
    `SELECT ... FOR UPDATE` sobre la fila del vehículo) serializa el acceso
    y solo una persiste.

    Usa dos sesiones/conexiones independientes (una por thread) contra la
    misma base de datos de test real, SIN mocks del acceso a datos. Un
    `threading.Barrier` sincroniza el arranque de ambos hilos, pero eso solo
    alinea el inicio de la función — no fuerza el interleaving real del
    punto crítico. Para forzarlo de verdad, se envuelve
    `repository.listar_activas_solapadas_con_lock` (paso que ambos hilos
    ejecutan siempre, sin importar el mecanismo de lock usado antes) de modo
    que el PRIMER hilo en completar esa consulta se queda 0.5s ADICIONALES
    sosteniendo su transacción abierta (sin commitear) antes de continuar —
    tiempo de sobra para que el segundo hilo, si el lock real que precede a
    este paso no lo bloqueó a nivel de Postgres, alcance a leer el mismo
    estado "vacío" y a insertar también. Si el lock del vehículo (fix)
    funciona, el segundo hilo queda genuinamente bloqueado en Postgres
    ANTES de llegar siquiera a este punto, y solo lo alcanza después de que
    el primero ya comiteó — viendo entonces la reserva ya creada y
    rechazando la propia por solapamiento.
    """
    import app.features.reservas.models  # noqa: F401
    import app.features.vehiculos.models  # noqa: F401
    from app.core.database import Base

    engine = create_engine(test_database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    setup_session = session_factory()
    vehiculo = _crear_vehiculo(setup_session)
    vehiculo_id = vehiculo.id
    setup_session.close()

    inicio, fin = _dt(0), _dt(2)
    resultados = {}
    barrier = threading.Barrier(2)

    original_listar_solapadas = repository.listar_activas_solapadas_con_lock
    primer_llegada = threading.Event()
    primer_llegada_lock = threading.Lock()

    def _listar_solapadas_con_retraso_al_primero(db, vehiculo_id_arg, fecha_inicio_arg, fecha_fin_arg):
        resultado = original_listar_solapadas(db, vehiculo_id_arg, fecha_inicio_arg, fecha_fin_arg)
        with primer_llegada_lock:
            soy_el_primero = not primer_llegada.is_set()
            primer_llegada.set()
        if soy_el_primero:
            # Sostiene la transacción abierta (sin commitear) el tiempo
            # suficiente para que, si el segundo hilo no está genuinamente
            # bloqueado a nivel de Postgres, alcance a leer el mismo estado
            # "sin solapamiento" y también inserte.
            time.sleep(0.5)
        return resultado

    monkeypatch.setattr(
        repository, "listar_activas_solapadas_con_lock", _listar_solapadas_con_retraso_al_primero
    )

    def intentar_reservar(nombre_legajo: str):
        session = session_factory()
        try:
            barrier.wait(timeout=5)
            data = _reserva_data(
                vehiculo_id, inicio, fin, legajo=nombre_legajo, nombre_empleado="Concurrente"
            )
            crear_reserva(session, data, ip_origen=IP_TEST)
            resultados[nombre_legajo] = "ok"
        except ReservaSolapadaError:
            resultados[nombre_legajo] = "rechazada"
        finally:
            session.close()

    hilo_a = threading.Thread(target=intentar_reservar, args=("A001",))
    hilo_b = threading.Thread(target=intentar_reservar, args=("B002",))
    hilo_a.start()
    hilo_b.start()
    hilo_a.join(timeout=10)
    hilo_b.join(timeout=10)

    try:
        assert set(resultados.values()) == {"ok", "rechazada"}, resultados

        verificacion = session_factory()
        try:
            from app.features.reservas.models import Reserva

            activas = (
                verificacion.query(Reserva)
                .filter(Reserva.vehiculo_id == vehiculo_id, Reserva.estado == "activa")
                .all()
            )
            assert len(activas) == 1, (
                f"se esperaba exactamente 1 reserva activa persistida, hay {len(activas)}"
            )
        finally:
            verificacion.close()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_consultar_disponibilidad(db_session):
    """AC-07: un vehículo con reserva solapando el rango consultado aparece
    `disponible=False`; uno sin solapamiento, `disponible=True`."""
    ocupado = _crear_vehiculo(db_session, patente="AA111AA", tipo="auto")
    libre = _crear_vehiculo(db_session, patente="BB222BB", tipo="camioneta")

    crear_reserva(db_session, _reserva_data(ocupado.id, _dt(0), _dt(4)), ip_origen=IP_TEST)

    resultado = consultar_disponibilidad(db_session, _dt(1), _dt(3))

    por_id = {r.vehiculo_id: r for r in resultado}
    assert por_id[ocupado.id].disponible is False
    assert por_id[libre.id].disponible is True
    assert por_id[ocupado.id].patente == "AA111AA"


def test_crear_reserva_loguea_operacion_sin_pii(db_session, caplog):
    """TM-C-04: el log de `crear_reserva` incluye vehiculo_id/legajo/
    resultado/ip_origen y NUNCA nombre_empleado ni licencia."""
    vehiculo = _crear_vehiculo(db_session)
    data = _reserva_data(
        vehiculo.id,
        _dt(0),
        _dt(2),
        nombre_empleado="Nombre Secreto Unico",
        licencia="LICENCIA-SECRETA",
        legajo="9999",
    )

    with caplog.at_level(logging.INFO, logger="app.features.reservas.service"):
        crear_reserva(db_session, data, ip_origen=IP_TEST)

    mensajes = [r.getMessage() for r in caplog.records]
    assert any(
        "crear_reserva" in m
        and str(vehiculo.id) in m
        and "9999" in m
        and IP_TEST in m
        and "ok" in m
        for m in mensajes
    )
    assert not any("Nombre Secreto Unico" in m for m in mensajes)
    assert not any("LICENCIA-SECRETA" in m for m in mensajes)
