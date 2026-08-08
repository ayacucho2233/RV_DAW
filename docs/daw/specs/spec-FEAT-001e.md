# Spec FEAT-001e: Integración con el ciclo de vida del vehículo

| Field | Value |
|-------|-------|
| Ticket | FEAT-001e |
| PRD | docs/daw/prd/prd-FEAT-001e.md |
| Tier | FEATURE |
| Date | 2026-08-08 |
| Spec loops | 0 |

## Summary

Agrega una validación de reservas activas sobre los endpoints de baja de vehículos ya existentes
(FEAT-001a), reutilizando el mismo mecanismo de lock (`SELECT ... FOR UPDATE` sobre la fila del
vehículo) que ya usa `reservas.service.crear_reserva` para prevenir condiciones de carrera entre
ambas operaciones sobre el mismo `vehiculo_id`. FR-02 (reservas pasadas visibles tras la baja) ya
está cubierto por el código existente — este ticket solo lo confirma con tests explícitos.

## Coverage: PRD → blocks

| Requirement | Covered by |
|---|---|
| FR-01 | Block 1 |
| FR-02 | Block 2 |
| NFR-01 | Strategy: `existe_activa_para_vehiculo` es un `SELECT EXISTS` sobre el índice existente `ix_reservas_vehiculo_fechas` (columna líder `vehiculo_id`, alta selectividad); sin JOIN, sin escaneo completo de tabla |

## Dependencies between blocks

Ninguna — Block 1 y Block 2 son independientes entre sí (Block 2 no depende de código nuevo de
Block 1). Se implementan en orden por prolijidad (Block 1 primero, ya que es el cambio funcional;
Block 2 es de verificación).

## Nota de dependencia cruzada (D-06)

Este ticket introduce `vehiculos.service` → `reservas.repository` (lectura, sin JOIN). Ya existía la
dirección opuesta (`reservas.service` → `vehiculos.repository`, documentada como D-01/D-02 en los
PRD de reservas). Con FEAT-001e el acoplamiento entre ambos features pasa a ser **bidireccional**,
siempre de solo lectura y siempre a nivel repository (nunca service→service). Confirmado por
`daw-impact-scanner`/`daw-arch-auditor` en PLAN: sin import circular, sin violación de "layer
separation" (la regla aplica dentro de un feature, no entre features). Aceptado explícitamente
como el costo de este ticket — si un futuro cambio necesitara una TERCERA dirección de dependencia
cruzada o lógica de negocio compartida entre `vehiculos` y `reservas`, es la señal de extraer un
servicio compartido en vez de seguir sumando acoplamiento cruzado.

## Block 1 — Bloquear baja de vehículos con reservas activas

**Files**
- `backend/app/features/reservas/repository.py` (modified) — nuevo `existe_activa_para_vehiculo`
- `backend/app/features/vehiculos/exceptions.py` (modified) — nueva `VehiculoConReservasActivasError`
- `backend/app/features/vehiculos/service.py` (modified) — `dar_de_baja_temporal`/`dar_de_baja_definitiva`
- `backend/app/features/vehiculos/router.py` (modified) — mapeo HTTP de la nueva excepción
- `frontend/src/features/vehiculos/VehiculosAdminPage.jsx` (modified) — deja de enmascarar el `detail` del backend para 409
- `backend/tests/test_vehiculos_service.py` (modified)
- `backend/tests/test_vehiculos_router.py` (modified)
- `frontend/src/features/vehiculos/VehiculosAdminPage.test.jsx` (modified)

**Logic**

`reservas/repository.py` agrega:
```python
def existe_activa_para_vehiculo(db: Session, vehiculo_id: int) -> bool:
    """¿Existe alguna reserva con estado 'activa' para este vehículo,
    sin calificador temporal (FR-01/AC-01/AC-02)? Un SELECT EXISTS,
    no un listar_todas+filtrar en Python — evita traer filas de más."""
    stmt = select(Reserva.id).where(
        Reserva.vehiculo_id == vehiculo_id,
        Reserva.estado == EstadoReserva.activa,
    ).limit(1)
    return db.execute(stmt).scalar_one_or_none() is not None
```

`vehiculos/exceptions.py` agrega:
```python
class VehiculoConReservasActivasError(VehiculoDomainError):
    """El vehículo tiene reservas activas y no puede darse de baja (FR-01/AC-01/AC-02)."""

    def __init__(self, vehiculo_id: int):
        self.vehiculo_id = vehiculo_id
        super().__init__(
            f"El vehículo con id {vehiculo_id} tiene reservas activas y no puede darse de baja."
        )
```

