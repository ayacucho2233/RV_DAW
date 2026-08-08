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
from sqlalchemy import select
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


def obtener_por_patente(db: Session, patente: str) -> Vehiculo | None:
    return db.execute(
        select(Vehiculo).where(Vehiculo.patente == patente)
    ).scalar_one_or_none()


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
