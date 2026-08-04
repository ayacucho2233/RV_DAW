"""Punto de entrada de la app FastAPI.

Registra el router de `vehiculos` (Block 3), CORS restringido al origen
exacto del frontend (nunca `["*"]`, ver AGENTS.md) y un exception handler
genérico para cualquier error no anticipado por el router: loguea el
detalle completo del lado del servidor y responde un 500 sin volcar el
mensaje interno ni el traceback al cliente (mitigación TM-03 del threat
model, complementa la traducción de `IntegrityError` en `repository.py`).
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.features.vehiculos.router import router as vehiculos_router

logger = logging.getLogger(__name__)

app = FastAPI(title="Reserva de Vehículos Corporativos — Admin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vehiculos_router)


@app.exception_handler(Exception)
async def manejador_error_generico(request: Request, exc: Exception) -> JSONResponse:
    """TM-03: nunca expone el mensaje interno ni el traceback al cliente."""
    logger.exception("Error no anticipado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
