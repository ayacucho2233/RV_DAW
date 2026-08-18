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
    LegajoNoCoincideError,
    ReservaNoEncontradaError,
    ReservaSolapadaError,
    ReservaYaCanceladaError,
    VehiculoNoActivoError,
    VehiculoNoEncontradoError,
)
from app.features.reservas.models import EstadoReserva
from app.features.reservas.schemas import ReservaCreate
from app.features.reservas.service import (
    cancelar_reserva,
    caducar_reservas_vencidas,
    consultar_disponibilidad,
    consultar_reservas_activas_por_patente,
    crear_reserva,
    listar_reservas,
    listar_vehiculos_pool,
)
from app.features.vehiculos import repository as vehiculos_repository
from app.features.vehiculos.models import EstadoVehiculo
from app.features.vehiculos.schemas import VehiculoCreate

IP_TEST = "10.0.0.1"


def _crear_vehiculo(db, patente="AA123BB", tipo="auto"):
    return vehiculos_repository.crear(db, VehiculoCreate(patente=patente, tipo=tipo))


def _reserva_data(vehiculo_id, inicio, fin, **overrides):
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


def _dt(offset_hours=0):
    """Datetime timezone-aware, offset en horas desde un punto fijo futuro."""
    base = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    return base + timedelta(hours=offset_hours)


def _dt_real(offset_hours=0):
    """Datetime timezone-aware relativo al momento real de ejecución del
    test (a diferencia de `_dt`, fijo en 2026-09-01) — necesario para los
    tests de filtro por período, que comparan contra
    `datetime.now(timezone.utc)`."""
    return datetime.now(timezone.utc) + timedelta(hours=offset_hours)


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
    # Naive a propósito: el test verifica que la app rechace datetimes sin
    # timezone, así que agregarles tzinfo anularía lo que se está probando.
    naive_inicio = datetime(2026, 9, 1, 10, 0)  # noqa: DTZ001
    naive_fin = datetime(2026, 9, 1, 12, 0)  # noqa: DTZ001

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
    import app.features.reservas.models
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


# --- Block 1 de spec-FEAT-001d: listado, filtros y cancelación ---


def test_listar_reservas_sin_filtro(db_session):
    """AC-01: devuelve todas las reservas existentes, enriquecidas con
    patente/tipo del vehículo asociado."""
    v1 = _crear_vehiculo(db_session, patente="AA111AA", tipo="auto")
    v2 = _crear_vehiculo(db_session, patente="BB222BB", tipo="camioneta")
    crear_reserva(db_session, _reserva_data(v1.id, _dt(0), _dt(2)), ip_origen=IP_TEST)
    crear_reserva(db_session, _reserva_data(v2.id, _dt(4), _dt(6)), ip_origen=IP_TEST)

    resultado = listar_reservas(db_session)

    assert len(resultado) == 2
    por_vehiculo = {r.vehiculo_id: r for r in resultado}
    assert por_vehiculo[v1.id].patente == "AA111AA"
    assert por_vehiculo[v1.id].tipo.value == "auto"
    assert por_vehiculo[v2.id].patente == "BB222BB"


def test_listar_reservas_filtro_futuras(db_session):
    """AC-02: solo devuelve reservas cuya `fecha_inicio` es posterior a
    ahora."""
    v_futura = _crear_vehiculo(db_session, patente="FU111TU", tipo="auto")
    v_pasada = _crear_vehiculo(db_session, patente="PA222SA", tipo="auto")
    crear_reserva(
        db_session, _reserva_data(v_futura.id, _dt_real(2), _dt_real(4)), ip_origen=IP_TEST
    )
    crear_reserva(
        db_session, _reserva_data(v_pasada.id, _dt_real(-4), _dt_real(-2)), ip_origen=IP_TEST
    )

    resultado = listar_reservas(db_session, periodo="futuras")

    assert {r.vehiculo_id for r in resultado} == {v_futura.id}


