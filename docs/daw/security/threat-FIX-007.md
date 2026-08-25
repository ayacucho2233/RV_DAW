# Threat Model — FIX-007

| Field | Value |
|-------|-------|
| Ticket | FIX-007 |
| Fecha | 2026-08-25 |
| Spec | docs/daw/specs/fix-FIX-007.md |

## Componentes analizados

1. `clasificar_periodo_reserva` (nueva función pura en `backend/app/features/reservas/schemas.py`).
2. `service.listar_reservas` (refactor: usa la función en vez de condicionales inline).
3. `evals/run.py` (nuevo script standalone, raíz del repo, fuera de `backend/`).
4. `evals/casos.json` (nuevo contenido: casos de test para la función de clasificación).

## Trust boundaries (F-TM-02)

Ninguno nuevo. `clasificar_periodo_reserva` no cruza ningún límite de confianza: recibe `datetime`
ya validados aguas arriba (Pydantic en `ReservaCreate`, o `datetime.now()` interno) y no hace I/O.
`evals/run.py` corre localmente/en CI, fuera del proceso de la app — no hay frontera cliente↔servidor
ni proceso↔proceso nueva. Es un script que se ejecuta con el mismo nivel de confianza que quien
tiene acceso de escritura al repo (igual que `pytest` o `ruff`).

## Análisis STRIDE

### `clasificar_periodo_reserva` (función pura)

| Categoría | Evaluación |
|---|---|
| Spoofing | N/A — no hay identidad involucrada, es lógica pura sobre 3 `datetime`. |
| Tampering | N/A — no persiste ni transmite datos. |
| Repudiation | N/A — no ejecuta ninguna acción auditable (no escribe, no muta estado). |
| Information Disclosure | N/A — no maneja datos sensibles, solo fechas ya presentes en el objeto `Reserva`. |
| Denial of Service | N/A — O(1), sin loops ni recursión. |
| Elevation of Privilege | N/A — sin autenticación/autorización involucrada. |

### `evals/run.py`

| Categoría | Evaluación |
|---|---|
| Spoofing | N/A — sin autenticación, corre local/CI con la identidad de quien lo ejecuta. |
| Tampering | 🟢 LOW — `evals/casos.json` es un archivo versionado del propio repo; alguien con permiso de escritura podría alterarlo para que el gate del 80% siempre pase falsamente. Mismo nivel de confianza que alterar cualquier test — no es una superficie nueva (ver mitigación). |
| Repudiation | N/A — script de dev/CI sin requisito de auditoría; su output va a stdout/logs de CI, que ya tienen su propia trazabilidad. |
| Information Disclosure | 🟢 LOW — las env vars dummy (`DATABASE_URL`, `ADMIN_PASSWORD_HASH`, etc.) son placeholders no sensibles, el mismo patrón ya usado en `backend/tests/conftest.py`; no son credenciales reales y el script nunca abre una conexión real a la base (la función que evalúa es pura, sin `db: Session`). |
| Denial of Service | 🟢 LOW — un `evals/casos.json` malformado o enorme podría hacer que el script tarde o falle, pero es un archivo local del propio repo, no expuesto a un adversario externo; el impacto se limita a la corrida de CI de ese PR, no a un servicio productivo. |
| Elevation of Privilege | N/A — no hay privilegios que escalar; el script no toca `backend/venv` de forma privilegiada ni el sistema. |

## Datos sensibles (F-TM-05)

Ninguno. La función clasifica fechas de reservas ya presentes en la tabla `reservas` (no PII nueva:
`fecha_inicio`/`fecha_fin` ya se exponían vía `GET /reservas`). Las env vars dummy de `evals/run.py`
son placeholders de desarrollo, no credenciales reales — no aplica cifrado en tránsito/reposo
(F-TM-07 no aplica: no hay PII ni credenciales reales involucradas).

## Riesgos y mitigaciones

Ningún riesgo CRITICAL o HIGH identificado. Los dos riesgos LOW (Tampering e Information Disclosure
sobre `evals/casos.json`) no requieren mitigación adicional: son equivalentes al riesgo ya aceptado
de cualquier archivo de test versionado en el repo, y el guard de CI (exit code 1 si <80%) ya es en
sí mismo la salvaguarda contra una regresión real en la función — alterar `casos.json` para ocultar
un bug requeriría que el mismo cambio pasara una revisión de PR, igual que alterar cualquier test.

## Resultado

```
┌─────────────────────────────────────────────────────────┐
│  /daw-threat-modeling — PASSED                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Attack surfaces identified: 4 (2 con riesgo LOW, 0 con  │
│    riesgo CRITICAL/HIGH/MEDIUM)                           │
│  Trust boundaries declared: 0 nuevas (ninguna se cruza)   │
│                                                          │
│  Risks:                                                  │
│    🟢 LOW: evals/casos.json alterable por quien ya tiene  │
│       write access al repo — mismo riesgo que cualquier   │
│       test versionado, sin mitigación adicional            │
│    🟢 LOW: evals/run.py imprime env vars dummy no          │
│       sensibles — mismo patrón que conftest.py existente   │
│                                                          │
│  Mitigaciones a incorporar al spec: ninguna (0 riesgos     │
│    CRITICAL/HIGH)                                          │
│                                                          │
│  ─────────────────────────────────────────────────────   │
│  Risks: C:0 H:0 M:0 L:2                                   │
│  Report: docs/daw/security/threat-FIX-007.md               │
└─────────────────────────────────────────────────────────┘
```
