# SAST — FIX-007

| Field | Value |
|-------|-------|
| Ticket | FIX-007 |
| Fecha | 2026-08-25 |
| Archivos escaneados | `backend/app/features/reservas/schemas.py`, `backend/app/features/reservas/service.py`, `evals/run.py`, `evals/casos.json` |

```
┌─────────────────────────────────────────────────────────────┐
│  /daw-security-sast — PASSED                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Secrets:                                                    │
│    ✅ F-SAST-01: evals/run.py — env vars dummy, sin valor     │
│       real (mismo patrón que backend/tests/conftest.py); .env │
│       ya está en .gitignore (verificado en tickets previos)   │
│                                                              │
│  Injection:                                                  │
│    ✅ F-SAST-02: sin queries SQL en los archivos tocados       │
│       (clasificar_periodo_reserva es lógica pura, sin DB)     │
│    ✅ F-SAST-05: evals/run.py — CASOS_PATH se construye desde  │
│       __file__ (Path fijo), no desde input externo             │
│                                                              │
│  Funciones inseguras / crypto débil:                          │
│    ✅ F-SAST-04: sin eval/exec en ningún archivo tocado         │
│    ✅ F-SAST-08: sin uso de crypto en este cambio                │
│                                                              │
│  Otras categorías:                                             │
│    ✅ F-SAST-07 (SSRF): sin llamadas de red                     │
│    ✅ F-SAST-10 (logging de datos sensibles): evals/run.py      │
│       imprime solo fechas de test, ninguna PII                  │
│    ✅ F-SAST-14 (validación de input incompleta): evals/run.py  │
│       no valida el shape de casos.json más allá del acceso a    │
│       claves — deliberado y documentado en el fix-plan          │
│       (Error handling): es un script de dev/CI sobre un         │
│       archivo local del propio repo, no input externo           │
│                                                              │
│  Dependencies:                                                 │
│    ✅ F-SAST-13/16: pip-audit — "No known vulnerabilities       │
│       found". Sin dependencias nuevas (evals/run.py usa solo    │
│       stdlib: json, os, sys, datetime, pathlib)                 │
│                                                              │
│  Suppressions: 0                                                │
│                                                              │
│  ────────────────────────────────────────────────────────────│
│  Total: 8 clean, 0 vulnerabilidades (0 critical, 0 high)        │
│  Report: docs/daw/security/sast-FIX-007.md                      │
│  Next: gates.sast = true, seguir con la transición a VERIFY     │
└─────────────────────────────────────────────────────────────┘
```
