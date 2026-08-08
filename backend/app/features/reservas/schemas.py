"""Schemas Pydantic del feature `reservas`.

`ReservaCreate` valida: campos de texto no vacíos con longitud máxima acorde
a la columna, `vehiculo_id` entero positivo, y `fecha_inicio`/`fecha_fin`
timezone-aware obligatorio (mitigación TM-C-03 del threat model: un datetime
naive nunca debe llegar a la comparación de solapamiento de
`repository.py`, para no comparar naive contra aware ni prestarse a
confusión de zona horaria) con `fecha_fin > fecha_inicio` (AC-04). La
existencia real del vehículo y su estado se validan en `service.py`, no acá
(no es responsabilidad de Pydantic).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.features.reservas.models import EstadoReserva
from app.features.vehiculos.models import TipoVehiculo


def _validar_timezone_aware(valor: datetime, nombre_campo: str) -> datetime:
    if valor.tzinfo is None or valor.tzinfo.utcoffset(valor) is None:
        raise ValueError(f"{nombre_campo} debe incluir zona horaria")
    return valor


class ReservaCreate(BaseModel):
    """Payload de alta de una reserva (FR-02)."""

    nombre_empleado: str = Field(..., min_length=1, max_length=200)
    legajo: str = Field(..., min_length=1, max_length=20)
    licencia: str = Field(..., min_length=1, max_length=20)
    vehiculo_id: int = Field(..., gt=0)
    fecha_inicio: datetime
    fecha_fin: datetime
    destino: str = Field(..., min_length=1, max_length=200)

    @field_validator("fecha_inicio")
    @classmethod
    def _fecha_inicio_aware(cls, valor: datetime) -> datetime:
        return _validar_timezone_aware(valor, "fecha_inicio")

    @field_validator("fecha_fin")
    @classmethod
    def _fecha_fin_aware(cls, valor: datetime) -> datetime:
        return _validar_timezone_aware(valor, "fecha_fin")

    @model_validator(mode="after")
    def _fecha_fin_posterior_a_inicio(self) -> "ReservaCreate":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self


class ReservaOut(BaseModel):
    """Representación de salida de una reserva (respuesta de la API)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    vehiculo_id: int
    nombre_empleado: str
    legajo: str
    licencia: str
    fecha_inicio: datetime
    fecha_fin: datetime
    destino: str
    estado: EstadoReserva
    created_at: datetime
    updated_at: datetime


class VehiculoPublico(BaseModel):
    """Vista pública de un vehículo del pool: solo patente/tipo (FR-01).

    Nunca expone `estado` ni ningún otro campo administrativo.
    """

    model_config = ConfigDict(from_attributes=True)

    patente: str
    tipo: TipoVehiculo


class DisponibilidadOut(BaseModel):
    """Resultado de la consulta de disponibilidad para un rango (FR-04)."""

    vehiculo_id: int
    patente: str
    tipo: TipoVehiculo
    disponible: bool
