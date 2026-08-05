# SAST — FEAT-001a: Gestión del pool de vehículos

| Campo | Valor |
|---|---|
| Ticket | FEAT-001a |
| Fase | CODE (closeout) |
| Alcance | `backend/app/` (Blocks 1-3), `frontend/src/` (Block 4) |
| Fecha | 2026-08-05 |

## Secretos

- ✅ Sin secretos hardcodeados (grep de patrones `password/secret/api_key/token = "..."` sobre `backend/app` y `frontend/src`: 0 matches).
- ✅ `.env` en `.gitignore` (línea 17) y sin `.env` real trackeado en git (`git ls-files | grep '\.env$'` vacío).
- ✅ Credenciales de admin (`ADMIN_PASSWORD_HASH`) leídas desde variable de entorno, sin default silencioso (`backend/app/core/config.py`).

## Inyección

- ✅ F-SAST-02 (SQL injection): sin SQL crudo. `backend/app/features/vehiculos/repository.py` usa exclusivamente `select()` de SQLAlchemy con parámetros ORM (`repository.py:39-41,45`).
- ✅ F-SAST-03 (command injection): sin `os.system`/`subprocess`/`eval`/`exec` en `backend/app` ni `frontend/src`.
- N/A F-SAST-05 (path traversal): sin manejo de rutas de archivo derivadas de input de usuario en este ticket.

## XSS y funciones inseguras

- ✅ F-SAST-06 (XSS): sin `innerHTML`/`dangerouslySetInnerHTML` en `frontend/src` (React escapa por defecto; el panel no inyecta HTML crudo).
- ✅ F-SAST-04/17 (eval/exec/deserialización insegura): 0 ocurrencias.
- ✅ F-SAST-08 (crypto débil): password de admin verificado con `bcrypt.checkpw` (`backend/app/core/security.py:59-62`), no MD5/SHA1.

## Resto de categorías obligatorias

- N/A F-SAST-07 (SSRF): sin llamadas salientes a URLs derivadas de input de usuario.
- ✅ F-SAST-09 (debug en producción): sin `debug=True`/`DEBUG=True` en `backend/app`.
- ✅ F-SAST-10 (logging de datos sensibles): `service.py:52-58` loguea `{operacion, vehiculo_id, resultado, timestamp}` — nunca credenciales ni el header `Authorization` (confirmado por lectura directa, mitigación TM-04 del threat model).
- N/A F-SAST-11 (upload sin restricciones): este ticket no expone ningún endpoint de carga de archivos.
- N/A F-SAST-12 (CSRF): la API usa HTTP Basic con `Authorization` seteado explícitamente por el cliente axios en cada request (no cookies de sesión que el navegador reenvíe automáticamente cross-origin); CORS restringe el origen a `FRONTEND_ORIGIN` exacto (`main.py:25`), nunca `"*"`. El vector clásico de CSRF (credencial ambient del navegador + request cross-origin) no aplica a este esquema de auth.
- ✅ F-SAST-14 (validación de input incompleta): `schemas.py` — `patente` con `min_length=1, max_length=10, pattern=r"^[A-Za-z0-9]+$"`; `tipo` restringido a `Literal["auto", "camioneta"]`.
- ✅ F-SAST-15 (manejo de errores inseguro): `router.py:_a_http` solo expone `str(exc)` de excepciones de dominio propias con mensajes controlados (`exceptions.py`); cualquier excepción no anticipada cae en el handler genérico de `main.py:36-38`, que loguea server-side y responde `{"detail": "Internal server error"}` sin traceback ni mensaje interno (TM-03).

## Dependencias (F-SAST-13/16)

