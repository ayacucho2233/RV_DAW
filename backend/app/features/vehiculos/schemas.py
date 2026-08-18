"""Schemas Pydantic del feature `vehiculos`.

`VehiculoCreate`/`VehiculoUpdate` validan `patente` (string alfanumérico,
sin espacios ni caracteres especiales, no vacío, hasta 10 caracteres) y
`tipo` (`Literal["auto", "camioneta"]`): Pydantic ya
rechaza cualquier otro valor de `tipo` antes de que la request llegue a
`service.py`, lo que cubre FR-10/FR-11 a nivel de esquema. `service.py`
repite esa validación de forma defensiva para callers internos que no pasen
por este schema (ver `exceptions.TipoInvalidoError`).
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.features.vehiculos.models import EstadoVehiculo, TipoVehiculo

TipoVehiculoLiteral = Literal["auto", "camioneta"]

PATENTE_PATTERN = r"^[A-Za-z0-9]+$"
"""Fuente de verdad del formato de patente (FIX-005): alfanumérica, sin
espacios ni caracteres especiales. Reusada por `reservas/router.py`
(`Path(pattern=...)`) y `reservas/service.py` (validación defensiva de
`consultar_reservas_activas_por_patente`) para no duplicar el literal."""


class VehiculoBase(BaseModel):
    # Alfanumérica, sin espacios ni caracteres especiales (aclaración de
    # negocio posterior a la spec escrita, que solo exigía 1-10 caracteres
    # no vacíos).
    patente: str = Field(..., min_length=1, max_length=10, pattern=PATENTE_PATTERN)
    tipo: TipoVehiculoLiteral


class VehiculoCreate(VehiculoBase):
    """Payload de alta de un vehículo (FR-01)."""


class VehiculoUpdate(VehiculoBase):
    """Payload de modificación de un vehículo existente (FR-02)."""


class VehiculoOut(BaseModel):
    """Representación de salida de un vehículo (respuesta de la API)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patente: str
    tipo: TipoVehiculo
    estado: EstadoVehiculo
    created_at: datetime
    updated_at: datetime
