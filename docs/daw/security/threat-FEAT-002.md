# Threat Model — FEAT-002: Menú principal y rediseño visual del frontend

| Campo | Valor |
|---|---|
| Ticket | FEAT-002 |
| Fase | PLAN |
| Spec | `docs/daw/specs/spec-FEAT-002.md` |
| Fecha | 2026-08-08 |

## Componentes nuevos/modificados

1. `frontend/src/index.css` — hoja de estilos estática, sin lógica.
2. `frontend/src/components/icons.jsx` — componentes SVG puros, sin estado, sin props de datos.
3. `frontend/src/features/menu/MenuPrincipal.jsx` — componente presentacional puro, sin fetch, sin
   estado propio, sin input de usuario (solo botones que invocan un callback).
4. `frontend/src/App.jsx` — se agrega el estado `"menu"` a `vista` y 2 botones nuevos ("Volver al
   menú", "Cerrar sesión"). **No se toca** la lógica de autenticación (`session` sigue siendo
   `useState` en memoria, nunca persistido; el guard `if (session) return <VehiculosAdminPage />`
   se preserva sin cambios de prioridad).

## Trust boundaries (F-TM-02)

Sin boundaries nuevas. Este ticket no agrega ni modifica ningún endpoint, ningún dato enviado al
backend, ni el mecanismo de autenticación (`verificar_admin`/HTTP Basic, sin cambios). La frontera
pública/admin ya establecida en FEAT-001a sigue exactamente igual: el guard de `session` en
`App.jsx` es el único punto que decide si se renderiza `VehiculosAdminPage`, y este ticket no
altera esa condición — solo la envuelve con botones de navegación.

## Análisis STRIDE

| STRIDE | Análisis |
|---|---|
| Spoofing | N/A — sin cambios en el mecanismo de autenticación. |
| Tampering | N/A — `MenuPrincipal`/`icons.jsx` no reciben ni transforman datos del usuario ni del servidor. |
| Repudiation | N/A — sin acciones nuevas que requieran trazabilidad (no hay logging de navegación de UI, igual que el resto del frontend). |
| Information Disclosure | N/A — no se expone ningún dato nuevo. El botón "Cerrar sesión" solo llama a `setSession(null)` (ya existía ese mecanismo, disparado hoy automáticamente ante un 401; este ticket solo lo expone también como acción manual explícita del usuario). |
| Denial of Service | N/A — contenido estático, sin requests adicionales al backend (`MenuPrincipal` no hace fetch). |
| Elevation of Privilege | ✅ Verificado: el guard `if (session) return <VehiculosAdminPage />` se preserva exactamente como está hoy (mismo orden de evaluación, misma condición). Ningún usuario sin sesión puede alcanzar `VehiculosAdminPage` a través del nuevo menú — "Administrador" sin sesión activa renderiza `LoginAdmin`, nunca el panel directamente. |

## Riesgos y mitigaciones (F-TM-03)

Ninguno. No se identificó ningún riesgo CRITICAL, HIGH, MEDIUM ni LOW nuevo: el ticket es
estrictamente de navegación y presentación, no toca autenticación, autorización, validación de
input, ni ningún flujo de datos con el backend. Los 4 componentes reutilizados
(`ReservasPublicPage`, `ReservasListado`, `VehiculosAdminPage`, `LoginAdmin`) no se modifican, así
que sus propias mitigaciones (ya evaluadas en los threat models de FEAT-001a/c/d/e) siguen
vigentes sin cambios.

### Aceptación de riesgos (F-TM-04)

N/A — no hay riesgos a aceptar.

## Datos sensibles (F-TM-05)

Sin datos sensibles nuevos. Este ticket no introduce ningún campo de PII ni de credenciales.

## Cifrado en tránsito y en reposo (F-TM-07)

N/A — sin cambios en el manejo de datos sensibles; hereda las precondiciones ya establecidas
(TLS obligatorio en despliegue) sin modificarlas.

## Resumen

```
┌─────────────────────────────────────────────────────────┐
│  /daw-threat-modeling — PASSED                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Attack surfaces identified: 0 nuevas (ticket de          │
│    navegación/presentación, sin tocar auth/datos/API)      │
│  Trust boundaries declared: 0 nuevas                        │
│                                                          │
│  Risks: ninguno — 0 CRITICAL, 0 HIGH, 0 MEDIUM, 0 LOW        │
│                                                          │
│  Verificación clave: el guard de sesión existente           │
│    (session → siempre panel admin) se preserva sin           │
│    cambios, confirmado en el spec.                            │
│                                                          │
│  Mitigations to fold into the spec: ninguna                   │
│                                                          │
│  ─────────────────────────────────────────────────────   │
│  Risks: C:0 H:0 M:0 L:0                                   │
│  Report: docs/daw/security/threat-FEAT-002.md              │
└─────────────────────────────────────────────────────────┘
```
