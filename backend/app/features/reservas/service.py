"""Lógica de negocio del feature `reservas`.

Capa intermedia entre `router.py` (Block 3, todavía no existe) y
`repository.py`: acá vive la prevención de solapamientos (FR-03/AC-05,
NFR-03/AC-06) y el rechazo de reservas sobre vehículos no activos
(FR-05/AC-08). Nunca accede a la base directamente — todo pasa por
`repository.py` (AGENTS.md: "Layer separation").

`listar_vehiculos_pool`/`crear_reserva`/`consultar_disponibilidad` importan
`app.features.vehiculos.repository` y `app.features.vehiculos.models` en
modo de solo lectura (dependencia D-01 del PRD): nunca escriben sobre las
tablas de `vehiculos`.
"""
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.features.reservas import repository
from app.features.reservas.exceptions import (
    LegajoNoCoincideError,
    PatenteFormatoInvalidoError,
    ReservaDomainError,
    ReservaNoEncontradaError,
    ReservaSolapadaError,
    ReservaYaCanceladaError,
    VehiculoNoActivoError,
    VehiculoNoEncontradoError,
)
from app.features.reservas.models import EstadoReserva, Reserva
from app.features.reservas.schemas import (
    DisponibilidadOut,
    FiltroPeriodoReserva,
    ReservaListItem,
    VehiculoPublico,
)
from app.features.vehiculos import repository as vehiculos_repository
from app.features.vehiculos.models import EstadoVehiculo
from app.features.vehiculos.schemas import PATENTE_PATTERN

_PATENTE_REGEX = re.compile(PATENTE_PATTERN)

logger = logging.getLogger(__name__)


def _log_operacion(
    operacion: str, vehiculo_id: int | None, legajo: str | None, resultado: str, ip_origen: str
) -> None:
    """Log de trazabilidad de operaciones del feature (mitigación TM-C-04
    del threat model). Sin autenticación en este feature, es el único
    rastro disponible para investigar abusos o disputas. **Nunca** debe
    recibir `nombre_empleado` ni `licencia` — reduce la superficie de PII en
    los logs a lo estrictamente necesario para trazabilidad operativa.
    """
    logger.info(
        "operacion=%s vehiculo_id=%s legajo=%s resultado=%s ip_origen=%s timestamp=%s",
        operacion,
        vehiculo_id,
        legajo,
        resultado,
        ip_origen,
        datetime.now(timezone.utc).isoformat(),
    )


def listar_vehiculos_pool(db: Session) -> list[VehiculoPublico]:
    """FR-01: listado público del pool, proyectado a solo patente/tipo."""
    vehiculos = vehiculos_repository.listar(db)
    return [VehiculoPublico.model_validate(v) for v in vehiculos]


def crear_reserva(db: Session, data, ip_origen: str) -> Reserva:
    """FR-02: alta de una reserva.

    (1) `SELECT FOR UPDATE` sobre la fila del vehículo: existe siempre que
    `vehiculo_id` sea válido, así que este lock SIEMPRE se toma (a
    diferencia de lockear reservas solapadas, que pueden no tener ninguna
    fila previa — "phantom row": un `SELECT ... FOR UPDATE` que devuelve 0
    filas no bloquea nada). `None` → `VehiculoNoEncontradoError`. A partir
    de acá, cualquier otra transacción concurrente que intente
    `crear_reserva` sobre el MISMO `vehiculo_id` queda bloqueada en este
    mismo `SELECT FOR UPDATE` hasta que esta termine (commit o rollback).
    (2) Verifica que esté `activo` (FR-05/AC-08). (3) Chequea solapamiento
    con las reservas activas de ese vehículo (FR-03/AC-05) — su propio
    `FOR UPDATE` es redundante una vez tomado el lock del paso (1), pero
    inofensivo. (4) Si no hay solapamiento, inserta y comitea dentro de esa
    misma transacción — el lock del vehículo se libera recién en ese
    commit, así que una segunda solicitud concurrente bloqueada en el paso
    (1) reevalúa el solapamiento DESPUÉS de ver la fila recién insertada
    (AC-06).
    """
    vehiculo_id = data.vehiculo_id
    legajo = data.legajo

    try:
        vehiculo = vehiculos_repository.obtener_por_id_con_lock(db, vehiculo_id)
        if vehiculo is None:
            raise VehiculoNoEncontradoError(vehiculo_id)

        if vehiculo.estado != EstadoVehiculo.activo:
            raise VehiculoNoActivoError(vehiculo_id, vehiculo.estado)

        solapadas = repository.listar_activas_solapadas_con_lock(
            db, vehiculo_id, data.fecha_inicio, data.fecha_fin
        )
        if solapadas:
            raise ReservaSolapadaError(vehiculo_id)

        reserva = repository.crear(db, data)
    except ReservaDomainError:
        db.rollback()
        _log_operacion("crear_reserva", vehiculo_id, legajo, "rechazada", ip_origen)
        raise

    _log_operacion("crear_reserva", vehiculo_id, legajo, "ok", ip_origen)
    return reserva


def consultar_disponibilidad(
    db: Session, fecha_inicio: datetime, fecha_fin: datetime
) -> list[DisponibilidadOut]:
    """FR-04: por cada vehículo del pool, marca `disponible` según si tiene
    o no una reserva activa que se superponga con el rango consultado."""
    vehiculos = vehiculos_repository.listar(db)
    solapadas = repository.listar_solapadas_en_rango(db, fecha_inicio, fecha_fin)
    ids_no_disponibles = {r.vehiculo_id for r in solapadas}

    return [
        DisponibilidadOut(
            vehiculo_id=v.id,
            patente=v.patente,
            tipo=v.tipo,
            disponible=v.id not in ids_no_disponibles,
        )
        for v in vehiculos
    ]


