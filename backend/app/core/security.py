"""Autenticación HTTP Basic para los endpoints de administración (Block 3).

`verificar_admin` es la dependency que protege los 6 endpoints de
`app.features.vehiculos.router`. Compara `credentials.username` contra
`ADMIN_USERNAME` y `credentials.password` (hasheado) contra
`ADMIN_PASSWORD_HASH` con `bcrypt.checkpw`. Ambas comparaciones se calculan
siempre, sin cortocircuito, y cualquier fallo levanta exactamente el mismo
`HTTPException(401, "Credenciales inválidas")` — nunca un mensaje distinto
según cuál campo falló (mitigación TM-05 del threat model: evita
enumeración de usuario).

Rate limiting (mitigación TM-02): máximo 5 intentos fallidos por IP por
minuto, compartido entre los 6 endpoints (la clave del contador no depende
del endpoint). Se implementa llamando directamente al `RateLimiter` que usa
`slowapi`/`limits` por debajo (`Limiter.limiter.hit(...)`) en lugar del
decorador `@limiter.limit(...)`, porque el requisito es contar solo los
intentos *fallidos*, no cada request — el decorador de slowapi limita todas
las llamadas al endpoint, no un subconjunto condicional.
"""
import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

_basic_auth = HTTPBasic()

# Un `Limiter` propio (no compartido con el resto de la app): expone
# `.limiter`, el `RateLimiter` de la librería `limits` que hace el conteo
# real, sin necesitar registrar middleware ni exception handler de slowapi.
_limiter = Limiter(key_func=get_remote_address)
_LIMITE_INTENTOS_FALLIDOS = parse("5/minute")
_CLAVE_RATE_LIMIT = "auth-fail"

_CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas",
    headers={"WWW-Authenticate": "Basic"},
)

_DEMASIADOS_INTENTOS = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Demasiados intentos fallidos. Intente nuevamente en unos minutos.",
)


def verificar_admin(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(_basic_auth),
) -> str:
    """Dependency de FastAPI que exige HTTP Basic válido para el admin único.

    Devuelve el username autenticado si las credenciales son correctas.
    """
    usuario_ok = credentials.username == settings.ADMIN_USERNAME
    password_ok = bcrypt.checkpw(
        credentials.password.encode("utf-8"),
        settings.ADMIN_PASSWORD_HASH.encode("utf-8"),
    )

    if not (usuario_ok and password_ok):
        ip = get_remote_address(request)
        bajo_limite = _limiter.limiter.hit(_LIMITE_INTENTOS_FALLIDOS, _CLAVE_RATE_LIMIT, ip)
        if not bajo_limite:
            raise _DEMASIADOS_INTENTOS
        raise _CREDENCIALES_INVALIDAS

    return credentials.username
