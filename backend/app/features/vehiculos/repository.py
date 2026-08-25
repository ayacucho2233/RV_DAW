"""Acceso a datos del feature `vehiculos`.

Capa "tonta": no contiene lógica de negocio (esa vive en `service.py` —
AGENTS.md, "Layer separation"). La única regla que aplica acá es la
traducción de `IntegrityError` a `PatenteYaExisteError` en `crear` y
`actualizar` (mitigación TM-03 del threat model): cierra la condición de
carrera TOCTOU entre el chequeo previo de unicidad de `service.py` y el
`INSERT`/`UPDATE` real — si dos altas concurrentes con la misma patente
llegan a la base, la que pierde contra el `UNIQUE` constraint recibe el
mismo error de dominio que el chequeo preventivo, nunca un `IntegrityError`
crudo sin manejar.
"""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.vehiculos.exceptions import PatenteYaExisteError
from app.features.vehiculos.models import TipoVehiculo, Vehiculo


def crear(db: Session, data) -> Vehiculo:
    """Inserta un vehículo nuevo. `data` expone `.patente` y `.tipo`."""
    vehiculo = Vehiculo(patente=data.patente, tipo=TipoVehiculo(data.tipo))
    db.add(vehiculo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PatenteYaExisteError(data.patente) from exc
    db.refresh(vehiculo)
    return vehiculo


def obtener_por_id(db: Session, vehiculo_id: int) -> Vehiculo | None:
    return db.get(Vehiculo, vehiculo_id)


def obtener_por_id_con_lock(db: Session, vehiculo_id: int) -> Vehiculo | None:
    """`SELECT ... FOR UPDATE` sobre la fila de `vehiculos` (NFR-03/AC-06,
    usado por `reservas.service.crear_reserva`).

    La fila del vehículo SIEMPRE existe si `vehiculo_id` es válido (a
    diferencia de las reservas solapadas, que pueden no tener ninguna fila
    previa que lockear — "phantom row"/gap-locking: `SELECT ... FOR UPDATE`
    en Postgres solo bloquea las filas que la consulta efectivamente
    devuelve, así que lockear reservas no sirve cuando es la primera del
    slot). Lockear el vehículo serializa TODOS los intentos concurrentes de
    `crear_reserva` sobre el mismo `vehiculo_id`, sin importar si hay 0 o N
    reservas previas. Sigue siendo de solo lectura sobre `vehiculos` — no
    escribe nada en esa tabla."""
    return db.execute(
        select(Vehiculo).where(Vehiculo.id == vehiculo_id).with_for_update()
    ).scalar_one_or_none()


def obtener_por_patente_normalizada(db: Session, patente: str) -> Vehiculo | None:
    """Búsqueda case-insensitive (FR-05). Usa func.lower() de ambos lados —
    para que la expresión de la query coincida con la del índice único
    funcional `ix_vehiculos_patente_lower_unique` (migración 0003, sobre
    `lower(patente)`); Postgres no usa un índice funcional sobre `lower(x)`
    para resolver una condición sobre `upper(x)` (FIX-004) — y `.limit(1)`
    — nunca `scalar_one_or_none()`, por la mitigación del threat model:
    aunque el índice único impida duplicados a futuro, esta query no debe
    poder levantar `MultipleResultsFound` bajo ningún escenario.

    `.limit(1)` por sí solo evita `MultipleResultsFound`, pero NO garantiza
    determinismo entre llamadas si hubiera más de una fila candidata —
    Postgres no promete ningún orden estable sin un `ORDER BY` explícito
    (FIX-005, hallazgo B). El `.order_by(Vehiculo.id)` es lo que da el
    determinismo real, mismo criterio que `obtener_por_id_con_lock`."""
    stmt = (
        select(Vehiculo)
        .where(func.lower(Vehiculo.patente) == patente.strip().lower())
        .order_by(Vehiculo.id)
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def listar(db: Session) -> list[Vehiculo]:
    return list(db.execute(select(Vehiculo)).scalars().all())


def actualizar(db: Session, vehiculo: Vehiculo, data) -> Vehiculo:
    """Actualiza patente/tipo de un vehículo existente. `data` expone
    `.patente` y `.tipo`."""
    vehiculo.patente = data.patente
    vehiculo.tipo = TipoVehiculo(data.tipo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PatenteYaExisteError(data.patente) from exc
    db.refresh(vehiculo)
    return vehiculo


def guardar(db: Session, vehiculo: Vehiculo) -> Vehiculo:
    """Persiste cambios ya aplicados sobre una instancia existente (p. ej.
    un cambio de `estado`)."""
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)
    return vehiculo
