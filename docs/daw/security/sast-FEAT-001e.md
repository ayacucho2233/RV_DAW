# SAST — FEAT-001e: Integración con el ciclo de vida del vehículo

| Campo | Valor |
|---|---|
| Ticket | FEAT-001e |
| Fase | CODE (closeout) |
| Alcance | `backend/app/features/reservas/repository.py` (Block 1), `backend/app/features/vehiculos/{exceptions.py,service.py,router.py}` (Block 1), `frontend/src/features/vehiculos/VehiculosAdminPage.jsx` (Block 1). Block 2 no agrega código de producción (solo tests). |
| Fecha | 2026-08-08 |

## Secretos

- ✅ Sin secretos hardcodeados (grep de patrones `password/secret/api_key/token` sobre el diff completo: 0 matches relevantes).
- ✅ `.env` en `.gitignore`, sin `.env` real trackeado.
- N/A este ticket no introduce credenciales nuevas.

## Inyección

- ✅ F-SAST-02 (SQL injection): `existe_activa_para_vehiculo` (`repository.py:74-82`) usa `select()` de SQLAlchemy con parámetros ORM (`Reserva.vehiculo_id == vehiculo_id`, `Reserva.estado == EstadoReserva.activa`) — sin SQL crudo, sin concatenación de strings.
- ✅ F-SAST-03 (command injection): sin `os.system`/`subprocess`/`eval`/`exec` en el diff.
- N/A F-SAST-05 (path traversal): sin manejo de rutas de archivo.

## XSS y funciones inseguras

- ✅ F-SAST-06 (XSS): el único cambio de `VehiculosAdminPage.jsx` es eliminar una entrada de un objeto literal (`MENSAJES_ERROR[409]`) — sin `innerHTML`/`dangerouslySetInnerHTML`. El texto que ahora se muestra (`error.detail`) sigue renderizándose vía interpolación JSX estándar, escapada por React por defecto (mismo mecanismo ya usado en toda la app).
- ✅ F-SAST-04/17 (eval/exec/deserialización insegura): 0 ocurrencias.
- N/A F-SAST-08 (crypto débil): sin manejo de contraseñas/hashing en este ticket.

## Resto de categorías obligatorias

- N/A F-SAST-07 (SSRF): sin llamadas salientes a URLs derivadas de input de usuario.
- ✅ F-SAST-09 (debug en producción): sin `debug=True` introducido.
- ✅ F-SAST-10 (logging de datos sensibles): `dar_de_baja_temporal`/`dar_de_baja_definitiva` ahora también loguean el camino de rechazo (`_log_operacion(..., vehiculo_id, "rechazada")`, agregado por el implementer más allá de lo pedido por el spec — cierra proactivamente el riesgo TM-E-01 del threat model, que había quedado aceptado sin mitigar). Confirmado que `_log_operacion` de `vehiculos` nunca recibe `nombre_empleado`/`legajo`/`licencia` — solo `operacion`, `vehiculo_id`, `resultado`, `timestamp`. Sin PII en ningún camino, éxito o rechazo.
- N/A F-SAST-11 (upload sin restricciones): sin endpoints de carga de archivos.
- N/A F-SAST-12 (CSRF): mismo esquema que tickets previos — los endpoints de baja ya exigían `verificar_admin` (HTTP Basic) sin cookies de sesión ambient, sin cambios en este ticket.
- ✅ F-SAST-14 (validación de input incompleta): `vehiculo_id` sigue siendo un path param `int` validado por FastAPI antes de llegar a `service.py` (sin cambios). Sin input nuevo introducido por este ticket.
- ✅ F-SAST-15 (manejo de errores inseguro): `router.py` sigue usando exclusivamente `_a_http`/`_MAPEO_ERRORES_HTTP`, que solo traduce `VehiculoDomainError`/subclases (nunca una excepción cruda). `VehiculoConReservasActivasError.__str__()` expone únicamente `vehiculo_id` (ya conocido por el caller) y el hecho "tiene reservas activas" — sin PII (`legajo`/`nombre_empleado`/`licencia` no aparecen en ningún mensaje de error de este ticket, confirmado por inspección de `exceptions.py`).

## Mitigaciones del threat model (verificadas en código)

- ✅ **TM-E-01** (repudio — rechazo de baja sin log, originalmente aceptado como riesgo LOW sin mitigar): el implementer agregó `_log_operacion(..., "rechazada")` en el `except VehiculoDomainError` de ambos métodos de baja, cerrando el gap más allá de lo que el spec exigía. Ahora simétrico con el patrón ya usado en `reservas.service`.
- ✅ **TM-E-02** (information disclosure — mensaje 409 sin enmascarar en el frontend): confirmado que solo excepciones de `VehiculoDomainError` llegan a `error.detail` — sin excepciones crudas ni stack traces expuestos.

## Dependencias (F-SAST-13/16)

- **Backend** (`pip-audit` sobre `requirements.txt`): ✅ 0 vulnerabilidades conocidas. Sin dependencias nuevas.
- **Frontend** (`npm audit --omit=dev`): ✅ 0 vulnerabilidades. Sin dependencias nuevas.

## Suppressions

Ninguna. No hay hallazgos Medium/High/Critical.

## Resumen

```
┌─────────────────────────────────────────────────────────────┐
│  /daw-security-sast — PASSED                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Secretos: ✅ 0 hallazgos                                    │
│  Inyección: ✅ 0 hallazgos                                    │
│  XSS / funciones inseguras: ✅ 0 hallazgos                    │
│  Input validation / error handling: ✅ 0 hallazgos            │
│  Mitigaciones threat model (TM-E-01/02): ✅ ambas cerradas —  │
│    TM-E-01 mejorado más allá de lo pedido por el spec          │
│  CSRF: N/A (sin cambios en auth)                               │
│  Dependencias backend (pip-audit): ✅ 0 vulnerabilidades       │
│  Dependencias frontend (npm audit): ✅ 0 vulnerabilidades      │
│                                                              │
│  Suppressions: 0                                              │
│                                                              │
│  ────────────────────────────────────────────────────────────│
│  Total: 0 vulnerabilidades bloqueantes abiertas                │
│  Report: docs/daw/security/sast-FEAT-001e.md                  │
│  Next: gates.sast = true → cerrar CODE, avanzar a VERIFY       │
└─────────────────────────────────────────────────────────────┘
```
