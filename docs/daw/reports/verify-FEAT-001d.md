# Verify — FEAT-001d: Listado, filtros y cancelación de reservas

| Campo | Valor |
|---|---|
| Ticket | FEAT-001d |
| Tier | FEATURE |
| PRD | `docs/daw/prd/prd-FEAT-001d.md` |
| Spec | `docs/daw/specs/spec-FEAT-001d.md` |
| Threat model | `docs/daw/security/threat-FEAT-001d.md` |
| SAST | `docs/daw/security/sast-FEAT-001d.md` |
| Rondas de verificación | 1 |

## Verdict: PASSED (4 WARN no bloqueantes, 1 de ellos aceptado explícitamente por el usuario)

Corrido por `daw-module-verifier`, cruzando PRD → spec → código → tests de forma independiente
(no reutiliza las revisiones por bloque de CODE, vuelve a leer el código y a correr las suites
en vivo).

## Trazabilidad PRD → Código → Tests (AC-01 a AC-06)

| AC | FR | Implementación | Test(s) | Estado |
|---|---|---|---|---|
| AC-01 | FR-01 listado sin filtro | `service.py:listar_reservas` + `router.py` GET `/reservas` | `test_listar_reservas_sin_filtro`, `test_get_reservas_sin_filtro_200`, `ReservasListado.test.jsx` | ✅ |
| AC-02 | FR-02 filtro `futuras` | `service.py:listar_reservas` | `test_listar_reservas_filtro_futuras`, `test_get_reservas_filtro_futuras_200`, `ReservasListado.test.jsx` | ✅ |
| AC-03 | FR-02 filtro `en_curso` | `service.py:listar_reservas` | `test_listar_reservas_filtro_en_curso`, `test_get_reservas_filtro_en_curso_200` | ✅ |
| AC-04 | FR-02 filtro `pasadas` | `service.py:listar_reservas` | `test_listar_reservas_filtro_pasadas`, `test_get_reservas_filtro_pasadas_200` | ✅ |
| AC-05 | FR-03 cancelación propia | `service.py:cancelar_reserva` + `router.py` PATCH `/reservas/{id}/cancelar` | `test_cancelar_reserva_ok`, `test_cancelar_reserva_libera_vehiculo`, `test_patch_cancelar_reserva_ok_200`, `ReservasListado.test.jsx` (verifica refresco y `estado=cancelada`) | ✅ |
| AC-06 | FR-04 legajo no coincide | `service.py:cancelar_reserva` (`LegajoNoCoincideError`, mensaje que no revela el legajo real) | `test_cancelar_reserva_legajo_no_coincide`, `test_patch_cancelar_reserva_legajo_no_coincide_403`, `ReservasListado.test.jsx` | ✅ |

## NFR

| NFR | Estrategia | Verificación |
|---|---|---|
| NFR-01 (listado <2s p95) | Sin joins SQL; reuso de `vehiculos_repository.listar` en Python (mismo patrón que `consultar_disponibilidad`) | ⚠️ Sin medición empírica de p95 — no hay infraestructura de carga en el proyecto. Riesgo bajo dado el volumen esperado, pero sin evidencia. |

## Spec — cobertura por bloque

- ✅ Block 1 (servicio/repositorio/schemas/excepciones) — 12/12 tests requeridos, en verde (+1 test adicional no pedido por el spec, cubre TM-D-03/TM-D-04).
- ✅ Block 2 (router) — 12/12 tests requeridos, en verde.
- ✅ Block 3 (frontend) — 7/7 tests requeridos, en verde.

## Mitigaciones del threat model (TM-D-01 a TM-D-03)

| TM | Mitigación | Verificación |
|---|---|---|
| TM-D-01 (crítico) | `ReservaListItem` nunca incluye `legajo`/`licencia` | Verificado en `schemas.py`, `service.py`, `router.py` y en `ReservasListado.jsx` (no los recibe ni renderiza); `test_listar_reservas_no_expone_legajo_ni_licencia` |
| TM-D-02 | Rate limiting con clave de contador independiente por endpoint | `test_get_reservas_rate_limit_429` (confirma que `"reservas-vehiculos"` conserva cupo tras agotar `"reservas-listado"`), `test_patch_cancelar_rate_limit_429` (ídem `"reservas-post"` vs `"reservas-cancelar"`) |
| TM-D-03 | Log de cancelación sin PII (`nombre_empleado`/`licencia` nunca loguean) | `test_cancelar_reserva_loguea_operacion_sin_pii`, `test_cancelar_reserva_legajo_no_coincide_loguea_rechazada` |

