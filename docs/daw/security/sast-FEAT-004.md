# SAST Report FEAT-004: Consulta de reservas activas por patente

| Field | Value |
|-------|-------|
| Ticket | FEAT-004 |
| Date | 2026-08-17 |
| Scope | 10 archivos modificados/nuevos en `backend/app/features/{vehiculos,reservas}/`, la migración `0003`, y `frontend/src/features/reservas/{ConsultaPorPatente,reservasApi,ReservasListado}` |

## Secrets

- ✅ F-SAST-01: sin credenciales, tokens ni API keys hardcodeadas en ninguno de los 15 archivos
  tocados por este ticket (`grep -niE "password|secret|token|api_key|apikey"` sobre el diff completo,
  0 hallazgos fuera de comentarios/tests irrelevantes).

## Injection

- ✅ F-SAST-02: `obtener_por_patente_normalizada` (vehículos) y `listar_activas_por_vehiculo`
  (reservas) usan exclusivamente `select()`/`where()`/`func.upper()` de SQLAlchemy Core —
  parametrizado, sin concatenación de strings.
- ✅ La migración `0003` usa `op.create_index(..., [sa.text("lower(patente)")], unique=True)` — la
  expresión `lower(patente)` es un literal estático de DDL, no interpola ningún input de usuario.
- ✅ El path param `patente` en `GET /reservas/vehiculo/{patente}` está acotado por
  `Path(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9]+$")` — FastAPI/Pydantic lo valida antes de
  que llegue a `service.py`; ningún caracter fuera de ese patrón alcanza la query.
- ✅ F-SAST-03: sin `subprocess`/`os.system`/`exec` en ningún archivo tocado.

## XSS y funciones inseguras

- ✅ F-SAST-04/F-SAST-06: `ConsultaPorPatente.jsx` renderiza todo vía JSX estándar (React escapa por
  defecto); sin `dangerouslySetInnerHTML`, sin `eval`.

## Resto de categorías obligatorias

- ✅ F-SAST-07 (SSRF): no aplica, sin llamadas de red salientes controladas por input externo.
- ✅ F-SAST-09 (debug en producción): sin flags de debug ni logging verboso nuevo.
- ✅ F-SAST-10 (logging de datos sensibles): la consulta nueva no loguea nada (es de solo lectura,
  mismo criterio que los otros GETs de este router, que tampoco loguean); `ReservaListItem` sigue sin
  exponer `legajo`/`licencia`.
- ✅ F-SAST-14 (validación de input incompleta): `patente` validada por `Path(...)` en el backend;
  el `<input required>` del frontend complementa, sin reemplazar, esa validación server-side.
- ✅ F-SAST-15 (error handling que filtra internals): los mensajes de error (`VehiculoNoEncontradoError`)
  no exponen stack traces ni detalles internos, solo el identificador consultado.

## Dependencias

- ✅ F-SAST-13: `npm audit --omit=dev` → 0 vulnerabilidades. Este ticket no agrega dependencias
  nuevas de npm.
- ✅ F-SAST-16: `pip-audit -r backend/requirements.txt` → "No known vulnerabilities found". Este
  ticket no agrega dependencias nuevas de pip.

## Suppressions

Ninguna. 0 hallazgos Medium que requieran documentación de supresión.

## Resumen

- Total: 0 vulnerabilidades (0 Critical, 0 High, 0 Medium, 0 Low)
- Resultado: **PASSED**