def test_listar_reservas_filtro_en_curso(db_session):
    """AC-03: solo devuelve reservas donde `fecha_inicio <= ahora <=
    fecha_fin`."""
    v_en_curso = _crear_vehiculo(db_session, patente="EC111EC", tipo="auto")
    v_futura = _crear_vehiculo(db_session, patente="FU222TU", tipo="auto")
    crear_reserva(
        db_session, _reserva_data(v_en_curso.id, _dt_real(-1), _dt_real(1)), ip_origen=IP_TEST
    )
    crear_reserva(
        db_session, _reserva_data(v_futura.id, _dt_real(2), _dt_real(4)), ip_origen=IP_TEST
    )

    resultado = listar_reservas(db_session, periodo="en_curso")

    assert {r.vehiculo_id for r in resultado} == {v_en_curso.id}


def test_listar_reservas_filtro_pasadas(db_session):
    """AC-04: solo devuelve reservas cuya `fecha_fin` es anterior a ahora."""
    v_pasada = _crear_vehiculo(db_session, patente="PA333SA", tipo="auto")
    v_futura = _crear_vehiculo(db_session, patente="FU333TU", tipo="auto")
    crear_reserva(
        db_session, _reserva_data(v_pasada.id, _dt_real(-4), _dt_real(-2)), ip_origen=IP_TEST
    )
    crear_reserva(
        db_session, _reserva_data(v_futura.id, _dt_real(2), _dt_real(4)), ip_origen=IP_TEST
    )

    resultado = listar_reservas(db_session, periodo="pasadas")

    assert {r.vehiculo_id for r in resultado} == {v_pasada.id}


def test_listar_reservas_filtro_incluye_canceladas_en_su_periodo(db_session):
    """Confirma que el filtro por período es puramente temporal: una
    reserva cancelada que cae en el rango futuro sigue apareciendo como
    'futura' (no se filtra por `estado`), evitando un falso supuesto."""
    vehiculo = _crear_vehiculo(db_session, patente="CA111CA", tipo="auto")
    reserva = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(2), _dt_real(4)), ip_origen=IP_TEST
    )
    cancelar_reserva(db_session, reserva.id, legajo="1234", ip_origen=IP_TEST)

    resultado = listar_reservas(db_session, periodo="futuras")

    assert len(resultado) == 1
    assert resultado[0].estado.value == "cancelada"


def test_listar_reservas_no_expone_legajo_ni_licencia(db_session):
    """TM-D-01: `ReservaListItem` no expone `legajo` ni `licencia` aunque la
    `Reserva` origen sí los tenga (evita que el listado público se
    convierta en un oráculo que anule la protección de AC-06)."""
    vehiculo = _crear_vehiculo(db_session)
    crear_reserva(
        db_session,
        _reserva_data(vehiculo.id, _dt(0), _dt(2), legajo="5555", licencia="B2"),
        ip_origen=IP_TEST,
    )

    resultado = listar_reservas(db_session)

    assert len(resultado) == 1
    assert not hasattr(resultado[0], "legajo")
    assert not hasattr(resultado[0], "licencia")


def test_cancelar_reserva_ok(db_session):
    """AC-05: cancelar una reserva activa pasa su `estado` a `cancelada`."""
    vehiculo = _crear_vehiculo(db_session)
    reserva = crear_reserva(db_session, _reserva_data(vehiculo.id, _dt(0), _dt(2)), ip_origen=IP_TEST)

    resultado = cancelar_reserva(db_session, reserva.id, legajo="1234", ip_origen=IP_TEST)

    assert resultado.estado.value == "cancelada"


