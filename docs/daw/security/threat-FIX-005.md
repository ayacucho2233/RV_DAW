# Threat Model FIX-005: Hardening de la búsqueda de patente

| Field | Value |
|-------|-------|
| Ticket | FIX-005 |
| Date | 2026-08-18 |
| Design reviewed | 3 fixes de robustez: validación defensiva en service.py, `ORDER BY` determinístico, pre-chequeo de duplicados en migración |

## Componentes y superficies de ataque

1. **Fix A**: nueva validación de formato en `consultar_reservas_activas_por_patente`
   (`reservas/service.py`) + nueva excepción `PatenteFormatoInvalidoError` + nuevo mapeo HTTP 422 en
   `reservas/router.py`.
2. **Fix B**: `.order_by(Vehiculo.id)` agregado a una query de solo lectura ya existente
   (`vehiculos/repository.py`) — no agrega superficie nueva, solo determinismo.
3. **Fix C**: query de solo lectura (`SELECT ... GROUP BY ... HAVING COUNT(*) > 1`) dentro de la
   migración `0003`, ejecutada vía `op.get_bind()` antes del `CREATE UNIQUE INDEX` ya existente.

## Trust boundaries

- **Usuario anónimo → `GET /reservas/vehiculo/{patente}` → `consultar_reservas_activas_por_patente`**:
  sin cambios respecto al límite ya existente y aceptado en FEAT-004 — Fix A solo adelanta una
  validación que hoy igual termina en el mismo resultado observable (`VehiculoNoEncontradoError`),
  ahora con un código HTTP más preciso (422 en vez de 404) y sin el round-trip a la base.
- **Operador de deploy → `alembic upgrade head` → migración `0003`**: límite ya existente (quien
  corre la migración ya tiene acceso administrativo a la base). Fix C no le da ningún acceso nuevo,
  solo le muestra un mensaje de error más claro si la migración va a fallar.

## Análisis STRIDE (los 3 fixes)

| Categoría | Evaluación |
|---|---|
| Spoofing | N/A — ningún fix agrega ni modifica un mecanismo de autenticación. |
| Tampering | N/A — Fix A y B son de solo lectura; Fix C es un `SELECT` antes de una `DDL` que ya existía sin cambios. |
| Repudiation | N/A — sin cambios en logging (ninguno de los 3 fixes toca `_log_operacion`). |
| Information Disclosure | Bajo. El mensaje de error de Fix C lista patentes en conflicto — pero solo lo ve quien corre `alembic upgrade head` (acceso administrativo a la base ya asumido), y las patentes ya son datos públicos vía `GET /reservas/vehiculos` (FEAT-001c). No hay disclosure nuevo. |
| Denial of Service | N/A — Fix A en realidad *reduce* la carga en el caso malformado (evita un round-trip a la base innecesario). Fix B/C no cambian el costo de ninguna query en el camino feliz. |
| Elevation of Privilege | N/A — ningún fix cambia quién puede hacer qué. |

## Riesgos clasificados

| Riesgo | STRIDE | Likelihood | Impact | Mitigación |
|---|---|---|---|---|
| Ventana TOCTOU entre el `SELECT` de pre-chequeo (Fix C) y el `CREATE UNIQUE INDEX`: un `INSERT`/`UPDATE` concurrente con patente duplicada podría colarse entre ambos pasos y de todos modos hacer fallar el índice con el error crudo de Postgres | Tampering (carrera) | Baja | Bajo | **Riesgo aceptado, no cerrado por este fix** — ver "Riesgo aceptado" abajo. No es un riesgo nuevo: las migraciones de este proyecto ya asumen una ventana de mantenimiento sin tráfico concurrente (mismo supuesto que el PRD de FEAT-004 ya hacía para el chequeo manual que Fix C reemplaza). |

**Riesgo aceptado (F-TM-04):**

| Campo | Valor |
|---|---|
| Riesgo | TOCTOU entre el pre-chequeo de duplicados (Fix C) y la creación del índice único — no es atómico. |
| Quién lo acepta | El usuario del proyecto, en la sesión de PLAN de FIX-005 (2026-08-18). |
| Justificación | Las migraciones de este proyecto corren en una ventana de mantenimiento controlada (deploy), no bajo tráfico de producción concurrente — mismo supuesto implícito que ya hacía FEAT-004 al delegar este chequeo a un paso manual. Cerrar el TOCTOU requeriría un `LOCK TABLE` explícito durante la migración, que es una complejidad no proporcional al riesgo real (una alta de vehículo justo durante el segundo exacto de una migración de mantenimiento). |
| Condición de revisión | Si este proyecto alguna vez corre migraciones contra una base con escritura concurrente activa (ej. despliegues sin downtime/zero-downtime migrations), revisar si hace falta un `LOCK TABLE vehiculos IN SHARE MODE` durante el pre-chequeo. |

Sin riesgos CRITICAL, HIGH ni MEDIUM sin aceptar.

## Mitigaciones a incorporar en el fix-plan

1. `PatenteFormatoInvalidoError` (nueva, en `reservas/exceptions.py`) mapea a 422 en
   `_MAPEO_ERRORES_HTTP` de `reservas/router.py`.
2. Constante compartida `PATENTE_PATTERN` (en `vehiculos/schemas.py`, fuente de verdad del
   constraint), reusada por `reservas/router.py` (`Path(pattern=PATENTE_PATTERN)`) y
   `reservas/service.py` (la validación defensiva de Fix A) — cierra el magic-string drift entre las
   2 copias ya existentes antes de este fix, en vez de agregar una tercera.
3. El TOCTOU de Fix C queda documentado como riesgo aceptado (arriba), no oculto.

## Resumen

- Superficies de ataque identificadas: 3 (todas de bajo riesgo o N/A)
- Trust boundaries declaradas: 2 (sin cambios respecto a las ya existentes)
- Riesgos: C:0 H:0 M:0 L:1 (aceptado)
- Datos sensibles manejados: ninguno nuevo — patentes ya son datos públicos existentes.
