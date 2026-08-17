# Fix-plan FIX-003: Configurar ruff/eslint correctamente y corregir hallazgos reales

| Field | Value |
|-------|-------|
| Ticket | FIX-003 |
| Tier | FIX |
| RCA | docs/daw/specs/rca-FIX-003.md |
| Date | 2026-08-17 |
| Spec loops | 0 |

## Problem

`ruff` (backend) y `eslint` (frontend) se instalaron con su configuración por defecto (ticket
anterior, commit `6e6a573`), sin adaptarla a los patrones ya presentes en el código. Resultado:
`ruff check .` reporta 36 errores y `npm run lint` reporta 6, mezclando un falso positivo de
configuración (12 casos) con deuda de estilo real nunca detectada antes (24 casos).

## Root cause

Ver `docs/daw/specs/rca-FIX-003.md`. Resumen: la regla `B008` de ruff no reconoce
`fastapi.Depends()` como llamada inmutable en un default-arg (el patrón de inyección de
dependencias de FastAPI), y el resto de los hallazgos es deuda de estilo preexistente sin detectar
por falta de linter.

## Solution — steps

### Config

1. `backend/ruff.toml` (nuevo) — agregar:
   ```toml
   [lint.flake8-bugbear]
   extend-immutable-calls = ["fastapi.Depends", "fastapi.Query", "fastapi.Path", "fastapi.Header", "fastapi.Cookie", "fastapi.Body", "fastapi.Form", "fastapi.File"]
   ```
   Resuelve los 12 `B008` en `app/core/security.py`, `app/features/reservas/router.py` y
   `app/features/vehiculos/router.py` sin tocar esos archivos.

2. `frontend/eslint.config.js` — desactivar `react-hooks/set-state-in-effect` (heredada de
   `reactHooks.configs.recommended.rules`), con un comentario explicando que conflictúa con el
   patrón "fetch on mount vía `useEffect` llamando a un loader async" ya establecido y revisado por
   `daw-arch-auditor` en FEAT-001a/c/d/e. Resuelve los 3 hallazgos en `ReservasListado.jsx:64`,
   `ReservasPublicPage.jsx:63` y `VehiculosAdminPage.jsx:76` sin tocar esos archivos.

### Autofix mecánico (I001, RUF100 — sin revisión manual, ruff los reescribe de forma segura)

3. `ruff check --fix` sobre `backend/` completo: ordena imports (I001) y elimina `# noqa` sin uso
   (RUF100) en `backend/tests/test_vehiculos_service.py`, `test_reservas_service.py`,
   `conftest.py`, `backend/alembic/env.py`, `backend/alembic/versions/0001_create_vehiculos.py`,
   `backend/alembic/versions/0002_create_reservas.py`, `backend/app/features/reservas/models.py`.

### Rewrites manuales mecánicos (C408, SIM117 — mismo comportamiento, otra sintaxis)

4. `backend/tests/test_vehiculos_service.py:44` — reescribir `dict(...)` como literal `{...}`.
5. `backend/tests/test_reservas_service.py:49` — reescribir `dict(...)` como literal `{...}`
   (`_reserva_data`).
6. `backend/tests/test_reservas_router.py:71,95` — reescribir los dos `dict(...)` como literal.
7. `backend/tests/test_reservas_service.py:598` — combinar los dos `with` anidados en uno.
8. `backend/tests/test_migration.py:90,114,122` — combinar los `with` anidados en cada caso.
9. `backend/tests/test_migration_reservas.py:117,131,185` — combinar los `with` anidados en cada
   caso.

### Suppressions documentadas (no son bugs)

10. `backend/tests/test_reservas_service.py:151-152` — agregar `# noqa: DTZ001` con comentario:
    estos `datetime(...)` son deliberadamente naive, el test verifica que la app los rechaza.
11. `backend/tests/test_migration.py` y `test_migration_reservas.py` — agregar `check=False`
    explícito al `subprocess.run(...)` existente (documenta la intención: el caller ya inspecciona
    `.returncode` manualmente vía `assert`, sin cambiar comportamiento).

### Código real

12. `frontend/src/api/client.js:33-37` — eliminar la rama muerta
    `Buffer.from(...).toString("base64")` del fallback de Basic Auth, dejando solo `btoa(...)`
    (siempre disponible en navegador real y en el jsdom de los tests; el fallback nunca se ejerce).
13. `frontend/src/features/reservas/ReservasListado.test.jsx:26` — quitar la variable sin usar
    `reservaCancelada`.
14. `frontend/src/features/reservas/ReservasPublicPage.test.jsx:5` — quitar el import sin usar
    `crearReserva`.

## Dependencies between steps

Ninguna — cada paso toca archivos independientes entre sí. Orden sugerido: 1-2 (config) → 3
(autofix) → 4-11 (rewrites manuales backend) → 12-14 (frontend), solo por prolijidad, no por
dependencia real.

## Error handling

No aplica — ningún paso introduce manejo de errores nuevo ni modifica el existente. El paso 11
(`check=False` explícito) documenta un comportamiento que ya era el default de `subprocess.run`,
sin cambiarlo.

## Tests

- [ ] **Regression test**: no aplica en el sentido clásico (no hay un bug de comportamiento que
  reproducir) — el criterio de regresión es que la suite completa (106 backend + 48 frontend) siga
  pasando exactamente igual antes y después del fix, y que `ruff check .` / `npm run lint` terminen
  en 0 errores.
- [ ] Suite completa de backend (`pytest`) sigue en 106/106 tras los rewrites de C408/SIM117/DTZ001/
  PLW1510.
- [ ] Suite completa de frontend (`npm test`) sigue en 48/48 tras eliminar la rama muerta en
  `client.js` y las variables sin usar en los tests.
- [ ] `ruff check .` → 0 errores.
- [ ] `npm run lint` → 0 errores.

## Regression risk

**Low.** Todos los cambios son mecánicos (reescrituras sintácticas equivalentes, reordenamiento de
imports, eliminación de código muerto/variables sin usar, configuración de linters) o
suppressions documentadas de falsos positivos. Ninguno modifica lógica de negocio, contratos de
API, ni comportamiento observable.

## Rollback plan

Trivial: `git revert` del commit de CODE. Ningún paso toca datos, migraciones ni contratos
externos — revertir el commit deja el repo exactamente como estaba, salvo por los 36+6 hallazgos
de lint que reaparecerían (comportamiento idéntico al actual, no una regresión nueva).
