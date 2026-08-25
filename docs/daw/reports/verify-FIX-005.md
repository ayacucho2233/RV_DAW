# Reporte de verificación FIX-005: Hardening de la búsqueda de patente

| Field | Value |
|-------|-------|
| Ticket | FIX-005 |
| Fix-plan | docs/daw/specs/fix-FIX-005.md |
| RCA | docs/daw/specs/rca-FIX-005.md |
| Threat model | docs/daw/security/threat-FIX-005.md |
| Fecha | 2026-08-18 |
| Verificado por | daw-module-verifier (independiente de la implementación) |
| Veredicto | **PASSED** — 15/15, 0 FAIL, 0 WARN |

## Fix-plan — 6 pasos

| Paso | Archivo:línea | Estado |
|---|---|---|
| 1 — Constante `PATENTE_PATTERN` | `backend/app/features/vehiculos/schemas.py:20,31` | ✅ |
| 2 — `PatenteFormatoInvalidoError` | `backend/app/features/reservas/exceptions.py:37-48` | ✅ |
| 3 — Validación defensiva en el service | `backend/app/features/reservas/service.py:196-199` | ✅ |
| 4 — Wiring del router | `backend/app/features/reservas/router.py:70,81,182,193` | ✅ |
| 5 — `ORDER BY` determinístico | `backend/app/features/vehiculos/repository.py:74` | ✅ |
| 6 — Pre-chequeo de duplicados en la migración | `backend/alembic/versions/0003_patente_unique_case_insensitive.py:31-46` | ✅ |

## Tests de regresión

| Test | Archivo:línea | Qué prueba realmente |
|---|---|---|
| A1 | `backend/tests/test_reservas_service.py:708-720` | `PatenteFormatoInvalidoError` + `mock_obtener.assert_not_called()` — ausencia de round-trip a la DB, no solo la excepción |
| A2 | `backend/tests/test_reservas_router.py:536-543` | Regresión preexistente de FEAT-004, sigue verificando 422 |
| B1 | `backend/tests/test_migration_patente_unique_ci.py:181-241` | Inspecciona el SQL compilado real (`before_cursor_execute`) para confirmar `ORDER BY vehiculos.id`, no solo el resultado |
| C1 | `backend/tests/test_migration_patente_unique_ci.py:244-294` | Migración corrida como subproceso real; confirma `RuntimeError` con las patentes en conflicto y descarta el error crudo de Postgres |

## Threat model

Riesgo aceptado F-TM-04 (TOCTOU en el pre-chequeo de duplicados) sigue documentado como tal en el
código de la migración y en el threat model — no se cerró con `LOCK TABLE`, consistente con lo
pactado con el usuario en PLAN.

## Regresión general

- Suite completa de backend: 125/125 tests, 0 fallos.
- `ruff check .`: 0 errores.
- Comportamiento HTTP observable sin cambios para el flujo normal (confirmado por A2).

## Conclusión

Los 3 hallazgos de la review de FEAT-004 (A: validación ausente en el service, B: `.limit(1)` sin
`ORDER BY`, C: migración sin pre-chequeo de duplicados) quedan resueltos según lo diseñado en PLAN,
sin regresiones. Listo para RELEASE.
