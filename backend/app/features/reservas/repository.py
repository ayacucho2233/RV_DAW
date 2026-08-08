"""Acceso a datos del feature `reservas`.

Capa "tonta": no contiene lógica de negocio (esa vive en `service.py` —
AGENTS.md, "Layer separation"). `crear` no traduce `IntegrityError` porque
acá no hay ningún `UNIQUE` que pueda violarse — la protección contra
solapamiento se hace antes de llegar a este método (ver `service.py`), vía
`vehiculos_repository.obtener_por_id_con_lock` + `listar_activas_solapadas_con_lock`.
Este módulo solo toca la tabla `reservas` — el lock sobre `vehiculos` vive en
`app.features.vehiculos.repository` (un repository, una tabla).
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.reservas.models import EstadoReserva, Reserva


def crear(db: Session, data) -> Reserva:
    """Inserta una reserva nueva. `data` expone los campos de `ReservaCreate`."""
    reserva = Reserva(
        vehiculo_id=data.vehiculo_id,
        nombre_empleado=data.nombre_empleado,
        legajo=data.legajo,
        licencia=data.licencia,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        destino=data.destino,
    )
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    return reserva


def listar_activas_solapadas_con_lock(
    db: Session, vehiculo_id: int, fecha_inicio: datetime, fecha_fin: datetime
) -> list[Reserva]:
    """`SELECT ... FOR UPDATE` sobre las reservas activas de `vehiculo_id`
    que se superponen con `[fecha_inicio, fecha_fin)` (NFR-03/AC-06).

    El `FOR UPDATE` bloquea las filas solapables de ESE vehículo hasta que
    la transacción que las lee haga commit o rollback — mandato explícito
    de AGENTS.md ("usar SELECT FOR UPDATE al verificar disponibilidad y
    crear una reserva en la misma operación atómica").
    """
    stmt = (
        select(Reserva)
        .where(
            Reserva.vehiculo_id == vehiculo_id,
            Reserva.estado == EstadoReserva.activa,
            Reserva.fecha_inicio < fecha_fin,
            Reserva.fecha_fin > fecha_inicio,
        )
        .with_for_update()
    )
    return list(db.execute(stmt).scalars().all())


def listar_solapadas_en_rango(
    db: Session, fecha_inicio: datetime, fecha_fin: datetime
) -> list[Reserva]:
    """Reservas activas (de cualquier vehículo) que se superponen con el
    rango consultado, SIN `FOR UPDATE` (de solo lectura, para el endpoint
    de disponibilidad — no participa de ninguna escritura)."""
    stmt = select(Reserva).where(
        Reserva.estado == EstadoReserva.activa,
        Reserva.fecha_inicio < fecha_fin,
        Reserva.fecha_fin > fecha_inicio,
    )
    return list(db.execute(stmt).scalars().all())


def listar_todas(db: Session) -> list[Reserva]:
    """`SELECT * FROM reservas` sin filtros ni joins (FR-01/FR-02): respeta
    "un repository, una tabla" — el enriquecimiento con datos de
    `vehiculos` se resuelve en `service.py`, no acá."""
    return list(db.execute(select(Reserva)).scalars().all())


def obtener_por_id(db: Session, reserva_id: int) -> Reserva | None:
    return db.get(Reserva, reserva_id)


def guardar(db: Session, reserva: Reserva) -> Reserva:
    """Persiste cambios ya aplicados sobre una instancia existente (p. ej.
    un cambio de `estado` al cancelar), mismo patrón que
    `vehiculos_repository.guardar`."""
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    return reserva
