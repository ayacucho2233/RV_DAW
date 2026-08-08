# Verify — FEAT-002: Menú principal y rediseño visual del frontend

| Campo | Valor |
|---|---|
| Ticket | FEAT-002 |
| Tier | FEATURE |
| PRD | `docs/daw/prd/prd-FEAT-002.md` |
| Spec | `docs/daw/specs/spec-FEAT-002.md` |
| Threat model | `docs/daw/security/threat-FEAT-002.md` |
| SAST | `docs/daw/security/sast-FEAT-002.md` |
| Rondas de verificación | 1 |

## Verdict: PASSED (3 WARN no bloqueantes)

Corrido por `daw-module-verifier`, cruzando PRD → spec → código → tests de forma independiente.

## Trazabilidad PRD → Código → Tests (AC-01 a AC-07)

| AC | FR | Implementación | Test(s) | Estado |
|---|---|---|---|---|
| AC-01 | FR-01 menú con 3 opciones | `MenuPrincipal.jsx` | `MenuPrincipal.test.jsx` + `App.test.jsx` (montaje inicial) | ✅ |
| AC-02 | FR-02 navegar a Consultar | `App.jsx:vista==="consultar"` | `App.test.jsx` | ✅ |
| AC-03 | FR-02 navegar a Gestionar | `App.jsx:vista==="gestionar"` | `App.test.jsx` | ✅ |
| AC-04 | FR-02 navegar a Administrador (con/sin sesión) | `App.jsx` guard de sesión + `vista==="admin"` | `App.test.jsx` (2 tests, ambas ramas) | ✅ |
| AC-05 | FR-03 volver al menú | `App.jsx` header compartido | `App.test.jsx` | ✅ (ver WARN 3) |
| AC-06 | FR-04 cerrar sesión independiente | `App.jsx` 2 botones, 2 handlers | `App.test.jsx` (3 tests) | ✅ |
| AC-07 | FR-05 paleta/íconos consistentes | `index.css` + `icons.jsx` | `index.css.test.js` + `icons.test.jsx` + inspección de código | ⚠️ (ver WARN 1) |

## Guard de sesión (decisión arquitectónica central)

`if (session) return <VehiculosAdminPage />` en `App.jsx` se preserva exactamente, evaluado antes
que `vista` — confirmado en código y con test de no-regresión explícito ("Volver al menú" con
sesión activa limpia la sesión Y muestra el menú; un 401 automático no rompe la navegación).
Consistente con lo ya verificado con mutación de regresión en la revisión de Block 3 de CODE.

## Spec — cobertura por bloque

- ✅ Block 1 (fundación visual) — 2/2 tests requeridos, en verde. `main.jsx` importa `index.css`,
  `npm run build` sin errores.
- ✅ Block 2 (MenuPrincipal) — 4/4 tests requeridos, en verde. Sin imports de `api/`/`context/`.
- ✅ Block 3 (integración App.jsx) — 9/9 tests requeridos, en verde. Ningún componente reutilizado
  (`ReservasPublicPage`, `ReservasListado`, `VehiculosAdminPage`, `LoginAdmin`) aparece en el diff.

## NFR-01 (sin dependencias de imágenes externas)

✅ `package.json`/`package-lock.json` sin cambios en todo el ticket (0 dependencias nuevas). Los 5
íconos son SVG inline escritos a mano. Sin `<img>`, `url()` externo, ni CDN de íconos en ningún
archivo tocado.

## Suite de tests (corrida en vivo por el verificador)

- **Frontend:** 49/49 vitest passed (10 archivos), 2 corridas independientes limpias en esta
  sesión — sumadas a las 6 corridas previas de CODE, sin evidencia de flakiness real (el hallazgo
  puntual del arch-auditor en la revisión de Block 3 no se reprodujo en ninguna de las 8 corridas
  totales).
- **Backend:** 105/106 pytest passed. El único fallo (`test_config_falla_sin_database_url`) es una
  causa externa a este ticket: un archivo `backend/.env` de uso manual (para probar la app en el
  navegador) sigue en disco y contamina ese test específico. Confirmado moviendo el archivo
  temporalmente: 106/106. FEAT-002 es 100% frontend, no toca `app.core.config` ni ningún archivo
  backend.

## Sad paths (F-VER-04)

N/A para inputs nuevos (sin formularios en este ticket). El único sad path aplicable —un 401
limpiando la sesión automáticamente sin romper la navegación— está cubierto con test de
comportamiento real.

## Calidad

- ⚪ Lint (F-VER-05): N/A, sin linter configurado (preexistente).
- ✅ Imports limpios, sin código muerto en los 5 archivos nuevos/modificados.
- ⚠️ Coverage: sin tooling instalado en frontend (preexistente, mismo WARN aceptado en
  FEAT-001c/d/e).

## WARN (no bloqueantes)

1. **AC-07 sin verificación visual en esta sesión** — el spec pide, como cierre de AC-07, levantar
   la app vía `/run` y confirmar visualmente que las 4 pantallas comparten paleta/íconos. El
   verificador no tuvo herramienta de navegador disponible en esta sesión; la verificación mecánica
   (variables CSS declaradas, sin estilos inline en los 4 componentes reutilizados, `index.css`
   como única hoja de estilos) sí se hizo. Mismo tipo de limitación ya aceptada en tickets
   anteriores. **La app está corriendo localmente** (backend `:8000`, frontend `:5173`) — se
   recomienda una confirmación visual rápida antes o después del cierre.
2. **Coverage de frontend no instrumentado** — preexistente, no introducido por este ticket.
3. **Nombre de test impreciso** — `App.test.jsx`: el test "click en Volver al menú desde
   Consultar/Gestionar regresa al menú principal" solo ejercita la rama Consultar en su cuerpo (el
   botón es el mismo código compartido por las 3 ramas, así que no hay riesgo funcional real, pero
   el nombre promete más cobertura de la que el test tiene). No se corrige en VERIFY (regla del
   pipeline); queda como mejora menor para un futuro ajuste.

Ningún AC, FR o mitigación del threat model quedó sin implementación o sin test que lo ejercite de
forma real.

## Resultado

```
┌─────────────────────────────────────────────────────────┐
│  VERIFY — Verification Summary                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Ticket: FEAT-002 — Menú principal y rediseño visual     │
│  Tier: FEATURE                                            │
│  PRD: docs/daw/prd/prd-FEAT-002.md                         │
│  Spec: docs/daw/specs/spec-FEAT-002.md                     │
│  Report: docs/daw/reports/verify-FEAT-002.md               │
│                                                          │
│  Results:                                                │
│    ✅ /daw-verify-module: PASSED (0 FAIL, 3 WARN, 14 PASS)│
│    ✅ Tests: 155 passed, 156 total (106 backend¹ + 49     │
│       frontend, ¹1 fallo externo a este ticket, ver WARN) │
│    ✅ SAST (CODE phase): PASSED                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```
