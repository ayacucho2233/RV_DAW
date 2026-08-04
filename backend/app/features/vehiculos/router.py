"""Router HTTP del feature `vehiculos` (Block 3).

Los 6 endpoints de administración del pool. Cada uno llama al método de
`service.py` (Block 2) correspondiente dentro de un `try/except` que
traduce las excepciones de dominio a HTTP según la tabla del spec — nunca
accede a la base directamente (AGENTS.md: "Layer separation", el router
solo habla con `service.py`).

Todos los endpoints están protegidos con `verificar_admin`
(`app.core.security`, HTTP Basic + rate limiting).

`GET /vehiculos` no corresponde a ningún FR del PRD: es un habilitador
técnico para que el panel admin (Block 4) pueda listar qué vehículos
editar/dar de baja (documentado también en el spec, sección Block 3 — no es
scope creep).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verificar_admin
from app.features.vehiculos import service
from app.features.vehiculos.exceptions import (
    PatenteYaExisteError,
    TipoInvalidoError,
    TransicionEstadoInvalidaError,
    VehiculoNoEncontradoError,
)
from app.features.vehiculos.schemas import VehiculoCreate, VehiculoOut, VehiculoUpdate

router = APIRouter(prefix="/vehiculos", tags=["vehiculos"])

_MAPEO_ERRORES_HTTP = {
    PatenteYaExisteError: status.HTTP_409_CONFLICT,
    TipoInvalidoError: status.HTTP_400_BAD_REQUEST,
    TransicionEstadoInvalidaError: status.HTTP_409_CONFLICT,
    VehiculoNoEncontradoError: status.HTTP_404_NOT_FOUND,
}


def _a_http(exc: Exception) -> HTTPException:
    """Traduce una excepción de dominio (`app.features.vehiculos.exceptions`)
    al `HTTPException` correspondiente, según la tabla del spec."""
    status_code = _MAPEO_ERRORES_HTTP[type(exc)]
    return HTTPException(status_code=status_code, detail=str(exc))


@router.post("", response_model=VehiculoOut, status_code=status.HTTP_201_CREATED)
def crear_vehiculo(
    data: VehiculoCreate,
    db: Session = Depends(get_db),
    _admin: str = Depends(verificar_admin),
) -> VehiculoOut:
    """FR-01: alta de un vehículo."""
    try:
        return service.crear_vehiculo(db, data)
    except (PatenteYaExisteError, TipoInvalidoError) as exc:
        raise _a_http(exc) from exc


@router.put("/{vehiculo_id}", response_model=VehiculoOut)
def modificar_vehiculo(
    vehiculo_id: int,
    data: VehiculoUpdate,
    db: Session = Depends(get_db),
    _admin: str = Depends(verificar_admin),
) -> VehiculoOut:
    """FR-02: modificación de patente/tipo."""
    try:
        return service.modificar_vehiculo(db, vehiculo_id, data)
    except (PatenteYaExisteError, TipoInvalidoError, VehiculoNoEncontradoError) as exc:
        raise _a_http(exc) from exc


@router.patch("/{vehiculo_id}/baja-temporal", response_model=VehiculoOut)
def dar_de_baja_temporal(
    vehiculo_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(verificar_admin),
) -> VehiculoOut:
    """FR-03: baja temporal, solo desde estado 'activo'."""
    try:
        return service.dar_de_baja_temporal(db, vehiculo_id)
    except (VehiculoNoEncontradoError, TransicionEstadoInvalidaError) as exc:
        raise _a_http(exc) from exc


@router.patch("/{vehiculo_id}/baja-definitiva", response_model=VehiculoOut)
def dar_de_baja_definitiva(
    vehiculo_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(verificar_admin),
) -> VehiculoOut:
    """FR-04: baja definitiva, desde 'activo' o 'baja_temporal'."""
    try:
        return service.dar_de_baja_definitiva(db, vehiculo_id)
    except (VehiculoNoEncontradoError, TransicionEstadoInvalidaError) as exc:
        raise _a_http(exc) from exc


@router.patch("/{vehiculo_id}/reactivar", response_model=VehiculoOut)
def reactivar_vehiculo(
    vehiculo_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(verificar_admin),
) -> VehiculoOut:
    """FR-06/FR-07: reactivar, solo desde 'baja_temporal'."""
    try:
        return service.reactivar(db, vehiculo_id)
    except (VehiculoNoEncontradoError, TransicionEstadoInvalidaError) as exc:
        raise _a_http(exc) from exc


@router.get("", response_model=list[VehiculoOut])
def listar_vehiculos(
    db: Session = Depends(get_db),
    _admin: str = Depends(verificar_admin),
) -> list[VehiculoOut]:
    """Habilitador técnico para el panel admin (Block 4), sin FR directo."""
    return service.listar_vehiculos(db)
