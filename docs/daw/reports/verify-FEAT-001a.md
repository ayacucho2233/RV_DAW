# Verify — FEAT-001a: Gestión del pool de vehículos

| Campo | Valor |
|---|---|
| Ticket | FEAT-001a |
| Tier | FEATURE |
| PRD | `docs/daw/prd/prd-FEAT-001a.md` |
| Spec | `docs/daw/specs/spec-FEAT-001a.md` |
| Threat model | `docs/daw/security/threat-FEAT-001a.md` |
| SAST | `docs/daw/security/sast-FEAT-001a.md` |
| Rondas de verificación | 1 |

## Verdict: PASSED (2 WARN no bloqueantes)

Corrido por `daw-module-verifier`, cruzando PRD → spec → código → tests de forma independiente (no
reutiliza las revisiones por bloque de CODE, vuelve a leer el código y a correr las suites en vivo).

## Trazabilidad PRD → Código → Tests (AC-01 a AC-11)

| AC | FR | Implementación | Test(s) | Estado |
|---|---|---|---|---|
| AC-01 | FR-01 alta | `service.py:crear_vehiculo` (L61) + `router.py:crear_vehiculo` (L48) | `test_crear_vehiculo_ok`, `test_post_vehiculo_ok_201` | ✅ |
| AC-02 | FR-02 modificar | `service.py:modificar_vehiculo` (L73) + `router.py` PUT (L61) | `test_modificar_vehiculo_ok`, `test_put_vehiculo_ok_200` | ✅ |
| AC-03 | FR-03 baja temporal | `service.py:dar_de_baja_temporal` (L91) + `router.py` PATCH (L75) | `test_baja_temporal_ok`, `test_baja_temporal_200` | ✅ |
| AC-04 | FR-04 baja definitiva | `service.py:dar_de_baja_definitiva` (L106) + `router.py` PATCH (L88) | `test_baja_definitiva_ok`, `test_baja_definitiva_200` | ✅ |
| AC-05 | FR-05 HTTP Basic en los 6 endpoints | `security.py:verificar_admin` inyectado idéntico en los 6 endpoints | `test_post_vehiculo_sin_credenciales_401` (solo POST) | ⚠️ WARN — ver detalle |
| AC-06 | FR-06 reactivar | `service.py:reactivar` (L121) + `router.py` PATCH (L101) | `test_reactivar_ok`, `test_reactivar_200` | ✅ |
| AC-07 | FR-07 no reactivar baja definitiva | `service.py:reactivar` (L127-128) | `test_reactivar_baja_definitiva_rechazado`, `test_reactivar_baja_definitiva_409` | ✅ |
| AC-08 | FR-08 patente única (alta) | `service.py:crear_vehiculo` (chequeo previo) + `repository.py:crear` (IntegrityError→dominio) | `test_crear_vehiculo_patente_duplicada`, `..._integrity_error_traducido`, `test_post_vehiculo_patente_duplicada_409` | ✅ |
| AC-09 | FR-09 patente única (modificación) | `service.py:modificar_vehiculo` (excluye propio id) | `test_modificar_vehiculo_patente_duplicada` | ✅ |
| AC-10 | FR-10 tipo válido (alta) | `schemas.py:VehiculoBase` (Literal) + `service.py:_validar_tipo` defensivo | `test_crear_vehiculo_tipo_invalido`, `test_post_vehiculo_tipo_invalido_400` | ✅ |
| AC-11 | FR-11 tipo válido (modificación) | `service.py:modificar_vehiculo` (L76) | `test_modificar_vehiculo_tipo_invalido` | ✅ |

## Reglas de negocio de AGENTS.md aplicables a este sub-ticket

- ✅ Patente única — constraint `UNIQUE` en DB + chequeo aplicativo (AC-08/AC-09).
- ✅ Tipo válido restringido a `auto`/`camioneta` — CHECK constraint + Pydantic `Literal` + validación defensiva de servicio.
- ✅ Máquina de estados de baja/reactivación, incluidas las transiciones inválidas.
- ✅ Soft delete — sin ninguna operación de borrado físico en `repository.py`.
- ✅ "Vehículo con reservas activas no puede darse de baja" — confirmado **fuera de alcance** de FEAT-001a, documentado consistentemente en PRD, spec y código (docstring de `service.py`), trazable a FEAT-001b. No es un gap silencioso.

