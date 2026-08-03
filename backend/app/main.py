"""Punto de entrada de la app FastAPI.

Instancia mínima por ahora: el router de vehículos, CORS y el exception
handler genérico se agregan en Block 3.
"""
from fastapi import FastAPI

app = FastAPI(title="Reserva de Vehículos Corporativos — Admin API")