- **Backend** (`pip-audit`): 0 vulnerabilidades conocidas.
- **Frontend** (`npm audit`), corrida inicial: 5 hallazgos, todos en la cadena de devDependencies de testing (`vitest`→`vite-node`/`@vitest/mocker`→`vite`→`esbuild`), ninguno en `dependencies` (`axios`, `react`, `react-dom` limpios).

  Triage (`daw-sec-auditor`), verificado empíricamente contra `package.json`, `package-lock.json`, `vite.config.js` y el árbol de `node_modules` instalado:

  | Advisory | Severidad reportada | Veredicto | Nota |
  |---|---|---|---|
  | GHSA-5xrq-8626-4rwp (vitest, "Vitest UI server" arbitrary file read) | 🔴 Critical (CVSS 9.8) | **Falso positivo** | `@vitest/ui` no está instalado (solo peerDependency opcional no resuelta); ningún script usa `--ui`. Precondición del CVE arquitectónicamente inalcanzable en este proyecto. |
  | GHSA-fx2h-pf6j-xcff (vite, `server.fs.deny` bypass en Windows) | 🟠 High (CVSS 7.5) | **Verdadero positivo** | Afecta el dev server real (`npm run dev`), usado rutinariamente en desarrollo (WSL2/Windows). No admite supresión por política del proyecto (Critical/High no suprimibles). |
  | GHSA-67mh-4wv8-2f99 (esbuild, dev-server CORS) | 🟡 Medium (CVSS 5.3) | Verdadero positivo | Mismo remedio que el anterior. |
  | GHSA-4w7w-66w2-5vf9 (vite, path traversal en sourcemaps) | 🟡 Medium | Verdadero positivo | Mismo remedio. |
  | GHSA-v6wh-96g9-6wx3 (vite, NTLMv2 hash disclosure vía launch-editor, Windows) | 🟡 Medium | Verdadero positivo | Mismo remedio. |
  | vite-node / @vitest/mocker (heredan de vite) | 🟡 Medium | Verdadero positivo | Mismo remedio. |

  **Remediación aplicada:** `npm install -D vitest@4.1.10` (arrastra versiones seguras de `vite`/`vite-node`/`@vitest/mocker`/`esbuild` como devDependencies). Cambios: `frontend/package.json`, `frontend/package-lock.json`.
  - Post-fix: `npm audit` → **0 vulnerabilidades**.
  - Post-fix: `npx vitest run` → **16/16 tests pasando**, sin cambios de comportamiento (el "breaking change" del major de vitest es sobre la API/config del test runner, no sobre `src/`).

## Suppressions

Ninguna suppression formal requerida (todos los hallazgos Medium/High/Critical se resolvieron con el upgrade, no se suprimió nada). Se documenta igual, por buena práctica, el falso positivo de la Critical:

### Suppression: GHSA-5xrq-8626-4rwp (vitest — "Vitest UI server" arbitrary file read)

| Campo | Valor |
|---|---|
| File | `frontend/package.json` (devDependency `vitest`) |
| Category | F-SAST-13 (CVE crítica en dependencia) |
| Disposition | Falso positivo (no aplica al footprint instalado) |
| Reviewer | daw-sec-auditor |
| Date | 2026-08-05 |
| Justification | El paquete `@vitest/ui`, requisito para que el servidor UI vulnerable exista, no está instalado (`npm ls @vitest/ui` no lo resuelve); ningún script del proyecto invoca `vitest --ui`. La precondición del CVE ("Vitest UI server is listening") es arquitectónicamente imposible en el estado actual del repo. |
| Compensating control / review-by | Resuelto de fábrica por el upgrade a `vitest@4.1.10` (versión no afectada), aplicado igualmente junto con los hallazgos verdaderos. Re-evaluar si en el futuro se instala `@vitest/ui`. |

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
│  CSRF: N/A (HTTP Basic, sin credencial ambient de navegador) │
│  Dependencias backend (pip-audit): ✅ 0 vulnerabilidades       │
│  Dependencias frontend (npm audit): ✅ 0 vulnerabilidades      │
│    tras remediación (1 High + 4 Medium arreglados,            │
│    1 Critical descartado como falso positivo documentado)     │
│                                                              │
│  Suppressions: 1 (falso positivo documentado, 7 campos)       │
│                                                              │
│  ────────────────────────────────────────────────────────────│
│  Total: 0 vulnerabilidades bloqueantes abiertas                │
│  Report: docs/daw/security/sast-FEAT-001a.md                  │
│  Next: gates.sast = true → cerrar CODE, avanzar a VERIFY       │
└─────────────────────────────────────────────────────────────┘
```
