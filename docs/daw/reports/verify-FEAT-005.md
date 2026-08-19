# Reporte de VERIFY — FEAT-005: Estado "Caducada" para reservas vencidas automáticamente

| Campo | Valor |
|---|---|
| Ticket | FEAT-005 |
| Tier | FEATURE |
| Fecha | 2026-08-19 |
| PRD | docs/daw/prd/prd-FEAT-005.md |
| Spec | docs/daw/specs/spec-FEAT-005.md |
| Threat model | docs/daw/security/threat-FEAT-005.md |
| SAST | docs/daw/security/sast-FEAT-005.md |
| Rama | feat/FEAT-005-estado-caducada |
| Commits | 9ba420e, d9aec08, c80b027, 5092966, c5b5237 |

## Ronda 1 — daw-verify-module (2026-08-19)

### Trazabilidad PRD → Código → Tests

**Functional Requirements**

| FR | Cumplimiento |
|---|---|
| FR-01 (agregar `caducada` al enum) | ✅ `models.py:23` → `test_migracion_agrega_caducada_al_check` |
| FR-02 (transición masiva) | ✅ `repository.caducar_vencidas` + `service.caducar_reservas_vencidas` → `test_caducar_vencidas_transiciona_activa_vencida_a_caducada`, `test_caducar_vencidas_devuelve_cantidad_correcta`, `test_post_caducar_vencidas_devuelve_200_y_cantidad_correcta` |
| FR-03 (rechazo de cancelación de `caducada`) | ✅ `cancelar_reserva` sin cambios (confirmado por diff), cubierto por construcción → `test_cancelar_reserva_caducada_rechaza_con_mismo_error_que_cancelada` |
| FR-04 (queries de solapamiento/disponibilidad/baja intactas) | ✅ `repository.py`/`vehiculos/` sin cambios en funciones existentes (confirmado por diff) → `test_crear_reserva_no_bloqueada_por_reserva_caducada_solapada` (AC-03), `test_baja_vehiculo_no_bloqueada_por_reserva_caducada` (AC-04) |
| FR-05 (schemas admiten `caducada`) | ✅ Enum ampliado alcanza sin tocar `schemas.py` → `test_get_reservas_devuelve_caducada_como_estado_valido` |

**Acceptance Criteria**

| AC | Test | Veredicto |
|---|---|---|
| AC-01 | `test_caducar_vencidas_transiciona_activa_vencida_a_caducada` + `test_post_caducar_vencidas_devuelve_200_y_cantidad_correcta` | ✅ PASS |
| AC-02 | `test_caducar_vencidas_no_toca_activa_vigente` | ✅ PASS |
| AC-03 | `test_crear_reserva_no_bloqueada_por_reserva_caducada_solapada` | ✅ PASS |
| AC-04 | `test_baja_vehiculo_no_bloqueada_por_reserva_caducada` | ✅ PASS |
| AC-05 | `test_cancelar_reserva_caducada_rechaza_con_mismo_error_que_cancelada` | ✅ PASS |
| AC-06 | `test_migracion_no_reescribe_filas_existentes` | ✅ PASS |
| AC-07 | `test_get_reservas_devuelve_caducada_como_estado_valido` | ✅ PASS |

**NFRs**

- ✅ NFR-01 (transaccionalidad antes de responder): `repository.caducar_vencidas` ejecuta y comitea de forma síncrona dentro de la misma llamada que responde el HTTP.
- ✅ NFR-02 (migración no reescribe filas): `upgrade()` de 0004 solo hace `drop_constraint`/`create_check_constraint`/`create_index`, sin DML — confirmado por `test_migracion_no_reescribe_filas_existentes`.

### Spec — tareas por bloque

| Block | Tests requeridos | Estado |
|---|---|---|
| Block 1 (modelo/migración/índice) | 4/4 | ✅ |
| Block 2 (repository/service) | 6/6 | ✅ |
| Block 3 (router/schema) | 6/6 | ✅ |
| Block 4 (frontend) | 4/4 | ✅ |

### Mitigaciones del threat model (verificadas en código)

- ✅ M-01 (índice `ix_reservas_estado_fecha_fin`): creado en la migración 0004, confirmado por `test_migracion_crea_indice_estado_fecha_fin`.
- ✅ M-02 (logging sin PII): `service.caducar_reservas_vencidas` loguea `operacion/count/ip_origen/timestamp`, sin `legajo`/`nombre_empleado` — confirmado por `test_caducar_reservas_vencidas_loguea_operacion`.
- ✅ Rate limit propio (60/min, balde de lectura): confirmado por `test_post_caducar_vencidas_respeta_rate_limit`.
- ℹ️ Riesgo LOW aceptado (carrera `cancelar_reserva` vs. sweep masivo): documentado en el threat model, sin mitigación de código requerida.

### Calidad

- ✅ Lint backend (`ruff check .`): 0 errores.
- ✅ Lint frontend (`npm run lint`): 0 errores.
- ✅ Coverage backend: 99% total, 100% en los 5 archivos tocados por FEAT-005.
- ✅ Sin código muerto ni imports sin usar.

### Suites ejecutadas

- ✅ Backend (`pytest`): 137/137 passed.
- ✅ Frontend (`npx vitest run --no-file-parallelism`): 12 archivos, 59/59 passed.
  - Nota: la corrida con paralelismo por defecto mostró un flake de infraestructura (timeout del pool de workers de vitest en WSL2, afectando 2 archivos aleatorios distintos en 3 corridas separadas). Confirmado como flake de entorno, no del código, al reproducir en verde con `--no-file-parallelism` y también al correr los archivos individuales de forma aislada.
- **Total: 196/196 en verde.**

### Evidencia TDD

- ✅ Block 2: 6/6 tests fallando antes (`ImportError`), 38/38 pasando después.
- ✅ Block 3: 6/6 tests fallando antes (404), 34/34 pasando después.
- ✅ Block 4: 4/4 tests fallando antes (incluye un test endurecido con `vi.waitFor` tras detectar que pasaba trivialmente sin implementación), 13/13 pasando después.
- ⚠️ Block 1: sin acceso al reporte original del `daw-implementer` (el código ya estaba implementado, de una sesión anterior pausada, al retomar el ticket). Evidencia circunstancial fuerte: los 3 tests nuevos de migración están estructuralmente acoplados a la migración (bajan a `base`/suben a `head` explícitamente, afirman `version_num=="0004"`) y no podrían pasar contra el esquema anterior. No bloqueante.

### Veredicto

```
FAILs: 0 | WARNs: 1 (evidencia TDD de Block 1 no accesible retrospectivamente, no bloqueante) | PASSes: 27
Resultado: PASSED
```

`gates.verify` → `true`.
