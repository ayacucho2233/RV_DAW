"""Router HTTP del feature `reservas` (Block 3 de FEAT-001c; Block 2 de
FEAT-001d agrega `GET /reservas` y `PATCH /reservas/{id}/cancelar`).

Los 5 endpoints públicos del pool de reservas. Cada uno llama al método de
`service.py` correspondiente dentro de un `try/except` que
traduce las excepciones de dominio a HTTP según la tabla del spec — nunca
accede a la base directamente (AGENTS.md: "Layer separation", el router
solo habla con `service.py`).

A diferencia de `vehiculos.router`, NINGÚN endpoint usa
`Depends(verificar_admin)`: este feature es público por diseño del PRD
(FR-01 a FR-04 no mencionan autenticación, y el PRD marca "Autenticación...
cubierto por FEAT-001a" como Out of Scope).

`GET /reservas/vehiculos` es un endpoint DISTINTO de `GET /vehiculos`
(`vehiculos.router`, que exige HTTP Basic). Coexisten sin colisión porque
tienen paths distintos — documentado así desde el PRD de FEAT-001a (nota en
su spec, Block 3) para que no se lo marque como scope creep ni como
duplicado.

Rate limiting (mitigación TM-C-02 del threat model): un `Limiter`
(`slowapi`/`limits`, mismo mecanismo ya presente en `app.core.security`)
propio de este módulo cuenta TODAS las requests por IP (no solo fallos, a
diferencia de `verificar_admin`: acá no hay "intentos fallidos de auth" en
un feature sin autenticación). Se llama directamente a
`Limiter.limiter.hit(...)` en vez de usar el decorador `@limiter.limit(...)`
para no depender de registrar un exception handler de `slowapi` en
`app.main` (que el spec de Block 3 no contempla tocar) — mismo patrón ya
usado en `app.core.security.verificar_admin`. Al superarse el límite,
`429 Too Many Requests` con el mismo `HTTPException` de status/mensaje.

`POST /reservas` y `PATCH /reservas/{id}/cancelar`: máx. 10 mutaciones por
IP por hora cada uno. `GET /reservas/vehiculos`, `GET /reservas/disponibilidad`
y `GET /reservas`: máx. 60 consultas por IP por minuto cada uno — los 5
endpoints cuentan de forma independiente entre sí (cada uno con su propia
clave de contador: `"reservas-post"`, `"reservas-cancelar"`,
`"reservas-vehiculos"`, `"reservas-disponibilidad"`, `"reservas-listado"`),
no un único balde compartido, ya que el spec no exige compartirlo y así un
abuso de uno no descuenta cupo del otro.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.reservas import service
from app.features.reservas.exceptions import (
    LegajoNoCoincideError,
    ReservaNoEncontradaError,
    ReservaSolapadaError,
    ReservaYaCanceladaError,
    VehiculoNoActivoError,
    VehiculoNoEncontradoError,
)
from app.features.reservas.schemas import (
    CancelarReservaRequest,
    DisponibilidadOut,
    FiltroPeriodoReserva,
    ReservaCreate,
    ReservaListItem,
    ReservaOut,
    VehiculoPublico,
)

router = APIRouter(prefix="/reservas", tags=["reservas"])

_MAPEO_ERRORES_HTTP = {
    VehiculoNoEncontradoError: status.HTTP_404_NOT_FOUND,
    VehiculoNoActivoError: status.HTTP_409_CONFLICT,
    ReservaSolapadaError: status.HTTP_409_CONFLICT,
    ReservaNoEncontradaError: status.HTTP_404_NOT_FOUND,
    ReservaYaCanceladaError: status.HTTP_409_CONFLICT,
    LegajoNoCoincideError: status.HTTP_403_FORBIDDEN,
}


def _a_http(exc: Exception) -> HTTPException:
    """Traduce una excepción de dominio (`app.features.reservas.exceptions`)
    al `HTTPException` correspondiente, según la tabla del spec."""
    status_code = _MAPEO_ERRORES_HTTP[type(exc)]
    return HTTPException(status_code=status_code, detail=str(exc))


# `Limiter` propio (no compartido con `app.core.security`): cada instancia
# tiene su propio almacenamiento en memoria, así que las claves de acá no
# colisionan con las de `verificar_admin`.
_limiter = Limiter(key_func=get_remote_address)
_LIMITE_ALTAS = parse("10/hour")
_LIMITE_LECTURA = parse("60/minute")

_DEMASIADAS_REQUESTS = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Demasiadas solicitudes. Intente nuevamente más tarde.",
)


def _aplicar_rate_limit(request: Request, limite, clave: str) -> None:
    ip = get_remote_address(request)
    bajo_limite = _limiter.limiter.hit(limite, clave, ip)
    if not bajo_limite:
        raise _DEMASIADAS_REQUESTS


@router.get("/vehiculos", response_model=list[VehiculoPublico])
def listar_vehiculos_pool(
    request: Request,
    db: Session = Depends(get_db),
) -> list[VehiculoPublico]:
    """FR-01: listado público del pool de vehículos."""
    _aplicar_rate_limit(request, _LIMITE_LECTURA, "reservas-vehiculos")
    return service.listar_vehiculos_pool(db)


@router.get("/disponibilidad", response_model=list[DisponibilidadOut])
def consultar_disponibilidad(
    request: Request,
    desde: datetime,
    hasta: datetime,
    db: Session = Depends(get_db),
) -> list[DisponibilidadOut]:
    """FR-04: disponibilidad de cada vehículo del pool para un rango."""
    _aplicar_rate_limit(request, _LIMITE_LECTURA, "reservas-disponibilidad")
    return service.consultar_disponibilidad(db, desde, hasta)


@router.post("", response_model=ReservaOut, status_code=status.HTTP_201_CREATED)
def crear_reserva(
    request: Request,
    data: ReservaCreate,
    db: Session = Depends(get_db),
) -> ReservaOut:
    """FR-02: alta de una reserva."""
    _aplicar_rate_limit(request, _LIMITE_ALTAS, "reservas-post")
    ip_origen = request.client.host if request.client else "desconocido"
    try:
        return service.crear_reserva(db, data, ip_origen)
    except (VehiculoNoEncontradoError, VehiculoNoActivoError, ReservaSolapadaError) as exc:
        raise _a_http(exc) from exc


@router.get("", response_model=list[ReservaListItem])
def listar_reservas(
    request: Request,
    periodo: FiltroPeriodoReserva | None = None,
    db: Session = Depends(get_db),
) -> list[ReservaListItem]:
    """FR-01/FR-02: listado público de todas las reservas, opcionalmente
    filtrado por `periodo` (`futuras`/`en_curso`/`pasadas`, puramente
    temporal — no excluye reservas `cancelada`)."""
    _aplicar_rate_limit(request, _LIMITE_LECTURA, "reservas-listado")
    return service.listar_reservas(db, periodo)


@router.patch("/{reserva_id}/cancelar", response_model=ReservaOut)
def cancelar_reserva(
    request: Request,
    reserva_id: int,
    data: CancelarReservaRequest,
    db: Session = Depends(get_db),
) -> ReservaOut:
    """FR-03: cancela una reserva propia, validando que el `legajo`
    indicado coincida con el de la reserva (AC-06)."""
    _aplicar_rate_limit(request, _LIMITE_ALTAS, "reservas-cancelar")
    ip_origen = request.client.host if request.client else "desconocido"
    try:
        return service.cancelar_reserva(db, reserva_id, data.legajo, ip_origen)
    except (ReservaNoEncontradaError, ReservaYaCanceladaError, LegajoNoCoincideError) as exc:
        raise _a_http(exc) from exc