Las 3 mitigaciones de este ticket están implementadas y verificadas por test.

## Suite de tests (corrida en vivo por el verificador)

- **Backend:** 96/96 pytest passed. Coverage 100% líneas (233/233), 99% branches sobre `app/features/reservas/` (la única rama parcial es inalcanzable: `FiltroPeriodoReserva` es un `Literal` que Pydantic ya valida antes de llegar a esa comparación).
- **Frontend:** 33/33 vitest passed (6 archivos de test, 7 nuevos de este ticket).
- **Total:** 129/129 — coincide con lo reportado en el cierre de CODE.

## Sad paths (F-VER-04)

- ✅ `GET /reservas` con `periodo` inválido → 422 (`test_get_reservas_periodo_invalido_422`).
- ✅ `PATCH /reservas/{id}/cancelar`: legajo faltante → 422, reserva inexistente → 404, ya cancelada → 409, legajo no coincide → 403 — los 4 casos de error tienen test.
- ✅ Frontend: legajo vacío no dispara request (`ReservasListado.test.jsx`).

## Calidad

- ⚪ Lint/type-checker (F-VER-05): N/A — no configurado en ninguno de los dos proyectos (preexistente, no introducido por este ticket).
- ✅ Sin imports no usados en los 5 archivos backend modificados (verificado por AST).
- ⚠️ `ReservasListado.test.jsx:26` declara `reservaCancelada` sin usar (el test usa `reservaCanceladaDesde(reserva)`, una función distinta) — variable muerta, no afecta comportamiento.
- ✅ Sin tests frágiles: sin dependencias de orden, sin estado global entre tests, los tests de filtro por período usan fechas relativas a `now()` en vez de timestamps fijos.

## WARN (no bloqueantes)

1. **NFR-01 sin medición empírica de p95** — solo estrategia documentada (sin joins SQL), sin infraestructura de carga en el proyecto para medirlo.
2. **Cobertura frontend no instrumentada** — `@vitest/coverage-v8` no está instalado (preexistente); cobertura funcional confirmada manualmente: los 7 tests requeridos cubren carga inicial, cambio de filtro, éxito de cancelación con refresco, y los 4 casos de error.
3. **Variable muerta en test** — `reservaCancelada` sin uso en `ReservasListado.test.jsx:26`.
4. **Evidencia TDD no persistida para Block 1/2 (backend, 24 tests)** — aceptado explícitamente por el usuario tras confirmar que no hay ninguna señal de discrepancia spec↔código↔tests: suite 100% verde, cobertura 100%/99%, conteo de tests por bloque coincide exactamente con los "Required tests" del spec sin faltantes ni sobrantes no declarados. Para Block 3 (frontend) la evidencia TDD SÍ se reconstruyó y se confirmó de forma independiente antes del commit (7 mutaciones puntuales, una por test, cada una revertida). Para Block 1/2 esos bloques fueron comiteados en una sesión de CODE anterior (commits `caf0e01`, `967f243`) que —según el historial de `.daw-state.json`— pasó por la revisión doble de rigor en su momento, pero ese reporte nunca quedó persistido como artefacto en disco, y reconstruirlo ahora requeriría mutar código fuente, lo cual VERIFY prohíbe explícitamente por diseño (ver `.daw/rules/*` — "VERIFY no escribe código fuente"). **Acción de mejora de proceso recomendada** (no bloqueante, para futuros tickets): persistir el reporte del `daw-implementer`/`daw-module-verifier` de cada bloque como artefacto en disco durante CODE, no solo como resumen narrativo en el historial del estado.

Ningún AC, FR o mitigación del threat model quedó sin implementación o sin test que lo ejercite de forma real.

## Resultado

```
┌─────────────────────────────────────────────────────────┐
│  VERIFY — Verification Summary                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Ticket: FEAT-001d — Listado, filtros y cancelación      │
│  Tier: FEATURE                                            │
│  PRD: docs/daw/prd/prd-FEAT-001d.md                       │
│  Spec: docs/daw/specs/spec-FEAT-001d.md                   │
│  Report: docs/daw/reports/verify-FEAT-001d.md             │
│                                                          │
│  Results:                                                │
│    ✅ /daw-verify-module: PASSED (0 FAIL, 4 WARN, 15 PASS)│
│    ✅ Tests: 129 passed, 129 total (96 backend + 33 frontend)│
│    ✅ SAST (CODE phase): PASSED                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```
