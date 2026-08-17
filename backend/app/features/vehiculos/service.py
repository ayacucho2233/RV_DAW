"""Lógica de negocio del feature `vehiculos` — un método por FR del PRD.

Capa intermedia entre `router.py` (Block 3, todavía no existe) y
`repository.py`: acá viven las reglas de unicidad de patente (FR-08/FR-09),
la máquina de estados de baja/reactivación (FR-03/FR-04/FR-06/FR-07) y la
validación defensiva de tipo (FR-10/FR-11). Nunca accede a la base
directamente — todo pasa por `repository.py` (AGENTS.md: "Layer
separation").

`dar_de_baja_temporal`/`dar_de_baja_definitiva` (FEAT-001e/FR-01/AC-01/AC-02)
además verifican que el vehículo no tenga reservas activas antes de mutar su
estado. Importan `app.features.reservas.repository` en modo de solo lectura
(dependencia cruzada D-06 del spec de FEAT-001e — ver "Nota de dependencia
cruzada" en spec-FEAT-001e.md): la dirección opuesta
(`reservas.service` → `vehiculos.repository`) ya existía desde FEAT-001c/D-01,
así que el acoplamiento entre ambos features pasa a ser bidireccional, pero
siempre de solo lectura y siempre a nivel repository (nunca service→service).
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.features.reservas import repository as reservas_repository
from app.features.vehiculos import repository
from app.features.vehiculos.exceptions import (
    PatenteYaExisteError,
    TipoInvalidoError,
    TransicionEstadoInvalidaError,
    VehiculoConReservasActivasError,
    VehiculoDomainError,
    VehiculoNoEncontradoError,
)
from app.features.vehiculos.models import EstadoVehiculo, TipoVehiculo, Vehiculo

logger = logging.getLogger(__name__)


def _validar_tipo(tipo) -> TipoVehiculo:
    """Validación defensiva de `tipo` (FR-10/FR-11).

    Pydantic ya bloquea valores inválidos en `schemas.py` vía `Literal`;
    esto cubre el caso de un caller interno que invoque el servicio con un
    objeto que no pasó por ese schema.
    """
    try:
        return TipoVehiculo(tipo)
    except ValueError as exc:
        raise TipoInvalidoError(tipo) from exc


def _log_operacion(operacion: str, vehiculo_id: int | None, resultado: str) -> None:
    """Log de trazabilidad de operaciones administrativas (mitigación TM-04
    del threat model). Nunca debe recibir el header `Authorization` ni
    ningún dato de credenciales — solo el nombre de la operación, el id del
    vehículo afectado y el resultado.
    """
    logger.info(
        "operacion=%s vehiculo_id=%s resultado=%s timestamp=%s",
        operacion,
        vehiculo_id,
        resultado,
        datetime.now(timezone.utc).isoformat(),
    )


def crear_vehiculo(db: Session, data) -> Vehiculo:
    """FR-01: alta de un vehículo. Valida patente única (FR-08)."""
    _validar_tipo(data.tipo)

    if repository.obtener_por_patente_normalizada(db, data.patente) is not None:
        raise PatenteYaExisteError(data.patente)

    vehiculo = repository.crear(db, data)
    _log_operacion("crear_vehiculo", vehiculo.id, "ok")
    return vehiculo


def modificar_vehiculo(db: Session, vehiculo_id: int, data) -> Vehiculo:
    """FR-02: modificación de patente/tipo. Valida patente única excluyendo
    el propio id (FR-09)."""
    _validar_tipo(data.tipo)

    vehiculo = repository.obtener_por_id(db, vehiculo_id)
    if vehiculo is None:
        raise VehiculoNoEncontradoError(vehiculo_id)

    existente = repository.obtener_por_patente_normalizada(db, data.patente)
    if existente is not None and existente.id != vehiculo_id:
        raise PatenteYaExisteError(data.patente)

    vehiculo = repository.actualizar(db, vehiculo, data)
    _log_operacion("modificar_vehiculo", vehiculo.id, "ok")
    return vehiculo


def dar_de_baja_temporal(db: Session, vehiculo_id: int) -> Vehiculo:
    """FR-03: solo permitido desde el estado 'activo'.

    FEAT-001e/FR-01/AC-01: además rechaza la baja si el vehículo tiene
    reservas activas. `obtener_por_id_con_lock` (`SELECT ... FOR UPDATE`)
    serializa esta operación con cualquier `reservas.service.crear_reserva`
    concurrente sobre el mismo `vehiculo_id` (mitigación de R-01 del PRD).
    Orden de validación: (1) existe → 404, (2) transición de estado válida →
    409, (3) sin reservas activas → 409.
    """
    try:
        vehiculo = repository.obtener_por_id_con_lock(db, vehiculo_id)
        if vehiculo is None:
            raise VehiculoNoEncontradoError(vehiculo_id)

        if vehiculo.estado != EstadoVehiculo.activo:
            raise TransicionEstadoInvalidaError(vehiculo.estado, "baja_temporal")

        if reservas_repository.existe_activa_para_vehiculo(db, vehiculo_id):
            raise VehiculoConReservasActivasError(vehiculo_id)

        vehiculo.estado = EstadoVehiculo.baja_temporal
        vehiculo = repository.guardar(db, vehiculo)
    except VehiculoDomainError:
        db.rollback()
        _log_operacion("dar_de_baja_temporal", vehiculo_id, "rechazada")
        raise

    _log_operacion("dar_de_baja_temporal", vehiculo.id, "ok")
    return vehiculo


def dar_de_baja_definitiva(db: Session, vehiculo_id: int) -> Vehiculo:
    """FR-04: permitido desde 'activo' o 'baja_temporal'.

    FEAT-001e/FR-01/AC-02: mismas reglas que `dar_de_baja_temporal` — lock,
    rechazo por reservas activas, y rollback explícito en el camino de
    error."""
    try:
        vehiculo = repository.obtener_por_id_con_lock(db, vehiculo_id)
        if vehiculo is None:
            raise VehiculoNoEncontradoError(vehiculo_id)

        if vehiculo.estado not in (EstadoVehiculo.activo, EstadoVehiculo.baja_temporal):
            raise TransicionEstadoInvalidaError(vehiculo.estado, "baja_definitiva")

        if reservas_repository.existe_activa_para_vehiculo(db, vehiculo_id):
            raise VehiculoConReservasActivasError(vehiculo_id)

        vehiculo.estado = EstadoVehiculo.baja_definitiva
        vehiculo = repository.guardar(db, vehiculo)
    except VehiculoDomainError:
        db.rollback()
        _log_operacion("dar_de_baja_definitiva", vehiculo_id, "rechazada")
        raise

    _log_operacion("dar_de_baja_definitiva", vehiculo.id, "ok")
    return vehiculo


def reactivar(db: Session, vehiculo_id: int) -> Vehiculo:
    """FR-06: solo desde 'baja_temporal'. FR-07: rechaza 'baja_definitiva'."""
    vehiculo = repository.obtener_por_id(db, vehiculo_id)
    if vehiculo is None:
        raise VehiculoNoEncontradoError(vehiculo_id)

    if vehiculo.estado != EstadoVehiculo.baja_temporal:
        raise TransicionEstadoInvalidaError(vehiculo.estado, "reactivar")

    vehiculo.estado = EstadoVehiculo.activo
    vehiculo = repository.guardar(db, vehiculo)
    _log_operacion("reactivar", vehiculo.id, "ok")
    return vehiculo


def listar_vehiculos(db: Session) -> list[Vehiculo]:
    """Soporte de Block 3/4 (GET /vehiculos, sin FR directo)."""
    return repository.listar(db)
