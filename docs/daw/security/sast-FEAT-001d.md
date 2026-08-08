# SAST — FEAT-001d: Listado, filtros y cancelación de reservas

| Campo | Valor |
|---|---|
| Ticket | FEAT-001d |
| Fase | CODE (closeout) |
| Alcance | `backend/app/features/reservas/{router.py,service.py,repository.py,schemas.py,exceptions.py}` (Blocks 1-2), `frontend/src/App.jsx` + `frontend/src/features/reservas/{reservasApi.js,ReservasListado.jsx}` (Block 3) |
| Fecha | 2026-08-08 |

## Secretos

- ✅ Sin secretos hardcodeados (grep de patrones `password/secret/api_key/token`/`md5`/`sha1` sobre los archivos del diff: 0 matches — la única mención de "password" es un comentario JSDoc en `App.jsx` describiendo la forma del objeto de sesión del admin, no un valor).
- ✅ `.env` en `.gitignore`, sin `.env` real trackeado.
- N/A este bloque no introduce credenciales nuevas (feature público por diseño, igual que FEAT-001c).

## Inyección

- ✅ F-SAST-02 (SQL injection): sin SQL crudo. Los métodos nuevos de `repository.py` (`listar_todas`, `obtener_por_id`, `guardar`) usan exclusivamente `select()`/`db.get()`/`db.add()` de SQLAlchemy con parámetros ORM (`repository.py:74-92`).
- ✅ F-SAST-03 (command injection): sin `os.system`/`subprocess`/`eval`/`exec` en el diff.
- N/A F-SAST-05 (path traversal): sin manejo de rutas de archivo derivadas de input de usuario.

## XSS y funciones inseguras

- ✅ F-SAST-06 (XSS): sin `innerHTML`/`dangerouslySetInnerHTML` en `ReservasListado.jsx` ni en `App.jsx` (grep limpio); todo el render (patente, nombre_empleado, destino, mensajes de error/éxito) pasa por interpolación JSX estándar, escapada por React por defecto.
- ✅ F-SAST-04/17 (eval/exec/deserialización insegura): 0 ocurrencias.
- N/A F-SAST-08 (crypto débil): este bloque no maneja contraseñas ni hashing.

## Resto de categorías obligatorias

- N/A F-SAST-07 (SSRF): sin llamadas salientes a URLs derivadas de input de usuario.
- ✅ F-SAST-09 (debug en producción): sin `debug=True` introducido.
- ✅ F-SAST-10 (logging de datos sensibles): `service.py:listar_reservas`/`cancelar_reserva` reusan `_log_operacion` ya existente (mismo patrón que FEAT-001c) — confirmado que ninguna llamada nueva pasa `nombre_empleado` ni `licencia`; `legajo` se loguea deliberadamente (identificador operativo, no secreto, mitigación TM-D-03 del threat model).
- N/A F-SAST-11 (upload sin restricciones): sin endpoints de carga de archivos.
- N/A F-SAST-12 (CSRF): mismo esquema que FEAT-001a/c — sin cookies de sesión ambient; los 2 endpoints nuevos (`GET /reservas`, `PATCH /reservas/{id}/cancelar`) son públicos por diseño, sin `Authorization`.
- ✅ F-SAST-14 (validación de input incompleta): `schemas.py` — `CancelarReservaRequest.legajo` con `min_length=1, max_length=20` (línea 103); `FiltroPeriodoReserva` es un `Literal["futuras","en_curso","pasadas"]` validado por Pydantic/FastAPI antes de llegar a `service.py` (rechaza cualquier otro valor con 422 automático).
- ✅ F-SAST-15 (manejo de errores inseguro): `router.py:_a_http` (líneas 81-85) solo expone `str(exc)` de las excepciones de dominio propias (`exceptions.py`, mensajes controlados con IDs numéricos, sin datos internos ni stack traces); el mapeo `_MAPEO_ERRORES_HTTP` cubre las 3 excepciones nuevas (`ReservaNoEncontradaError`→404, `ReservaYaCanceladaError`→409, `LegajoNoCoincideError`→403 con mensaje que no revela el legajo real).

## Mitigaciones del threat model (verificadas en código)

- ✅ **TM-D-01** (crítico — el listado no debe exponer `legajo`/`licencia`): `ReservaListItem` (`schemas.py:106-131`) expone únicamente `id, vehiculo_id, nombre_empleado, fecha_inicio, fecha_fin, destino, estado, patente, tipo, created_at, updated_at` — sin `legajo` ni `licencia`. `ReservasListado.jsx` no los renderiza (no los recibe del backend).
- ✅ **TM-D-02** (DoS — rate limiting propio por endpoint): `router.py:_aplicar_rate_limit` aplicado a `GET /reservas` (60/min, clave `"reservas-listado"`) y `PATCH /reservas/{id}/cancelar` (10/hora, clave `"reservas-cancelar"`), independientes entre sí y de los 3 endpoints preexistentes.
- ✅ **TM-D-03** (repudio — log de cancelación): `cancelar_reserva` loguea `{operacion="cancelar_reserva", vehiculo_id, legajo, resultado, ip_origen, timestamp}` tanto en éxito como en rechazo (`service.py:209-214`).

## Dependencias (F-SAST-13/16)

- **Backend** (`pip-audit` sobre `requirements.txt`): ✅ 0 vulnerabilidades conocidas. Este bloque no agrega dependencias nuevas.
- **Frontend** (`npm audit --omit=dev`): ✅ 0 vulnerabilidades. Este bloque no agrega dependencias nuevas.

## Hallazgo informativo (no bloqueante, fuera de alcance de este bloque)

- ℹ️ `backend/.coverage` aparece como untracked en el working tree — artefacto de la corrida de `pytest --cov` de una sesión anterior, no generado por los cambios de este bloque, no contiene código ni secretos (solo conteos de líneas ejecutadas). No se incluyó en el commit del bloque. Recomendación (no bloqueante): agregar `backend/.coverage` a `.gitignore` en un commit de chore separado.

## Suppressions

Ninguna. No hay hallazgos Medium/High/Critical que requieran documentación de excepción.

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
│  Mitigaciones threat model (TM-D-01/02/03): ✅ verificadas    │
│    en código                                                 │
│  CSRF: N/A (sin credencial ambient de navegador)              │
│  Dependencias backend (pip-audit): ✅ 0 vulnerabilidades       │
│  Dependencias frontend (npm audit): ✅ 0 vulnerabilidades      │
│                                                              │
│  Suppressions: 0                                              │
│                                                              │
│  ────────────────────────────────────────────────────────────│
│  Total: 0 vulnerabilidades bloqueantes abiertas                │
│  Report: docs/daw/security/sast-FEAT-001d.md                  │
│  Next: gates.sast = true → cerrar CODE, avanzar a VERIFY       │
└─────────────────────────────────────────────────────────────┘
```
