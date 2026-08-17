# SAST — FIX-003

| Campo | Valor |
|-------|-------|
| Ticket | FIX-003 |
| Tier | FIX |
| Fecha | 2026-08-17 |
| Alcance | 14 archivos modificados + `backend/ruff.toml` (nuevo) |

## Resumen

Configuración de linters (ruff/eslint) + correcciones mecánicas de estilo. Ningún cambio de lógica
de negocio, de superficie de API, ni de flujo de datos. El único archivo con código de producción
tocado es `frontend/src/api/client.js`, donde se elimina una rama de fallback muerta
(`Buffer.from(...)`) manteniendo exactamente el mismo cálculo de Basic Auth (`btoa`).

## Hallazgos

| Categoría | Regla | Resultado |
|-----------|-------|-----------|
| Secretos hardcodeados | F-SAST-01 | ✅ Clean — sin credenciales/tokens en el diff |
| Inyección SQL/NoSQL | F-SAST-02 | ✅ Clean — sin queries nuevas; los `with` combinados y `dict()`→literal no cambian el SQL parametrizado existente |
| Inyección de comandos | F-SAST-03 | ✅ Clean — `subprocess.run` ya usaba lista de args (no shell), `check=False` explícito no cambia superficie |
| Auth / Basic Auth (client.js) | — | ✅ Clean — se elimina una rama muerta, el cálculo de `btoa` que sí se ejecuta es idéntico al anterior |
| XSS | F-SAST-06 | ✅ Clean — no aplica (sin HTML nuevo) |
| Dependencias | F-SAST-13/16 | ✅ Clean — sin dependencias nuevas ni modificadas |

## Suppressions

| Archivo | Regla | Disposición | Justificación |
|---|---|---|---|
| `backend/tests/test_reservas_service.py:152-153` | DTZ001 (ruff) | Suprimida (`noqa`) | Datetimes deliberadamente naive para testear que la app los rechaza (TM-C-03); agregar tzinfo anularía el test. Documentado inline y en el RCA. |

## Veredicto

**PASSED** — 0 Critical, 0 High, 0 Medium sin suprimir. `gates.sast = true`.