def test_cancelar_reserva_libera_vehiculo(db_session):
    """AC-05: tras cancelar, una nueva reserva solapada sobre el mismo
    vehículo/período ya no choca contra `ReservaSolapadaError` (el chequeo
    de solapamiento solo considera reservas `activa`)."""
    vehiculo = _crear_vehiculo(db_session)
    reserva = crear_reserva(db_session, _reserva_data(vehiculo.id, _dt(0), _dt(4)), ip_origen=IP_TEST)

    cancelar_reserva(db_session, reserva.id, legajo="1234", ip_origen=IP_TEST)

    nueva = crear_reserva(db_session, _reserva_data(vehiculo.id, _dt(1), _dt(3)), ip_origen=IP_TEST)
    assert nueva.id is not None


def test_cancelar_reserva_inexistente(db_session):
    """404 de dominio: `reserva_id` que no existe."""
    with pytest.raises(ReservaNoEncontradaError):
        cancelar_reserva(db_session, 9999, legajo="1234", ip_origen=IP_TEST)


def test_cancelar_reserva_ya_cancelada(db_session):
    """409: cancelar una reserva ya cancelada se rechaza explícitamente, no
    se responde éxito idempotente (decisión de diseño confirmada en PLAN)."""
    vehiculo = _crear_vehiculo(db_session)
    reserva = crear_reserva(db_session, _reserva_data(vehiculo.id, _dt(0), _dt(2)), ip_origen=IP_TEST)
    cancelar_reserva(db_session, reserva.id, legajo="1234", ip_origen=IP_TEST)

    with pytest.raises(ReservaYaCanceladaError):
        cancelar_reserva(db_session, reserva.id, legajo="1234", ip_origen=IP_TEST)


def test_cancelar_reserva_legajo_no_coincide(db_session):
    """AC-06: el `legajo` indicado debe coincidir con el de la reserva; el
    mensaje de error no revela el legajo real (evita filtrar el dato por el
    camino de un mensaje de error)."""
    vehiculo = _crear_vehiculo(db_session)
    reserva = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt(0), _dt(2), legajo="1234"), ip_origen=IP_TEST
    )

    with pytest.raises(LegajoNoCoincideError) as excinfo:
        cancelar_reserva(db_session, reserva.id, legajo="9999", ip_origen=IP_TEST)

    assert "1234" not in str(excinfo.value)


def test_cancelar_reserva_loguea_operacion_sin_pii(db_session, caplog):
    """TM-C-04: el log de `cancelar_reserva` incluye vehiculo_id/legajo/
    resultado/ip_origen y NUNCA nombre_empleado ni licencia (mismo criterio
    que `crear_reserva`)."""
    vehiculo = _crear_vehiculo(db_session)
    reserva = crear_reserva(
        db_session,
        _reserva_data(
            vehiculo.id,
            _dt(0),
            _dt(2),
            nombre_empleado="Nombre Secreto Unico",
            licencia="LICENCIA-SECRETA",
            legajo="7777",
        ),
        ip_origen=IP_TEST,
    )
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="app.features.reservas.service"):
        cancelar_reserva(db_session, reserva.id, legajo="7777", ip_origen=IP_TEST)

    mensajes = [r.getMessage() for r in caplog.records]
    assert any(
        "cancelar_reserva" in m
        and str(vehiculo.id) in m
        and "7777" in m
        and IP_TEST in m
        and "ok" in m
        for m in mensajes
    )
    assert not any("Nombre Secreto Unico" in m for m in mensajes)
    assert not any("LICENCIA-SECRETA" in m for m in mensajes)


# --- Block 2 de spec-FEAT-001e: reservas pasadas de vehículos dados de baja ---


