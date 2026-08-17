# SAST Report FEAT-003: CI en GitHub Actions para PRs

| Field | Value |
|-------|-------|
| Ticket | FEAT-003 |
| Date | 2026-08-17 |
| Scope | `.github/workflows/ci.yml` (único archivo tocado por este ticket) + auditoría de dependencias existentes |

## Secrets

- ✅ F-SAST-01: sin API keys, passwords ni tokens hardcodeados. `grep -niE
  "secret|password|token|api_key|apikey"` sobre el workflow solo encuentra menciones en comentarios
  explicativos (líneas 15 y 19), documentando por qué no hay password en el servicio Postgres de
  test (riesgo aceptado F-TM-04 del threat model, no un secreto real).
- ✅ Ningún `secrets.*` de GitHub referenciado en el archivo.
- ✅ `.env` / `backend/.env` / `frontend/.env` siguen fuera del repo (`.gitignore`, sin cambios de
  este ticket).

## Injection

- ✅ F-SAST-02/F-SAST-03: no aplica — el workflow no construye queries ni comandos por
  concatenación; todos los `run:` son strings estáticos (`pip install -r requirements.txt`,
  `ruff check .`, `pytest`, `npm ci`, `npm run lint`, `npm test`).
- ✅ **GitHub Actions script injection** (patrón específico de CI, no cubierto por las categorías
  genéricas pero relevante aquí): `grep -n '\${{'` sobre el workflow no encuentra ninguna expresión
  de template — no hay interpolación de datos controlados por el autor del PR (título, body,
  branch name) dentro de ningún step `run:`. Es el patrón más seguro posible para este tipo de
  archivo.
- ✅ F-SAST-05 (path traversal): no aplica, no hay manejo de paths dinámicos.

## XSS y funciones inseguras

- ✅ F-SAST-04/F-SAST-06/F-SAST-08: no aplica — no hay `eval`, deserialización, HTML ni crypto en
  un workflow de CI.

## Resto de categorías obligatorias

- ✅ F-SAST-07 (SSRF): no aplica, sin llamadas de red controladas por input externo.
- ✅ F-SAST-09 (debug en producción): no aplica a CI; ningún flag `--verbose`/`-v` que exponga datos.
- ✅ F-SAST-10 (logging de datos sensibles): no aplica, no hay datos sensibles que loguear.
- ✅ F-SAST-11/F-SAST-12 (upload/CSRF): no aplica, el workflow no expone endpoints.
- ✅ F-SAST-14 (validación de input incompleta): no aplica, el workflow no acepta input estructurado.
- ✅ F-SAST-15 (error handling que filtra internals): los errores del workflow son los logs
  estándar de GitHub Actions (stdout/stderr de pytest/ruff/npm), no hay manejo custom que pueda
  filtrar algo distinto.

## Dependencias

- ✅ F-SAST-13: `npm audit --omit=dev` (frontend) → 0 vulnerabilidades.
- ✅ F-SAST-16: `pip-audit -r backend/requirements.txt` → "No known vulnerabilities found".
- Nota: este ticket no modifica `requirements.txt` ni `package-lock.json` — la auditoría se corrió
  sobre el estado actual del repo por completitud, no porque el diff las toque.

## Suppressions

Ninguna. 0 hallazgos Medium que requieran documentación de supresión.

## Resumen

- Total: 0 vulnerabilidades (0 Critical, 0 High, 0 Medium, 0 Low)
- Resultado: **PASSED**
