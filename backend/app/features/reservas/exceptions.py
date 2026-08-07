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
    """Clase base de las excepciones de dominio de `reservas`."""


class VehiculoNoEncontradoError(ReservaDomainError):
    """No existe ningún vehículo con el `vehiculo_id` solicitado."""

    def __init__(self, vehiculo_id: int):
        self.vehiculo_id = vehiculo_id
        super().__init__(f"No se encontró el vehículo con id {vehiculo_id}.")


class VehiculoNoActivoError(ReservaDomainError):
    """El vehículo existe pero no está en estado `activo` (FR-05/AC-08).

    Cubre `baja_temporal` y `baja_definitiva`: un vehículo dado de baja no
    debería poder reservarse aunque todavía no tenga reservas activas
    bloqueándolo.
    """

    def __init__(self, vehiculo_id: int, estado_actual):
        self.vehiculo_id = vehiculo_id
        self.estado_actual = estado_actual
        super().__init__(
            f"El vehículo con id {vehiculo_id} no está disponible para reservas "
            f"(estado actual: '{estado_actual}')."
        )


class ReservaSolapadaError(ReservaDomainError):
    """Existe otra reserva activa que se superpone con el período solicitado
    para el mismo vehículo (FR-03/AC-05, cierre de la carrera NFR-03/AC-06).
    """

    def __init__(self, vehiculo_id: int):
        self.vehiculo_id = vehiculo_id
        super().__init__(
            f"Ya existe una reserva activa que se superpone para el vehículo {vehiculo_id}."
        )


class ReservaNoEncontradaError(ReservaDomainError):
    """No existe ninguna reserva con el `reserva_id` solicitado (FR-03)."""

    def __init__(self, reserva_id: int):
        self.reserva_id = reserva_id
        super().__init__(f"No se encontró la reserva con id {reserva_id}.")


class ReservaYaCanceladaError(ReservaDomainError):
    """La reserva ya tiene `estado == cancelada`.

    Decisión de diseño confirmada con el usuario en PLAN: cancelar una
    reserva ya cancelada se rechaza explícitamente (409), en vez de
    responder éxito de forma idempotente — mismo criterio que
    `TransicionEstadoInvalidaError` aplica a las transiciones de estado de
    `vehiculos`.
    """

    def __init__(self, reserva_id: int):
        self.reserva_id = reserva_id
        super().__init__(f"La reserva con id {reserva_id} ya estaba cancelada.")


class LegajoNoCoincideError(ReservaDomainError):
    """El `legajo` indicado para cancelar no coincide con el de la reserva
    (FR-04/AC-06).

    El mensaje deliberadamente NO incluye el legajo real de la reserva —
    evitar filtrar ese dato por el camino de un mensaje de error.
    """

    def __init__(self, reserva_id: int):
        self.reserva_id = reserva_id
        super().__init__(
            f"El legajo indicado no coincide con el de la reserva {reserva_id}."
        )