def test_listar_reservas_incluye_reserva_de_vehiculo_en_baja_temporal(db_session):
    """AC-03: una reserva pasada (`fecha_fin` en el pasado) de un vehículo en
    `baja_temporal` sigue apareciendo en `listar_reservas`, sin filtro y con
    `periodo='pasadas'`. El vehículo se pasa a `baja_temporal` mutando el
    modelo directamente (no vía `vehiculos_service.dar_de_baja_temporal`) para
    no acoplar este test a la validación de reservas activas de Block 1 — acá
    solo importa el estado final del vehículo, no cómo se llegó a él."""
    vehiculo = _crear_vehiculo(db_session, patente="BT111BT", tipo="auto")
    crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(-4), _dt_real(-2)), ip_origen=IP_TEST
    )
    vehiculo.estado = EstadoVehiculo.baja_temporal
    vehiculos_repository.guardar(db_session, vehiculo)

    sin_filtro = listar_reservas(db_session)
    pasadas = listar_reservas(db_session, periodo="pasadas")

    assert {r.vehiculo_id for r in sin_filtro} == {vehiculo.id}
    assert {r.vehiculo_id for r in pasadas} == {vehiculo.id}
    assert pasadas[0].patente == "BT111BT"
    assert pasadas[0].tipo.value == "auto"


def test_listar_reservas_incluye_reserva_de_vehiculo_en_baja_definitiva(db_session):
    """AC-04: ídem `test_listar_reservas_incluye_reserva_de_vehiculo_en_baja_temporal`
    pero para `baja_definitiva`."""
    vehiculo = _crear_vehiculo(db_session, patente="BD222BD", tipo="camioneta")
    crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(-6), _dt_real(-3)), ip_origen=IP_TEST
    )
    vehiculo.estado = EstadoVehiculo.baja_definitiva
    vehiculos_repository.guardar(db_session, vehiculo)

    sin_filtro = listar_reservas(db_session)
    pasadas = listar_reservas(db_session, periodo="pasadas")

    assert {r.vehiculo_id for r in sin_filtro} == {vehiculo.id}
    assert {r.vehiculo_id for r in pasadas} == {vehiculo.id}
    assert pasadas[0].patente == "BD222BD"
    assert pasadas[0].tipo.value == "camioneta"


def test_cancelar_reserva_legajo_no_coincide_loguea_rechazada(db_session, caplog):
    """TM-D-03/TM-D-04: un rechazo por `LegajoNoCoincideError` (alguien
    probando legajos al azar para cancelar la reserva de otro) también debe
    quedar logueado con `resultado="rechazada"` — mismo criterio que
    `crear_reserva` ya aplica en su propio `except`. Sin esto no queda
    ningún rastro de un intento de fuerza bruta sobre el legajo."""
    vehiculo = _crear_vehiculo(db_session)
    reserva = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt(0), _dt(2), legajo="1234"), ip_origen=IP_TEST
    )
    caplog.clear()

    with (
        caplog.at_level(logging.INFO, logger="app.features.reservas.service"),
        pytest.raises(LegajoNoCoincideError),
    ):
        cancelar_reserva(db_session, reserva.id, legajo="9999", ip_origen=IP_TEST)

    mensajes = [r.getMessage() for r in caplog.records]
    assert any(
        "cancelar_reserva" in m
        and str(vehiculo.id) in m
        and "9999" in m
        and IP_TEST in m
        and "rechazada" in m
        for m in mensajes
    )


# --- Block 2 de spec-FEAT-004: consulta de reservas activas por patente ---


def test_consultar_reservas_activas_por_patente_con_activas(db_session):
    """AC-01: patente con reservas activas devuelve exactamente esas
    reservas."""
    vehiculo = _crear_vehiculo(db_session, patente="AC111AC", tipo="auto")
    reserva = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(2), _dt_real(4)), ip_origen=IP_TEST
    )

    resultado = consultar_reservas_activas_por_patente(db_session, "AC111AC")

    assert len(resultado) == 1
    assert resultado[0].id == reserva.id
    assert resultado[0].vehiculo_id == vehiculo.id


def test_consultar_reservas_activas_por_patente_sin_activas(db_session):
    """AC-02: patente sin reservas activas devuelve una lista vacía, no un
    error."""
    _crear_vehiculo(db_session, patente="SA222SA", tipo="auto")

    resultado = consultar_reservas_activas_por_patente(db_session, "SA222SA")

    assert resultado == []


