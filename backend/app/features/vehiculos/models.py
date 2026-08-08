"""Modelo SQLAlchemy de la entidad Vehiculo (tabla `vehiculos`)."""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class TipoVehiculo(str, enum.Enum):
    auto = "auto"
    camioneta = "camioneta"


class EstadoVehiculo(str, enum.Enum):
    activo = "activo"
    baja_temporal = "baja_temporal"
    baja_definitiva = "baja_definitiva"


class Vehiculo(Base):
    __tablename__ = "vehiculos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # UNIQUE + índice sobre la misma columna: es la columna por la que se
    # busca en el chequeo de unicidad de Block 2, así que además de la
    # restricción de integridad necesita quedar indexada para esas
    # búsquedas (en Postgres, `unique=True` ya genera un índice único que
    # cubre ambos requisitos, sin duplicar un segundo índice redundante).
    patente: Mapped[str] = mapped_column(
        String(10), nullable=False, unique=True, index=True
    )

    tipo: Mapped[TipoVehiculo] = mapped_column(
        Enum(
            TipoVehiculo,
            name="tipo_vehiculo",
            native_enum=False,
            length=10,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_constraint=True,
        ),
        nullable=False,
    )

    estado: Mapped[EstadoVehiculo] = mapped_column(
        Enum(
            EstadoVehiculo,
            name="estado_vehiculo",
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_constraint=True,
        ),
        nullable=False,
        default=EstadoVehiculo.activo,
        server_default=EstadoVehiculo.activo.value,
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
