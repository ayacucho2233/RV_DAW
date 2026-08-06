# SAST — FEAT-001c: Consulta y creación de reservas

| Campo | Valor |
|---|---|
| Ticket | FEAT-001c |
| Fase | CODE (closeout) |
| Alcance | `backend/app/features/reservas/` + `backend/alembic/` (Blocks 1-3), `backend/app/main.py` (Block 3), `frontend/src/features/reservas/` + `frontend/src/App.jsx` (Block 4) |
| Fecha | 2026-08-06 |

## Secretos

- ✅ Sin secretos hardcodeados (grep de patrones `password/secret/api_key/token`/`md5`/`sha1` sobre los archivos del diff: 0 matches).
- ✅ `.env` en `.gitignore` (línea 17), sin `.env` real trackeado.
- N/A este feature no introduce credenciales nuevas (es público por diseño, ver PRD "Out of Scope: autenticación").

## Inyección

- ✅ F-SAST-02 (SQL injection): sin SQL crudo. `repository.py` usa exclusivamente `select()`/`with_for_update()` de SQLAlchemy con parámetros ORM (`repository.py:47-57,66-70`); la migración `0002_create_reservas.py` usa el DSL de Alembic (`op.create_table`/`op.create_index`), sin `execute()` de texto plano.
- ✅ F-SAST-03 (command injection): sin `os.system`/`subprocess`/`eval`/`exec` en el diff.
- N/A F-SAST-05 (path traversal): sin manejo de rutas de archivo derivadas de input de usuario.

## XSS y funciones inseguras

- ✅ F-SAST-06 (XSS): sin `innerHTML`/`dangerouslySetInnerHTML` en `frontend/src/features/reservas/` ni en `App.jsx` (grep limpio); todo el render de `patente`/`tipo`/`destino`/mensajes de error pasa por interpolación JSX estándar, escapada por React por defecto.
- ✅ F-SAST-04/17 (eval/exec/deserialización insegura): 0 ocurrencias.
- N/A F-SAST-08 (crypto débil): este feature no maneja contraseñas ni hashing.

## Resto de categorías obligatorias

- N/A F-SAST-07 (SSRF): sin llamadas salientes a URLs derivadas de input de usuario.
- ✅ F-SAST-09 (debug en producción): sin `debug=True` introducido.
- ✅ F-SAST-10 (logging de datos sensibles): `service.py:_log_operacion` (líneas 34-49) loguea `{operacion, vehiculo_id, legajo, resultado, ip_origen, timestamp}` — confirmado que **nunca** recibe `nombre_empleado` ni `licencia` (no forman parte de la firma de la función ni se referencian en el cuerpo), mitigación TM-C-04 del threat model. `legajo` se loguea deliberadamente (identificador operativo, no un secreto).
- N/A F-SAST-11 (upload sin restricciones): sin endpoints de carga de archivos.
- N/A F-SAST-12 (CSRF): mismo esquema que FEAT-001a — sin cookies de sesión ambient; estos 3 endpoints ni siquiera requieren `Authorization` (públicos por diseño). CORS restringe el origen exacto (`main.py`, sin cambios en este ticket), nunca `"*"`.
- ✅ F-SAST-14 (validación de input incompleta): `schemas.py` — campos de texto con `min_length=1`/`max_length` acorde a columna; `vehiculo_id: int = Field(..., gt=0)`; `fecha_inicio`/`fecha_fin` con `field_validator` que rechaza datetimes naive (líneas 20-23, 37-45) y `model_validator` que rechaza `fecha_fin <= fecha_inicio` (líneas 47-51) — cierra TM-C-03 y AC-04.
- ✅ F-SAST-15 (manejo de errores inseguro): `router.py:_a_http` (líneas 69-73) solo expone `str(exc)` de las 3 excepciones de dominio propias (`exceptions.py`, mensajes controlados sin datos internos); cualquier excepción no anticipada cae en el handler genérico ya existente en `main.py` (sin cambios, mismo mecanismo de FEAT-001a).

## Rate limiting (mitigación TM-C-02, no es una categoría F-SAST pero es un control de seguridad del bloque)

- ✅ `router.py:_aplicar_rate_limit` — `POST /reservas` limitado a 10/hora por IP, `GET /reservas/vehiculos` y `GET /reservas/disponibilidad` a 60/minuto por IP, cada uno con su propia clave de contador (líneas 80-93, 102, 114, 125). Sin esto, un feature sin autenticación quedaría expuesto a scraping/spam de reservas sin fricción.

## Dependencias (F-SAST-13/16)

- **Backend** (`pip-audit`): ✅ 0 vulnerabilidades conocidas.
- **Frontend** (`npm audit --production`): ✅ 0 vulnerabilidades. Este bloque no agrega ninguna dependencia nueva (decisión de PLAN: sin librería de ruteo); el estado de devDependencies ya fue remediado en el SAST de FEAT-001a.

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
│  Rate limiting (TM-C-02): ✅ implementado en los 3 endpoints  │
│  CSRF: N/A (sin credencial ambient de navegador)              │
│  Dependencias backend (pip-audit): ✅ 0 vulnerabilidades       │
│  Dependencias frontend (npm audit): ✅ 0 vulnerabilidades      │
│                                                              │
│  Suppressions: 0                                              │
│                                                              │
│  ────────────────────────────────────────────────────────────│
│  Total: 0 vulnerabilidades bloqueantes abiertas                │
│  Report: docs/daw/security/sast-FEAT-001c.md                  │
│  Next: gates.sast = true → cerrar CODE, avanzar a VERIFY       │
└─────────────────────────────────────────────────────────────┘
```
