"""Excepciones de dominio del feature `vehiculos`.

Estas excepciones NO conocen HTTP: las levantan `service.py`/`repository.py`
y es `router.py` (Block 3) quien las traduce a códigos de respuesta HTTP.
Mantenerlas separadas de FastAPI permite testear `service.py` sin levantar
ningún servidor y evita que `service.py`/`repository.py` filtren detalle de
transporte hacia capas que no deberían conocerlo (AGENTS.md: "Tipar
errores; nunca captura silenciosa").
"""


class VehiculoDomainError(Exception):
    """Clase base de las excepciones de dominio de `vehiculos`."""


class PatenteYaExisteError(VehiculoDomainError):
    """La patente ya está en uso por otro vehículo del pool (FR-08/FR-09).

    Se levanta tanto por el chequeo previo en `service.py` como por la
    traducción de `IntegrityError` en `repository.py` (mitigación TM-03 del
    threat model: cierra la condición de carrera TOCTOU entre ambos).
    """

    def __init__(self, patente: str):
        self.patente = patente
        super().__init__(f"La patente '{patente}' ya existe en el pool de vehículos.")


class TipoInvalidoError(VehiculoDomainError):
    """El tipo de vehículo no es 'auto' ni 'camioneta' (FR-10/FR-11).

    En la práctica, Pydantic ya bloquea esto en `schemas.py` (`Literal`).
    Esta excepción es la validación defensiva que hace `service.py` por si
    algún caller interno invoca los métodos del servicio con un objeto que
    no pasó por el schema.
    """

    def __init__(self, tipo):
        self.tipo = tipo
        super().__init__(
            f"El tipo de vehículo '{tipo}' no es válido. Debe ser 'auto' o 'camioneta'."
        )


class TransicionEstadoInvalidaError(VehiculoDomainError):
    """La transición de estado solicitada no está permitida (FR-03/FR-04/FR-06/FR-07)."""

    def __init__(self, estado_actual, accion: str):
        self.estado_actual = estado_actual
        self.accion = accion
        super().__init__(
            f"No se puede realizar la operación '{accion}' desde el estado "
            f"'{estado_actual}'."
        )


class VehiculoNoEncontradoError(VehiculoDomainError):
    """No existe ningún vehículo con el id solicitado."""

    def __init__(self, vehiculo_id: int):
        self.vehiculo_id = vehiculo_id
        super().__init__(f"No se encontró el vehículo con id {vehiculo_id}.")


class VehiculoConReservasActivasError(VehiculoDomainError):
    """El vehículo tiene reservas activas y no puede darse de baja (FR-01/AC-01/AC-02)."""

    def __init__(self, vehiculo_id: int):
        self.vehiculo_id = vehiculo_id
        super().__init__(
            f"El vehículo con id {vehiculo_id} tiene reservas activas y no puede darse de baja."
        )
