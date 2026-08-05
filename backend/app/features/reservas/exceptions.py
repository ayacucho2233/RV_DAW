"""Excepciones de dominio del feature `reservas`.

Estas excepciones NO conocen HTTP: las levantan `service.py`/`repository.py`
y es `router.py` (Block 3) quien las traduce a códigos de respuesta HTTP.
Mantenerlas separadas de FastAPI permite testear `service.py` sin levantar
ningún servidor y evita que `service.py`/`repository.py` filtren detalle de
transporte hacia capas que no deberían conocerlo (AGENTS.md: "Tipar
errores; nunca captura silenciosa"). Mismo patrón que
`vehiculos/exceptions.py`.
"""


class ReservaDomainError(Exception):
    """Clase base de las excepciones de dominio de `reservas`.

    Block 2 agrega las subclases concretas (`VehiculoNoEncontradoError`,
    `VehiculoNoActivoError`, `ReservaSolapadaError`).
    """
