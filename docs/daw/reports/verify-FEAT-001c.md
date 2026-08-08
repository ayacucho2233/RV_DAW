# Verify — FEAT-001c: Consulta y creación de reservas

| Campo | Valor |
|---|---|
| Ticket | FEAT-001c |
| Tier | FEATURE |
| PRD | `docs/daw/prd/prd-FEAT-001c.md` |
| Spec | `docs/daw/specs/spec-FEAT-001c.md` |
| Threat model | `docs/daw/security/threat-FEAT-001c.md` |
| SAST | `docs/daw/security/sast-FEAT-001c.md` |
| Rondas de verificación | 1 |

## Verdict: PASSED (5 WARN no bloqueantes)

Corrido por `daw-module-verifier`, cruzando PRD → spec → código → tests de forma independiente (no
reutiliza las revisiones por bloque de CODE, vuelve a leer el código y a correr las suites en vivo).

## Trazabilidad PRD → Código → Tests (AC-01 a AC-08)

| AC | FR | Implementación | Test(s) | Estado |
|---|---|---|---|---|
| AC-01 | FR-01 listado del pool | `service.py:listar_vehiculos_pool` + `router.py` GET `/reservas/vehiculos` | `test_listar_vehiculos_pool`, `test_get_vehiculos_pool_200`, `ReservasPublicPage.test.jsx` | ✅ |
| AC-02 | FR-02 alta OK | `service.py:crear_reserva` + `router.py` POST `/reservas` | `test_crear_reserva_ok`, `test_post_reserva_ok_201`, `ReservaForm.test.jsx` | ✅ |
| AC-03 | FR-02 campo faltante | `schemas.py:ReservaCreate` (`Field` required) | `test_post_reserva_campo_faltante_422`, `ReservaForm.test.jsx` | ✅ |
| AC-04 | FR-02 `fecha_fin <= fecha_inicio` | `schemas.py:_fecha_fin_posterior_a_inicio` | `test_reserva_create_rechaza_fecha_fin_menor_o_igual`, `test_post_reserva_fecha_fin_menor_o_igual_422`, `ReservaForm.test.jsx` | ✅ (triple capa) |
| AC-05 | FR-03 solapamiento | `service.py:crear_reserva` paso 3 (`ReservaSolapadaError`) | `test_crear_reserva_solapada_rechazada`, `test_post_reserva_solapada_409`, `ReservaForm.test.jsx` | ✅ |
| AC-06 | NFR-03 concurrencia | `vehiculos/repository.py:obtener_por_id_con_lock` (`SELECT FOR UPDATE`) invocado desde `service.py:crear_reserva` | `test_crear_reserva_concurrencia_solo_una_confirmada` (dos conexiones reales, sin mocks, retraso inyectado para forzar interleaving) | ✅ |
| AC-07 | FR-04 disponibilidad | `service.py:consultar_disponibilidad` + `router.py` GET `/reservas/disponibilidad` | `test_consultar_disponibilidad`, `test_get_disponibilidad_200`, `ReservasPublicPage.test.jsx` | ✅ |
| AC-08 | FR-05 vehículo no activo (corrective loop PLAN) | `service.py:crear_reserva` paso 2 (`VehiculoNoActivoError`) | `test_crear_reserva_vehiculo_no_activo`, `test_post_reserva_vehiculo_no_activo_409`, `ReservaForm.test.jsx` | ✅ — ver WARN 1 |

## NFR

| NFR | Estrategia | Verificación |
|---|---|---|
| NFR-01 (reserva <1 min) | Formulario de un solo paso, sin flujo de autenticación previo | `ReservaForm.jsx` — un único submit, sin wizard |
| NFR-02 (disponibilidad <2s p95) | Índice compuesto `(vehiculo_id, fecha_inicio, fecha_fin)` | `test_migracion_crea_tabla_reservas` inspecciona el índice real en Postgres |
| NFR-03 (race conditions) | `SELECT FOR UPDATE` sobre la fila del vehículo | Ver AC-06 |

## Spec — cobertura por bloque

- ✅ Block 1 (modelo + migración) — 2/2 tests requeridos, en verde.
- ✅ Block 2 (servicio/repositorio/schemas) — 11/11 tests requeridos, en verde.
- ✅ Block 3 (router) — 11/11 tests requeridos, en verde.
- ✅ Block 4 (frontend) — 10 tests de componente cubren los escenarios pedidos (3 `ReservasPublicPage` + 7 `ReservaForm`).