def listar_reservas(
    db: Session, periodo: FiltroPeriodoReserva | None = None
) -> list[ReservaListItem]:
    """FR-01/FR-02: listado público de todas las reservas, enriquecido con
    patente/tipo del vehículo asociado — combina `repository.listar_todas`
    (solo tabla `reservas`) con `vehiculos_repository.listar` (ya existente,
    solo lectura entre features, dependencia D-02 del PRD) por
    `vehiculo_id` en Python, mismo patrón que `consultar_disponibilidad`.

    Si `periodo` no es `None`, filtra en Python contra
    `datetime.now(timezone.utc)`. El filtro es puramente temporal — NO
    excluye reservas `cancelada` (AC-02 a AC-04 del PRD son criterios sobre
    fechas, no sobre `estado`).
    """
    reservas = repository.listar_todas(db)
    vehiculos_por_id = {v.id: v for v in vehiculos_repository.listar(db)}

    if periodo is not None:
        ahora = datetime.now(timezone.utc)
        if periodo == "futuras":
            reservas = [r for r in reservas if r.fecha_inicio > ahora]
        elif periodo == "en_curso":
            reservas = [r for r in reservas if r.fecha_inicio <= ahora <= r.fecha_fin]
        elif periodo == "pasadas":
            reservas = [r for r in reservas if r.fecha_fin < ahora]

    return [
        ReservaListItem(
            id=r.id,
            vehiculo_id=r.vehiculo_id,
            nombre_empleado=r.nombre_empleado,
            fecha_inicio=r.fecha_inicio,
            fecha_fin=r.fecha_fin,
            destino=r.destino,
            estado=r.estado,
            created_at=r.created_at,
            updated_at=r.updated_at,
            patente=vehiculos_por_id[r.vehiculo_id].patente,
            tipo=vehiculos_por_id[r.vehiculo_id].tipo,
        )
        for r in reservas
        if r.vehiculo_id in vehiculos_por_id
    ]


def consultar_reservas_activas_por_patente(db: Session, patente: str) -> list[ReservaListItem]:
    """FR-01/FR-02/FR-03 (Block 2 de FEAT-004): reservas activas de un
    vehículo dado por patente (búsqueda case-insensitive, Block 1), o
    `VehiculoNoEncontradoError` si la patente no existe en el pool.

    Valida el formato de `patente` de forma defensiva (FIX-005, hallazgo A)
    antes de tocar la base: hoy el único caller es `router.py`, que ya
    valida vía `Path(pattern=PATENTE_PATTERN)`, pero un caller interno
    futuro que invoque esta función directo (sin pasar por FastAPI) no
    tendría ninguna otra barrera de formato — mismo criterio que
    `crear_vehiculo`/`modificar_vehiculo` en `vehiculos/service.py`."""
    if not (1 <= len(patente) <= 10) or not _PATENTE_REGEX.match(patente):
        raise PatenteFormatoInvalidoError(patente)

    vehiculo = vehiculos_repository.obtener_por_patente_normalizada(db, patente)
    if vehiculo is None:
        raise VehiculoNoEncontradoError(patente)

    ahora = datetime.now(timezone.utc)
    reservas = repository.listar_activas_por_vehiculo(db, vehiculo.id, ahora)

    return [
        ReservaListItem(
            id=r.id,
            vehiculo_id=r.vehiculo_id,
            nombre_empleado=r.nombre_empleado,
            fecha_inicio=r.fecha_inicio,
            fecha_fin=r.fecha_fin,
            destino=r.destino,
            estado=r.estado,
            created_at=r.created_at,
            updated_at=r.updated_at,
            patente=vehiculo.patente,
            tipo=vehiculo.tipo,
        )
        for r in reservas
    ]


def cancelar_reserva(db: Session, reserva_id: int, legajo: str, ip_origen: str) -> Reserva:
    """FR-03: cancela una reserva propia, validando que el `legajo`
    indicado coincida con el de la reserva (AC-06).

    Orden de validación: (1) existe (`ReservaNoEncontradaError`, 404) → (2)
    `estado == activa` (`ReservaYaCanceladaError`, 409 — decisión de diseño
    confirmada en PLAN: no responde éxito de forma idempotente) → (3)
    `legajo` coincide (`LegajoNoCoincideError`, 403, mensaje que no revela
    el legajo real) → (4) muta `estado` a `cancelada` y persiste (AC-05: el
    vehículo queda disponible para ese período porque
    `listar_activas_solapadas_con_lock`/`listar_solapadas_en_rango` ya
    filtran por `estado == activa`, no hace falta ningún paso adicional).
    """
    vehiculo_id = None
    try:
        reserva = repository.obtener_por_id(db, reserva_id)
        if reserva is None:
            raise ReservaNoEncontradaError(reserva_id)

        vehiculo_id = reserva.vehiculo_id

        if reserva.estado != EstadoReserva.activa:
            raise ReservaYaCanceladaError(reserva_id)

        if reserva.legajo != legajo:
            raise LegajoNoCoincideError(reserva_id)

        reserva.estado = EstadoReserva.cancelada
        reserva = repository.guardar(db, reserva)
    except ReservaDomainError:
        _log_operacion("cancelar_reserva", vehiculo_id, legajo, "rechazada", ip_origen)
        raise

    _log_operacion("cancelar_reserva", reserva.vehiculo_id, legajo, "ok", ip_origen)
    return reserva