`vehiculos/service.py` — en `dar_de_baja_temporal` y `dar_de_baja_definitiva`:
1. Cambiar `repository.obtener_por_id(db, vehiculo_id)` por
   `repository.obtener_por_id_con_lock(db, vehiculo_id)` (mismo método que usa
   `reservas.service.crear_reserva`; serializa esta operación con cualquier `crear_reserva`
   concurrente sobre el mismo `vehiculo_id` — mitigación de R-01 del PRD).
2. Import a nivel de módulo: `from app.features.reservas import repository as reservas_repository`.
3. Tras validar la transición de estado (chequeo ya existente, sin cambios) y ANTES de mutar
   `vehiculo.estado`: `if reservas_repository.existe_activa_para_vehiculo(db, vehiculo_id): raise VehiculoConReservasActivasError(vehiculo_id)`.
4. Envolver el cuerpo en `try/except VehiculoDomainError: db.rollback(); raise` — mismo patrón que
   `reservas.service.crear_reserva`/`cancelar_reserva` (hallazgo WARN de `daw-arch-auditor` en
   PLAN: con el lock recién agregado, liberar la fila explícitamente en el camino de error evita
   depender del cierre implícito de la sesión bajo carga, relevante para NFR-01).

`vehiculos/router.py`:
- Agregar `VehiculoConReservasActivasError: status.HTTP_409_CONFLICT` a `_MAPEO_ERRORES_HTTP`.
- Agregar `VehiculoConReservasActivasError` a la tupla `except (...)` de `dar_de_baja_temporal` y
  `dar_de_baja_definitiva`.

`VehiculosAdminPage.jsx`:
- Sacar la línea `409: "La operación no es válida para el estado actual del vehículo."` de
  `MENSAJES_ERROR`. `mensajeDeError` cae entonces a `error.detail` (ya poblado por `vehiculosApi.js`
  desde `error.response.data.detail`), mostrando el mensaje real del backend para las 2 causas
  posibles de 409 en esta página (transición inválida, y ahora reservas activas). Sin lógica de
  negocio nueva — el frontend nunca decide si hay reservas activas, solo muestra lo que el backend
  ya determinó.

**API contract (delta sobre los endpoints existentes de FEAT-001a — método/path/auth sin cambios)**

- `PATCH /vehiculos/{vehiculo_id}/baja-temporal` — auth: `verificar_admin` (HTTP Basic, sin cambios).
  Request: sin body. Response 200: `VehiculoOut` (sin cambios). Error codes: `404` (sin cambios),
  `409` (ahora dos causas posibles: transición inválida — sin cambios — o reservas activas — nueva).
- `PATCH /vehiculos/{vehiculo_id}/baja-definitiva` — mismo auth, mismo request/response 200. Error
  codes: `404` (sin cambios), `409` (dos causas, igual que arriba).

**Error handling**

- `VehiculoNoEncontradoError` (404) — **sin cambios, ya existente**. Cubierto por los tests
  pre-existentes `test_baja_temporal_vehiculo_inexistente`/`test_baja_definitiva_vehiculo_inexistente`
  (`test_vehiculos_service.py`) y sus equivalentes HTTP en `test_vehiculos_router.py` — no se
  retestea en este bloque, solo se preserva.
- `TransicionEstadoInvalidaError` (409) — **sin cambios, ya existente**. Cubierto por
  `test_baja_temporal_transicion_invalida`/`test_baja_definitiva_transicion_invalida` y sus
  equivalentes HTTP, ya presentes en la suite — no se retestea en este bloque.
