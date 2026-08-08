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
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.features.reservas import repository
from app.features.reservas.exceptions import (
    ReservaDomainError,
    ReservaSolapadaError,
    VehiculoNoActivoError,
    VehiculoNoEncontradoError,
)
from app.features.reservas.models import Reserva
from app.features.reservas.schemas import DisponibilidadOut, VehiculoPublico
from app.features.vehiculos import repository as vehiculos_repository
from app.features.vehiculos.models import EstadoVehiculo

logger = logging.getLogger(__name__)


def _log_operacion(vehiculo_id: int | None, legajo: str | None, resultado: str, ip_origen: str) -> None:
    """Log de trazabilidad de `crear_reserva` (mitigación TM-C-04 del threat
    model). Sin autenticación en este feature, es el único rastro disponible
    para investigar abusos o disputas. **Nunca** debe recibir
    `nombre_empleado` ni `licencia` — reduce la superficie de PII en los
    logs a lo estrictamente necesario para trazabilidad operativa.
    """
    logger.info(
        "operacion=%s vehiculo_id=%s legajo=%s resultado=%s ip_origen=%s timestamp=%s",
        "crear_reserva",
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
        _log_operacion(vehiculo_id, legajo, "rechazada", ip_origen)
        raise

    _log_operacion(vehiculo_id, legajo, "ok", ip_origen)
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