## Mitigaciones del threat model (TM-C-01 a TM-C-06)

| TM | Mitigación | Verificación |
|---|---|---|
| TM-C-01 | TLS obligatorio en despliegue (PII de empleados) | Documentado como precondición, misma que TM-01 de FEAT-001a |
| TM-C-02 | Rate limiting (10/h alta, 60/min lectura) | `router.py:_aplicar_rate_limit` + `test_post_reserva_rate_limit_429`, `test_get_disponibilidad_rate_limit_429` |
| TM-C-03 | Datetime naive rechazado | `schemas.py:_validar_timezone_aware` + `test_reserva_create_rechaza_fecha_naive` |
| TM-C-04 | Logging de trazabilidad sin PII | `service.py:_log_operacion` + `test_crear_reserva_loguea_operacion_sin_pii` |
| TM-C-05 | Spoofing de identidad del empleado (riesgo aceptado) | Documentado con los 3 campos de F-TM-04 en el threat model |
| TM-C-06 | PII en reposo sin cifrado adicional (riesgo aceptado) | Documentado con los 3 campos de F-TM-04 en el threat model |

Las 6 mitigaciones están implementadas o documentadas como precondición/riesgo aceptado.

## Suite de tests (corrida en vivo por el verificador)

- **Backend:** 71/71 pytest passed. Coverage 100% líneas (164/164) sobre `app/features/reservas/`.
- **Frontend:** 26/26 vitest passed (5 archivos de test, 10 nuevos de este ticket).
- **Total:** 97/97 — coincide con lo reportado en el cierre de CODE.

## Calidad

- ⚠️ Lint/type-checker: no configurado en ninguno de los dos proyectos (preexistente, no introducido por este ticket).
- ✅ Sin imports no usados, sin código muerto.
- ⚠️ Coverage frontend no medible (`@vitest/coverage-v8` no instalado, preexistente); evaluación manual confirma cobertura de happy path y sad paths (404/409×2/422).

## WARN (no bloqueantes)

1. **AC-08 — cobertura de test parcial por sub-estado**: `VehiculoNoActivoError` cubre tanto `baja_temporal` como `baja_definitiva` (la condición es `estado != activo`, rama única), pero solo hay test explícito para `baja_temporal`. Sin riesgo funcional real porque no hay lógica condicional por tipo de baja.
2. **Rollback del spec sin test dedicado**: el criterio de cierre del spec ("`alembic downgrade -1` revierte solo `reservas`, sin afectar `vehiculos`") no tiene un test que ejercite un downgrade parcial — el test existente usa `downgrade base` (revierte todo). El código de `downgrade()` en `0002_create_reservas.py` es correcto por inspección (solo emite `DROP` sobre `reservas`), pero la afirmación específica no está verificada por test automatizado.
3. **Desviación cosmética de la lista de "Files" del Block 2**: la implementación agrega `obtener_por_id_con_lock` a `vehiculos/repository.py` (fuera de lo declarado en el spec) para cerrar un caso de "phantom row" que el diseño original (`obtener_por_id` sin lock) no cubría. Mejora legítima y necesaria para que el test de concurrencia (AC-06) sea genuino, pero no estaba anunciada en la lista de archivos del bloque.
4. **Sin linter configurado** (preexistente, no introducido por este ticket).
5. **Sin tooling de coverage en frontend** (preexistente, no introducido por este ticket).

Ningún AC, FR, NFR o mitigación del threat model quedó sin implementación o sin test que lo ejercite de forma real.

## Resultado

```
┌─────────────────────────────────────────────────────────┐
│  VERIFY — Verification Summary                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Ticket: FEAT-001c — Consulta y creación de reservas     │
│  Tier: FEATURE                                            │
│  PRD: docs/daw/prd/prd-FEAT-001c.md                       │
│  Spec: docs/daw/specs/spec-FEAT-001c.md                   │
│  Report: docs/daw/reports/verify-FEAT-001c.md             │
│                                                          │
│  Results:                                                │
│    ✅ /daw-verify-module: PASSED (0 FAIL, 5 WARN, 21 PASS)│
│    ✅ Tests: 97 passed, 97 total (71 backend + 26 frontend)│
│    ✅ SAST (CODE phase): PASSED                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```