- `VehiculoConReservasActivasError` (409, **nueva**) — el vehículo existe y la transición de estado
  sería válida, pero tiene ≥1 reserva con `estado == 'activa'`. Cubierto por los 4 tests nuevos de
  este bloque que la ejercitan explícitamente (2 a nivel servicio, 2 a nivel HTTP, ver "Required
  tests").
- Orden de validación en `dar_de_baja_*`: (1) existe → 404, (2) transición de estado válida → 409,
  (3) sin reservas activas → 409. El orden (2) antes de (3) preserva el comportamiento actual para
  los casos que no involucran reservas (un vehículo ya en `baja_definitiva` sigue rechazando
  `baja_temporal` por transición inválida, sin necesidad de consultar reservas).

**Required tests**

- [ ] `test_baja_temporal_rechazada_con_reserva_activa` — AC-01: vehículo `activo` con 1 reserva
      `activa` → `VehiculoConReservasActivasError`, el vehículo permanece `activo`.
- [ ] `test_baja_definitiva_rechazada_con_reserva_activa` — AC-02: ídem para baja definitiva.
- [ ] `test_baja_temporal_permitida_sin_reservas_activas` — vehículo `activo` sin reservas, o solo
      con reservas `cancelada` → baja OK (no regresión).
- [ ] `test_baja_definitiva_permitida_con_reserva_cancelada` — vehículo con una reserva `cancelada`
      (no activa) → baja OK, confirma que el filtro es por `estado`, no por existencia de cualquier
      reserva.
- [ ] `test_baja_vs_crear_reserva_concurrencia` — AC-01/AC-02/R-01: dos conexiones reales (mismo
      patrón que `test_crear_reserva_concurrencia_solo_una_confirmada` de
      `test_reservas_service.py`), una dando de baja y otra creando una reserva sobre el mismo
      `vehiculo_id` en paralelo → nunca ambas operaciones terminan en éxito (o la baja se rechaza
      porque la reserva ya existe, o la reserva se rechaza porque el vehículo ya no está `activo`).
- [ ] `test_patch_baja_temporal_con_reserva_activa_409` — AC-01 a nivel HTTP, con el mensaje de
      `VehiculoConReservasActivasError` en el body.
- [ ] `test_patch_baja_definitiva_con_reserva_activa_409` — AC-02 a nivel HTTP.
- [ ] `test_muestra_mensaje_especifico_de_reservas_activas` (frontend) — mock de `bajaTemporal`
      rechazando con `error.status = 409` y `error.detail = "El vehículo con id 1 tiene reservas
      activas y no puede darse de baja."` → el `role="alert"` muestra ese texto verbatim, no el
      genérico anterior.

**Completion criterion**

Los 8 tests listados pasan; `dar_de_baja_temporal`/`dar_de_baja_definitiva` rechazan con 409 y sin
persistir el cambio de estado cuando el vehículo tiene ≥1 reserva `activa`; el test de concurrencia
demuestra que el lock serializa correctamente contra `crear_reserva`.

## Block 2 — Confirmar que el listado conserva reservas pasadas de vehículos dados de baja

**Files**
- `backend/tests/test_reservas_service.py` (modified)
- `backend/tests/test_reservas_router.py` (modified)

**Logic**

Sin cambios de código de producción. `reservas.service.listar_reservas` ya construye
`vehiculos_por_id` a partir de `vehiculos_repository.listar(db)` (sin filtro de `estado`), así que
una reserva de un vehículo en `baja_temporal`/`baja_definitiva` ya aparece en el listado igual que
una de un vehículo `activo`. Este bloque agrega tests que lo prueban explícitamente, para que AC-03
y AC-04 tengan evidencia propia en vez de depender de una lectura del código.

**Error handling**

N/A — este bloque no agrega manejo de errores nuevo.

**Required tests**

- [ ] `test_listar_reservas_incluye_reserva_de_vehiculo_en_baja_temporal` — AC-03: una reserva
      pasada (`fecha_fin` en el pasado) de un vehículo en `baja_temporal` sigue apareciendo en
      `listar_reservas` (sin filtro y con `periodo="pasadas"`).
- [ ] `test_listar_reservas_incluye_reserva_de_vehiculo_en_baja_definitiva` — AC-04: ídem para
      `baja_definitiva`.
- [ ] `test_get_reservas_incluye_reserva_de_vehiculo_dado_de_baja_200` — AC-03/AC-04 a nivel HTTP
      (`GET /reservas`), confirmando que `patente`/`tipo` del vehículo dado de baja siguen
      resolviéndose correctamente en la respuesta.

**Completion criterion**

Los 3 tests pasan, confirmando sin ambigüedad que ninguna baja de vehículo oculta sus reservas
pasadas del listado.

## Final verification

- Suite completa (backend + frontend) en verde, incluyendo los 11 tests nuevos de este ticket.
- Un vehículo con al menos una reserva `activa` no puede pasar a `baja_temporal` ni a
  `baja_definitiva` por ningún camino (service directo o vía HTTP).
- Un vehículo sin reservas activas (0 reservas, o solo `cancelada`) se sigue dando de baja
  normalmente — sin regresión sobre FEAT-001a.
- Las reservas pasadas de un vehículo dado de baja (cualquiera de los 2 estados) siguen visibles en
  `GET /reservas`.
- SAST sin vulnerabilidades bloqueantes sobre los archivos tocados.
