"""Modelo SQLAlchemy de la entidad Reserva (tabla `reservas`)."""
import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class EstadoReserva(str, enum.Enum):
    activa = "activa"
    cancelada = "cancelada"


class Reserva(Base):
    __tablename__ = "reservas"

    __table_args__ = (
        CheckConstraint("fecha_fin > fecha_inicio", name="ck_reservas_fecha_fin_mayor_inicio"),
        # Índice compuesto explícito (vehiculo_id, fecha_inicio, fecha_fin):
        # mandato de AGENTS.md ("crear índices en... vehículo + fechas para
        # las búsquedas de disponibilidad"). Es la combinación de columnas
        # por la que Block 2 consulta tanto el chequeo de solapamiento como
        # la disponibilidad.
        Index(
            "ix_reservas_vehiculo_fechas",
            "vehiculo_id",
            "fecha_inicio",
            "fecha_fin",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    vehiculo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehiculos.id"), nullable=False
    )

    nombre_empleado: Mapped[str] = mapped_column(String(200), nullable=False)
    legajo: Mapped[str] = mapped_column(String(20), nullable=False)
    licencia: Mapped[str] = mapped_column(String(20), nullable=False)

    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    destino: Mapped[str] = mapped_column(String(200), nullable=False)

    estado: Mapped[EstadoReserva] = mapped_column(
        Enum(
            EstadoReserva,
            name="estado_reserva",
            native_enum=False,
            length=10,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_constraint=True,
        ),
        nullable=False,
        default=EstadoReserva.activa,
        server_default=EstadoReserva.activa.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