def test_consultar_reservas_activas_por_patente_excluye_pasadas_y_canceladas(db_session):
    """AC-02: una reserva pasada y otra cancelada (ambas fuera de la ventana
    'activa') no aparecen en el resultado."""
    vehiculo = _crear_vehiculo(db_session, patente="EX333EX", tipo="auto")
    crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(-4), _dt_real(-2)), ip_origen=IP_TEST
    )
    reserva_cancelada = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(2), _dt_real(4)), ip_origen=IP_TEST
    )
    cancelar_reserva(db_session, reserva_cancelada.id, legajo="1234", ip_origen=IP_TEST)

    resultado = consultar_reservas_activas_por_patente(db_session, "EX333EX")

    assert resultado == []


def test_consultar_reservas_activas_por_patente_incluye_campos_requeridos(db_session):
    """AC-04: cada ítem trae nombre del empleado, fecha_inicio, fecha_fin y
    destino."""
    vehiculo = _crear_vehiculo(db_session, patente="CR444CR", tipo="auto")
    crear_reserva(
        db_session,
        _reserva_data(
            vehiculo.id, _dt_real(2), _dt_real(4), nombre_empleado="Ana Gomez", destino="Cordoba"
        ),
        ip_origen=IP_TEST,
    )

    resultado = consultar_reservas_activas_por_patente(db_session, "CR444CR")

    assert len(resultado) == 1
    item = resultado[0]
    assert item.nombre_empleado == "Ana Gomez"
    assert item.fecha_inicio is not None
    assert item.fecha_fin is not None
    assert item.destino == "Cordoba"


def test_consultar_reservas_activas_patente_inexistente(db_session):
    """AC-03: patente que no existe en el pool levanta
    VehiculoNoEncontradoError."""
    with pytest.raises(VehiculoNoEncontradoError):
        consultar_reservas_activas_por_patente(db_session, "ZZ999ZZ")


def test_consultar_reservas_activas_patente_case_insensitive(db_session):
    """AC-01/AC-02 + FR-05: consultar con un casing distinto al guardado
    igual encuentra el vehículo (usa Block 1)."""
    vehiculo = _crear_vehiculo(db_session, patente="CI555CI", tipo="auto")
    reserva = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(2), _dt_real(4)), ip_origen=IP_TEST
    )

    resultado = consultar_reservas_activas_por_patente(db_session, "ci555ci")

    assert len(resultado) == 1
    assert resultado[0].id == reserva.id


# --- Block 2 de spec-FEAT-005: caducar reservas vencidas ---


def test_caducar_vencidas_transiciona_activa_vencida_a_caducada(db_session):
    """AC-01: una reserva `activa` con `fecha_fin` estrictamente en el
    pasado pasa a `caducada`."""
    vehiculo = _crear_vehiculo(db_session)
    reserva = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(-4), _dt_real(-2)), ip_origen=IP_TEST
    )

    caducadas = repository.caducar_vencidas(db_session, datetime.now(timezone.utc))

    db_session.refresh(reserva)
    assert caducadas == 1
    assert reserva.estado == EstadoReserva.caducada


def test_caducar_vencidas_no_toca_activa_vigente(db_session):
    """AC-02: una reserva `activa` con `fecha_fin >= ahora` permanece
    `activa`."""
    vehiculo = _crear_vehiculo(db_session)
    reserva = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(2), _dt_real(4)), ip_origen=IP_TEST
    )

    caducadas = repository.caducar_vencidas(db_session, datetime.now(timezone.utc))

    db_session.refresh(reserva)
    assert caducadas == 0
    assert reserva.estado == EstadoReserva.activa