## Mitigaciones del threat model (TM-01 a TM-06)

| TM | Mitigación | Verificación |
|---|---|---|
| TM-01 | TLS obligatorio en despliegue | Documentado como precondición de infraestructura (D-01/D-02 del PRD, aún sin resolver) — consistente, no es código pendiente |
| TM-02 | Rate limiting 5 intentos fallidos/IP/min | `security.py:verificar_admin` + `test_rate_limit_429_tras_intentos_fallidos` |
| TM-03 | IntegrityError traducido + handler genérico sin detalle interno | `repository.py` + `main.py` + `test_..._integrity_error_traducido` + `test_error_no_anticipado_500_sin_detalle_interno` |
| TM-04 | Logging sin credenciales | `service.py:_log_operacion` + `test_crear_vehiculo_loguea_operacion_sin_credenciales` |
| TM-05 | 401 genérico, sin distinguir usuario/password | `security.py` + `test_post_vehiculo_credenciales_invalidas_401_mensaje_generico` |
| TM-06 | DoS general | Mismo mecanismo que TM-02 por diseño |

Las 6 mitigaciones están implementadas o documentadas como precondición.

## Suite de tests (corrida en vivo por el verificador)

- **Backend:** 47/47 pytest passed. Cobertura 96% líneas sobre `app/`, sin líneas sin cubrir en `exceptions.py`/`schemas.py`/`service.py`/`security.py`/`config.py`/`main.py`. Huecos menores en ramas de manejo de errores ya ejercitadas indirectamente por patrones equivalentes en otros endpoints/métodos.
- **Frontend:** 16/16 vitest passed (3 archivos de test de componente).

## Calidad

- N/A Lint/type-checker — no hay ESLint ni Ruff/Flake8/mypy configurado en ninguno de los dos proyectos.
- ✅ Sin imports no usados, sin código muerto (`TODO`/`FIXME`/`console.log`/`pdb.set_trace`) en `backend/app` ni `frontend/src`.

## WARN (no bloqueantes)

1. **AC-05 — cobertura de test parcial del caso "sin credenciales"**: la protección HTTP Basic es idéntica en los 6 endpoints (`Depends(verificar_admin)`), pero solo `POST /vehiculos` tiene un test directo de "sin credenciales → 401" (`test_post_vehiculo_sin_credenciales_401`). Los otros 5 endpoints no repiten ese caso explícitamente. Riesgo real bajo (no hay lógica condicional por endpoint que pudiera divergir), pero no es prueba directa por AC.
2. **Cobertura del frontend no medible**: falta `@vitest/coverage-v8` como devDependency; `npx vitest run --coverage` falla por dependencia ausente. Los 16 tests existentes verifican comportamiento real, no solo status/smoke, pero no hay un número de cobertura contra el cual contrastar.

Ningún AC, FR o mitigación del threat model quedó sin implementación o sin test que lo ejercite de forma real.

## Resultado

```
┌─────────────────────────────────────────────────────────┐
│  VERIFY — Verification Summary                           │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Ticket: FEAT-001a — Gestión del pool de vehículos       │
│  Tier: FEATURE                                            │
│  PRD: docs/daw/prd/prd-FEAT-001a.md                       │
│  Spec: docs/daw/specs/spec-FEAT-001a.md                   │
│  Report: docs/daw/reports/verify-FEAT-001a.md             │
│                                                          │
│  Results:                                                │
│    ✅ /daw-verify-module: PASSED (0 FAIL, 2 WARN, 24 PASS)│
│    ✅ Tests: 63 passed, 63 total (47 backend + 16 frontend)│
│    ✅ SAST (CODE phase): PASSED                           │
│                                                          │
└─────────────────────────────────────────────────────────┘
```
