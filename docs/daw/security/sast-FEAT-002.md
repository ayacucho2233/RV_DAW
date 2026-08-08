# SAST — FEAT-002: Menú principal y rediseño visual del frontend

| Campo | Valor |
|---|---|
| Ticket | FEAT-002 |
| Fase | CODE (closeout) |
| Alcance | `frontend/src/{App.jsx,main.jsx,index.css}`, `frontend/src/components/icons.jsx`, `frontend/src/features/menu/MenuPrincipal.jsx` (los 3 bloques) |
| Fecha | 2026-08-08 |

## Secretos

- ✅ Sin secretos hardcodeados (grep de patrones `password/secret/api_key` sobre el diff completo: 0 matches).
- N/A este ticket no introduce credenciales ni configuración sensible.

## Inyección

- N/A F-SAST-02/03 (SQL/command injection): ticket 100% frontend, sin backend tocado.
- N/A F-SAST-05 (path traversal): sin manejo de rutas de archivo.

## XSS y funciones inseguras

- ✅ F-SAST-06 (XSS): 0 ocurrencias de `dangerouslySetInnerHTML`/`innerHTML` en los 5 archivos de producción tocados. Los íconos son SVG estático embebido en JSX (sin interpolar contenido de usuario), y los textos del menú/header son strings literales, no datos dinámicos.
- ✅ F-SAST-04/17 (eval/exec): 0 ocurrencias.
- N/A F-SAST-08 (crypto débil): sin manejo de contraseñas/hashing en este ticket.

## Resto de categorías obligatorias

- N/A F-SAST-07 (SSRF): sin llamadas salientes nuevas (`MenuPrincipal` no hace fetch; `App.jsx` no agrega ninguna).
- N/A F-SAST-09 (debug en producción): sin cambios de configuración de entorno.
- ✅ F-SAST-10 (logging de datos sensibles): sin logging nuevo (frontend no loguea al servidor; `console.log` grep: 0 ocurrencias en el diff).
- N/A F-SAST-11 (upload sin restricciones): sin endpoints de carga.
- N/A F-SAST-12 (CSRF): sin cambios en el manejo de sesión/cookies — `session` sigue siendo estado en memoria de React, nunca persistido (verificado: `localStorage`/`sessionStorage` no aparecen en el diff).
- N/A F-SAST-14 (validación de input incompleta): `MenuPrincipal` no acepta ningún input de usuario (solo clicks en botones fijos, sin campos de texto).
- ✅ F-SAST-15 (manejo de errores inseguro): sin cambios — `App.jsx` sigue usando `setUnauthorizedHandler` ya existente sin modificarlo.

## Verificación de la superficie de sesión (dado que el ticket toca el flujo de logout)

- ✅ El guard `if (session) return <VehiculosAdminPage />` se preserva exactamente (verificado por `daw-module-verifier` en la revisión de bloque, con mutación de regresión reproducida): ningún usuario sin sesión puede alcanzar el panel de administración a través del nuevo menú.
- ✅ Los 2 botones nuevos (`Cerrar sesión`, `Volver al menú`) solo llaman a `setSession(null)` — el mismo mecanismo que ya usaba `setUnauthorizedHandler` ante un 401. No se agrega ningún nuevo camino de autenticación ni se debilita el existente (HTTP Basic vía `verificar_admin`, sin cambios en backend).

## Dependencias (F-SAST-13/16)

- **Frontend** (`npm audit --omit=dev`): ✅ 0 vulnerabilidades. Sin dependencias nuevas (diff de `package.json`/`package-lock.json`: vacío).
- **Backend**: sin cambios en este ticket, no aplica re-auditar.

## Suppressions

Ninguna. No hay hallazgos Medium/High/Critical.

## Resumen

```
┌─────────────────────────────────────────────────────────────┐
│  /daw-security-sast — PASSED                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Secretos: ✅ 0 hallazgos                                    │
│  XSS / funciones inseguras: ✅ 0 hallazgos                    │
│  Superficie de sesión: ✅ guard preservado, verificado con     │
│    mutación de regresión en la revisión de bloque              │
│  CSRF: N/A (sin cookies, session en memoria sin persistir)      │
│  Dependencias frontend (npm audit): ✅ 0 vulnerabilidades       │
│                                                              │
│  Suppressions: 0                                              │
│                                                              │
│  ────────────────────────────────────────────────────────────│
│  Total: 0 vulnerabilidades bloqueantes abiertas                │
│  Report: docs/daw/security/sast-FEAT-002.md                   │
│  Next: gates.sast = true → cerrar CODE, avanzar a VERIFY       │
└─────────────────────────────────────────────────────────────┘
```