def test_caducar_vencidas_no_toca_ya_cancelada_ni_ya_caducada(db_session):
    """Idempotencia: reservas que ya están en `cancelada`/`caducada` no se
    tocan ni se cuentan de nuevo."""
    vehiculo = _crear_vehiculo(db_session, patente="CC111CC")
    reserva_cancelada = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(-4), _dt_real(-2)), ip_origen=IP_TEST
    )
    cancelar_reserva(db_session, reserva_cancelada.id, legajo="1234", ip_origen=IP_TEST)

    vehiculo2 = _crear_vehiculo(db_session, patente="CC222CC")
    reserva_ya_caducada = crear_reserva(
        db_session, _reserva_data(vehiculo2.id, _dt_real(-8), _dt_real(-6)), ip_origen=IP_TEST
    )
    reserva_ya_caducada.estado = EstadoReserva.caducada
    repository.guardar(db_session, reserva_ya_caducada)

    caducadas = repository.caducar_vencidas(db_session, datetime.now(timezone.utc))

    db_session.refresh(reserva_cancelada)
    db_session.refresh(reserva_ya_caducada)
    assert caducadas == 0
    assert reserva_cancelada.estado == EstadoReserva.cancelada
    assert reserva_ya_caducada.estado == EstadoReserva.caducada


def test_caducar_vencidas_devuelve_cantidad_correcta(db_session):
    """El `int` devuelto coincide con la cantidad real de filas
    transicionadas: dos vencidas y una vigente, solo cuenta las dos."""
    v1 = _crear_vehiculo(db_session, patente="CT111CT")
    v2 = _crear_vehiculo(db_session, patente="CT222CT")
    v3 = _crear_vehiculo(db_session, patente="CT333CT")
    crear_reserva(db_session, _reserva_data(v1.id, _dt_real(-6), _dt_real(-4)), ip_origen=IP_TEST)
    crear_reserva(db_session, _reserva_data(v2.id, _dt_real(-4), _dt_real(-2)), ip_origen=IP_TEST)
    crear_reserva(db_session, _reserva_data(v3.id, _dt_real(2), _dt_real(4)), ip_origen=IP_TEST)

    caducadas = repository.caducar_vencidas(db_session, datetime.now(timezone.utc))

    assert caducadas == 2


def test_caducar_reservas_vencidas_loguea_operacion(db_session, caplog):
    """El log de `caducar_reservas_vencidas` incluye `operacion=
    caducar_vencidas` y el `count` correcto, sin `legajo` ni
    `nombre_empleado` (operación masiva, no aplica PII por reserva)."""
    vehiculo = _crear_vehiculo(db_session)
    crear_reserva(
        db_session,
        _reserva_data(
            vehiculo.id, _dt_real(-4), _dt_real(-2), nombre_empleado="Nombre Secreto Unico"
        ),
        ip_origen=IP_TEST,
    )
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="app.features.reservas.service"):
        resultado = caducar_reservas_vencidas(db_session, ip_origen=IP_TEST)

    assert resultado == 1
    mensajes = [r.getMessage() for r in caplog.records]
    assert any(
        "operacion=caducar_vencidas" in m and "count=1" in m and IP_TEST in m for m in mensajes
    )
    assert not any("legajo" in m for m in mensajes)
    assert not any("Nombre Secreto Unico" in m for m in mensajes)


def test_cancelar_reserva_caducada_rechaza_con_mismo_error_que_cancelada(db_session):
    """AC-05: regresión sobre `cancelar_reserva` (sin cambiar su código)
    confirmando que una reserva `caducada` dispara `ReservaYaCanceladaError`
    igual que una `cancelada`."""
    vehiculo = _crear_vehiculo(db_session)
    reserva = crear_reserva(
        db_session, _reserva_data(vehiculo.id, _dt_real(-4), _dt_real(-2)), ip_origen=IP_TEST
    )
    repository.caducar_vencidas(db_session, datetime.now(timezone.utc))

    with pytest.raises(ReservaYaCanceladaError):
        cancelar_reserva(db_session, reserva.id, legajo="1234", ip_origen=IP_TEST)
