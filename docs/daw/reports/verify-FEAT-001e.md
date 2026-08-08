# Verify — FEAT-001e: Integración con el ciclo de vida del vehículo

| Campo | Valor |
|---|---|
| Ticket | FEAT-001e |
| Tier | FEATURE |
| PRD | `docs/daw/prd/prd-FEAT-001e.md` |
| Spec | `docs/daw/specs/spec-FEAT-001e.md` |
| Threat model | `docs/daw/security/threat-FEAT-001e.md` |
| SAST | `docs/daw/security/sast-FEAT-001e.md` |
| Rondas de verificación | 1 |

## Verdict: PASSED (2 WARN no bloqueantes)

Corrido por `daw-module-verifier`, cruzando PRD → spec → código → tests de forma independiente
(no reutiliza las revisiones por bloque de CODE, vuelve a leer el código y a correr las suites
en vivo).

## Trazabilidad PRD → Código → Tests (AC-01 a AC-04)

| AC | FR | Implementación | Test(s) | Estado |
|---|---|---|---|---|
| AC-01 | FR-01 rechazar baja temporal con reservas activas | `service.py:dar_de_baja_temporal` (lock + `existe_activa_para_vehiculo`) + `router.py` (409) | `test_baja_temporal_rechazada_con_reserva_activa`, `test_patch_baja_temporal_con_reserva_activa_409` | ✅ |
| AC-02 | FR-01 rechazar baja definitiva con reservas activas | `service.py:dar_de_baja_definitiva` | `test_baja_definitiva_rechazada_con_reserva_activa`, `test_patch_baja_definitiva_con_reserva_activa_409` | ✅ |
| AC-03 | FR-02 reservas pasadas visibles tras baja temporal | `reservas.service.listar_reservas` (sin cambios — ya soportaba esto) | `test_listar_reservas_incluye_reserva_de_vehiculo_en_baja_temporal`, `test_get_reservas_incluye_reserva_de_vehiculo_dado_de_baja_200` | ✅ |
| AC-04 | FR-02 reservas pasadas visibles tras baja definitiva | ídem | `test_listar_reservas_incluye_reserva_de_vehiculo_en_baja_definitiva`, mismo test HTTP combinado | ✅ |

## NFR

| NFR | Estrategia | Verificación |
|---|---|---|
| NFR-01 (rechazo de baja <2s p95) | `existe_activa_para_vehiculo`: `SELECT EXISTS` con `LIMIT 1`, sin JOIN, sobre el índice `ix_reservas_vehiculo_fechas` (columna líder `vehiculo_id`) | Estrategia verificada en código real (el índice existe en `alembic/versions/0002_create_reservas.py`); ⚠️ sin medición empírica de p95 — mismo criterio aceptado en FEAT-001d |

## Spec — cobertura por bloque

- ✅ Block 1 (bloquear baja con reservas activas) — 8/8 tests requeridos, en verde. Incluye el test
  de concurrencia real (dos conexiones, `threading.Barrier`, mismo patrón que
  `test_crear_reserva_concurrencia_solo_una_confirmada` de FEAT-001c).
- ✅ Block 2 (confirmar reservas visibles tras baja) — 3/3 tests requeridos, en verde, sin cambios
  de producción (hipótesis del spec confirmada).
- ✅ Nota D-06 (dependencia cruzada bidireccional `vehiculos↔reservas`, solo lectura, a nivel
  repository) respetada: `service.py` importa `reservas.repository`, nunca `reservas.service`.

## Mitigaciones del threat model (TM-E-01, TM-E-02)

| TM | Mitigación | Verificación |
|---|---|---|
| TM-E-01 | Log del rechazo de baja (no solo del éxito) | `_log_operacion(..., "rechazada")` agregado en el `except VehiculoDomainError` de ambos métodos de baja — cierra el riesgo más allá de lo exigido por el spec |
| TM-E-02 | Mensaje 409 sin enmascarar en el frontend, sin exponer excepciones crudas | Confirmado: `_a_http`/`_MAPEO_ERRORES_HTTP` solo traducen `VehiculoDomainError`/subclases |

## Suite de tests (corrida en vivo por el verificador)

- **Backend:** 106/106 pytest passed. Coverage 99% sobre `app.features.vehiculos` + `app.features.reservas` (452 stmts, 3 missed — los 3 en un camino de FEAT-001a no tocado por este ticket). Los 4 archivos de producción modificados por FEAT-001e están al 100%.
- **Frontend:** 34/34 vitest passed (6 archivos de test).
- **Total:** 140/140 — coincide con lo reportado en el cierre de CODE.

## Sad paths (F-VER-05)

- ✅ `dar_de_baja_*`: vehículo inexistente → 404, transición inválida → 409, reservas activas → 409 — los 3 caminos de error cubiertos.
- ✅ Caso límite: una reserva `cancelada` (no activa) no bloquea la baja (`test_baja_definitiva_permitida_con_reserva_cancelada`), confirmando que el filtro es por `estado`, no por existencia de cualquier reserva.

## Calidad

- ⚠️ W-VER-01: sin herramienta de coverage en frontend (`@vitest/coverage-*` no instalado, preexistente, no introducido por este ticket).
- ⚠️ W-VER-02: sin linter/type-checker configurado en ninguno de los dos proyectos (preexistente).
- ✅ Imports limpios, sin código muerto (la entrada `409` de `MENSAJES_ERROR` se eliminó, no se dejó comentada).
- ✅ Sin tests frágiles: el test de concurrencia usa `threading.Barrier` + timeout explícito, no sleeps arbitrarios.

## WARN (no bloqueantes)

1. **W-VER-01 — sin coverage tool en frontend**: limitación preexistente del proyecto, no introducida por este ticket. `VehiculosAdminPage.jsx` sí tiene el test explícito que ejercita el código modificado.
2. **W-VER-02 — sin linter configurado**: preexistente, no introducido por este ticket.

Ningún AC, FR o mitigación del threat model quedó sin implementación o sin test que lo ejercite de
forma real.

## Resultado

```
┌─────────────────────────────────────────────────────────┐
│  VERIFY — Verification Summary                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Ticket: FEAT-001e — Integración con el ciclo de vida    │
│    del vehículo                                          │
│  Tier: FEATURE                                            │
│  PRD: docs/daw/prd/prd-FEAT-001e.md                       │
│  Spec: docs/daw/specs/spec-FEAT-001e.md                   │
│  Report: docs/daw/reports/verify-FEAT-001e.md             │
│                                                          │
│  Results:                                                │
│    ✅ /daw-verify-module: PASSED (0 FAIL, 2 WARN, 19 PASS)│
│    ✅ Tests: 140 passed, 140 total (106 backend + 34 frontend)│
│    ✅ SAST (CODE phase): PASSED                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```
